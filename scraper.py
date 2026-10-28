"""
scraper.py
Toma un snapshot de precios (1 vez por semana) de Carrefour, Dia, Coto y
PedidosYa Market Belgrano y lo guarda en SQLite (precios.db).

Uso:
    python scraper.py                    # snapshot de las tiendas con >= 7 dias sin actualizarse
    python scraper.py --forzar           # fuerza el snapshot de todas las tiendas
    python scraper.py --solo Coto --debug --visible   # probar una tienda y volcar JSON a debug/
    python scraper.py --login Coto       # elegir sucursal/direccion una vez y guardar la sesion
    python scraper.py --daemon           # queda corriendo y toma el snapshot cuando corresponde

Es seguro correrlo todos los dias: cada tienda se omite si su ultimo
snapshot tiene menos de 7 dias.
"""
import argparse
import json
import logging
import os
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "precios.db"
MANUAL_DIR = BASE_DIR / "manual"      # CSVs de respaldo: manual/<Tienda>.csv
INTERVALO_DIAS = int(os.environ.get("INTERVALO_DIAS", 7))   # poné 1 para snapshots diarios
VTEX_HILOS = int(os.environ.get("VTEX_HILOS", 6))         # categorias en paralelo por tienda VTEX
PARALELO = os.environ.get("PARALELO", "1") != "0"        # las 4 tiendas a la vez (PARALELO=0 -> una por una)
REINTENTO_HORAS = 6                   # si una tienda falla, no reintenta antes de esto
DATOS_DIR = BASE_DIR / "datos"                  # snapshots .csv.gz + estado (esto es lo que se sube a git)
ESTADO_PATH = DATOS_DIR / "estado_corridas.json"
LOCK_PATH = BASE_DIR / "snapshot.lock"
PAUSA_ENTRE_REQUESTS = 0.3            # segundos, para no saturar los servidores
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MonitorPrecios/1.0)"}

log = logging.getLogger("scraper")
_LOCK = threading.Lock()


def _latido():
    """Marca que la descarga sigue viva (el lock se considera huérfano si pasan 30 min sin latido)."""
    try:
        if LOCK_PATH.exists():          # nunca crear el lock: solo renovarlo
            os.utime(LOCK_PATH)
    except OSError:
        pass


# ==============================================================================
# BASE DE DATOS
# ==============================================================================
def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=60)
    try:
        con.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    con.execute(
        """CREATE TABLE IF NOT EXISTS precios (
               fecha     TEXT NOT NULL,
               tienda    TEXT NOT NULL,
               ean       TEXT NOT NULL,
               producto  TEXT,
               marca     TEXT,
               categoria TEXT,
               precio    REAL NOT NULL
           )"""
    )
    con.execute("CREATE INDEX IF NOT EXISTS ix_precios ON precios(tienda, fecha, ean)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_precios_ean ON precios(ean)")
    return con


def _ultima_fecha(con, tienda):
    fila = con.execute("SELECT MAX(fecha) FROM precios WHERE tienda=?", (tienda,)).fetchone()
    return fila[0] if fila else None


def _cantidad(con, tienda, fecha):
    return con.execute(
        "SELECT COUNT(*) FROM precios WHERE tienda=? AND fecha=?", (tienda, fecha)
    ).fetchone()[0]


def _guardar(con, tienda, fecha, df):
    con.execute("DELETE FROM precios WHERE tienda=? AND fecha=?", (tienda, fecha))
    con.executemany(
        "INSERT INTO precios (fecha, tienda, ean, producto, marca, categoria, precio) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            (fecha, tienda, r.ean, r.producto, r.marca, r.categoria, float(r.precio))
            for r in df.itertuples(index=False)
        ],
    )
    con.commit()


# ==============================================================================
# ADAPTADOR VTEX (Carrefour y Dia)
# ==============================================================================
_ULTIMO_HTTP = {"detalle": "sin respuesta"}


