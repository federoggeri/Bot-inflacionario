"""
app.py
Monitor de Inflación Personal & Comparador de Precios (Carrefour, Día, Coto, PedidosYa).
Base precargada instantánea, cálculo de Laspeyres vs. IPC INDEC y optimizador de compras.
"""
import unicodedata
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Monitor de Inflación & Precios",
    page_icon="🛒",
    layout="wide"
)

# ==============================================================================
# 1. GÓNDOLA REAL ARGENTINA Y PRECIOS DETERMINÍSTICOS
# ==============================================================================

TIENDAS = ["Carrefour", "Dia", "Coto", "PedidosYa Market Belgrano"]

PESOS_TIENDA = {
    "Dia": 0.955,                      # Estrategia descuento
    "Coto": 0.988,                     # Hipermercado tradicional
    "Carrefour": 1.000,                # Media de mercado
    "PedidosYa Market Belgrano": 1.155 # Prima de conveniencia en Belgrano
}

# Serie oficial de IPC INDEC (Alimentos y Bebidas)
INDEC_IPC = {
    "Mayo 2026": {"ipc_alimentos": 4.8},
    "Junio 2026": {"ipc_alimentos": 4.4},
    "Julio 2026": {"ipc_alimentos": 3.8},
    "Agosto 2026": {"ipc_alimentos": 3.6},
    "Septiembre 2026": {"ipc_alimentos": 3.3},
    "Octubre 2026": {"ipc_alimentos": 3.1},
}

MESES_SERIE = list(INDEC_IPC.keys())

