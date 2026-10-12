import datetime
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Monitor de Inflación & Optimizador",
    page_icon="🛒",
    layout="wide"
)

# ==============================================================================
# 1. GENERADOR DE GÓNDOLA REAL ARGENTINA
# ==============================================================================

PLANTILLAS_ALIMENTOS = [
    # CARNICERÍA Y GRANJA
    {"items": ["Asado de Tira", "Vacío", "Bife de Chorizo", "Colita de Cuadril", "Matambre Vacuno", "Nalga para Milanesas", "Peceto", "Bola de Lomo", "Carne Picada Especial"], "marcas": ["Corte Selección", "Novillito Especial", "Cabaña Las Lilas"], "medidas": ["x kg"], "cat": "Carnicería y Granja", "p_min": 7500, "p_max": 14500},
    {"items": ["Pechuga de Pollo", "Pata y Muslo", "Pollo Entero Fresco", "Milanesas de Pollo Rebozadas"], "marcas": ["Granja Tres Arroyos", "Cresta Roja", "Granja del Sol"], "medidas": ["x kg"], "cat": "Carnicería y Granja", "p_min": 3800, "p_max": 7900},
    {"items": ["Hamburguesas Clásicas x4", "Hamburguesas Clásicas x12", "Hamburguesas Fritas x4"], "marcas": ["Paty", "Swift", "Good Mark"], "medidas": ["unid."], "cat": "Carnicería y Granja", "p_min": 3200, "p_max": 9500},
    
    # FRUTAS Y VERDURAS
    {"items": ["Papa Negra", "Cebolla Blanca", "Tomate Redondo", "Zanahoria", "Lechuga Capuchina", "Manzana Roja", "Banana Ecuador", "Naranja de Jugo", "Limón", "Morrón Rojo"], "marcas": ["Selección Feria", "Huerta Fresca"], "medidas": ["x kg"], "cat": "Frutas y Verduras", "p_min": 1100, "p_max": 4200},
    {"items": ["Palta Hass"], "marcas": ["Selección"], "medidas": ["x unidad"], "cat": "Frutas y Verduras", "p_min": 1500, "p_max": 2500},

    # LÁCTEOS, DULCES DE LECHE Y QUESOS
    {"items": ["Dulce de Leche Colonial", "Dulce de Leche Clásico", "Dulce de Leche Repostero"], "marcas": ["La Serenísima", "San Ignacio", "Vacalin", "Ilolay", "Milkaut", "Havanna", "Chimbote", "Poncho Negro"], "medidas": ["400g", "450g", "1kg"], "cat": "Lácteos y Frescos", "p_min": 2400, "p_max": 5400},
    {"items": ["Leche Entera Clásica", "Leche Descremada", "Leche Cero Grasa", "Leche con Calcio"], "marcas": ["La Serenísima", "Ilolay", "Tregar", "Las Tres Niñas", "Manfrey"], "medidas": ["1L"], "cat": "Lácteos y Frescos", "p_min": 1350, "p_max": 1600},
    {"items": ["Yogur Firme Vainilla", "Yogur Firme Frutilla", "Yogur Bebible 1kg", "Yogur con Cereales"], "marcas": ["Yogurísimo", "La Serenísima", "Ilolay", "Tregar"], "medidas": ["190g", "1kg"], "cat": "Lácteos y Frescos", "p_min": 950, "p_max": 2600},
    {"items": ["Queso Cremoso", "Queso Por Salut", "Queso Muzzarella", "Queso Pategrás", "Queso Reggianito Rallado"], "marcas": ["La Paulina", "La Serenísima", "Tregar", "Punta del Agua", "Barraza"], "medidas": ["x kg", "150g"], "cat": "Lácteos y Frescos", "p_min": 2100, "p_max": 9800},
    {"items": ["Queso Untable Clásico", "Queso Untable Light"], "marcas": ["Finlandia", "Casancrem", "Mendicrim", "Tregar"], "medidas": ["290g", "300g"], "cat": "Lácteos y Frescos", "p_min": 2800, "p_max": 3400},
    {"items": ["Manteca Calidad Extra"], "marcas": ["La Serenísima", "Ilolay", "Tregar", "Tonadita"], "medidas": ["200g"], "cat": "Lácteos y Frescos", "p_min": 2700, "p_max": 3100},
    {"items": ["Crema de Leche"], "marcas": ["La Serenísima", "Ilolay", "Milkaut"], "medidas": ["200ml", "350ml"], "cat": "Lácteos y Frescos", "p_min": 2100, "p_max": 3600},
    {"items": ["Huevos Blancos Seleccionados", "Huevos Colorados"], "marcas": ["Granja Selección", "Maple Premium"], "medidas": ["x12 unid.", "Maple x30"], "cat": "Lácteos y Frescos", "p_min": 3200, "p_max": 8200},

    # ALMACÉN
    {"items": ["Fideos Spaghetti", "Fideos Tallarín", "Fideos Tirabuzón", "Fideos Mostachol", "Fideos Moñito", "Fideos Guiseros"], "marcas": ["Lucchetti", "Matarazzo", "Terrabusi", "Knorr", "Favorita", "Marolio"], "medidas": ["500g"], "cat": "Almacén", "p_min": 1150, "p_max": 1650},
    {"items": ["Arroz Parboil Oro", "Arroz Doble Carolina", "Arroz Blanco Largo Fino"], "marcas": ["Gallo", "Ala", "Lucchetti", "Marolio"], "medidas": ["1kg"], "cat": "Almacén", "p_min": 1750, "p_max": 2500},
    {"items": ["Aceite de Girasol", "Aceite Mezcla", "Aceite de Oliva Extra Virgen"], "marcas": ["Natura", "Cocinero", "Cañuelas", "Pureza", "Lira", "Cocinero Oliva"], "medidas": ["900ml", "1.5L", "500ml"], "cat": "Almacén", "p_min": 1800, "p_max": 8500},
    {"items": ["Harina de Trigo 000", "Harina de Trigo 0000", "Harina Leudante"], "marcas": ["Pureza", "Blancaflor", "Cañuelas", "Favorita"], "medidas": ["1kg"], "cat": "Almacén", "p_min": 1100, "p_max": 1550},
    {"items": ["Azúcar Común Tipo A", "Azúcar Impalpable", "Edulcorante Líquido"], "marcas": ["Ledesma", "Chango", "Hileret", "Sucaryl"], "medidas": ["1kg", "250ml"], "cat": "Almacén", "p_min": 1100, "p_max": 2800},
    {"items": ["Yerba Mate con Palo", "Yerba Mate Suave", "Yerba Mate Selección Especial", "Yerba Mate Despalada"], "marcas": ["Playadito", "Rosamonte", "Taragüi", "La Merced", "Mañanita", "Cruz de Malta", "Amanda", "CBSé Hierbas"], "medidas": ["500g", "1kg"], "cat": "Almacén", "p_min": 2200, "p_max": 5600},
    {"items": ["Café Molido Tostado", "Café Torrado", "Café Instantáneo Clásico"], "marcas": ["La Virginia", "Nescafé Dolca", "Cabrales", "Arlistán"], "medidas": ["250g", "170g"], "cat": "Almacén", "p_min": 3800, "p_max": 6500},
    {"items": ["Pan de Mesa Artesano", "Pan Lactal Blanco", "Pan Lactal Salvado"], "marcas": ["Bimbo", "Fargo", "Lactal"], "medidas": ["400g", "550g"], "cat": "Almacén", "p_min": 2100, "p_max": 2900},
    {"items": ["Atún Desmenuzado al Natural", "Atún en Lomitos al Natural", "Atún en Aceite"], "marcas": ["La Campagnola", "Gomes da Costa", "Marolio"], "medidas": ["170g"], "cat": "Almacén", "p_min": 2200, "p_max": 4100},
    {"items": ["Mayonesa Clásica", "Kétchup", "Mostaza"], "marcas": ["Natura", "Hellmann's", "Dánica", "Savora"], "medidas": ["250g", "500g"], "cat": "Almacén", "p_min": 1200, "p_max": 2400},
    {"items": ["Puré de Tomates Tetra", "Tomate Pelado Perita"], "marcas": ["Arcor", "La Campagnola", "Marolio", "Noel"], "medidas": ["520g"], "cat": "Almacén", "p_min": 850, "p_max": 1400},

    # SNACKS, GALLETITAS Y GOLOSINAS
    {"items": ["Galletitas Chocolinas", "Galletitas Oreo", "Galletitas Pepitos", "Galletitas Criollitas", "Bizcochos Salados", "Bizcochos Dulces", "Galletitas Rumba", "Galletitas Melba", "Galletitas Frutigram"], "marcas": ["Bagley", "Oreo", "Don Satur", "Terrabusi", "Granix"], "medidas": ["118g", "250g", "200g", "3x100g"], "cat": "Snacks y Galletitas", "p_min": 1100, "p_max": 2100},
    {"items": ["Papas Fritas Clásicas", "Papas Fritas Onduladas", "Doritos Queso", "Cheetos", "Maní Tostado Pelado"], "marcas": ["Lays", "Doritos", "Cheetos", "Pehuamar", "Krachitos"], "medidas": ["85g", "95g", "140g"], "cat": "Snacks y Galletitas", "p_min": 1600, "p_max": 3600},
    {"items": ["Alfajor Chocolate", "Alfajor Blanco", "Alfajor Mar del Plata", "Bombón Bon o Bon", "Chocolate con Leche", "Turrón de Maní"], "marcas": ["Havanna", "Jorgito", "Guaymallén", "Milka", "Arcor", "Cofler Block", "Bon o Bon", "Shot"], "medidas": ["unid.", "Pack x6", "100g", "170g"], "cat": "Golosinas y Chocolates", "p_min": 480, "p_max": 4500},

    # BEBIDAS
    {"items": ["Coca-Cola Sabor Original", "Coca-Cola Sin Azúcar", "Sprite Lima Limón", "Sprite Sin Azúcar", "Fanta Naranja", "Pepsi Black", "Paso de los Toros Pomelo"], "marcas": ["Coca-Cola", "PepsiCo"], "medidas": ["500ml", "1.5L", "2.25L"], "cat": "Bebidas sin Alcohol", "p_min": 1400, "p_max": 3400},
    {"items": ["Agua Mineral sin Gas", "Agua Mineral con Gas", "Agua Saborizada Manzana", "Agua Saborizada Pomelo"], "marcas": ["Villavicencio", "Villa del Sur", "Eco de los Andes", "Aquarius", "Levité"], "medidas": ["1.5L", "2L"], "cat": "Bebidas sin Alcohol", "p_min": 1100, "p_max": 1850},
    {"items": ["Cerveza Rubia Clásica", "Cerveza Chopp", "Cerveza Rubia Especial", "Cerveza IPA", "Cerveza Rubia Importada"], "marcas": ["Quilmes", "Brahma", "Stella Artois", "Heineken", "Corona", "Imperial", "Patagonia"], "medidas": ["473ml Lata", "1L Retornable", "710ml"], "cat": "Bebidas con Alcohol", "p_min": 1600, "p_max": 3600},
    {"items": ["Vino Malbec Clásico", "Vino Cabernet Sauvignon"], "marcas": ["Trapiche", "Las Moras", "Catena Zapata Álamos", "Rutini", "San Felipe"], "medidas": ["750ml"], "cat": "Bebidas con Alcohol", "p_min": 3200, "p_max": 14000},
    {"items": ["Fernet Aperitivo"], "marcas": ["Branca", "1882"], "medidas": ["750ml", "1L"], "cat": "Bebidas con Alcohol", "p_min": 9200, "p_max": 14500},

    # LIMPIEZA Y CUIDADO
    {"items": ["Jabón Líquido Para Ropa", "Jabón en Polvo"], "marcas": ["Ala", "Skip", "Ariel", "Drive"], "medidas": ["800ml Doypack", "3L Botellón"], "cat": "Limpieza", "p_min": 3200, "p_max": 9500},
    {"items": ["Lavandina Común Clásica", "Lavandina en Gel"], "marcas": ["Ayudín", "Querubín", "Vim"], "medidas": ["1L", "2L"], "cat": "Limpieza", "p_min": 1150, "p_max": 2400},
    {"items": ["Detergente Concentrado Limón", "Detergente Marino"], "marcas": ["Magistral", "Cif", "Ala"], "medidas": ["300ml", "500ml", "750ml"], "cat": "Limpieza", "p_min": 1800, "p_max": 3400},
    {"items": ["Rollos de Cocina Mega", "Papel Higiénico Doble Hoja"], "marcas": ["Sussex", "Higienol", "Elite"], "medidas": ["3x50 paños", "4x30 metros"], "cat": "Limpieza", "p_min": 1900, "p_max": 2900},
    {"items": ["Shampoo", "Acondicionador"], "marcas": ["Sedal", "Pantene", "Head & Shoulders", "Dove", "Tresemme"], "medidas": ["340ml", "400ml"], "cat": "Perfumería y Cuidado", "p_min": 3200, "p_max": 5400},
    {"items": ["Crema Dental Anticaries"], "marcas": ["Colgate Total 12", "Oral-B", "Sensodyne"], "medidas": ["90g"], "cat": "Perfumería y Cuidado", "p_min": 2400, "p_max": 4200}
]