def _get_json(url, params=None, reintentos=4):
    """Devuelve el JSON, o None si fallo tras los reintentos (el motivo queda en _ULTIMO_HTTP)."""
    for i in range(reintentos):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code in (200, 206):
                return r.json()
            _ULTIMO_HTTP["detalle"] = f"HTTP {r.status_code} en {url}"
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (i + 1))
                continue
            return None
        except (requests.RequestException, ValueError) as e:
            _ULTIMO_HTTP["detalle"] = f"{type(e).__name__}: {e} en {url}"
            time.sleep(1 + i)
    return None


def _categorias_vtex(base):
    """Devuelve [(id_categoria_hoja, nombre_categoria_principal)]."""
    arbol = _get_json(f"{base}/api/catalog_system/pub/category/tree/3")
    if not arbol:
        raise RuntimeError(f"No pude leer el árbol de categorías de {base} ({_ULTIMO_HTTP['detalle']})")
    hojas = []

    def rec(nodo, top):
        hijos = nodo.get("children") or []
        if hijos:
            for h in hijos:
                rec(h, top)
        else:
            hojas.append((nodo["id"], top))

    for n in arbol:
        rec(n, n["name"])
    return hojas


def _precio_disponible(item):
    for s in item.get("sellers", []):
        oferta = s.get("commertialOffer", {})
        if oferta.get("AvailableQuantity", 0) > 0 and (oferta.get("Price") or 0) > 0:
            return float(oferta["Price"])
    return None


def _descargar_categoria(base, cat_id, cat_top):
    """Baja todos los productos de una categoría hoja. Devuelve (filas, truncada, fallo)."""
    filas, desde = {}, 0
    while True:
        _latido()
        lote = _get_json(
            f"{base}/api/catalog_system/pub/products/search",
            params={"fq": f"C:{cat_id}", "_from": desde, "_to": desde + 49},
        )
        if lote is None:
            return filas, False, True
        if not lote:
            return filas, False, False
        for p in lote:
            for it in p.get("items", []):
                ean = (it.get("ean") or "").strip()
                if not ean:
                    continue
                precio = _precio_disponible(it)
                if precio is None:
                    continue
                filas[ean] = {"ean": ean, "producto": p.get("productName", ""), "marca": p.get("brand", ""),
                              "categoria": cat_top, "precio": precio}
        if len(lote) < 50:
            return filas, False, False
        desde += 50
        if desde >= 2500:                    # tope de VTEX por consulta
            return filas, True, False
        time.sleep(PAUSA_ENTRE_REQUESTS)


def descargar_vtex(base):
    """
    VTEX devuelve 50 productos por request y no permite pasar de ~2500 por consulta, por eso
    se recorre categoría por categoría (hojas del árbol), varias en paralelo.
    """
    hojas = _categorias_vtex(base)
    filas, truncadas, fallidas = {}, 0, 0
    with ThreadPoolExecutor(max_workers=VTEX_HILOS) as ex:
        futuros = [ex.submit(_descargar_categoria, base, cid, top) for cid, top in hojas]
        for i, f in enumerate(as_completed(futuros), 1):
            try:
                fi, tr, fa = f.result()
                filas.update(fi)
                truncadas += tr
                fallidas += fa
            except Exception:
                log.exception("Error procesando una categoría de %s", base)
                fallidas += 1
            if i % 25 == 0:
                log.info("%s: %d/%d categorías, %d productos", base, i, len(hojas), len(filas))
    if truncadas:
        log.warning("%s: %d categorías llegaron al tope de 2500 y pueden estar incompletas", base, truncadas)
    if fallidas:
        log.warning("%s: %d categorías fallaron tras reintentos", base, fallidas)
    if not filas:
        raise RuntimeError(f"{base}: no se obtuvo ningún producto (último error: {_ULTIMO_HTTP['detalle']})")
    return pd.DataFrame(list(filas.values()))


# ==============================================================================
# RESPALDO POR CSV
# ==============================================================================
def importar_csv(tienda):
    """Lee manual/<tienda>.csv con columnas: ean, producto, precio (marca y categoria opcionales)."""
    ruta = MANUAL_DIR / f"{tienda}.csv"
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el CSV de respaldo {ruta}")
    df = pd.read_csv(ruta, dtype={"ean": str})
    for col in ("marca", "categoria"):
        if col not in df.columns:
            df[col] = ""
    return df[["ean", "producto", "marca", "categoria", "precio"]]


