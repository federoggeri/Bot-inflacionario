import subprocess
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import scraper

st.set_page_config(page_title="Monitor de Inflación & Precios", page_icon="🛒", layout="wide")

TIENDAS = list(scraper.ADAPTADORES)

# ==============================================================================
# 1. SERIE OFICIAL DE IPC INDEC (clave "AAAA-MM")
#    Valores heredados de tu código original: verificalos y actualizalos con
#    los informes técnicos del INDEC a medida que salgan.
# ==============================================================================
INDEC_IPC = {
    "2026-05": {"ipc_alimentos": 4.8, "ipc_general": 4.2},
    "2026-06": {"ipc_alimentos": 4.4, "ipc_general": 4.6},
    "2026-07": {"ipc_alimentos": 3.8, "ipc_general": 4.0},
    "2026-08": {"ipc_alimentos": 3.6, "ipc_general": 4.2},
    "2026-09": {"ipc_alimentos": 3.3, "ipc_general": 3.5},
    "2026-10": {"ipc_alimentos": 3.1, "ipc_general": 3.2},
}
MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
            "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def etiqueta_mes(clave: str) -> str:
    anio, mes = clave.split("-")
    return f"{MESES_ES[int(mes) - 1]} {anio}"


def normalizar_texto(texto) -> str:
    if not isinstance(texto, str):
        return ""
    n = unicodedata.normalize("NFD", texto)
    return "".join(c for c in n if unicodedata.category(c) != "Mn").lower().strip()


# ==============================================================================
# 2. ACCESO A DATOS (SQLite)
# ==============================================================================
def _query(sql, params=()):
    con = scraper.conectar()
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


_ULTIMO_SNAPSHOT = ("JOIN (SELECT tienda, MAX(fecha) AS f FROM precios GROUP BY tienda) m "
                    "ON p.tienda = m.tienda AND p.fecha = m.f")


@st.cache_data(ttl=300, show_spinner=False)
def cargar_catalogo() -> pd.DataFrame:
    """Catálogo único por EAN, a partir del último snapshot de cada cadena."""
    df = _query(f"""
        SELECT p.ean, MAX(p.producto) AS producto, MAX(p.marca) AS marca,
               MAX(p.categoria) AS categoria, MIN(p.precio) AS precio_min,
               COUNT(DISTINCT p.tienda) AS cadenas
        FROM precios p {_ULTIMO_SNAPSHOT}
        GROUP BY p.ean""")
    df["busqueda"] = (df["producto"].fillna("") + " " + df["marca"].fillna("") + " " + df["ean"]).map(normalizar_texto)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def cargar_ultimos_precios() -> pd.DataFrame:
    return _query(f"SELECT p.tienda, p.fecha, p.ean, p.precio FROM precios p {_ULTIMO_SNAPSHOT}")


@st.cache_data(ttl=300, show_spinner=False)
def cargar_historial(eans: tuple) -> pd.DataFrame:
    if not eans:
        return pd.DataFrame(columns=["fecha", "tienda", "ean", "precio"])
    marcas = ",".join("?" * len(eans))
    df = _query(f"SELECT fecha, tienda, ean, precio FROM precios WHERE ean IN ({marcas})", eans)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["semana"] = df["fecha"].dt.to_period("W").dt.start_time
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")
    return df


def matriz_precios(hist: pd.DataFrame, periodo: str) -> pd.DataFrame:
    """Precio medio por período y producto; completa huecos para mantener la misma canasta."""
    return (hist.groupby([periodo, "ean"])["precio"].mean()
            .unstack("ean").sort_index().ffill().bfill())


def costo_por_tienda(hist: pd.DataFrame, q: pd.Series, solo_comunes: bool) -> pd.DataFrame:
    por_tienda = {}
    for t, g in hist.groupby(["tienda"]):
        t = t[0] if isinstance(t, tuple) else t
        p = (g.groupby(["semana", "ean"])["precio"].mean().unstack("ean")
             .sort_index().ffill().bfill())
        por_tienda[t] = p
    if solo_comunes and len(por_tienda) > 1:
        comunes = sorted(set.intersection(*[set(p.columns) for p in por_tienda.values()]))
        por_tienda = {t: p[comunes] for t, p in por_tienda.items()}
    filas = []
    for t, p in por_tienda.items():
        if p.shape[1] == 0:
            continue
        costo = (p * q.reindex(p.columns)).sum(axis=1)
        for semana, v in costo.items():
            filas.append({"semana": semana, "supermercado": t, "gasto": v, "items": p.shape[1]})
    return pd.DataFrame(filas)