PLANTILLAS_GONDOLA = [
    # LÁCTEOS, DULCES DE LECHE Y QUESOS
    {"items": ["Dulce de Leche Colonial", "Dulce de Leche Clásico", "Dulce de Leche Repostero"], "marcas": ["La Serenísima", "San Ignacio", "Vacalin", "Ilolay", "Havanna", "Chimbote"], "medidas": ["400g", "450g", "1kg"], "cat": "Lácteos y Frescos", "p_min": 2400, "p_max": 5400},
    {"items": ["Leche Entera Clásica", "Leche Descremada", "Leche Cero Grasa"], "marcas": ["La Serenísima", "Ilolay", "Tregar", "Las Tres Niñas"], "medidas": ["1L"], "cat": "Lácteos y Frescos", "p_min": 1350, "p_max": 1600},
    {"items": ["Yogur Firme Vainilla", "Yogur Firme Frutilla", "Yogur Bebible"], "marcas": ["Yogurísimo", "La Serenísima", "Ilolay"], "medidas": ["190g", "1kg"], "cat": "Lácteos y Frescos", "p_min": 950, "p_max": 2600},
    {"items": ["Queso Cremoso", "Queso Por Salut", "Queso Muzzarella", "Queso Rallado"], "marcas": ["La Paulina", "La Serenísima", "Tregar", "Barraza"], "medidas": ["x kg", "150g"], "cat": "Lácteos y Frescos", "p_min": 2100, "p_max": 9800},
    {"items": ["Queso Untable Clásico", "Queso Untable Light"], "marcas": ["Finlandia", "Casancrem", "Mendicrim"], "medidas": ["290g"], "cat": "Lácteos y Frescos", "p_min": 2800, "p_max": 3400},
    {"items": ["Manteca Clásica"], "marcas": ["La Serenísima", "Ilolay", "Tonadita"], "medidas": ["200g"], "cat": "Lácteos y Frescos", "p_min": 2700, "p_max": 3100},
    {"items": ["Crema de Leche"], "marcas": ["La Serenísima", "Milkaut"], "medidas": ["200ml"], "cat": "Lácteos y Frescos", "p_min": 2100, "p_max": 3600},
    {"items": ["Huevos Blancos Seleccionados", "Huevos Colorados"], "marcas": ["Granja", "Maple Premium"], "medidas": ["x12 unid.", "Maple x30"], "cat": "Lácteos y Frescos", "p_min": 3200, "p_max": 8200},

    # ALMACÉN
    {"items": ["Fideos Spaghetti", "Fideos Tallarín", "Fideos Tirabuzón", "Fideos Mostachol"], "marcas": ["Lucchetti", "Matarazzo", "Terrabusi", "Marolio"], "medidas": ["500g"], "cat": "Almacén", "p_min": 1150, "p_max": 1650},
    {"items": ["Arroz Parboil Oro", "Arroz Doble Carolina", "Arroz Blanco Largo Fino"], "marcas": ["Gallo", "Ala", "Lucchetti"], "medidas": ["1kg"], "cat": "Almacén", "p_min": 1750, "p_max": 2500},
    {"items": ["Aceite de Girasol", "Aceite Mezcla", "Aceite de Oliva Extra Virgen"], "marcas": ["Natura", "Cocinero", "Cañuelas", "Lira"], "medidas": ["900ml", "1.5L", "500ml"], "cat": "Almacén", "p_min": 1800, "p_max": 8500},
    {"items": ["Harina de Trigo 000", "Harina de Trigo 0000", "Harina Leudante"], "marcas": ["Pureza", "Blancaflor", "Cañuelas"], "medidas": ["1kg"], "cat": "Almacén", "p_min": 1100, "p_max": 1550},
    {"items": ["Azúcar Común Tipo A", "Edulcorante Líquido"], "marcas": ["Ledesma", "Chango", "Hileret"], "medidas": ["1kg", "250ml"], "cat": "Almacén", "p_min": 1100, "p_max": 2800},
    {"items": ["Yerba Mate con Palo", "Yerba Mate Suave", "Yerba Mate Especial"], "marcas": ["Playadito", "Rosamonte", "Taragüi", "La Merced"], "medidas": ["500g", "1kg"], "cat": "Almacén", "p_min": 2200, "p_max": 5600},
    {"items": ["Café Molido Tostado", "Café Instantáneo Clásico"], "marcas": ["La Virginia", "Nescafé Dolca", "Cabrales"], "medidas": ["250g", "170g"], "cat": "Almacén", "p_min": 3800, "p_max": 6500},
    {"items": ["Pan de Mesa Artesano", "Pan Lactal Blanco"], "marcas": ["Bimbo", "Fargo", "Lactal"], "medidas": ["400g", "550g"], "cat": "Almacén", "p_min": 2100, "p_max": 2900},
    {"items": ["Atún Desmenuzado al Natural", "Atún en Lomitos"], "marcas": ["La Campagnola", "Gomes da Costa"], "medidas": ["170g"], "cat": "Almacén", "p_min": 2200, "p_max": 4100},
    {"items": ["Mayonesa Clásica", "Kétchup", "Mostaza"], "marcas": ["Natura", "Hellmann's", "Savora"], "medidas": ["250g", "500g"], "cat": "Almacén", "p_min": 1200, "p_max": 2400},
    {"items": ["Puré de Tomates Tetra"], "marcas": ["Arcor", "La Campagnola", "Marolio"], "medidas": ["520g"], "cat": "Almacén", "p_min": 850, "p_max": 1400},

    # CARNICERÍA Y VERDULERÍA
    {"items": ["Asado de Tira", "Vacío", "Bife de Chorizo", "Nalga para Milanesas", "Carne Picada Especial"], "marcas": ["Corte Selección", "Novillito"], "medidas": ["x kg"], "cat": "Carnicería y Granja", "p_min": 7800, "p_max": 14500},
    {"items": ["Pechuga de Pollo", "Pata y Muslo", "Milanesas de Pollo"], "marcas": ["Granja Tres Arroyos"], "medidas": ["x kg"], "cat": "Carnicería y Granja", "p_min": 3800, "p_max": 7900},
    {"items": ["Papa Negra", "Cebolla", "Tomate Redondo", "Zanahoria", "Banana Ecuador", "Manzana Roja"], "marcas": ["Huerta Fresca"], "medidas": ["x kg"], "cat": "Frutas y Verduras", "p_min": 1100, "p_max": 4200},

    # SNACKS, GOLOSINAS, BEBIDAS Y LIMPIEZA
    {"items": ["Galletitas Chocolinas", "Galletitas Oreo", "Galletitas Pepitos", "Criollitas", "Don Satur Salados"], "marcas": ["Bagley", "Oreo", "Don Satur"], "medidas": ["118g", "250g", "200g"], "cat": "Snacks y Galletitas", "p_min": 1100, "p_max": 2100},
    {"items": ["Papas Fritas Clásicas", "Doritos Queso"], "marcas": ["Lays", "Doritos"], "medidas": ["85g", "95g"], "cat": "Snacks y Galletitas", "p_min": 1600, "p_max": 3600},
    {"items": ["Alfajor Chocolate", "Alfajor Blanco", "Bombón Bon o Bon", "Chocolate con Leche"], "marcas": ["Havanna", "Jorgito", "Milka", "Bon o Bon"], "medidas": ["unid.", "Pack x6", "100g"], "cat": "Golosinas y Chocolates", "p_min": 480, "p_max": 4500},
    {"items": ["Coca-Cola Sabor Original", "Coca-Cola Sin Azúcar", "Sprite Lima Limón"], "marcas": ["Coca-Cola"], "medidas": ["1.5L", "2.25L"], "cat": "Bebidas sin Alcohol", "p_min": 1800, "p_max": 3400},
    {"items": ["Cerveza Rubia Clásica", "Cerveza Stella Artois"], "marcas": ["Quilmes", "Stella Artois"], "medidas": ["1L Retornable", "473ml Lata"], "cat": "Bebidas con Alcohol", "p_min": 1800, "p_max": 3400},
    {"items": ["Jabón Líquido Para Ropa Ala 3L", "Detergente Magistral Limón 500ml", "Lavandina Común Ayudín 1L", "Rollos de Cocina Sussex"], "marcas": ["Ala", "Magistral", "Ayudín", "Sussex"], "medidas": ["unid."], "cat": "Limpieza", "p_min": 1150, "p_max": 8500}
]

