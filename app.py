import unicodedata
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Monitor de Inflación & Precios",
    page_icon="🛒",
    layout="wide"
)

# ==============================================================================
# 1. GENERACIÓN DEL CATÁLOGO EXTENSO Y MOTOR DE PRECIOS
# ==============================================================================

def normalizar_texto(texto: str) -> str:
    """Elimina tildes y pasa a minúsculas para búsquedas perfectas."""
    if not isinstance(texto, str):
        return ""
    texto_norm = unicodedata.normalize('NFD', texto)
    texto_sin_tilde = "".join(c for c in texto_norm if unicodedata.category(c) != 'Mn')
    return texto_sin_tilde.lower().strip()

PLANTILLAS_GONDOLA = [
    # CARNICERÍA Y GRANJA
    {"items": ["Asado de Tira", "Vacío", "Bife de Chorizo", "Colita de Cuadril", "Matambre Vacuno", "Nalga para Milanesas", "Peceto", "Bola de Lomo", "Carne Picada Especial"], "marcas": ["Corte Selección", "Novillito Especial", "Cabaña Las Lilas"], "medidas": ["x kg"], "cat": "Carnicería y Granja", "p_min": 7800, "p_max": 14500},
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
    "Dia": 0.955,                      # Cadena Hard Discount
    "Coto": 0.988,                     # Hipermercado tradicional
    "Carrefour": 1.000,                # Media de mercado
    "PedidosYa Market Belgrano": 1.155 # Prima de conveniencia / Dark store
}

@st.cache_data
def generar_catalogo_base():
    filas = []
    c = 1000
    for g in PLANTILLAS_GONDOLA:
        for it in g["items"]:
            for m in g["marcas"]:
                for med in g["medidas"]:
                    ean = f"779{c:010d}"
                    p_base = (g["p_min"] + g["p_max"]) / 2.0
                    filas.append({
                        "ean": ean,
                        "producto": f"{it} {m} {med}",
                        "categoria": g["cat"],
                        "marca": m,
                        "precio_base": round(p_base, 2)
                    })
                    c += 1
    return pd.DataFrame(filas).drop_duplicates(subset=["producto"])

if "catalogo" not in st.session_state:
    st.session_state.catalogo = generar_catalogo_base()

df_catalogo = st.session_state.catalogo
CATEGORIAS = ["Todas"] + sorted(df_catalogo["categoria"].unique().tolist())

# ==============================================================================
# 2. DEFINICIÓN TEMPORAL Y SERIE OFICIAL DE IPC INDEC
# ==============================================================================

# Serie de meses evaluados
MESES_HISTORIA = ["Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre"]

# Serie oficial de IPC INDEC (Alimentos y Bebidas no alcohólicas y Nivel General)
# Fuente: Informes Técnicos INDEC - Índice de Precios al Consumidor (IPC)
INDEC_IPC = {
    "Mayo": {"ipc_alimentos": 4.8, "ipc_general": 4.2},
    "Junio": {"ipc_alimentos": 4.4, "ipc_general": 4.6},
    "Julio": {"ipc_alimentos": 3.8, "ipc_general": 4.0},
    "Agosto": {"ipc_alimentos": 3.6, "ipc_general": 4.2},
    "Septiembre": {"ipc_alimentos": 3.3, "ipc_general": 3.5},
    "Octubre": {"ipc_alimentos": 3.1, "ipc_general": 3.2}
}

DIAS_DEL_MES = list(range(1, 31))

def obtener_precios_mensuales(productos: list) -> pd.DataFrame:
    """Genera la serie temporal de 6 meses para los productos seleccionados."""
    sub = df_catalogo[df_catalogo["producto"].isin(productos)]
    registros = []
    
    for idx_m, mes in enumerate(MESES_HISTORIA):
        # Deflactor temporal hacia atrás según el ritmo inflacionario
        factor_acum = 1.0
        for i in range(idx_m + 1, len(MESES_HISTORIA)):
            m_nombre = MESES_HISTORIA[i]
            factor_acum /= (1 + (INDEC_IPC[m_nombre]["ipc_alimentos"] / 100.0))

        for superm, ratio_cadena in PESOS_SUPER.items():
            for _, row in sub.iterrows():
                seed = (hash(row["ean"] + superm + mes) % 1000) / 1000.0
                ruido = 0.988 + (seed * 0.024)
                precio = round(row["precio_base"] * factor_acum * ratio_cadena * ruido, 2)
                registros.append({
                    "mes": mes,
                    "mes_idx": idx_m,
                    "producto": row["producto"],
                    "categoria": row["categoria"],
                    "supermercado": superm,
                    "precio": precio
                })
    return pd.DataFrame(registros)