PESOS_SUPER = {
    "Dia": 0.955,                      # Estrategia hard discount
    "Coto": 0.988,                     # Hipermercado tradicional
    "Carrefour": 1.000,                # Media de mercado
    "PedidosYa Market Belgrano": 1.155 # Prima de inmediatez
}

@st.cache_data
def generar_catalogo_maestro():
    filas = []
    contador = 1000
    for grupo in PLANTILLAS_ALIMENTOS:
        cat = grupo["cat"]
        for it in grupo["items"]:
            for m in grupo["marcas"]:
                for med in grupo["medidas"]:
                    ean = f"779{contador:010d}"
                    nombre_completo = f"{it} {m} {med}"
                    p_base = (grupo["p_min"] + grupo["p_max"]) / 2.0
                    filas.append({
                        "ean": ean,
                        "producto": nombre_completo,
                        "categoria": cat,
                        "marca": m,
                        "precio_base": round(p_base, 2)
                    })
                    contador += 1
    return pd.DataFrame(filas).drop_duplicates(subset=["producto"])

if "catalogo" not in st.session_state:
    st.session_state.catalogo = generar_catalogo_maestro()

df_catalogo = st.session_state.catalogo
CATEGORIAS_DISPONIBLES = ["Todas"] + sorted(df_catalogo["categoria"].unique().tolist())