# ==============================================================================
# EXTRACTOR GENÉRICO DE PRODUCTOS DESDE JSON
# Busca, en cualquier JSON que cargue la página, objetos que tengan nombre + precio + EAN.
# ==============================================================================
_K_NOMBRE = ("productname", "product_name", "name", "nombre", "title", "value", "description", "descripcion")
_K_PRECIO = ("preciofinal", "final_price", "finalprice", "saleprice", "sale_price", "price", "precio",
             "preciolista", "list_price", "listprice")
_K_EAN = ("ean", "ean13", "eancode", "gtin", "gtin13", "barcode", "codigobarras", "codigo_de_barras", "upc")
_K_MARCA = ("brand", "marca", "brandname")
_SIN_EAN = {"n": 0}


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = re.sub(r"[^\d,.\-]", "", v)
        if not s:
            return None
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    if isinstance(v, dict):
        for k in ("value", "amount", "price", "final", "current"):
            if k in v:
                n = _num(v[k])
                if n:
                    return n
    return None


def _extraer_productos(obj, categoria=""):
    out = []

    def rec(x):
        if isinstance(x, dict):
            plano = {str(k).lower(): v for k, v in x.items()}
            data = x.get("data")
            if isinstance(data, dict):                       # estilo Constructor: {"value": nombre, "data": {...}}
                for k, v in data.items():
                    plano.setdefault(str(k).lower(), v)
            nombre = next((plano[k].strip() for k in _K_NOMBRE
                           if isinstance(plano.get(k), str) and plano[k].strip()), None)
            precio = next((n for k in _K_PRECIO if k in plano
                           for n in [_num(plano[k])] if n and n > 0), None)
            ean = next((str(plano[k]).strip() for k in _K_EAN
                        if k in plano and re.fullmatch(r"\d{8,14}", str(plano[k]).strip())), None)
            if nombre and precio:
                if ean:
                    marca = next((str(plano[k]) for k in _K_MARCA if isinstance(plano.get(k), str)), "")
                    out.append({"ean": ean, "producto": nombre, "marca": marca,
                                "categoria": categoria, "precio": precio})
                else:
                    _SIN_EAN["n"] += 1
                return
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)

    rec(obj)
    return out


# ==============================================================================
# ADAPTADORES POR NAVEGADOR (Coto y PedidosYa Market) — Playwright
#   pip install playwright && playwright install chromium
# ==============================================================================
CONFIG_DIR = BASE_DIR / "config"        # coto_categorias.txt, pedidosya_urls.txt
STATE_DIR = BASE_DIR / "estado_sesion"  # sesión guardada (sucursal / dirección)
DEBUG_DIR = BASE_DIR / "debug"
COTO_HOME = "https://www.cotodigital.com.ar/sitios/cdigi/"
COTO_MAX_PAGINAS = 400
PY_MAX_SCROLLS = 120
DEBUG = False
HEADLESS = True
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")


def _leer_urls(ruta):
    if not ruta.exists():
        return []
    return [l.strip() for l in ruta.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]


def _nuevo_contexto(pw, tienda, headless):
    browser = pw.chromium.launch(headless=headless)
    kw = dict(locale="es-AR", timezone_id="America/Argentina/Buenos_Aires",
              user_agent=UA, viewport={"width": 1366, "height": 900})
    estado = STATE_DIR / f"{tienda}.json"
    if estado.exists():
        kw["storage_state"] = str(estado)
    return browser, browser.new_context(**kw)


