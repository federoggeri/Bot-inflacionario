import datetime
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

# Configuración de página de Streamlit
st.set_page_config(
    page_title="Monitor de Inflación & Optimizador",
    page_icon="🛒",
    layout="wide"
)

# ==============================================================================
# 1. MOTOR DE DATOS: CATÁLOGO DE 120.000 PRODUCTOS Y PRECIOS DETERMINÍSTICOS
# ==============================================================================

CATEGORIAS = [
    "Lácteos y Frescos", "Almacén", "Golosinas y Chocolates", "Snacks y Galletitas",
    "Bebidas sin Alcohol", "Bebidas con Alcohol", "Limpieza", "Perfumería y Cuidado",
    "Congelados", "Carnicería y Fiambrería", "Panadería", "Frutas y Verduras"
]

MARCAS = [
    "La Serenísima", "Arcor", "Molinos", "Quilmes", "Coca-Cola", "Unilever",
    "Lucchetti", "Gallo", "Natura", "Bimbo", "Lays", "Havanna", "Ilolay",
    "San Ignacio", "Playadito", "Rosamonte", "Sedal", "Ala", "Magistral"
]

VARIEDADES = [
    "Clásico", "Tradicional", "Premium", "Light", "Sin Azúcar", "Familiar",
    "Especial", "Intenso", "Suave", "Extra", "Cero Grasa", "Doble", "Pack Ahorro"
]

PRODUCTOS_ICONICOS = [
    # Lácteos y Dulces de Leche específicos
    ("7790742355100", "Dulce de Leche Colonial La Serenísima 400g", "Lácteos y Frescos", "La Serenísima", 2850.0),
    ("7790742355001", "Dulce de Leche Clásico La Serenísima 400g", "Lácteos y Frescos", "La Serenísima", 2550.0),
    ("7790742355209", "Dulce de Leche Repostero La Serenísima 400g", "Lácteos y Frescos", "La Serenísima", 2900.0),
    ("7790358000045", "Dulce de Leche Tradicional San Ignacio 400g", "Lácteos y Frescos", "San Ignacio", 2700.0),
    ("7790358000052", "Dulce de Leche Repostero San Ignacio 400g", "Lácteos y Frescos", "San Ignacio", 2850.0),
    ("7798031540012", "Dulce de Leche Original Vacalin 400g", "Lácteos y Frescos", "Vacalin", 2400.0),
    ("7798031540029", "Dulce de Leche Familiar Vacalin 1kg", "Lácteos y Frescos", "Vacalin", 5100.0),
    ("7790580541155", "Dulce de Leche Pote Cartón Havanna 450g", "Lácteos y Frescos", "Havanna", 4600.0),
    ("7791234567890", "Dulce de Leche Tradicional Chimbote 500g", "Lácteos y Frescos", "Chimbote", 5300.0),
    ("7790742330800", "Leche Entera Clásica La Serenísima 1L", "Lácteos y Frescos", "La Serenísima", 1450.0),
    ("7790742336215", "Leche Descremada La Serenísima 1L", "Lácteos y Frescos", "La Serenísima", 1450.0),
    ("7790358000100", "Leche Entera Larga Vida Ilolay 1L", "Lácteos y Frescos", "Ilolay", 1380.0),
    ("7790742010207", "Manteca Clásica La Serenísima 200g", "Lácteos y Frescos", "La Serenísima", 2950.0),
    ("7790358000014", "Queso Cremoso La Paulina 1kg", "Lácteos y Frescos", "La Paulina", 8400.0),
    ("7790358001158", "Queso Untable Finlandia Clásico 290g", "Lácteos y Frescos", "La Serenísima", 3200.0),
    ("7790890200002", "Huevos Blancos Seleccionados x12", "Lácteos y Frescos", "Granja", 3400.0),
    # Almacén
    ("7790070411752", "Arroz Gallo Oro Parboil 1kg", "Almacén", "Gallo", 2150.0),
    ("7790272001005", "Aceite de Girasol Natura 1.5L", "Almacén", "Natura", 2650.0),
    ("7790070318648", "Fideos Spaghetti Lucchetti 500g", "Almacén", "Lucchetti", 1390.0),
    ("7790580120008", "Azúcar Común Tipo A Ledesma 1kg", "Almacén", "Ledesma", 1150.0),
    ("7791720016086", "Yerba Mate Playadito con Palo 1kg", "Almacén", "Playadito", 4200.0),
    ("7790387011400", "Yerba Mate Rosamonte Tradicional 1kg", "Almacén", "Rosamonte", 4350.0),
    ("7790080010013", "Café Molido La Virginia Tostado 250g", "Almacén", "La Virginia", 4450.0),
    ("7792690000108", "Pan de Mesa Bimbo Artesano 500g", "Almacén", "Bimbo", 2450.0),
    # Golosinas y Snacks
    ("7790580541100", "Alfajor Havanna Chocolate 60g", "Golosinas y Chocolates", "Havanna", 1900.0),
    ("7790580131103", "Alfajor Jorgito Chocolate Pack x6", "Golosinas y Chocolates", "Jorgito", 4200.0),
    ("7622210815148", "Chocolate con Leche Milka 100g", "Golosinas y Chocolates", "Milka", 3300.0),
    ("7791813421155", "Papas Fritas Lays Clásicas 85g", "Snacks y Galletitas", "Lays", 2150.0),
    ("7790040133035", "Galletitas Chocolinas 250g", "Snacks y Galletitas", "Bagley", 1800.0),
    # Bebidas y Limpieza
    ("7790895000997", "Coca Cola Sabor Original 1.5L", "Bebidas sin Alcohol", "Coca-Cola", 2450.0),
    ("7790070507271", "Cerveza Rubia Quilmes Clásica 1L", "Bebidas con Alcohol", "Quilmes", 2350.0),
    ("7791290000450", "Jabón Líquido Para Ropa Ala Matic 3L", "Limpieza", "Ala", 7900.0),
    ("7790010000010", "Detergente Magistral Limón 500ml", "Limpieza", "Magistral", 2850.0)
]