# ==============================================================================
# 3. BARRA LATERAL: ESTADO DE LOS SNAPSHOTS
# ==============================================================================
with st.sidebar:
    st.header("🗓️ Snapshots semanales")
    st.caption("Los snapshots los toma `scraper.py` (programado en tu PC); esta app solo lee la base.")
    st.dataframe(scraper.estado_snapshots(), hide_index=True)
    if st.button("🔄 Actualizar precios ahora"):
        subprocess.Popen([sys.executable, str(Path(scraper.__file__).resolve()), "--forzar"],
                         cwd=str(Path(scraper.__file__).resolve().parent))
        st.info("Descarga iniciada en segundo plano. Puede tardar un buen rato; refrescá esta página más tarde.")

df_cat = cargar_catalogo()

st.title("🛒 Monitor de Inflación Personal & Comparador de Precios")

if df_cat.empty:
    st.warning("Todavía no hay precios guardados. Corré `python scraper.py` o usá el botón "
               "**Actualizar precios ahora** de la barra lateral para tomar el primer snapshot.")
    st.stop()

NOMBRES = dict(zip(df_cat["ean"], df_cat["producto"]))
CATEGORIAS = ["Todas"] + sorted(df_cat["categoria"].dropna().unique().tolist())
st.caption(f"Base de góndola activa: **{len(df_cat):,} productos** (por EAN) | "
           f"Comercios: {', '.join(TIENDAS)}")

if "canasta" not in st.session_state:
    st.session_state.canasta = {}       # {ean: cantidad mensual}
canasta = st.session_state.canasta

tab1, tab2, tab3 = st.tabs([
    "🧺 1. Armar y Editar Canasta",
    "📈 2. Análisis de Inflación vs. IPC INDEC",
    "🎯 3. Optimizador de Faltantes",
])

# ==============================================================================
# PESTAÑA 1: ARMAR Y EDITAR CANASTA
# ==============================================================================
with tab1:
    st.subheader("1. Selección y Búsqueda de Alimentos")
    st.write("Buscá por nombre, marca o EAN (ej: *dulce de leche*, *playadito*, *leche*). "
             "Seleccioná una o varias filas y agregalas a la canasta:")

    c_cat, c_txt = st.columns([1, 2])
    with c_cat:
        cat_filtro = st.selectbox("Filtrar por Categoría:", CATEGORIAS)
    with c_txt:
        busq_input = st.text_input("Buscador por Texto:")

    sub_df = df_cat if cat_filtro == "Todas" else df_cat[df_cat["categoria"] == cat_filtro]
    for t in normalizar_texto(busq_input).split():
        sub_df = sub_df[sub_df["busqueda"].str.contains(t, regex=False)]
    sub_df = sub_df.sort_values("producto").reset_index(drop=True)

    st.caption(f"Coincidencias encontradas: **{len(sub_df):,}** productos")

    if len(sub_df) > 0:
        vista = sub_df[["producto", "marca", "categoria", "ean", "precio_min", "cadenas"]].rename(columns={
            "producto": "Producto", "marca": "Marca", "categoria": "Categoría",
            "ean": "EAN", "precio_min": "Precio mín. ($)", "cadenas": "Cadenas"})
        evento = st.dataframe(vista, hide_index=True, height=320,
                              on_select="rerun", selection_mode="multi-row", key="tabla_busqueda")
        filas_sel = evento.selection.rows
        c_cant, c_btn = st.columns([1, 1])
        with c_cant:
            cant_elegida = st.number_input("Cantidad mensual (q₀):", min_value=1.0, value=2.0, step=1.0)
        with c_btn:
            st.write("")
            st.write("")
            if st.button(f"➕ Agregar {len(filas_sel)} producto(s) a la canasta", disabled=not filas_sel):
                for i in filas_sel:
                    canasta[sub_df.loc[i, "ean"]] = cant_elegida
                st.toast(f"Agregados: {len(filas_sel)}", icon="✅")
    else:
        st.warning("No se encontraron productos con ese filtro.")

    st.divider()

    st.subheader("Tu Canasta Mensual Ponderada Actual")
    if canasta:
        info = df_cat.set_index("ean")
        items_vista = [{
            "Categoría": info.loc[e, "categoria"] if e in info.index else "Sin stock actual",
            "Código EAN": e,
            "Producto": NOMBRES.get(e, e),
            "Cantidad Mensual (q₀)": q,
        } for e, q in canasta.items()]
        st.dataframe(pd.DataFrame(items_vista), hide_index=True)

        col_del, col_btn_del, col_vaciar = st.columns([3, 1, 1])
        with col_del:
            ean_borrar = st.selectbox("Seleccionar producto para quitar:", list(canasta),
                                      format_func=lambda e: NOMBRES.get(e, e))
        with col_btn_del:
            st.write("")
            st.write("")
            if st.button("🗑️ Quitar este ítem"):
                del canasta[ean_borrar]
                st.rerun()
        with col_vaciar:
            st.write("")
            st.write("")
            if st.button("❌ Vaciar Canasta"):
                st.session_state.canasta = {}
                st.rerun()
    else:
        st.info("Tu canasta está vacía. Sumá alimentos arriba para comenzar a medir.")