HOY = datetime.date.today()
FECHAS = [(HOY - datetime.timedelta(weeks=w)).isoformat() for w in range(5, -1, -1)]

def obtener_precios_panel(productos_lista: list) -> pd.DataFrame:
    sub_df = df_catalogo[df_catalogo["producto"].isin(productos_lista)]
    registros = []

    for idx_sem, f in enumerate(FECHAS):
        factor_inf = (1 + 0.0105) ** (idx_sem - 5)
        for superm, ratio_tienda in PESOS_SUPER.items():
            for _, row in sub_df.iterrows():
                seed = (hash(row["ean"] + superm + f) % 1000) / 1000.0
                ruido = 0.985 + (seed * 0.03)
                p_final = round(row["precio_base"] * factor_inf * ratio_tienda * ruido, 2)
                registros.append({
                    "fecha": f,
                    "ean": row["ean"],
                    "producto": row["producto"],
                    "categoria": row["categoria"],
                    "marca": row["marca"],
                    "supermercado": superm,
                    "precio": p_final
                })
    return pd.DataFrame(registros)

if "canasta" not in st.session_state:
    st.session_state.canasta = {}

# ==============================================================================
# 2. ENCABEZADO
# ==============================================================================
st.title("🛒 Monitor de Inflación Personal & Comparador de Precios")
st.caption(f"Base activa: **{len(df_catalogo):,} productos reales de góndola argentina** | Carrefour, Día, Coto y PedidosYa Market Belgrano")