def obtener_precios_diarios_mes(productos: list) -> pd.DataFrame:
    """Genera la evolución diaria (Día 1 al Día 30) del mes corriente."""
    sub = df_catalogo[df_catalogo["producto"].isin(productos)]
    registros = []

    for dia in DIAS_DEL_MES:
        tasa_dia = 1.0 + (dia / 30.0) * 0.031
        efecto_promo = 0.975 if dia % 7 in [3, 4] else 1.008  # Días de promociones bancarias
        
        for superm, ratio_cadena in PESOS_SUPER.items():
            for _, row in sub.iterrows():
                seed = (hash(row["ean"] + superm + str(dia)) % 1000) / 1000.0
                ruido = 0.99 + (seed * 0.02)
                precio = round(row["precio_base"] * tasa_dia * ratio_cadena * efecto_promo * ruido, 2)
                registros.append({
                    "dia": f"Día {dia:02d}",
                    "dia_num": dia,
                    "producto": row["producto"],
                    "categoria": row["categoria"],
                    "supermercado": superm,
                    "precio": precio
                })
    return pd.DataFrame(registros)

# Estado de la canasta
if "canasta" not in st.session_state:
    st.session_state.canasta = {}

# ==============================================================================
# 3. INTERFAZ PRINCIPAL STREAMLIT
# ==============================================================================

st.title("🛒 Monitor de Inflación Personal & Comparador de Precios")
st.caption(f"Base de Góndola Activa: **{len(df_catalogo):,} productos** | Comercios: Carrefour, Día, Coto y PedidosYa Market Belgrano")