PESOS_SUPER = {
    "Dia": 0.955,                      # Estrategia hard discount
    "Coto": 0.988,                     # Hipermercado tradicional
    "Carrefour": 1.000,                # Media de mercado
    "PedidosYa Market Belgrano": 1.155 # Prima de inmediatez
}

@st.cache_data(show_spinner="Cargando catálogo masivo de 120.000 productos...")
def cargar_catalogo_completo():
    """Genera 120.000 productos indexados de manera vectorizada y ultrarrápida."""
    n_total = 120_000
    np.random.seed(42)

    eans = [f"779{i:010d}" for i in range(1, n_total + 1)]
    cats = np.random.choice(CATEGORIAS, size=n_total)
    mrcs = np.random.choice(MARCAS, size=n_total)
    vars_ = np.random.choice(VARIEDADES, size=n_total)
    precios = np.round(np.random.uniform(900.0, 16000.0, size=n_total), 2)
    nombres = [f"{c} {m} {v} - Art. #{i+1}" for i, (c, m, v) in enumerate(zip(cats, mrcs, vars_))]

    # Inyección de los artículos de referencia
    for idx, (ean, nom, cat, marc, p_ref) in enumerate(PRODUCTOS_ICONICOS):
        eans[idx] = ean
        nombres[idx] = nom
        cats[idx] = cat
        mrcs[idx] = marc
        precios[idx] = p_ref

    df = pd.DataFrame({
        "ean": eans,
        "producto": nombres,
        "categoria": cats,
        "marca": mrcs,
        "precio_base": precios
    })
    return df

df_catalogo = cargar_catalogo_completo()

# Fechas de las últimas 6 semanas
HOY = datetime.date.today()
FECHAS = [(HOY - datetime.timedelta(weeks=w)).isoformat() for w in range(5, -1, -1)]

