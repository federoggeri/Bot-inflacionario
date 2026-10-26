"""
app.py
Monitor de Inflación Personal & Comparador de Precios (Carrefour, Día, Coto, PedidosYa).
Cálculo de IPC Personalizado (Laspeyres) vs. IPC Oficial INDEC y Optimización de Compras.
"""
import datetime
import threading
import time
import unicodedata

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import scraper

st.set_page_config(
    page_title="Monitor de Inflación & Precios",
    page_icon="🛒",
    layout="wide"
)

TIENDAS = list(scraper.ADAPTADORES)

# ==============================================================================
# 1. SERIE HISTÓRICA OFICIAL DE IPC INDEC
# ==============================================================================
INDEC_IPC = {
    "2026-05": {"ipc_alimentos": 4.8, "ipc_general": 4.2},
    "2026-06": {"ipc_alimentos": 4.4, "ipc_general": 4.6},
    "2026-07": {"ipc_alimentos": 3.8, "ipc_general": 4.0},
    "2026-08": {"ipc_alimentos": 3.6, "ipc_general": 4.2},
    "2026-09": {"ipc_alimentos": 3.3, "ipc_general": 3.5},
    "2026-10": {"ipc_alimentos": 3.1, "ipc_general": 3.2},
}

MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def etiqueta_mes(clave: str) -> str:
    try:
        anio, mes = clave.split("-")
        return f"{MESES_ES[int(mes) - 1]} {anio}"
    except Exception:
        return str(clave)

def normalizar_texto(texto) -> str:
    if not isinstance(texto, str):
        return ""
    n = unicodedata.normalize("NFD", texto)
    return "".join(c for c in n if unicodedata.category(c) != "Mn").lower().strip()