# ==============================================================================
# PESTAÑA 2: ANÁLISIS DE INFLACIÓN VS IPC INDEC (MES A MES & SEMANA A SEMANA)
# ==============================================================================
with tab2:
    st.subheader("2. Medición Econométrica: Tu Inflación vs. IPC INDEC Oficial")
    if not canasta:
        st.warning("Primero agregá productos en la pestaña '1. Armar y Editar Canasta'.")
    else:
        hist = cargar_historial(tuple(canasta))
        if hist.empty:
            st.warning("Ningún producto de tu canasta tiene precios guardados.")
        q0 = pd.Series(canasta, dtype=float)

        if not hist.empty:
            sin_datos = [NOMBRES.get(e, e) for e in canasta if e not in set(hist["ean"])]
            if sin_datos:
                st.caption(f"⚠️ Sin precios en el historial (excluidos del cálculo): {', '.join(sin_datos)}")

            # --- Serie mensual (Laspeyres sobre canasta fija) ---
            piv_mes = matriz_precios(hist, "mes")
            costo_mes = (piv_mes * q0.reindex(piv_mes.columns)).sum(axis=1).rename("gasto_item").reset_index()
            costo_mes["etiqueta"] = costo_mes["mes"].map(etiqueta_mes)
            costo_mes["inflacion_personal_%"] = costo_mes["gasto_item"].pct_change() * 100
            costo_mes["ipc_indec_alimentos_%"] = costo_mes["mes"].map(
                lambda m: INDEC_IPC.get(m, {}).get("ipc_alimentos", float("nan")))
            costo_mes["ipc_indec_general_%"] = costo_mes["mes"].map(
                lambda m: INDEC_IPC.get(m, {}).get("ipc_general", float("nan")))

            n_snap = hist["fecha"].nunique()
            st.caption(f"Historial disponible: **{n_snap}** fecha(s) de snapshot en **{len(costo_mes)}** mes(es).")

            if len(costo_mes) < 2:
                st.info("La comparación mes a mes con el INDEC necesita snapshots de **al menos 2 meses distintos**. "
                        "Mientras se acumula el historial, podés ver la evolución semanal más abajo (Gráfico 3).")
            else:
                df_graf = costo_mes.iloc[1:].copy()
                gasto_inicio = costo_mes["gasto_item"].iloc[0]
                gasto_fin = costo_mes["gasto_item"].iloc[-1]
                inf_personal_acum = (gasto_fin / gasto_inicio - 1) * 100

                ipc_meses = costo_mes["ipc_indec_alimentos_%"].iloc[1:]
                faltan = costo_mes["etiqueta"].iloc[1:][ipc_meses.isna()].tolist()
                factor_indec = (1 + ipc_meses.fillna(0) / 100).prod()
                inf_indec_acum = (factor_indec - 1) * 100

                m1, m2, m3 = st.columns(3)
                m1.metric(f"Tu Inflación Acumulada ({len(costo_mes)} meses)", f"{inf_personal_acum:.2f}%")
                m2.metric("IPC INDEC Alimentos Acumulado", f"{inf_indec_acum:.2f}%")
                brecha_total = inf_personal_acum - inf_indec_acum
                m3.metric("Brecha con INDEC", f"{brecha_total:+.2f} p.p.",
                          delta=f"{'Mayor impacto' if brecha_total > 0 else 'Menor impacto'} en tu bolsillo",
                          delta_color="inverse")
                if faltan:
                    st.warning(f"Faltan datos del INDEC para: {', '.join(faltan)} (se tomaron como 0% en el acumulado). "
                               "Cargalos en `INDEC_IPC`.")
                st.caption("Los precios mensuales son el promedio de los snapshots del mes y de todas las cadenas; "
                           "el primer mes puede ser parcial.")

                st.divider()

                # --- GRÁFICO 1 ---
                st.markdown("### 📊 Gráfico 1: Comparativa Mensual Mes a Mes (Tu Inflación vs. IPC INDEC)")
                st.caption("Fuente oficial: **INDEC - IPC Alimentos y Bebidas**.")
                fmt = lambda x: "" if pd.isna(x) else f"{x:.2f}%"
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    x=df_graf["etiqueta"], y=df_graf["inflacion_personal_%"],
                    name="Tu Inflación Personal (Laspeyres)", marker_color="#1f77b4",
                    text=df_graf["inflacion_personal_%"].map(fmt), textposition="outside"))
                fig_comp.add_trace(go.Bar(
                    x=df_graf["etiqueta"], y=df_graf["ipc_indec_alimentos_%"],
                    name="IPC INDEC (Alimentos y Bebidas)", marker_color="#ff7f0e",
                    text=df_graf["ipc_indec_alimentos_%"].map(fmt), textposition="outside"))
                fig_comp.update_layout(
                    barmode="group",
                    title="Inflación Mensual: Canasta Personal vs. Benchmark Oficial INDEC (%)",
                    xaxis_title="Mes de Medición", yaxis_title="Variación Mensual (%)", yaxis_ticksuffix="%",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_comp)

                st.divider()

                # --- GRÁFICO 2 ---
                st.markdown(f"### 📈 Gráfico 2: Trayectoria Acumulada del Nivel de Precios "
                            f"(Base {costo_mes['etiqueta'].iloc[0]} = 100)")
                costo_mes["indice_personal"] = costo_mes["gasto_item"] / gasto_inicio * 100
                idx_indec = [100.0]
                for v in costo_mes["ipc_indec_alimentos_%"].iloc[1:]:
                    idx_indec.append(idx_indec[-1] * (1 + (0 if pd.isna(v) else v) / 100))
                costo_mes["indice_indec"] = idx_indec

                fig_idx = go.Figure()
                fig_idx.add_trace(go.Scatter(
                    x=costo_mes["etiqueta"], y=costo_mes["indice_personal"], mode="lines+markers",
                    name="Índice Personal (Canasta Propia)", line=dict(color="#1f77b4", width=3)))
                fig_idx.add_trace(go.Scatter(
                    x=costo_mes["etiqueta"], y=costo_mes["indice_indec"], mode="lines+markers",
                    name="Índice Oficial INDEC Alimentos", line=dict(color="#ff7f0e", width=3, dash="dash")))
                fig_idx.update_layout(
                    title="Evolución Acumulada del Nivel de Precios (puntos de índice)",
                    xaxis_title="Mes", yaxis_title="Puntos de Índice",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig_idx)

                st.divider()

            # --- GRÁFICO 3: EVOLUCIÓN SEMANAL POR CADENA ---
            st.markdown("### 📅 Gráfico 3: Dinámica Semanal por Cadena")
            st.caption("Costo de tu canasta en cada supermercado, un punto por snapshot semanal.")
            solo_comunes = st.checkbox("Comparar solo ítems presentes en todas las cadenas", value=True)
            df_sem = costo_por_tienda(hist, q0, solo_comunes)
            if df_sem.empty:
                st.warning("No hay ítems de tu canasta presentes en todas las cadenas. Desmarcá la opción de arriba.")
            else:
                fig_sem = px.line(
                    df_sem, x="semana", y="gasto", color="supermercado", markers=True,
                    title="Costo Total Semanal de la Canasta por Cadena Minorista ($)",
                    labels={"semana": "Semana", "gasto": "Gasto Canasta ($)", "supermercado": "Supermercado"},
                    hover_data={"items": True})
                st.plotly_chart(fig_sem)
                cob = df_sem.groupby("supermercado")["items"].max()
                st.caption("Ítems considerados por cadena: " + " | ".join(f"{t}: {n}" for t, n in cob.items()))