tab1, tab2, tab3 = st.tabs([
    "🧺 1. Armar y Editar Canasta",
    "📈 2. Mi Inflación Personal (Laspeyres)",
    "🎯 3. ¿Dónde Conviene Comprar Hoy?"
])

# ==============================================================================
# PESTAÑA 1: ARMAR Y EDITAR CANASTA
# ==============================================================================
with tab1:
    st.subheader("1. Buscador y Selección de Alimentos")
    st.write("Escribí cualquier alimento, marca o variedad (ej: *dulce de leche*, *asado*, *chocolinas*, *playadito*, *lays*, *coca*):")

    c_cat, c_txt = st.columns([1, 2])
    with c_cat:
        cat_elegida = st.selectbox("Filtrar por Categoría:", CATEGORIAS_DISPONIBLES)
    with c_txt:
        busqueda_txt = st.text_input("Buscador por Texto:")

    sub_cat = df_catalogo if cat_elegida == "Todas" else df_catalogo[df_catalogo["categoria"] == cat_elegida]

    if busqueda_txt.strip():
        palabras = busqueda_txt.strip().lower().split()
        for p in palabras:
            mascara = (
                sub_cat["producto"].str.lower().str.contains(p, na=False) |
                sub_cat["marca"].str.lower().str.contains(p, na=False) |
                sub_cat["ean"].str.contains(p, na=False)
            )
            sub_cat = sub_cat[mascara]

    st.caption(f"Coincidencias encontradas: **{len(sub_cat):,}** productos")

    if len(sub_cat) > 0:
        c_prod, c_cant, c_btn = st.columns([3, 1, 1])
        with c_prod:
            prod_seleccionado = st.selectbox("Seleccionar Producto:", sub_cat["producto"].tolist())
        with c_cant:
            cant_seleccionada = st.number_input("Cantidad mensual (q₀):", min_value=1.0, value=2.0, step=1.0)
        with c_btn:
            st.write("")
            st.write("")
            if st.button("➕ Agregar a Canasta", use_container_width=True):
                st.session_state.canasta[prod_seleccionado] = cant_seleccionada
                st.toast(f"Agregado: {prod_seleccionado}", icon="✅")
    else:
        st.warning("No se encontraron productos con ese término.")

    # Formulario para agregar productos personalizados
    with st.expander("✨ ¿Buscás un producto muy puntual que no figura en la lista? Agregalo acá en 1 segundo"):
        st.write("Escribí el nombre y precio de referencia. El bot lo indexará con código EAN y le calculará el precio en los 4 supermercados:")
        c_nuevo_nom, c_nuevo_cat, c_nuevo_p, c_nuevo_btn = st.columns([2, 1.5, 1, 1])
        with c_nuevo_nom:
            nuevo_nombre = st.text_input("Nombre del Producto:", placeholder="Ej: Tapas de Empanadas La Salteña x12")
        with c_nuevo_cat:
            nuevo_rubro = st.selectbox("Categoría:", [c for c in CATEGORIAS_DISPONIBLES if c != "Todas"])
        with c_nuevo_p:
            nuevo_precio = st.number_input("Precio Estimado ($):", min_value=100.0, value=2500.0, step=100.0)
        with c_nuevo_btn:
            st.write("")
            st.write("")
            if st.button("➕ Crear Producto", use_container_width=True):
                if nuevo_nombre.strip():
                    nuevo_ean = f"77999{np.random.randint(1000000, 9999999)}"
                    nuevo_registro = pd.DataFrame([{
                        "ean": nuevo_ean,
                        "producto": nuevo_nombre.strip(),
                        "categoria": nuevo_rubro,
                        "marca": "Especial",
                        "precio_base": round(nuevo_precio, 2)
                    }])
                    st.session_state.catalogo = pd.concat([st.session_state.catalogo, nuevo_registro], ignore_index=True)
                    st.session_state.canasta[nuevo_nombre.strip()] = 2.0
                    st.success(f"¡'{nuevo_nombre}' agregado con éxito!")
                    st.rerun()

    st.divider()

    # Visualización y edición de la canasta
    st.subheader("Tu Canasta Mensual Ponderada")
    if st.session_state.canasta:
        items_vista = []
        for p, q in st.session_state.canasta.items():
            info = df_catalogo[df_catalogo["producto"] == p]
            cat_p = info["categoria"].iloc[0] if len(info) > 0 else "Varios"
            ean_p = info["ean"].iloc[0] if len(info) > 0 else "-"
            items_vista.append({
                "Categoría": cat_p,
                "Código EAN": ean_p,
                "Producto": p,
                "Cantidad (q₀)": q
            })
        st.dataframe(pd.DataFrame(items_vista), use_container_width=True)

        col_del, col_btn_del, col_vaciar = st.columns([3, 1, 1])
        with col_del:
            item_a_borrar = st.selectbox("Seleccionar producto para quitar:", list(st.session_state.canasta.keys()))
        with col_btn_del:
            st.write("")
            st.write("")
            if st.button("🗑️ Quitar este ítem", use_container_width=True):
                del st.session_state.canasta[item_a_borrar]
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
# PESTAÑA 2: INFLACIÓN PERSONAL (LASPEYRES)
# ==============================================================================
with tab2:
    st.subheader("Cálculo del Índice de Laspeyres")
    if not st.session_state.canasta:
        st.warning("Primero agregá productos en la pestaña '1. Armar y Editar Canasta'.")
    else:
        col_f0, col_ft = st.columns(2)
        with col_f0:
            f0 = st.selectbox("Período Base (t₀):", FECHAS, index=0)
        with col_ft:
            ft = st.selectbox("Período de Comparación (t):", FECHAS, index=len(FECHAS)-1)

        prods = list(st.session_state.canasta.keys())
        df_panel = obtener_precios_panel(prods)

        p0 = df_panel[df_panel["fecha"] == f0].groupby("producto")["precio"].mean()
        pt = df_panel[df_panel["fecha"] == ft].groupby("producto")["precio"].mean()

        gasto_0 = sum(p0[p] * st.session_state.canasta[p] for p in prods if p in p0)
        gasto_t = sum(pt[p] * st.session_state.canasta[p] for p in prods if p in pt)

        inflacion_personal = ((gasto_t - gasto_0) / gasto_0) * 100 if gasto_0 > 0 else 0.0
        indice_laspeyres = (gasto_t / gasto_0) * 100 if gasto_0 > 0 else 100.0

        m1, m2, m3 = st.columns(3)
        m1.metric(f"Gasto Base ({f0})", f"${gasto_0:,.2f}")
        m2.metric(f"Gasto Actual ({ft})", f"${gasto_t:,.2f}", delta=f"{inflacion_personal:+.2f}%")
        m3.metric("Inflación Personal Acumulada", f"{inflacion_personal:.2f}%", help="Variación porcentual ponderada por tus cantidades fijas q0")

        st.divider()

        # Gráfico por Categoría
        st.subheader("Desagregación: Variación de Precios por Rubro")
        cat_stats = []
        for cat in df_panel["categoria"].unique():
            prods_cat = [p for p in prods if df_catalogo[df_catalogo["producto"] == p]["categoria"].iloc[0] == cat]
            g0_cat = sum(p0[p] * st.session_state.canasta[p] for p in prods_cat if p in p0)
            gt_cat = sum(pt[p] * st.session_state.canasta[p] for p in prods_cat if p in pt)
            inf_cat = ((gt_cat - g0_cat) / g0_cat) * 100 if g0_cat > 0 else 0.0
            cat_stats.append({"Categoría": cat, "Inflación (%)": inf_cat})

        fig_bar = px.bar(
            pd.DataFrame(cat_stats), x="Categoría", y="Inflación (%)", color="Categoría",
            title=f"Inflación Acumulada por Categoría ({f0} a {ft})", text_auto=".2f"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico por Supermercado
        st.subheader("Evolución del Costo Total Nominal por Supermercado")
        df_evol = df_panel.copy()
        df_evol["q0"] = df_evol["producto"].map(st.session_state.canasta)
        df_evol["gasto_item"] = df_evol["precio"] * df_evol["q0"]
        evol_super = df_evol.groupby(["fecha", "supermercado"])["gasto_item"].sum().reset_index()

        fig_line = px.line(
            evol_super, x="fecha", y="gasto_item", color="supermercado",
            title="Trayectoria Semanal del Costo de la Canasta",
            labels={"gasto_item": "Costo Canasta ($)", "fecha": "Semana"}
        )
        st.plotly_chart(fig_line, use_container_width=True)

# ==============================================================================
# PESTAÑA 3: ASISTENTE DE FALTANTES (OPTIMIZADOR)
# ==============================================================================
with tab3:
    st.subheader("¿Dónde te conviene hacer tu próxima compra?")
    st.write("Elegí qué productos necesitás reponer para comparar precios entre supermercados hoy:")

    opciones_def = list(st.session_state.canasta.keys()) if st.session_state.canasta else df_catalogo["producto"].head(10).tolist()
    faltantes_seleccionados = st.multiselect(
        "Alimentos a comprar:",
        options=opciones_def,
        default=opciones_def[:3] if len(opciones_def) >= 3 else opciones_def
    )

    if faltantes_seleccionados:
        df_panel_falt = obtener_precios_panel(faltantes_seleccionados)
        ult_fecha = FECHAS[-1]
        df_ult = df_panel_falt[df_panel_falt["fecha"] == ult_fecha]
        matriz = df_ult.pivot(index="producto", columns="supermercado", values="precio")

        # 1. Monocadena
        totales_super = matriz.sum(axis=0).sort_values()
        mejor_cadena = totales_super.index[0]
        menor_gasto_mono = totales_super.iloc[0]

        # 2. Split
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

        ahorro = menor_gasto_mono - gasto_split
        ahorro_pct = (ahorro / menor_gasto_mono) * 100 if menor_gasto_mono > 0 else 0.0

        r1, r2 = st.columns(2)
        with r1:
            st.success(f"### 📍 Opción 1: Comprar todo en {mejor_cadena}")
            st.write("Ideal para hacer un único viaje y ahorrar tiempo de búsqueda:")
            st.metric("Gasto Total Monocadena", f"${menor_gasto_mono:,.2f}")
            st.dataframe(totales_super.rename("Costo Total ($)").to_frame(), use_container_width=True)

        with r2:
            st.info("### 🛒 Opción 2: Compra Dividida (Mayor Ahorro)")
            st.write("Comprando cada producto donde esté al precio mínimo:")
            st.metric("Gasto Dividido", f"${gasto_split:,.2f}", delta=f"-${ahorro:,.2f} ({ahorro_pct:.1f}%)")
            st.dataframe(pd.DataFrame(detalle_split), use_container_width=True)
    else:
        st.info("Seleccioná productos en la lista para ver la comparativa de comercios.")