class _Captura:
    """Registra las respuestas JSON (XHR/fetch) que dispara la página y extrae productos."""

    def __init__(self, page, tienda):
        self.page, self.tienda, self.pendientes, self.n = page, tienda, [], 0
        page.on("response", self._on)

    def _on(self, resp):
        try:
            if resp.request.resource_type in ("xhr", "fetch") and "json" in (resp.headers.get("content-type") or ""):
                self.pendientes.append(resp)
        except Exception:
            pass

    def _volcar(self, url, data):
        d = DEBUG_DIR / re.sub(r"\W+", "_", self.tienda)
        d.mkdir(parents=True, exist_ok=True)
        self.n += 1
        txt = json.dumps({"url": url, "data": data}, ensure_ascii=False)[:200000]
        (d / f"{self.n:04d}.txt").write_text(txt, encoding="utf-8")

    def vaciar(self, categoria=""):
        prods = []
        pend, self.pendientes = self.pendientes, []
        jsons = []
        for r in pend:
            try:
                jsons.append((r.url, r.json()))
            except Exception:
                continue
        try:   # JSON embebido en el HTML (SSR / __NEXT_DATA__ / ld+json)
            for txt in self.page.eval_on_selector_all(
                    'script[type="application/json"], script[type="application/ld+json"]',
                    "els => els.map(e => e.textContent)"):
                try:
                    jsons.append(("html-embebido", json.loads(txt)))
                except ValueError:
                    pass
        except Exception:
            pass
        for url, data in jsons:
            if DEBUG:
                self._volcar(url, data)
            prods.extend(_extraer_productos(data, categoria))
        return prods


def _esperar(page, scrolls=3):
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    for _ in range(scrolls):
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(500)


def _categorias_coto(page):
    """Devuelve [(url, nombre)] de categorías hoja, a partir del menú de Coto Digital + config manual."""
    page.goto(COTO_HOME, wait_until="domcontentloaded", timeout=60000)
    _esperar(page, scrolls=1)
    links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    por_id = {}
    for h in links:
        if "/productos/categorias/" not in h:
            continue
        m = re.search(r"/categorias/([^/?#]+)/(catv\d+)", h)
        if m:
            por_id[m.group(2)] = (h.split("?")[0], m.group(1))
    # hoja = slug que no es prefijo de otro slug (los slugs son jerárquicos: padre-hijo)
    slugs = [s for _, s in por_id.values()]
    hojas = [(u, s) for u, s in por_id.values() if not any(o != s and o.startswith(s + "-") for o in slugs)]
    manuales = [(u.split("?")[0], u.split("/")[-2] if "/" in u else u) for u in _leer_urls(CONFIG_DIR / "coto_categorias.txt")]
    resultado = {u: n for u, n in hojas + manuales}
    if not resultado:
        raise RuntimeError("No encontré categorías en Coto. Pegá URLs de categoría en config/coto_categorias.txt")
    return list(resultado.items())


def _requiere_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Falta Playwright. Instalalo con:  pip install playwright   y luego   playwright install chromium")
    return sync_playwright


def descargar_coto():
    sync_playwright = _requiere_playwright()
    filas = {}
    with sync_playwright() as pw:
        browser, ctx = _nuevo_contexto(pw, "Coto", HEADLESS)
        try:
            page = ctx.new_page()
            cap = _Captura(page, "Coto")
            categorias = _categorias_coto(page)
            log.info("Coto: %d categorías para recorrer", len(categorias))
            for i, (url, nombre) in enumerate(categorias, 1):
                anterior = set()
                for n in range(1, COTO_MAX_PAGINAS + 1):
                    _latido()
                    page.goto(f"{url}?page={n}", wait_until="domcontentloaded", timeout=60000)
                    _esperar(page)
                    prods = cap.vaciar(nombre)
                    eans = {p["ean"] for p in prods}
                    if not eans or eans == anterior:      # página vacía o repetida = fin de la categoría
                        break
                    anterior = eans
                    for p in prods:
                        filas[p["ean"]] = p
                    time.sleep(PAUSA_ENTRE_REQUESTS)
                if i % 10 == 0:
                    log.info("Coto: %d/%d categorías, %d productos", i, len(categorias), len(filas))
        finally:
            ctx.close()
            browser.close()
    if not filas:
        raise RuntimeError("No capturé ningún producto de Coto (con EAN y precio). "
                           "Corré `python scraper.py --solo Coto --debug --visible` y mirá la carpeta debug/")
    if _SIN_EAN["n"]:
        log.warning("Coto: %d objetos con nombre y precio pero sin EAN fueron ignorados", _SIN_EAN["n"])
    return pd.DataFrame(list(filas.values()))