def obtener_precios_panel(productos_seleccionados: list) -> pd.DataFrame:
    """Calcula precios históricos por supermercado solo para los productos consultados."""
    sub_cat = df_catalogo[df_catalogo["producto"].isin(productos_seleccionados)]
    registros = []

    for idx_sem, fecha in enumerate(FECHAS):
        factor_inflacion = (1 + 0.0105) ** (idx_sem - 5)  # ~1.05% inflación semanal promedio
        
        for superm, ratio_cadena in PESOS_SUPER.items():
            for _, row in sub_cat.iterrows():
                # Factor seudoaleatorio estable por producto y supermercado
                seed_val = (hash(row["ean"] + superm + fecha) % 1000) / 1000.0
                ruido = 0.985 + (seed_val * 0.03)
                p_final = round(row["precio_base"] * factor_inflacion * ratio_cadena * ruido, 2)
                
                registros.append({
                    "fecha": fecha,
                    "ean": row["ean"],
                    "producto": row["producto"],
                    "categoria": row["categoria"],
                    "marca": row["marca"],
                    "supermercado": superm,
                    "precio": p_final
                })

    return pd.DataFrame(registros)

# Estado de la sesión: Canasta del usuario
if "canasta" not in st.session_state:
    st.session_state.canasta = {}

# ==============================================================================
# 2. ENCABEZADO
# ==============================================================================
st.title("🛒 Monitor de Inflación Personal & Optimizador de Compras")
st.caption(f"Base de datos activa: **{len(df_catalogo):,} productos** | Comercios: Carrefour, Día, Coto y PedidosYa Market Belgrano")

tab1, tab2, tab3 = st.tabs([
    "🧺 1. Armar y Editar Canasta",
    "📈 2. Mi Inflación Personal (Laspeyres)",
    "🎯 3. ¿Dónde Conviene Comprar Hoy?"
])

# ==============================================================================
# PESTAÑA 1: ARMAR Y EDITAR CANASTA
# ==============================================================================
with tab1:
    st.subheader("Búsqueda en Góndola (120.000 Productos)")
    st.write("Filtrá por categoría o escribí para buscar alimentos y agregarlos a tu canasta mensual:")

    c_cat, c_txt = st.columns([1, 2])
    with c_cat:
        cat_filtro = st.selectbox("Filtrar por Categoría:", ["Todas"] + CATEGORIAS)
    with c_txt:
        busqueda_input = st.text_input("Buscador por nombre, marca o EAN (ej: dulce de leche, colonial, havanna, lays, playadito):")

    # Filtrado eficiente
    df_filtrado = df_catalogo
    if cat_filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado["categoria"] == cat_filtro]

    if busqueda_input.strip():
        terminos = busqueda_input.strip().lower().split()
        for t in terminos:
            mascara = (
                df_filtrado["producto"].str.lower().str.contains(t, na=False) |
                df_filtrado["marca"].str.lower().str.contains(t, na=False) |
                df_filtrado["ean"].str.contains(t, na=False)
            )
            df_filtrado = df_filtrado[mascara]

    total_hallados = len(df_filtrado)
    df_mostrar = df_filtrado.head(100)
    st.caption(f"Coincidencias: **{total_hallados:,}** productos (mostrando los primeros 100 resultados)")

    if total_hallados > 0:
        c_prod, c_cant, c_btn = st.columns([3, 1, 1])
        with c_prod:
            prod_seleccionado = st.selectbox("Seleccionar Producto:", df_mostrar["producto"].tolist())
        with c_cant:
            cant_input = st.number_input("Cantidad mensual (q₀):", min_value=1.0, value=2.0, step=1.0)
        with c_btn:
            st.write("")
            st.write("")
            if st.button("➕ Agregar a Canasta", use_container_width=True):
                st.session_state.canasta[prod_seleccionado] = cant_input
                st.toast(f"Agregado: {prod_seleccionado}", icon="✅")
    else:
        st.warning("No se encontraron productos con ese criterio de búsqueda.")

    st.divider()

    # Visualización y edición de la canasta
    st.subheader("Tu Canasta Mensual Ponderada")
    if st.session_state.canasta:
        items_tabla = []
        for p, q in st.session_state.canasta.items():
            info = df_catalogo[df_catalogo["producto"] == p].iloc[0]
            items_tabla.append({
                "Categoría": info["categoria"],
                "Marca": info["marca"],
                "Código EAN": info["ean"],
                "Producto": p,
                "Cantidad (q₀)": q
            })
        st.dataframe(pd.DataFrame(items_tabla), use_container_width=True)

        col_quitar, col_btn_q, col_vaciar = st.columns([3, 1, 1])
        with col_quitar:
            item_a_quitar = st.selectbox("Seleccionar ítem para eliminar:", list(st.session_state.canasta.keys()))
        with col_btn_q:
            st.write("")
            st.write("")
            if st.button("🗑️ Quitar este ítem", use_container_width=True):
                del st.session_state.canasta[item_a_quitar]
                st.rerun()
        with col_vaciar:
            st.write("")
            st.write("")
            if st.button("❌ Vaciar Todo", use_container_width=True):
                st.session_state.canasta = {}
                st.rerun()
    else:
        st.info("Tu canasta está vacía. Sumá alimentos arriba para comenzar a medir.")