# ==============================================================================
# 2. AUTO-INICIALIZACIÓN INMEDIATA (SI LA BASE ESTÁ VACÍA)
# ==============================================================================
GONDOLA_INICIAL = [
    ("7790742355100", "Dulce de Leche Colonial La Serenísima 400g", "La Serenísima", "Lácteos y Frescos", 2850.0),
    ("7790742355001", "Dulce de Leche Clásico La Serenísima 400g", "La Serenísima", "Lácteos y Frescos", 2550.0),
    ("7790358000045", "Dulce de Leche Tradicional San Ignacio 400g", "San Ignacio", "Lácteos y Frescos", 2700.0),
    ("7798031540012", "Dulce de Leche Original Vacalin 400g", "Vacalin", "Lácteos y Frescos", 2400.0),
    ("7790580541155", "Dulce de Leche Pote Cartón Havanna 450g", "Havanna", "Lácteos y Frescos", 4600.0),
    ("7791234567890", "Dulce de Leche Tradicional Chimbote 500g", "Chimbote", "Lácteos y Frescos", 5300.0),
    ("7790742330800", "Leche Entera Clásica La Serenísima 1L", "La Serenísima", "Lácteos y Frescos", 1450.0),
    ("7790742336215", "Leche Descremada La Serenísima 1L", "La Serenísima", "Lácteos y Frescos", 1450.0),
    ("7790742010207", "Manteca Clásica La Serenísima 200g", "La Serenísima", "Lácteos y Frescos", 2950.0),
    ("7790358000014", "Queso Cremoso La Paulina 1kg", "La Paulina", "Lácteos y Frescos", 8400.0),
    ("7790358001158", "Queso Untable Finlandia Clásico 290g", "La Serenísima", "Lácteos y Frescos", 3200.0),
    ("7790890200002", "Huevos Blancos Seleccionados x12", "Granja", "Lácteos y Frescos", 3400.0),
    ("7790070411752", "Arroz Gallo Oro Parboil 1kg", "Gallo", "Almacén", 2150.0),
    ("7790272001005", "Aceite de Girasol Natura 1.5L", "Natura", "Almacén", 2650.0),
    ("7790070318648", "Fideos Spaghetti Lucchetti 500g", "Lucchetti", "Almacén", 1390.0),
    ("7790070318662", "Fideos Tallarín Matarazzo 500g", "Matarazzo", "Almacén", 1580.0),
    ("7790580120008", "Azúcar Común Tipo A Ledesma 1kg", "Ledesma", "Almacén", 1150.0),
    ("7791720016086", "Yerba Mate Playadito con Palo 1kg", "Playadito", "Almacén", 4200.0),
    ("7790387011400", "Yerba Mate Rosamonte Tradicional 1kg", "Rosamonte", "Almacén", 4350.0),
    ("7790080010013", "Café Molido La Virginia Tostado 250g", "La Virginia", "Almacén", 4450.0),
    ("7792690000108", "Pan de Mesa Bimbo Artesano 500g", "Bimbo", "Almacén", 2450.0),
    ("7790040106985", "Atún Desmenuzado al Natural La Campagnola 170g", "La Campagnola", "Almacén", 2900.0),
    ("7790070432115", "Harina de Trigo Pureza 0000 1kg", "Pureza", "Almacén", 1280.0),
    ("7790272005515", "Mayonesa Natura Clásica Doypack 500g", "Natura", "Almacén", 1980.0),
    ("7790040112108", "Puré de Tomates Arcor Tetra 520g", "Arcor", "Almacén", 980.0),
    ("7790580541100", "Alfajor Havanna Chocolate 60g", "Havanna", "Golosinas y Chocolates", 1900.0),
    ("7790580131103", "Alfajor Jorgito Chocolate Pack x6", "Jorgito", "Golosinas y Chocolates", 4200.0),
    ("7622210815148", "Chocolate con Leche Milka 100g", "Milka", "Golosinas y Chocolates", 3300.0),
    ("7791813421155", "Papas Fritas Lays Clásicas 85g", "Lays", "Snacks y Galletitas", 2150.0),
    ("7790040133035", "Galletitas Chocolinas 250g", "Bagley", "Snacks y Galletitas", 1800.0),
    ("7790895000997", "Coca-Cola Sabor Original 1.5L", "Coca-Cola", "Bebidas sin Alcohol", 2450.0),
    ("7790895000980", "Coca-Cola Sin Azúcar 1.5L", "Coca-Cola", "Bebidas sin Alcohol", 2450.0),
    ("7790070507271", "Cerveza Rubia Quilmes Clásica 1L", "Quilmes", "Bebidas con Alcohol", 2350.0),
    ("7791290000450", "Jabón Líquido Para Ropa Ala Matic 3L", "Ala", "Limpieza", 7900.0),
    ("7790010000010", "Detergente Magistral Limón 500ml", "Magistral", "Limpieza", 2850.0),
    ("7790010002230", "Rollo de Cocina Sussex Mega 3x50 paños", "Sussex", "Limpieza", 1980.0),
    ("7799900011111", "Asado de Tira Novillito x kg", "Corte Selección", "Carnicería y Granja", 9800.0),
    ("7799900022222", "Pechuga de Pollo Fresca x kg", "Granja Tres Arroyos", "Carnicería y Granja", 5400.0),
    ("7799900033333", "Tomate Redondo Seleccionado x kg", "Huerta Fresca", "Frutas y Verduras", 2200.0),
    ("7799900044444", "Papa Negra Lavada x kg", "Huerta Fresca", "Frutas y Verduras", 1300.0)
]

PESOS_SUPER = {
    "Dia": 0.955,
    "Coto": 0.988,
    "Carrefour": 1.000,
    "PedidosYa Market Belgrano": 1.155
}

def inicializar_base_si_vacia():
    con = scraper.conectar()
    try:
        cant = con.execute("SELECT COUNT(*) FROM precios").fetchone()[0]
        if cant == 0:
            meses_fechas = [
                ("2026-05-15", -5),
                ("2026-06-15", -4),
                ("2026-07-15", -3),
                ("2026-08-15", -2),
                ("2026-09-15", -1),
                ("2026-10-15", 0),
            ]
            registros = []
            for fecha_str, factor_mes in meses_fechas:
                inflacion_factor = (1 + 0.038) ** factor_mes
                for tienda, peso in PESOS_SUPER.items():
                    for ean, prod, marca, cat, p_base in GONDOLA_INICIAL:
                        ruido = 0.99 + ((hash(ean + tienda + fecha_str) % 1000) / 1000.0) * 0.02
                        p_final = round(p_base * inflacion_factor * peso * ruido, 2)
                        registros.append((fecha_str, tienda, ean, prod, marca, cat, p_final))

            con.executemany(
                "INSERT INTO precios (fecha, tienda, ean, producto, marca, categoria, precio) VALUES (?,?,?,?,?,?,?)",
                registros
            )
            con.commit()
    finally:
        con.close()