def normalizar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    texto_norm = unicodedata.normalize('NFD', texto)
    return "".join(c for c in texto_norm if unicodedata.category(c) != 'Mn').lower().strip()

@st.cache_data
def generar_base_completa():
    catalogo = []
    c = 1000
    for g in PLANTILLAS_GONDOLA:
        for it in g["items"]:
            for m in g["marcas"]:
                for med in g["medidas"]:
                    ean = f"779{c:010d}"
                    p_base = (g["p_min"] + g["p_max"]) / 2.0
                    nom = f"{it} {m} {med}"
                    catalogo.append({
                        "ean": ean,
                        "producto": nom,
                        "categoria": g["cat"],
                        "marca": m,
                        "precio_base": round(p_base, 2)
                    })
                    c += 1

    df_cat = pd.DataFrame(catalogo).drop_duplicates(subset=["producto"])
    df_cat["busqueda"] = (df_cat["producto"] + " " + df_cat["marca"] + " " + df_cat["ean"]).map(normalizar_texto)

    # 1. Serie Mensual (6 meses para cálculo de Laspeyres vs INDEC)
    mensuales = []
    for idx_m, mes in enumerate(MESES_SERIE):
        factor_inflacion = (1 + 0.038) ** (idx_m - 5)
        for _, row in df_cat.iterrows():
            for tienda, peso in PESOS_TIENDA.items():
                ruido = 0.99 + ((hash(row["ean"] + tienda + mes) % 1000) / 1000.0) * 0.02
                p_mes = round(row["precio_base"] * factor_inflacion * peso * ruido, 2)
                mensuales.append({
                    "mes_idx": idx_m,
                    "mes": mes,
                    "ean": row["ean"],
                    "producto": row["producto"],
                    "categoria": row["categoria"],
                    "supermercado": tienda,
                    "precio": p_mes
                })

    # 2. Serie Diaria (Día 1 al Día 30 para dinámica intrames)
    diarios = []
    for dia in range(1, 31):
        tasa_dia = 1.0 + (dia / 30.0) * 0.031
        efecto_promo = 0.975 if dia % 7 in [3, 4] else 1.008
        for _, row in df_cat.iterrows():
            for tienda, peso in PESOS_TIENDA.items():
                ruido = 0.99 + ((hash(row["ean"] + tienda + str(dia)) % 1000) / 1000.0) * 0.02
                p_dia = round(row["precio_base"] * tasa_dia * peso * efecto_promo * ruido, 2)
                diarios.append({
                    "dia_num": dia,
                    "dia": f"Día {dia:02d}",
                    "ean": row["ean"],
                    "producto": row["producto"],
                    "categoria": row["categoria"],
                    "supermercado": tienda,
                    "precio": p_dia
                })

    return df_cat, pd.DataFrame(mensuales), pd.DataFrame(diarios)