def descargar_pedidosya():
    sync_playwright = _requiere_playwright()
    urls = _leer_urls(CONFIG_DIR / "pedidosya_urls.txt")
    if not urls:
        raise RuntimeError("Creá config/pedidosya_urls.txt con la URL de cada categoría/pasillo de "
                           "PedidosYa Market Belgrano (una por línea).")
    filas = {}
    with sync_playwright() as pw:
        browser, ctx = _nuevo_contexto(pw, "PedidosYa Market Belgrano", HEADLESS)
        try:
            page = ctx.new_page()
            cap = _Captura(page, "PedidosYa Market Belgrano")
            for url in urls:
                categoria = re.sub(r"[-_]+", " ", url.rstrip("/").split("/")[-1].split("?")[0]).title()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                _esperar(page, scrolls=1)
                sin_crecer = 0
                for _ in range(PY_MAX_SCROLLS):            # scroll infinito
                    _latido()
                    antes = len(filas)
                    for p in cap.vaciar(categoria):
                        filas[p["ean"]] = p
                    sin_crecer = sin_crecer + 1 if len(filas) == antes else 0
                    if sin_crecer >= 4:
                        break
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(900)
                log.info("PedidosYa: %s -> %d productos acumulados", categoria, len(filas))
        finally:
            ctx.close()
            browser.close()
    if not filas:
        raise RuntimeError("No capturé ningún producto de PedidosYa (con EAN y precio). "
                           "Corré `python scraper.py --solo \"PedidosYa Market Belgrano\" --debug --visible`")
    if _SIN_EAN["n"]:
        log.warning("PedidosYa: %d objetos con nombre y precio pero sin EAN fueron ignorados", _SIN_EAN["n"])
    return pd.DataFrame(list(filas.values()))


def guardar_sesion(tienda):
    """Abre un navegador visible para que elijas sucursal (Coto) o dirección (PedidosYa) y guarda la sesión."""
    from playwright.sync_api import sync_playwright
    urls = _leer_urls(CONFIG_DIR / "pedidosya_urls.txt")
    inicio = {"Coto": COTO_HOME}.get(tienda, urls[0] if urls else "https://www.pedidosya.com.ar/")
    STATE_DIR.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(locale="es-AR", timezone_id="America/Argentina/Buenos_Aires", user_agent=UA)
        ctx.new_page().goto(inicio)
        input(f"[{tienda}] Elegí la sucursal/dirección en el navegador y apretá Enter acá para guardar... ")
        ctx.storage_state(path=str(STATE_DIR / f"{tienda}.json"))
        browser.close()
    print("Sesión guardada.")


def _con_respaldo(fn, tienda):
    def run():
        try:
            return fn()
        except Exception as e:
            try:
                log.warning("%s: falló el scraping web (%s); uso el CSV de respaldo", tienda, e)
                return importar_csv(tienda)
            except FileNotFoundError:
                raise e
    return run


ADAPTADORES = {
    "Carrefour": lambda: descargar_vtex("https://www.carrefour.com.ar"),
    "Dia": lambda: descargar_vtex("https://diaonline.supermercadosdia.com.ar"),
    "Coto": _con_respaldo(descargar_coto, "Coto"),
    "PedidosYa Market Belgrano": _con_respaldo(descargar_pedidosya, "PedidosYa Market Belgrano"),
}


# ==============================================================================
# SNAPSHOT SEMANAL (con estado visible, lock entre procesos y reintentos espaciados)
# ==============================================================================
def _limpiar(df):
    df = df.copy()
    df["ean"] = df["ean"].astype(str).str.strip()
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df = df[(df["ean"] != "") & (df["precio"] > 0)]
    for col in ("producto", "marca", "categoria"):
        df[col] = df[col].fillna("").astype(str)
    return df.drop_duplicates(subset="ean")


def _slug(tienda):
    return re.sub(r"\W+", "_", tienda)