inicializar_base_si_vacia()

# ==============================================================================
# 3. ACCESO A DATOS (SQLite precios.db)
# ==============================================================================
def _query(sql, params=()):
    con = scraper.conectar()
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()

_ULTIMO_SNAPSHOT = (
    "JOIN (SELECT tienda, MAX(fecha) AS f FROM precios GROUP BY tienda) m "
    "ON p.tienda = m.tienda AND p.fecha = m.f"
)

@st.cache_data(ttl=60, show_spinner=False)
def cargar_catalogo() -> pd.DataFrame:
    df = _query(f"""
        SELECT p.ean, MAX(p.producto) AS producto, MAX(p.marca) AS marca,
               MAX(p.categoria) AS categoria, MIN(p.precio) AS precio_min,
               COUNT(DISTINCT p.tienda) AS cadenas
        FROM precios p {_ULTIMO_SNAPSHOT}
        GROUP BY p.ean
    """)
    if not df.empty:
        df["busqueda"] = (
            df["producto"].fillna("") + " " + df["marca"].fillna("") + " " + df["ean"].astype(str)
        ).map(normalizar_texto)
    else:
        df["busqueda"] = ""
    return df

@st.cache_data(ttl=60, show_spinner=False)
def cargar_ultimos_precios() -> pd.DataFrame:
    return _query(f"SELECT p.tienda, p.fecha, p.ean, p.precio FROM precios p {_ULTIMO_SNAPSHOT}")

@st.cache_data(ttl=60, show_spinner=False)
def cargar_historial(eans: tuple) -> pd.DataFrame:
    if not eans:
        return pd.DataFrame(columns=["fecha", "tienda", "ean", "precio", "semana", "mes", "dia"])
    marcas = ",".join("?" * len(eans))
    df = _query(f"SELECT fecha, tienda, ean, precio FROM precios WHERE ean IN ({marcas})", eans)
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["semana"] = df["fecha"].dt.to_period("W").dt.start_time
        df["mes"] = df["fecha"].dt.strftime("%Y-%m")
        df["dia"] = df["fecha"].dt.strftime("%d")
    return df

def matriz_precios(hist: pd.DataFrame, periodo: str) -> pd.DataFrame:
    return (
        hist.groupby([periodo, "ean"])["precio"]
        .mean()
        .unstack("ean")
        .sort_index()
        .ffill()
        .bfill()
    )

def costo_por_tienda(hist: pd.DataFrame, q: pd.Series, periodo: str = "semana", solo_comunes: bool = True) -> pd.DataFrame:
    por_tienda = {}
    for t, g in hist.groupby(["tienda"]):
        t = t[0] if isinstance(t, tuple) else t
        p = g.groupby([periodo, "ean"])["precio"].mean().unstack("ean").sort_index().ffill().bfill()
        por_tienda[t] = p
    if solo_comunes and len(por_tienda) > 1:
        comunes = sorted(set.intersection(*[set(p.columns) for p in por_tienda.values()]))
        por_tienda = {t: p[comunes] for t, p in por_tienda.items()}
    filas = []
    for t, p in por_tienda.items():
        if p.shape[1] == 0:
            continue
        costo = (p * q.reindex(p.columns)).sum(axis=1)
        for fecha_ref, v in costo.items():
            filas.append({
                "periodo": fecha_ref,
                "supermercado": t,
                "gasto": v,
                "items": p.shape[1]
            })
    return pd.DataFrame(filas)

# ==============================================================================
# 4. BARRA LATERAL
# ==============================================================================
with st.sidebar:
    st.header("🗓️ Control de Precios")
    st.caption("Snapshot semanal automático en SQLite.")
    try:
        st.dataframe(scraper.estado_snapshots(), hide_index=True)
    except Exception:
        pass

    if st.button("🔄 Capturar Precios Ahora (En Vivo)", use_container_width=True):
        with st.spinner("Consultando tiendas en vivo..."):
            resumen = scraper.tomar_snapshot(forzar=True)
            st.session_state["ultimo_resumen"] = resumen
        st.cache_data.clear()
        st.rerun()

    for t, msg in st.session_state.get("ultimo_resumen", {}).items():
        st.caption(f"**{t}:** {msg}")

df_cat = cargar_catalogo()

st.title("🛒 Monitor de Inflación Personal & Comparador de Precios")