# ==============================================================================
# PESTAÑA 3: ASISTENTE DE FALTANTES (OPTIMIZADOR)
# ==============================================================================
with tab3:
    st.subheader("3. Asistente de Compras: ¿Dónde comprar más barato?")
    st.write("Elegí qué productos necesitás reponer hoy para encontrar la opción más económica:")

    ultimos = cargar_ultimos_precios()
    if canasta:
        opciones = list(canasta)
    else:
        opciones = df_cat.sort_values(["cadenas", "producto"], ascending=[False, True])["ean"].head(10).tolist()

    seleccion = st.multiselect("Alimentos a comprar:", options=opciones, default=opciones[:3],
                               format_func=lambda e: NOMBRES.get(e, e))

    if seleccion:
        matriz = (ultimos[ultimos["ean"].isin(seleccion)]
                  .pivot_table(index="ean", columns="tienda", values="precio", aggfunc="min")
                  .reindex(index=seleccion, columns=TIENDAS))
        fechas = ultimos.groupby("tienda")["fecha"].max()
        st.caption("Precios al: " + " | ".join(f"{t}: {fechas.get(t, '—')}" for t in TIENDAS))

        n_sel = len(seleccion)
        cobertura = matriz.notna().sum()
        totales = matriz.sum(min_count=1)
        tabla = pd.DataFrame({
            "Cadena": TIENDAS,
            "Cobertura": [f"{int(cobertura[t])}/{n_sel}" for t in TIENDAS],
            "Costo Total ($)": [totales[t] for t in TIENDAS],
        })
        completas = [t for t in TIENDAS if cobertura[t] == n_sel]

        # Opción 2: compra dividida (mínimo por producto)
        detalle_split, gasto_split = [], 0.0
        for e in matriz.index:
            fila = matriz.loc[e].dropna()
            if fila.empty:
                continue
            gasto_split += fila.min()
            detalle_split.append({"Producto": NOMBRES.get(e, e),
                                  "Comercio más Barato": fila.idxmin(),
                                  "Precio ($)": fila.min()})
        sin_precio = [NOMBRES.get(e, e) for e in matriz.index if matriz.loc[e].isna().all()]

        r1, r2 = st.columns(2)
        with r1:
            if completas:
                mejor = min(completas, key=lambda t: totales[t])
                st.success(f"### 📍 Opción 1: Comprar todo en {mejor}")
                st.write("Ideal para hacer **un único viaje** y no perder tiempo:")
                st.metric("Gasto Total Monocadena", f"${totales[mejor]:,.2f}")
            else:
                mejor = None
                st.warning("### 📍 Opción 1: ninguna cadena tiene todos los productos")
            st.dataframe(tabla.sort_values("Costo Total ($)"), hide_index=True)
            if completas and len(completas) < len(TIENDAS):
                st.caption("Solo compiten por 'todo en una cadena' las que tienen el 100% de los ítems.")

        with r2:
            st.info("### 🛒 Opción 2: Compra Dividida (Mayor Ahorro)")
            st.write("Comprando cada producto donde esté al precio mínimo:")
            if mejor:
                ahorro = totales[mejor] - gasto_split
                ahorro_pct = ahorro / totales[mejor] * 100 if totales[mejor] > 0 else 0.0
                st.metric("Gasto Dividido", f"${gasto_split:,.2f}", delta=f"-${ahorro:,.2f} ({ahorro_pct:.1f}%)")
            else:
                st.metric("Gasto Dividido", f"${gasto_split:,.2f}")
            st.dataframe(pd.DataFrame(detalle_split), hide_index=True)
        if sin_precio:
            st.caption(f"⚠️ Sin precio en ninguna cadena: {', '.join(sin_precio)}")
    else:
        st.info("Seleccioná productos en la lista para ver la comparativa de supermercados.")