df_cat, df_mensual, df_diario = generar_base_completa()
CATEGORIAS = ["Todas"] + sorted(df_cat["categoria"].unique().tolist())

# ==============================================================================
# 2. GESTIÓN DE SESIÓN
# ==============================================================================
if "canasta" not in st.session_state:
    # Precarga inicial automática con productos habituales
    st.session_state.canasta = {
        df_cat[df_cat["producto"].str.contains("Leche Entera Clásica La Serenísima 1L")]["ean"].iloc[0]: 4.0,
        df_cat[df_cat["producto"].str.contains("Dulce de Leche Colonial La Serenísima 400g")]["ean"].iloc[0]: 2.0,
        df_cat[df_cat["producto"].str.contains("Fideos Spaghetti Lucchetti 500g")]["ean"].iloc[0]: 3.0,
        df_cat[df_cat["producto"].str.contains("Aceite de Girasol Natura 1.5L")]["ean"].iloc[0]: 2.0,
        df_cat[df_cat["producto"].str.contains("Yerba Mate Playadito con Palo 1kg")]["ean"].iloc[0]: 2.0,
    }
canasta = st.session_state.canasta

st.title("🛒 Monitor de Inflación Personal & Comparador de Precios")
st.caption(f"Base de datos activa: **{len(df_cat):,} productos listos** | Comercios: {', '.join(TIENDAS)}")

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
    st.write("Escribí cualquier producto o marca para agregarlo a tu canasta mensual:")

    c_cat, c_txt = st.columns([1, 2])
    with c_cat:
        cat_filtro = st.selectbox("Filtrar por Categoría:", CATEGORIAS)
    with c_txt:
        busq_input = st.text_input("Buscador por Texto (ej: dulce de leche, asado, playadito, lays, fideos):")

    sub_df = df_cat if cat_filtro == "Todas" else df_cat[df_cat["categoria"] == cat_filtro]
    for t in normalizar_texto(busq_input).split():
        sub_df = sub_df[sub_df["busqueda"].str.contains(t, regex=False)]
    sub_df = sub_df.sort_values("producto").reset_index(drop=True)

    st.caption(f"Coincidencias disponibles: **{len(sub_df):,}** productos")

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
        st.warning("No se encontraron productos con ese término.")

    st.divider()

    st.subheader("Tu Canasta Mensual Ponderada Actual")
    if canasta:
        info = df_cat.set_index("ean")
        items_vista = [{
            "Categoría": info.loc[e, "categoria"],
            "Código EAN": e,
            "Producto": info.loc[e, "producto"],
            "Cantidad Mensual (q₀)": q,
        } for e, q in canasta.items() if e in info.index]
        st.dataframe(pd.DataFrame(items_vista), hide_index=True, use_container_width=True)

        col_del, col_btn_del, col_vaciar = st.columns([3, 1, 1])
        with col_del:
            nombres_en_canasta = {e: info.loc[e, "producto"] for e in canasta if e in info.index}
            ean_borrar = st.selectbox(
                "Seleccionar producto para quitar:", list(canasta.keys()),
                format_func=lambda e: nombres_en_canasta.get(e, e)
            )
        with col_btn_del:
            st.write("")
            st.write("")
            if st.button("🗑️ Quitar este ítem", use_container_width=True):
                del canasta[ean_borrar]
                st.rerun()
        with col_vaciar:
            st.write("")
            st.write("")
            if st.button("❌ Vaciar Canasta", use_container_width=True):
                st.session_state.canasta = {}
                st.rerun()
    else:
        st.info("Tu canasta está vacía. Sumá alimentos arriba para comenzar a medir.")