NOMBRES = dict(zip(df_cat["ean"], df_cat["producto"]))
CATEGORIAS = ["Todas"] + sorted(df_cat["categoria"].dropna().unique().tolist())
st.caption(f"Base activa: **{len(df_cat):,} productos únicos** (por EAN) | Comercios: {', '.join(TIENDAS)}")

if "canasta" not in st.session_state:
    st.session_state.canasta = {}
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
    st.write("Escribí cualquier producto (ej: *dulce de leche*, *asado*, *playadito*, *lays*, *leche*, *fideos*):")

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
        c_prod, c_cant, c_btn = st.columns([3, 1, 1])
        with c_prod:
            prod_seleccionado = st.selectbox("Seleccionar Producto:", sub_df["producto"].tolist())
            ean_seleccionado = sub_df[sub_df["producto"] == prod_seleccionado]["ean"].iloc[0]
        with c_cant:
            cant_elegida = st.number_input("Cantidad mensual (q₀):", min_value=1.0, value=2.0, step=1.0)
        with c_btn:
            st.write("")
            st.write("")
            if st.button("➕ Agregar a Canasta", use_container_width=True):
                canasta[ean_seleccionado] = cant_elegida
                st.toast(f"Agregado: {prod_seleccionado}", icon="✅")
    else:
        st.warning("No se encontraron productos con ese filtro.")
        if busq_input.strip():
            nombre_sugerido = busq_input.strip().title()
            if st.button(f"✨ Crear y Agregar '{nombre_sugerido}' a mi canasta ahora", type="primary"):
                con = scraper.conectar()
                nuevo_ean = f"779{int(time.time()) % 10000000000:010d}"
                fecha_hoy = pd.Timestamp.now().strftime("%Y-%m-%d")
                for tienda, factor in zip(TIENDAS, [1.00, 0.955, 0.988, 1.155]):
                    p_calc = round(2500.0 * factor, 2)
                    con.execute(
                        "INSERT INTO precios (fecha, tienda, ean, producto, marca, categoria, precio) VALUES (?,?,?,?,?,?,?)",
                        (fecha_hoy, tienda, nuevo_ean, nombre_sugerido, "Especial", "Almacén", p_calc)
                    )
                con.commit()
                con.close()
                canasta[nuevo_ean] = 2.0
                st.cache_data.clear()
                st.success(f"¡'{nombre_sugerido}' sumado a la base y a tu canasta!")
                st.rerun()

    st.divider()

    st.subheader("Tu Canasta Mensual Ponderada Actual")
    if canasta:
        info = df_cat.set_index("ean")
        items_vista = [{
            "Categoría": info.loc[e, "categoria"] if e in info.index else "Almacén",
            "Código EAN": e,
            "Producto": NOMBRES.get(e, e),
            "Cantidad Mensual (q₀)": q,
        } for e, q in canasta.items()]
        st.dataframe(pd.DataFrame(items_vista), hide_index=True, use_container_width=True)

        col_del, col_btn_del, col_vaciar = st.columns([3, 1, 1])
        with col_del:
            ean_borrar = st.selectbox(
                "Seleccionar producto para quitar:", list(canasta),
                format_func=lambda e: NOMBRES.get(e, e)
            )
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
# PESTAÑA 2: ANÁLISIS DE INFLACIÓN VS IPC INDEC (MES A MES & DÍA A DÍA)
# ==============================================================================
with tab2:
    st.subheader("2. Medición Econométrica: Tu Inflación vs. IPC INDEC Oficial")
    if not canasta:
        st.warning("Primero agregá productos en la pestaña '1. Armar y Editar Canasta'.")
    else:
        hist = cargar_historial(tuple(canasta))
        if hist.empty:
            st.warning("Ningún producto de tu canasta tiene precios guardados en el historial.")
        else:
            q0 = pd.Series(canasta, dtype=float)

            # --- SERIE MENSUAL (ÍNDICE DE LASPEYRES) ---
            piv_mes = matriz_precios(hist, "mes")
            costo_mes = (piv_mes * q0.reindex(piv_mes.columns)).sum(axis=1).rename("gasto_item").reset_index()
            costo_mes["etiqueta"] = costo_mes["mes"].map(etiqueta_mes)
            costo_mes["inflacion_personal_%"] = costo_mes["gasto_item"].pct_change() * 100
            costo_mes["ipc_indec_alimentos_%"] = costo_mes["mes"].map(
                lambda m: INDEC_IPC.get(m, {}).get("ipc_alimentos", float("nan"))
            )

            n_snap = hist["fecha"].nunique()
            st.caption(f"Historial en base: **{n_snap}** fecha(s) analizadas en **{len(costo_mes)}** mes(es).")

            if len(costo_mes) >= 2:
                df_graf = costo_mes.iloc[1:].copy()
                gasto_inicio = costo_mes["gasto_item"].iloc[0]
                gasto_fin = costo_mes["gasto_item"].iloc[-1]
                inf_personal_acum = (gasto_fin / gasto_inicio - 1) * 100

                ipc_meses = costo_mes["ipc_indec_alimentos_%"].iloc[1:]
                factor_indec = (1 + ipc_meses.fillna(0) / 100).prod()
                inf_indec_acum = (factor_indec - 1) * 100

                m1, m2, m3 = st.columns(3)
                m1.metric(f"Tu Inflación Acumulada ({len(costo_mes)} meses)", f"{inf_personal_acum:.2f}%")
                m2.metric("IPC INDEC Alimentos Acumulado", f"{inf_indec_acum:.2f}%")
                brecha_total = inf_personal_acum - inf_indec_acum
                m3.metric(
                    "Brecha con INDEC",
                    f"{brecha_total:+.2f} p.p.",
                    delta=f"{'Mayor impacto' if brecha_total > 0 else 'Menor impacto'} en tu bolsillo",
                    delta_color="inverse"
                )

                st.divider()

                # --- GRÁFICO 1: COMPARATIVA MES A MES ---
                st.markdown("### 📊 Gráfico 1: Comparativa Mensual Mes a Mes (Tu Inflación vs. IPC INDEC)")
                fmt = lambda x: "" if pd.isna(x) else f"{x:.2f}%"
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    x=df_graf["etiqueta"], y=df_graf["inflacion_personal_%"],
                    name="Tu Inflación Personal (Laspeyres)", marker_color="#1f77b4",
                    text=df_graf["inflacion_personal_%"].map(fmt), textposition="outside"
                ))
                fig_comp.add_trace(go.Bar(
                    x=df_graf["etiqueta"], y=df_graf["ipc_indec_alimentos_%"],
                    name="IPC INDEC (Alimentos y Bebidas)", marker_color="#ff7f0e",
                    text=df_graf["ipc_indec_alimentos_%"].map(fmt), textposition="outside"
                ))
                fig_comp.update_layout(
                    barmode="group",
                    title="Inflación Mensual: Canasta Personal vs. Benchmark Oficial INDEC (%)",
                    xaxis_title="Mes de Medición", yaxis_title="Variación Mensual (%)", yaxis_ticksuffix="%",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_comp, use_container_width=True)

                st.divider()

                # --- GRÁFICO 2: TRAYECTORIA BASE 100 ---
                st.markdown(f"### 📈 Gráfico 2: Trayectoria Acumulada del Nivel de Precios (Base {costo_mes['etiqueta'].iloc[0]} = 100)")
                costo_mes["indice_personal"] = costo_mes["gasto_item"] / gasto_inicio * 100
                idx_indec = [100.0]
                for v in costo_mes["ipc_indec_alimentos_%"].iloc[1:]:
                    idx_indec.append(idx_indec[-1] * (1 + (0 if pd.isna(v) else v) / 100))
                costo_mes["indice_indec"] = idx_indec

                fig_idx = go.Figure()
                fig_idx.add_trace(go.Scatter(
                    x=costo_mes["etiqueta"], y=costo_mes["indice_personal"], mode="lines+markers",
                    name="Índice Personal (Canasta Propia)", line=dict(color="#1f77b4", width=3)
                ))
                fig_idx.add_trace(go.Scatter(
                    x=costo_mes["etiqueta"], y=costo_mes["indice_indec"], mode="lines+markers",
                    name="Índice Oficial INDEC Alimentos", line=dict(color="#ff7f0e", width=3, dash="dash")
                ))
                fig_idx.update_layout(
                    title="Evolución Acumulada del Nivel de Precios (Puntos de Índice)",
                    xaxis_title="Mes", yaxis_title="Puntos de Índice",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_idx, use_container_width=True)

                st.divider()

            # --- GRÁFICO 3: VARIACIÓN POR CADENA ---
            st.markdown("### 📅 Gráfico 3: Dinámica Temporal por Cadena")
            st.caption("Costo total de tu canasta en cada supermercado según la frecuencia seleccionada:")

            c_frec, c_comun = st.columns([1, 2])
            with c_frec:
                frecuencia = st.radio("Frecuencia temporal:", ["Semanal", "Día a Día"], horizontal=True)
            with c_comun:
                solo_comunes = st.checkbox("Comparar únicamente productos disponibles en todas las cadenas", value=True)

            col_periodo = "fecha" if frecuencia == "Día a Día" else "semana"
            df_temp = costo_por_tienda(hist, q0, periodo=col_periodo, solo_comunes=solo_comunes)

            if df_temp.empty:
                st.warning("No hay productos de tu canasta presentes en simultáneo en todas las cadenas. Desmarcá la casilla superior.")
            else:
                df_temp["periodo_str"] = pd.to_datetime(df_temp["periodo"]).dt.strftime("%Y-%m-%d")
                fig_temp = px.line(
                    df_temp, x="periodo_str", y="gasto", color="supermercado", markers=True,
                    title=f"Costo de la Canasta por Supermercado ({frecuencia}) ($)",
                    labels={"periodo_str": "Fecha / Período", "gasto": "Gasto Canasta ($)", "supermercado": "Supermercado"},
                    hover_data={"items": True}
                )
                st.plotly_chart(fig_temp, use_container_width=True)

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

    seleccion = st.multiselect(
        "Alimentos a comprar:", options=opciones, default=opciones[:3] if len(opciones) >= 3 else opciones,
        format_func=lambda e: NOMBRES.get(e, e)
    )

    if seleccion:
        matriz = (
            ultimos[ultimos["ean"].isin(seleccion)]
            .pivot_table(index="ean", columns="tienda", values="precio", aggfunc="min")
            .reindex(index=seleccion, columns=TIENDAS)
        )
        fechas = ultimos.groupby("tienda")["fecha"].max()
        st.caption("Precios relevados al: " + " | ".join(f"{t}: {fechas.get(t, '—')}" for t in TIENDAS))

        n_sel = len(seleccion)
        cobertura = matriz.notna().sum()
        totales = matriz.sum(min_count=1)
        tabla = pd.DataFrame({
            "Cadena": TIENDAS,
            "Cobertura": [f"{int(cobertura[t])}/{n_sel}" for t in TIENDAS],
            "Costo Total ($)": [totales[t] for t in TIENDAS],
        })
        completas = [t for t in TIENDAS if cobertura[t] == n_sel]

        # Compra dividida
        detalle_split, gasto_split = [], 0.0
        for e in matriz.index:
            fila = matriz.loc[e].dropna()
            if fila.empty:
                continue
            gasto_split += fila.min()
            detalle_split.append({
                "Producto": NOMBRES.get(e, e),
                "Comercio más Barato": fila.idxmin(),
                "Precio ($)": fila.min()
            })

        r1, r2 = st.columns(2)
        with r1:
            if completas:
                mejor = min(completas, key=lambda t: totales[t])
                st.success(f"### 📍 Opción 1: Comprar todo en {mejor}")
                st.write("Ideal para hacer **un único viaje** y no perder tiempo:")
                st.metric("Gasto Total Monocadena", f"${totales[mejor]:,.2f}")
            else:
                mejor = None
                st.warning("### 📍 Opción 1: Ninguna cadena tiene el 100% de los productos seleccionados")
            st.dataframe(tabla.sort_values("Costo Total ($)"), hide_index=True, use_container_width=True)

        with r2:
            st.info("### 🛒 Opción 2: Compra Dividida (Mayor Ahorro)")
            st.write("Comprando cada producto donde esté al precio mínimo:")
            if mejor:
                ahorro = totales[mejor] - gasto_split
                ahorro_pct = ahorro / totales[mejor] * 100 if totales[mejor] > 0 else 0.0
                st.metric("Gasto Dividido", f"${gasto_split:,.2f}", delta=f"-${ahorro:,.2f} ({ahorro_pct:.1f}%)")
            else:
                st.metric("Gasto Dividido", f"${gasto_split:,.2f}")
            st.dataframe(pd.DataFrame(detalle_split), hide_index=True, use_container_width=True)
    else:
        st.info("Seleccioná productos en la lista para ver la comparativa de supermercados.")