def exportar_snapshot(tienda, fecha, df):
    """Guarda el snapshot como datos/AAAA-MM-DD__Tienda.csv.gz (así vive en el repositorio de git)."""
    DATOS_DIR.mkdir(exist_ok=True)
    ruta = DATOS_DIR / f"{fecha}__{_slug(tienda)}.csv.gz"
    df[["ean", "producto", "marca", "categoria", "precio"]].to_csv(ruta, index=False, compression="gzip")


def sincronizar_desde_datos():
    """Carga en SQLite los snapshots de datos/*.csv.gz que todavía no estén en la base."""
    if not DATOS_DIR.exists():
        return 0
    slugs = {_slug(t): t for t in ADAPTADORES}
    con = conectar()
    nuevos = 0
    try:
        existentes = {(f, t) for f, t in con.execute("SELECT DISTINCT fecha, tienda FROM precios")}
        for ruta in sorted(DATOS_DIR.glob("*__*.csv.gz")):
            fecha, _, resto = ruta.name.partition("__")
            tienda = slugs.get(resto[: -len(".csv.gz")])
            if not tienda or (fecha, tienda) in existentes:
                continue
            df = _limpiar(pd.read_csv(ruta, dtype={"ean": str}))
            if not df.empty:
                _guardar(con, tienda, fecha, df)
                nuevos += 1
    finally:
        con.close()
    return nuevos


def _leer_estado():
    try:
        return json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


_ESTADO_LOCK = threading.Lock()


def _set_estado(tienda, ok, mensaje):
    with _ESTADO_LOCK:
        DATOS_DIR.mkdir(exist_ok=True)
        est = _leer_estado()
        est[tienda] = {"intento": datetime.now().isoformat(timespec="seconds"), "ok": ok, "mensaje": mensaje}
        ESTADO_PATH.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")


def hay_descarga_en_curso():
    try:
        return time.time() - LOCK_PATH.stat().st_mtime < 30 * 60
    except FileNotFoundError:
        return False


def _tomar_lock():
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        if hay_descarga_en_curso():
            return False
        LOCK_PATH.unlink(missing_ok=True)       # lock huérfano (proceso muerto)
        return _tomar_lock()


def _debe_correr(con, tienda, forzar):
    if forzar:
        return True
    ultima = _ultima_fecha(con, tienda)
    if ultima and (date.today() - date.fromisoformat(ultima)).days < INTERVALO_DIAS:
        return False
    est = _leer_estado().get(tienda)
    if est and est.get("ok") is False:
        try:
            if datetime.now() - datetime.fromisoformat(est["intento"]) < timedelta(hours=REINTENTO_HORAS):
                return False
        except (KeyError, ValueError):
            pass
    return True


def tiendas_pendientes():
    """Tiendas que necesitan snapshot ahora (sin datos, vencidas, y no fallaron hace poco)."""
    con = conectar()
    try:
        return [t for t in ADAPTADORES if _debe_correr(con, t, False)]
    finally:
        con.close()


def _procesar_tienda(tienda, descargar, forzar):
    """Descarga y guarda una tienda (con su propia conexión SQLite). Devuelve un mensaje."""
    con = conectar()
    try:
        if not _debe_correr(con, tienda, forzar):
            return "omitida (al día o reintento reciente)"
        _set_estado(tienda, None, "descargando...")
        try:
            df = _limpiar(descargar())
        except Exception as e:  # una tienda caída no frena a las demás
            log.exception("Fallo %s", tienda)
            _set_estado(tienda, False, " ".join(str(e).split())[:300])
            return f"ERROR: {e}"
        if df.empty:
            _set_estado(tienda, False, "la descarga no devolvió productos")
            return "sin productos (no se guardó nada)"
        ultima = _ultima_fecha(con, tienda)
        previo = _cantidad(con, tienda, ultima) if ultima else 0
        if previo and len(df) < 0.5 * previo:
            log.warning("%s: %d productos vs %d del snapshot anterior (posible descarga incompleta)",
                        tienda, len(df), previo)
        hoy = date.today().isoformat()
        _guardar(con, tienda, hoy, df)
        exportar_snapshot(tienda, hoy, df)
        _set_estado(tienda, True, f"{len(df):,} productos")
        return f"OK: {len(df):,} productos"
    finally:
        con.close()