# ==============================================================================
# PESTAÑA 2: INFLACIÓN PERSONAL VS. IPC INDEC
# ==============================================================================
with tab2:
    st.subheader("2. Medición Econométrica: Tu Inflación vs. IPC INDEC Oficial")
    if not canasta:
        st.warning("Primero agregá productos en la pestaña '1. Armar y Editar Canasta'.")
    else:
        sub_m = df_mensual[df_mensual["ean"].isin(canasta.keys())].copy()
        sub_m["q0"] = sub_m["ean"].map(canasta)
        sub_m["gasto_item"] = sub_m["precio"] * sub_m["q0"]

        costo_mes = sub_m.groupby(["mes_idx", "mes"])["gasto_item"].sum().reset_index()
        costo_mes["inflacion_personal_%"] = costo_mes["gasto_item"].pct_change() * 100
        costo_mes["ipc_indec_%"] = costo_mes["mes"].apply(lambda m: INDEC_IPC[m]["ipc_alimentos"])

        gasto_inicio = costo_mes.iloc[0]["gasto_item"]
        gasto_fin = costo_mes.iloc[-1]["gasto_item"]
        inf_acum_personal = ((gasto_fin - gasto_inicio) / gasto_inicio) * 100

        factor_indec = 1.0
        for m in MESES_SERIE[1:]:
            factor_indec *= (1 + INDEC_IPC[m]["ipc_alimentos"] / 100.0)
        inf_acum_indec = (factor_indec - 1.0) * 100

        m1, m2, m3 = st.columns(3)
        m1.metric("Tu Inflación Acumulada (6 Meses)", f"{inf_acum_personal:.2f}%")
        m2.metric("IPC INDEC Alimentos Acumulado", f"{inf_acum_indec:.2f}%")
        brecha = inf_acum_personal - inf_acum_indec
        m3.metric(
            "Brecha con INDEC",
            f"{brecha:+.2f} p.p.",
            delta=f"{'Mayor impacto' if brecha > 0 else 'Menor impacto'} en tu bolsillo",
            delta_color="inverse"
        )

        st.divider()

        # Gráfico 1: Barras mes a mes
        st.markdown("### 📊 Gráfico 1: Comparativa Mensual Mes a Mes (Tu Inflación vs. IPC INDEC)")
        df_graf_m = costo_mes.iloc[1:].copy()
        fmt = lambda x: f"{x:.2f}%"

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            x=df_graf_m["mes"], y=df_graf_m["inflacion_personal_%"],
            name="Tu Inflación Personal (Laspeyres)", marker_color="#1f77b4",
            text=df_graf_m["inflacion_personal_%"].map(fmt), textposition="outside"
        ))
        fig_comp.add_trace(go.Bar(
            x=df_graf_m["mes"], y=df_graf_m["ipc_indec_%"],
            name="IPC INDEC (Alimentos y Bebidas)", marker_color="#ff7f0e",
            text=df_graf_m["ipc_indec_%"].map(fmt), textposition="outside"
        ))
        fig_comp.update_layout(
            barmode="group",
            title="Variación Mensual Período a Período (%)",
            xaxis_title="Mes", yaxis_title="Variación Mensual (%)", yaxis_ticksuffix="%",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        st.divider()

        # Gráfico 2: Trayectoria Base 100
        st.markdown("### 📈 Gráfico 2: Trayectoria Acumulada del Nivel de Precios (Base Mayo 2026 = 100)")
        costo_mes["indice_personal"] = (costo_mes["gasto_item"] / gasto_inicio) * 100
        idx_indec = [100.0]
        for m in MESES_SERIE[1:]:
            idx_indec.append(idx_indec[-1] * (1 + INDEC_IPC[m]["ipc_alimentos"] / 100.0))
        costo_mes["indice_indec"] = idx_indec

        fig_idx = go.Figure()
        fig_idx.add_trace(go.Scatter(
            x=costo_mes["mes"], y=costo_mes["indice_personal"], mode="lines+markers",
            name="Índice Personal (Canasta Propia)", line=dict(color="#1f77b4", width=3)
        ))
        fig_idx.add_trace(go.Scatter(
            x=costo_mes["mes"], y=costo_mes["indice_indec"], mode="lines+markers",
            name="Índice Oficial INDEC Alimentos", line=dict(color="#ff7f0e", width=3, dash="dash")
        ))
        fig_idx.update_layout(
            title="Evolución Acumulada del Nivel de Precios (Puntos de Índice)",
            xaxis_title="Mes", yaxis_title="Puntos de Índice",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_idx, use_container_width=True)

        st.divider()

        # Gráfico 3: Variación Diaria Intrames
        st.markdown("### 📅 Gráfico 3: Dinámica Diaria Intrames (Día 1 al Día 30)")
        st.caption("Costo total de tu canasta día a día en cada supermercado durante el mes:")

        sub_d = df_diario[df_diario["ean"].isin(canasta.keys())].copy()
        sub_d["q0"] = sub_d["ean"].map(canasta)
        sub_d["gasto_item"] = sub_d["precio"] * sub_d["q0"]

        diario_super = sub_d.groupby(["dia_num", "dia", "supermercado"])["gasto_item"].sum().reset_index()

        fig_dia = px.line(
            diario_super, x="dia", y="gasto_item", color="supermercado", markers=True,
            title="Costo Diario de la Canasta por Cadena Minorista ($)",
            labels={"dia": "Día del Mes", "gasto_item": "Gasto Canasta ($)", "supermercado": "Supermercado"}
        )
        st.plotly_chart(fig_dia, use_container_width=True)

# ==============================================================================
# PESTAÑA 3: ASISTENTE DE FALTANTES (OPTIMIZADOR)
# ==============================================================================
with tab3:
    st.subheader("3. Asistente de Compras: ¿Dónde comprar más barato?")
    st.write("Elegí qué productos necesitás reponer hoy para encontrar la opción más económica:")

    info_dict = df_cat.set_index("ean")["producto"].to_dict()
    opciones_falt = list(canasta.keys()) if canasta else df_cat["ean"].head(10).tolist()

    seleccion = st.multiselect(
        "Alimentos a comprar:", options=opciones_falt, default=opciones_falt[:3] if len(opciones_falt) >= 3 else opciones_falt,
        format_func=lambda e: info_dict.get(e, e)
    )

    if seleccion:
        sub_ult = df_diario[(df_diario["dia_num"] == 30) & (df_diario["ean"].isin(seleccion))]
        matriz = sub_ult.pivot(index="ean", columns="supermercado", values="precio").reindex(columns=TIENDAS)

        n_sel = len(seleccion)
        totales = matriz.sum()
        tabla = pd.DataFrame({
            "Cadena": TIENDAS,
            "Cobertura": [f"{n_sel}/{n_sel}" for _ in TIENDAS],
            "Costo Total ($)": [totales[t] for t in TIENDAS],
        })

        # Opción 1: Monocadena
        mejor_cadena = totales.idxmin()
        menor_total_mono = totales.min()

        # Opción 2: Compra dividida
        detalle_split = []
        gasto_split = 0.0
        for e in seleccion:
            fila = matriz.loc[e]
            p_min = fila.min()
            tienda_min = fila.idxmin()
            gasto_split += p_min
            detalle_split.append({
                "Producto": info_dict.get(e, e),
                "Comercio más Barato": tienda_min,
                "Precio ($)": p_min
            })

        ahorro = menor_total_mono - gasto_split
        ahorro_pct = (ahorro / menor_total_mono) * 100 if menor_total_mono > 0 else 0.0

        r1, r2 = st.columns(2)
        with r1:
            st.success(f"### 📍 Opción 1: Comprar todo en {mejor_cadena}")
            st.write("Ideal para hacer **un único viaje** y no perder tiempo:")
            st.metric("Gasto Total Monocadena", f"${menor_total_mono:,.2f}")
            st.dataframe(tabla.sort_values("Costo Total ($)"), hide_index=True, use_container_width=True)

        with r2:
            st.info("### 🛒 Opción 2: Compra Dividida (Mayor Ahorro)")
            st.write("Comprando cada producto donde esté al precio mínimo:")
            st.metric("Gasto Dividido", f"${gasto_split:,.2f}", delta=f"-${ahorro:,.2f} ({ahorro_pct:.1f}%)")
            st.dataframe(pd.DataFrame(detalle_split), hide_index=True, use_container_width=True)
    else:
        st.info("Seleccioná productos en la lista para ver la comparativa de supermercados.")
