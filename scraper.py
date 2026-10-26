"""
scraper.py
Toma un snapshot de precios (1 vez por semana) de Carrefour, Dia, Coto y
PedidosYa Market Belgrano y lo guarda en SQLite (precios.db).
"""
import argparse
import logging
import sqlite3
import threading
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "precios.db"
MANUAL_DIR = BASE_DIR / "manual"
INTERVALO_DIAS = 7
PAUSA_ENTRE_REQUESTS = 0.3
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

log = logging.getLogger("scraper")
_LOCK = threading.Lock()


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
def _get_json(url, params=None, reintentos=4):
    for i in range(reintentos):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code in (200, 206):
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (i + 1))
                continue
            return None
        except (requests.RequestException, ValueError):
            time.sleep(1 + i)
    return None


def _categorias_vtex(base):
    arbol = _get_json(f"{base}/api/catalog_system/pub/category/tree/3")
    if not arbol:
        raise RuntimeError(f"No pude leer el arbol de categorias de {base}")
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


def descargar_vtex(base):
    filas = {}
    hojas = _categorias_vtex(base)
    truncadas, fallidas = [], 0
    for i, (cat_id, cat_top) in enumerate(hojas, 1):
        desde = 0
        while True:
            lote = _get_json(
                f"{base}/api/catalog_system/pub/products/search",
                params={"fq": f"C:{cat_id}", "_from": desde, "_to": desde + 49},
            )
            if lote is None:
                fallidas += 1
                break
            if not lote:
                break
            for p in lote:
                for it in p.get("items", []):
                    ean = (it.get("ean") or "").strip()
                    if not ean:
                        continue
                    precio = _precio_disponible(it)
                    if precio is None:
                        continue
                    filas[ean] = {
                        "ean": ean,
                        "producto": p.get("productName", ""),
                        "marca": p.get("brand", ""),
                        "categoria": cat_top,
                        "precio": precio,
                    }
            if len(lote) < 50:
                break
            desde += 50
            if desde >= 2500:
                truncadas.append(cat_id)
                break
            time.sleep(PAUSA_ENTRE_REQUESTS)
        if i % 25 == 0:
            log.info("%s: %d/%d categorias, %d productos", base, i, len(hojas), len(filas))
        time.sleep(PAUSA_ENTRE_REQUESTS)
    return pd.DataFrame(list(filas.values()))


# ==============================================================================
# RESPALDO POR CSV (Coto y PedidosYa)
# ==============================================================================
def importar_csv(tienda):
    ruta = MANUAL_DIR / f"{tienda}.csv"
    if not ruta.exists():
        # Fallback defensivo para evitar caídas si el archivo no fue cargado
        return pd.DataFrame(columns=["ean", "producto", "marca", "categoria", "precio"])
    df = pd.read_csv(ruta, dtype={"ean": str})
    for col in ("marca", "categoria"):
        if col not in df.columns:
            df[col] = ""
    return df[["ean", "producto", "marca", "categoria", "precio"]]


def descargar_coto():
    return importar_csv("Coto")


def descargar_pedidosya():
    return importar_csv("PedidosYa Market Belgrano")


ADAPTADORES = {
    "Carrefour": lambda: descargar_vtex("https://www.carrefour.com.ar"),
    "Dia": lambda: descargar_vtex("https://diaonline.supermercadosdia.com.ar"),
    "Coto": descargar_coto,
    "PedidosYa Market Belgrano": descargar_pedidosya,
}


# ==============================================================================
# SNAPSHOT SEMANAL
# ==============================================================================
def _limpiar(df):
    if df.empty:
        return df
    df = df.copy()
    df["ean"] = df["ean"].astype(str).str.strip()
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df = df[(df["ean"] != "") & (df["precio"] > 0)]
    for col in ("producto", "marca", "categoria"):
        df[col] = df[col].fillna("").astype(str)
    return df.drop_duplicates(subset="ean")


def tomar_snapshot(forzar=False):
    if not _LOCK.acquire(blocking=False):
        return {"info": "Ya hay un snapshot en curso"}
    resumen = {}
    try:
        hoy = date.today()
        con = conectar()
        try:
            for tienda, descargar in ADAPTADORES.items():
                ultima = _ultima_fecha(con, tienda)
                if (not forzar) and ultima and (hoy - date.fromisoformat(ultima)).days < INTERVALO_DIAS:
                    resumen[tienda] = f"omitida (ultimo snapshot: {ultima})"
                    continue
                try:
                    df = _limpiar(descargar())
                except Exception as e:
                    log.exception("Fallo %s", tienda)
                    resumen[tienda] = f"ERROR: {e}"
                    continue
                if df.empty:
                    resumen[tienda] = "sin productos (no se guardo nada)"
                    continue
                _guardar(con, tienda, hoy.isoformat(), df)
                resumen[tienda] = f"OK: {len(df):,} productos"
        finally:
            con.close()
    finally:
        _LOCK.release()
    return resumen


def estado_snapshots():
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
    out.columns = ["Tienda", "Último snapshot", "Snapshots", "Productos"]
    out["Último snapshot"] = out["Último snapshot"].fillna("—")
    out["Snapshots"] = out["Snapshots"].fillna(0).astype(int)
    out["Productos"] = out["Productos"].fillna(0).astype(int)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="ignora el intervalo de 7 dias")
    args = ap.parse_args()
    for t, msg in tomar_snapshot(forzar=args.forzar).items():
        print(f"{t}: {msg}")