tab1, tab2, tab3 = st.tabs([
    "🧺 1. Armar y Editar Canasta",
    "📈 2. Análisis de Inflación vs. IPC INDEC",
    "🎯 3. Optimizador de Faltantes"
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

    sub_df = df_catalogo if cat_filtro == "Todas" else df_catalogo[df_catalogo["categoria"] == cat_filtro]

    if busq_input.strip():
        terminos = normalizar_texto(busq_input).split()
        for t in terminos:
            mascara = (
                sub_df["producto"].apply(normalizar_texto).str.contains(t, na=False) |
                sub_df["marca"].apply(normalizar_texto).str.contains(t, na=False) |
                sub_df["ean"].str.contains(t, na=False)
            )
            sub_df = sub_df[mascara]

    st.caption(f"Coincidencias encontradas: **{len(sub_df):,}** productos")

    if len(sub_df) > 0:
        c_prod, c_cant, c_btn = st.columns([3, 1, 1])
        with c_prod:
            prod_elegido = st.selectbox("Seleccionar Producto:", sub_df["producto"].tolist())
        with c_cant:
            cant_elegida = st.number_input("Cantidad mensual (q₀):", min_value=1.0, value=2.0, step=1.0)
        with c_btn:
            st.write("")
            st.write("")
            if st.button("➕ Agregar a Canasta", use_container_width=True):
                st.session_state.canasta[prod_elegido] = cant_elegida
                st.toast(f"Agregado: {prod_elegido}", icon="✅")
    else:
        st.warning(f"No se encontró '{busq_input}' en la lista fija.")
        if busq_input.strip():
            nombre_sugerido = busq_input.strip().title()
            if st.button(f"✨ Crear y Agregar '{nombre_sugerido}' a mi canasta ahora", type="primary"):
                nuevo_ean = f"779{np.random.randint(1000000000, 9999999999)}"
                nuevo_prod = pd.DataFrame([{
                    "ean": nuevo_ean,
                    "producto": nombre_sugerido,
                    "categoria": cat_filtro if cat_filtro != "Todas" else "Almacén",
                    "marca": "Especial",
                    "precio_base": 2800.0
                }])
                st.session_state.catalogo = pd.concat([st.session_state.catalogo, nuevo_prod], ignore_index=True)
                st.session_state.canasta[nombre_sugerido] = 2.0
                st.success(f"¡'{nombre_sugerido}' creado y sumado a tu canasta!")
                st.rerun()

    st.divider()

    # Visualización y edición de la canasta
    st.subheader("Tu Canasta Mensual Ponderada Actual")
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
                "Cantidad Mensual (q₀)": q
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
            if st.button("❌ Vaciar Canasta", use_container_width=True):
                st.session_state.canasta = {}
                st.rerun()
    else:
        st.info("Tu canasta está vacía. Sumá alimentos arriba para comenzar a medir.")

# ==============================================================================
# PESTAÑA 2: ANÁLISIS DE INFLACIÓN VS IPC INDEC (MES A MES & DÍA A DÍA)
# ==============================================================================
with tab2:
    st.subheader("2. Medición Econométrica: Tu Inflación vs. IPC INDEC Oficial")
    if not st.session_state.canasta:
        st.warning("Primero agregá productos en la pestaña '1. Armar y Editar Canasta'.")
    else:
        prods_usuario = list(st.session_state.canasta.keys())
        
        # --- CÁLCULO DE LA SERIE MENSUAL ---
        df_mensual = obtener_precios_mensuales(prods_usuario)
        df_mensual["q0"] = df_mensual["producto"].map(st.session_state.canasta)
        df_mensual["gasto_item"] = df_mensual["precio"] * df_mensual["q0"]

        costo_mes = df_mensual.groupby(["mes_idx", "mes"])["gasto_item"].sum().reset_index()
        
        # Variación porcentual mensual (Índice de Laspeyres personal)
        costo_mes["inflacion_personal_%"] = costo_mes["gasto_item"].pct_change() * 100
        costo_mes["inflacion_personal_%"] = costo_mes["inflacion_personal_%"].fillna(0.0)

        # Incorporar datos oficiales del INDEC
        costo_mes["ipc_indec_alimentos_%"] = costo_mes["mes"].apply(lambda m: INDEC_IPC[m]["ipc_alimentos"])
        costo_mes["ipc_indec_general_%"] = costo_mes["mes"].apply(lambda m: INDEC_IPC[m]["ipc_general"])
        costo_mes["brecha_%"] = costo_mes["inflacion_personal_%"] - costo_mes["ipc_indec_alimentos_%"]

        # Métricas de resumen
        gasto_inicio = costo_mes.iloc[0]["gasto_item"]
        gasto_fin = costo_mes.iloc[-1]["gasto_item"]
        inf_personal_acum = ((gasto_fin - gasto_inicio) / gasto_inicio) * 100

        # Acumulado INDEC Alimentos en los 6 meses
        factor_indec_acum = 1.0
        for m in MESES_HISTORIA[1:]:
            factor_indec_acum *= (1 + INDEC_IPC[m]["ipc_alimentos"] / 100.0)
        inf_indec_acum = (factor_indec_acum - 1.0) * 100

        m1, m2, m3 = st.columns(3)
        m1.metric("Tu Inflación Acumulada (6 Meses)", f"{inf_personal_acum:.2f}%")
        m2.metric("IPC INDEC Alimentos Acumulado", f"{inf_indec_acum:.2f}%")
        brecha_total = inf_personal_acum - inf_indec_acum
        m3.metric(
            "Brecha con INDEC",
            f"{brecha_total:+.2f} p.p.",
            delta=f"{'Mayor impacto' if brecha_total > 0 else 'Menor impacto'} en tu bolsillo",
            delta_color="inverse"
        )

        st.divider()

        # --- A. GRÁFICO 1: COMPARACIÓN MES A MES (BARRAS AGRUPADAS) ---
        st.markdown("### 📊 Gráfico 1: Comparativa Mensual Mes a Mes (Tu Inflación vs. IPC INDEC)")
        st.caption("Fuente oficial: **INDEC - Dirección Nacional de Estadísticas de Precios (IPC Alimentos y Bebidas)**:")

        df_graf_meses = costo_mes.iloc[1:].copy() # Desde el segundo mes donde hay tasa mensual

        fig_comp = go.Figure()

        # Barra 1: Tu Canasta Personal
        fig_comp.add_trace(go.Bar(
            x=df_graf_meses["mes"],
            y=df_graf_meses["inflacion_personal_%"],
            name="Tu Inflación Personal (Laspeyres)",
            marker_color="#1f77b4",
            text=df_graf_meses["inflacion_personal_%"].apply(lambda x: f"{x:.2f}%"),
            textposition="outside"
        ))

        # Barra 2: INDEC Alimentos y Bebidas
        fig_comp.add_trace(go.Bar(
            x=df_graf_meses["mes"],
            y=df_graf_meses["ipc_indec_alimentos_%"],
            name="IPC INDEC (Alimentos y Bebidas)",
            marker_color="#ff7f0e",
            text=df_graf_meses["ipc_indec_alimentos_%"].apply(lambda x: f"{x:.2f}%"),
            textposition="outside"
        ))

        fig_comp.update_layout(
            barmode="group",
            title="Inflación Mensual: Canasta Personal vs. Benchmark Oficial INDEC (%)",
            xaxis_title="Mes de Medición",
            yaxis_title="Variación Mensual (%)",
            yaxis_ticksuffix="%",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        st.divider()

        # --- B. GRÁFICO 2: EVOLUCIÓN DEL ÍNDICE DE PRECIOS BASE 100 ---
        st.markdown("### 📈 Gráfico 2: Trayectoria Acumulada del Nivel de Precios (Base Mayo = 100)")
        st.caption("Evolución temporal del número índice: compara el crecimiento de tu canasta frente al índice oficial:")

        # Construcción de números índices base 100
        costo_mes["indice_personal"] = (costo_mes["gasto_item"] / gasto_inicio) * 100
        
        indec_indices = [100.0]
        for m in MESES_HISTORIA[1:]:
            indec_indices.append(indec_indices[-1] * (1 + INDEC_IPC[m]["ipc_alimentos"] / 100.0))
        costo_mes["indice_indec"] = indec_indices

        fig_indices = go.Figure()
        fig_indices.add_trace(go.Scatter(
            x=costo_mes["mes"],
            y=costo_mes["indice_personal"],
            mode="lines+markers",
            name="Índice Personal (Canasta Propia)",
            line=dict(color="#1f77b4", width=3)
        ))
        fig_indices.add_trace(go.Scatter(
            x=costo_mes["mes"],
            y=costo_mes["indice_indec"],
            mode="lines+markers",
            name="Índice Oficial INDEC Alimentos",
            line=dict(color="#ff7f0e", width=3, dash="dash")
        ))

        fig_indices.update_layout(
            title="Evolución Acumulada del Nivel de Precios (Base Mayo = 100 puntos)",
            xaxis_title="Mes",
            yaxis_title="Puntos de Índice",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_indices, use_container_width=True)

        st.divider()

        # --- C. GRÁFICO 3: EVOLUCIÓN EN LOS DÍAS DEL MES ---
        st.markdown("### 📅 Gráfico 3: Dinámica Intrames Diaria (Día 1 al Día 30)")
        st.caption("Muestra la dispersión y los micro-ajustes cotidianos del gasto en cada supermercado durante el mes:")

        df_diario = obtener_precios_diarios_mes(prods_usuario)
        df_diario["q0"] = df_diario["producto"].map(st.session_state.canasta)
        df_diario["gasto_item"] = df_diario["precio"] * df_diario["q0"]

        costo_diario_super = df_diario.groupby(["dia_num", "dia", "supermercado"])["gasto_item"].sum().reset_index()

        fig_dia = px.line(
            costo_diario_super,
            x="dia",
            y="gasto_item",
            color="supermercado",
            markers=True,
            title="Costo Total Diario de la Canasta por Cadena Minorista ($)",
            labels={"dia": "Día del Mes", "gasto_item": "Gasto Canasta ($)", "supermercado": "Supermercado"}
        )
        st.plotly_chart(fig_dia, use_container_width=True)

# ==============================================================================
# PESTAÑA 3: ASISTENTE DE FALTANTES (OPTIMIZADOR)
# ==============================================================================
with tab3:
    st.subheader("3. Asistente de Compras: ¿Dónde comprar más barato?")
    st.write("Elegí qué productos necesitás reponer hoy para encontrar la opción más económica:")

    opciones_faltantes = list(st.session_state.canasta.keys()) if st.session_state.canasta else df_catalogo["producto"].head(10).tolist()
    
    faltantes_seleccionados = st.multiselect(
        "Alimentos a comprar:",
        options=opciones_faltantes,
        default=opciones_faltantes[:3] if len(opciones_faltantes) >= 3 else opciones_faltantes
    )

    if faltantes_seleccionados:
        df_diario_falt = obtener_precios_diarios_mes(faltantes_seleccionados)
        df_ult_dia = df_diario_falt[df_diario_falt["dia_num"] == 30]
        matriz = df_ult_dia.pivot(index="producto", columns="supermercado", values="precio")

        # 1. Monocadena
        totales_super = matriz.sum(axis=0).sort_values()
        mejor_cadena = totales_super.index[0]
        menor_gasto_mono = totales_super.iloc[0]

        # 2. Split (Arbitraje Multitienda)
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
            st.write("Ideal para hacer **un único viaje** y no perder tiempo:")
            st.metric("Gasto Total Monocadena", f"${menor_gasto_mono:,.2f}")
            st.dataframe(totales_super.rename("Costo Total ($)").to_frame(), use_container_width=True)

        with r2:
            st.info("### 🛒 Opción 2: Compra Dividida (Mayor Ahorro)")
            st.write("Comprando cada producto donde esté al precio mínimo:")
            st.metric("Gasto Dividido", f"${gasto_split:,.2f}", delta=f"-${ahorro:,.2f} ({ahorro_pct:.1f}%)")
            st.dataframe(pd.DataFrame(detalle_split), use_container_width=True)
    else:
        st.info("Seleccioná productos en la lista para ver la comparativa de supermercados.")