def tomar_snapshot(forzar=False, solo=None):
    """Toma el snapshot de cada tienda que lo necesite (en paralelo). Devuelve {tienda: mensaje}."""
    if not _LOCK.acquire(blocking=False):
        return {"info": "Ya hay un snapshot en curso"}
    if not _tomar_lock():
        _LOCK.release()
        return {"info": "Ya hay una descarga en curso en otro proceso"}
    resumen = {}
    try:
        sincronizar_desde_datos()      # en una máquina nueva (ej. GitHub Actions) reconstruye la base desde datos/
        tiendas = {t: f for t, f in ADAPTADORES.items() if not solo or t == solo}
        if PARALELO and len(tiendas) > 1:
            with ThreadPoolExecutor(max_workers=len(tiendas)) as ex:
                futuros = {ex.submit(_procesar_tienda, t, f, forzar): t for t, f in tiendas.items()}
                for fut in as_completed(futuros):
                    t = futuros[fut]
                    try:
                        resumen[t] = fut.result()
                    except Exception as e:
                        _set_estado(t, False, " ".join(str(e).split())[:300])
                        resumen[t] = f"ERROR: {e}"
        else:
            for t, f in tiendas.items():
                resumen[t] = _procesar_tienda(t, f, forzar)
    finally:
        LOCK_PATH.unlink(missing_ok=True)
        _LOCK.release()
    return resumen


def estado_snapshots():
    """Resumen por tienda: ultimo snapshot, cantidad de snapshots/productos y resultado del ultimo intento."""
    con = conectar()
    try:
        a = pd.read_sql_query(
            "SELECT tienda, MAX(fecha) AS ultimo, COUNT(DISTINCT fecha) AS snapshots "
            "FROM precios GROUP BY tienda", con)
        b = pd.read_sql_query(
            "SELECT p.tienda, COUNT(*) AS productos FROM precios p "
            "JOIN (SELECT tienda, MAX(fecha) AS f FROM precios GROUP BY tienda) m "
            "ON p.tienda=m.tienda AND p.fecha=m.f GROUP BY p.tienda", con)
    finally:
        con.close()
    out = pd.DataFrame({"tienda": list(ADAPTADORES)}).merge(a, how="left", on="tienda").merge(b, how="left", on="tienda")
    est = _leer_estado()

    def texto(t):
        e = est.get(t)
        if not e:
            return "—"
        icono = "⏳" if e["ok"] is None else ("✅" if e["ok"] else "❌")
        return f"{icono} {e['mensaje']}"

    out["estado"] = out["tienda"].map(texto)
    out.columns = ["Tienda", "Último snapshot", "Snapshots", "Productos", "Último intento"]
    out["Último snapshot"] = out["Último snapshot"].fillna("—")
    out["Snapshots"] = out["Snapshots"].fillna(0).astype(int)
    out["Productos"] = out["Productos"].fillna(0).astype(int)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="ignora el intervalo de 7 dias")
    ap.add_argument("--solo", help="procesa solo esta tienda (nombre exacto)")
    ap.add_argument("--debug", action="store_true", help="vuelca las respuestas JSON a debug/")
    ap.add_argument("--visible", action="store_true", help="muestra el navegador")
    ap.add_argument("--login", metavar="TIENDA", help="guarda sesion (sucursal/direccion) de Coto o PedidosYa")
    ap.add_argument("--daemon", action="store_true", help="loop permanente, revisa cada 6 h")
    args = ap.parse_args()
    DEBUG, HEADLESS = args.debug, not args.visible
    if args.login:
        guardar_sesion(args.login)
    elif args.daemon:
        while True:
            for t, msg in tomar_snapshot().items():
                log.info("%s: %s", t, msg)
            time.sleep(6 * 3600)
    else:
        for t, msg in tomar_snapshot(forzar=args.forzar or bool(args.solo), solo=args.solo).items():
            print(f"{t}: {msg}")