# ==============================================================================
# PESTAÑA 2: MEDICIÓN DE INFLACIÓN (LASPEYRES)
# ==============================================================================
with tab2:
    st.subheader("Cálculo del Índice de Laspeyres")
    if not st.session_state.canasta:
        st.warning("Primero agregá productos en la pestaña '1. Armar y Editar Canasta'.")
    else:
        c_f0, c_ft = st.columns(2)
        with c_f0:
            f0 = st.selectbox("Período Base (t₀):", FECHAS, index=0)
        with c_ft:
            ft = st.selectbox("Período de Comparación (t):", FECHAS, index=len(FECHAS)-1)

        prods_canasta = list(st.session_state.canasta.keys())
        df_panel = obtener_precios_panel(prods_canasta)

        # Precios promedio de mercado
        p0 = df_panel[df_panel["fecha"] == f0].groupby("producto")["precio"].mean()
        pt = df_panel[df_panel["fecha"] == ft].groupby("producto")["precio"].mean()

        gasto_0 = sum(p0[p] * st.session_state.canasta[p] for p in prods_canasta if p in p0)
        gasto_t = sum(pt[p] * st.session_state.canasta[p] for p in prods_canasta if p in pt)

        inflacion_personal = ((gasto_t - gasto_0) / gasto_0) * 100 if gasto_0 > 0 else 0.0
        indice_laspeyres = (gasto_t / gasto_0) * 100 if gasto_0 > 0 else 100.0

        m1, m2, m3 = st.columns(3)
        m1.metric(f"Gasto Base ({f0})", f"${gasto_0:,.2f}")
        m2.metric(f"Gasto Actual ({ft})", f"${gasto_t:,.2f}", delta=f"{inflacion_personal:+.2f}%")
        m3.metric("Inflación Personal Acumulada", f"{inflacion_personal:.2f}%", help="Variación porcentual calculada con ponderaciones fijas de tu consumo")

        st.divider()

        # Inflación desagregada por rubro
        st.subheader("Variación Acumulada por Categoría")
        cat_stats = []
        for cat in df_panel["categoria"].unique():
            prods_cat = [p for p in prods_canasta if df_catalogo[df_catalogo["producto"] == p]["categoria"].iloc[0] == cat]
            g0_cat = sum(p0[p] * st.session_state.canasta[p] for p in prods_cat if p in p0)
            gt_cat = sum(pt[p] * st.session_state.canasta[p] for p in prods_cat if p in pt)
            inf_cat = ((gt_cat - g0_cat) / g0_cat) * 100 if g0_cat > 0 else 0.0
            cat_stats.append({"Categoría": cat, "Inflación (%)": inf_cat})

        fig_bar = px.bar(
            pd.DataFrame(cat_stats), x="Categoría", y="Inflación (%)", color="Categoría",
            title=f"Inflación por Rubro ({f0} a {ft})", text_auto=".2f"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Evolución semanal por comercio
        st.subheader("Costo de tu Canasta por Supermercado a lo largo del tiempo")
        df_evol = df_panel.copy()
        df_evol["q0"] = df_evol["producto"].map(st.session_state.canasta)
        df_evol["gasto_item"] = df_evol["precio"] * df_evol["q0"]
        evol_super = df_evol.groupby(["fecha", "supermercado"])["gasto_item"].sum().reset_index()

        fig_line = px.line(
            evol_super, x="fecha", y="gasto_item", color="supermercado",
            title="Evolución del Costo Total Nominal por Supermercado",
            labels={"gasto_item": "Costo Canasta ($)", "fecha": "Semana"}
        )
        st.plotly_chart(fig_line, use_container_width=True)

# ==============================================================================
# PESTAÑA 3: ASISTENTE DE FALTANTES (OPTIMIZADOR)
# ==============================================================================
with tab3:
    st.subheader("Optimizador de Faltantes: ¿Dónde conviene comprar?")
    st.write("Elegí qué productos necesitás comprar hoy para calcular la mejor estrategia:")

    # Si hay canasta armada, sugiere esos ítems; de lo contrario, muestra una muestra de productos icónicos
    opciones_defecto = list(st.session_state.canasta.keys()) if st.session_state.canasta else [p[1] for p in PRODUCTOS_ICONICOS[:5]]

    faltantes_seleccionados = st.multiselect(
        "Alimentos a reponer:",
        options=opciones_defecto,
        default=opciones_defecto[:3] if len(opciones_defecto) >= 3 else opciones_defecto
    )

    if faltantes_seleccionados:
        df_panel_faltantes = obtener_precios_panel(faltantes_seleccionados)
        ult_fecha = FECHAS[-1]
        df_ult = df_panel_faltantes[df_panel_faltantes["fecha"] == ult_fecha]
        matriz = df_ult.pivot(index="producto", columns="supermercado", values="precio")

        # 1. Monocadena
        totales_super = matriz.sum(axis=0).sort_values()
        mejor_cadena = totales_super.index[0]
        menor_gasto_mono = totales_super.iloc[0]

        # 2. Arbitraje Split
        detalle_split = []
        gasto_split = 0.0
        for p in faltantes_seleccionados:
            if p in matriz.index:
                super_min = matriz.loc[p].idxmin()
                p_min = matriz.loc[p].min()
                gasto_split += p_min
                detalle_split.append({
                    "Producto": p,
                    "Comercio más Barato": super_min,
                    "Precio ($)": p_min
                })

        ahorro_dinero = menor_gasto_mono - gasto_split
        ahorro_pct = (ahorro_dinero / menor_gasto_mono) * 100 if menor_gasto_mono > 0 else 0.0

        r1, r2 = st.columns(2)
        with r1:
            st.success(f"### 📍 Opción 1: Comprar todo en {mejor_cadena}")
            st.write("Para hacer **un solo viaje** y minimizar el costo de búsqueda:")
            st.metric("Gasto Total", f"${menor_gasto_mono:,.2f}")
            st.dataframe(totales_super.rename("Costo Total ($)").to_frame(), use_container_width=True)

        with r2:
            st.info("### 🛒 Opción 2: Compra Dividida (Mayor Ahorro)")
            st.write("Comprando cada producto donde esté al precio mínimo:")
            st.metric("Gasto Dividido", f"${gasto_split:,.2f}", delta=f"-${ahorro_dinero:,.2f} ({ahorro_pct:.1f}%)")
            st.dataframe(pd.DataFrame(detalle_split), use_container_width=True)
    else:
        st.info("Seleccioná productos en la lista para ver la comparativa de precios.")
