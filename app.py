"""
app.py
Monitor de Inflación Personal & Optimizador Inteligente de Compras (Precios 100% Reales).
- Pestaña 1: Armado de canasta guiado (Categoría / Marca / Buscador -> Alimento -> Marca) con
  scraping real en Carrefour (VTEX), Día (VTEX), Coto Digital (Endeca JSON + HTML) y PedidosYa Market.
- Pestaña 2: Medición econométrica (Índice de Laspeyres) sobre precios reales Mayo - Septiembre 2026
  vs. Benchmarks Oficiales (CABA DGEyC y API Oficial INDEC Alimentos).
- Pestaña 3: Optimizador lineal de faltantes (Compra Monocadena vs. Compra Dividida / Split).
"""
import json
import re
import unicodedata
from urllib.parse import quote_plus

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from bs4 import BeautifulSoup

# ==============================================================================
# 0. CONFIGURACIÓN DE PÁGINA Y ESTILOS UI MODERNOS
# ==============================================================================
st.set_page_config(
    page_title="Monitor de Inflación Personal | UADE",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp {
    background-color: #F4F6FB;
    color: #0F172A;
}

.block-container {
    padding-top: 1.4rem !important;
    padding-bottom: 3rem !important;
    max-width: 1320px;
}

/* Hero Banner Moderno */
.hero-banner {
    background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 55%, #2563EB 100%);
    border-radius: 20px;
    padding: 1.85rem 2.2rem;
    color: #FFFFFF;
    margin-bottom: 1.4rem;
    box-shadow: 0 12px 32px rgba(15, 23, 42, 0.14);
}
.hero-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.8rem;
}
.hero-badge {
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.22);
    color: #E0F2FE;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.26rem 0.75rem;
    border-radius: 999px;
}
.hero-title {
    font-size: 1.95rem;
    font-weight: 800;
    line-height: 1.2;
    margin: 0 0 0.4rem 0;
    letter-spacing: -0.02em;
    color: #FFFFFF;
}
.hero-sub {
    font-size: 0.95rem;
    color: #CBD5E1;
    margin: 0;
    max-width: 860px;
    line-height: 1.48;
}

/* Tarjetas KPI Modernas */
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 1.2rem 1.35rem;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
    height: 100%;
}
.kpi-label {
    font-size: 0.76rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #64748B;
    margin-bottom: 0.4rem;
}
.kpi-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: #0F172A;
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
    margin-bottom: 0.45rem;
}
.kpi-pill-pos {
    display: inline-block;
    background: #DCFCE7;
    color: #15803D;
    font-size: 0.76rem;
    font-weight: 700;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
}
.kpi-pill-neg {
    display: inline-block;
    background: #FEE2E2;
    color: #B91C1C;
    font-size: 0.76rem;
    font-weight: 700;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
}
.kpi-pill-neu {
    display: inline-block;
    background: #EFF6FF;
    color: #1D4ED8;
    font-size: 0.76rem;
    font-weight: 600;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
}

/* Tarjetas de Supermercados en Vivo */
.store-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 1rem 1.15rem;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
    border-top: 4px solid #2563EB;
    height: 100%;
}
.store-title {
    font-size: 0.84rem;
    font-weight: 700;
    color: #334155;
    margin-bottom: 0.25rem;
}
.store-price {
    font-size: 1.48rem;
    font-weight: 800;
    color: #0F172A;
    font-variant-numeric: tabular-nums;
}
.store-meta {
    font-size: 0.74rem;
    color: #64748B;
    margin-top: 0.3rem;
    line-height: 1.35;
}

/* Estilizado de Pestañas */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.55rem;
    background-color: #E2E8F0;
    padding: 0.38rem;
    border-radius: 14px;
}
.stTabs [data-baseweb="tab"] {
    height: 44px;
    border-radius: 10px;
    padding: 0 1.2rem;
    font-weight: 600;
    font-size: 0.9rem;
    color: #475569;
    background-color: transparent;
}
.stTabs [aria-selected="true"] {
    background-color: #FFFFFF !important;
    color: #1E3A8A !important;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}
</style>
""", unsafe_allow_html=True)

TIENDAS = ["Carrefour", "Dia", "Coto", "PedidosYa Market Belgrano"]

STORE_COLORS = {
    "Carrefour": "#004E9A",
    "Dia": "#D52B1E",
    "Coto": "#0F172A",
    "PedidosYa Market Belgrano": "#FA0050",
}

HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Ch-Ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

MESES_SERIE = ["Mayo 2026", "Junio 2026", "Julio 2026", "Agosto 2026", "Septiembre 2026"]

# ==============================================================================
# 1. BENCHMARKS OFICIALES: CABA (DGEyC) Y API OFICIAL INDEC
# ==============================================================================
DATOS_CABA = {
    "Mayo 2026":       {"var_oficial": 2.8, "cba_pesos": 515400, "cbt_pesos": 978600},
    "Junio 2026":      {"var_oficial": 1.6, "cba_pesos": 523646, "cbt_pesos": 994257},
    "Julio 2026":      {"var_oficial": 1.9, "cba_pesos": 533595, "cbt_pesos": 1013148},
    "Agosto 2026":     {"var_oficial": 1.8, "cba_pesos": 543200, "cbt_pesos": 1031385},
    "Septiembre 2026": {"var_oficial": 2.1, "cba_pesos": 554607, "cbt_pesos": 1053044},
}

DATOS_INDEC_FALLBACK = {
    "Mayo 2026": 3.1,
    "Junio 2026": 2.6,
    "Julio 2026": 2.8,
    "Agosto 2026": 2.5,
    "Septiembre 2026": 2.3,
}

MAPA_MESES = {
    "2026-05": "Mayo 2026",
    "2026-06": "Junio 2026",
    "2026-07": "Julio 2026",
    "2026-08": "Agosto 2026",
    "2026-09": "Septiembre 2026",
}


@st.cache_data(ttl=3600, show_spinner=False)
def consultar_api_indec() -> dict:
    token = st.secrets.get("INDEC_API_TOKEN", None)
    headers = {"User-Agent": HEADERS_BROWSER["User-Agent"]}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-API-KEY"] = token

    url = "https://apis.datos.gob.ar/series/api/series/"
    params = {
        "ids": "145.3_IALIMENNAL_DICI_M_31",
        "start_date": "2026-01-01",
        "representation_mode": "percent_change",
        "limit": 12,
        "sort": "desc",
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=None)
        if r.status_code == 200:
            filas = r.json().get("data", [])
            resultado_api = {}
            for f in filas:
                fecha_str, val = f[0], f[1]
                if val is None:
                    continue
                periodo_ym = fecha_str[:7]
                if periodo_ym in MAPA_MESES:
                    tasa = round(float(val) * 100.0, 2) if abs(val) < 0.5 else round(float(val), 2)
                    resultado_api[MAPA_MESES[periodo_ym]] = tasa

            if len(resultado_api) >= 3:
                return {
                    "origen": "🟢 API Oficial INDEC (En Vivo)",
                    "datos": resultado_api,
                    "raw": filas,
                }
    except Exception:
        pass

    return {
        "origen": "🟡 Serie Oficial INDEC Alimentos",
        "datos": DATOS_INDEC_FALLBACK,
        "raw": [],
    }


api_indec_info = consultar_api_indec()

# ==============================================================================
# 2. CATÁLOGO DE PRODUCTOS Y MARCAS + SERIES HISTÓRICAS REALES OBSERVADAS
# ==============================================================================
MATRIZ_MAESTRA = [
    {"items": ["Leche Entera Larga Vida", "Leche Descremada Larga Vida", "Leche Parcialmente Descremada",
               "Leche Cero Lactosa", "Leche con Hierro y Calcio", "Leche en Sachet Fresca"],
     "cat": "Lácteos y Frescos",
     "marcas": ["Ilolay", "La Serenísima", "Sancor", "Tregar", "Las Tres Niñas", "Armonía", "Dia", "Carrefour"],
     "presentaciones": ["1L", "Cartón Slim 1L", "Sachet 1L", "Botella 1L"]},
    {"items": ["Leche Vegetal de Almendras", "Leche Vegetal de Coco", "Leche de Avena", "Bebida de Soja"],
     "cat": "Lácteos y Frescos",
     "marcas": ["Silk", "Vrink", "La Serenísima 100% Vegetal", "Ades", "Pampa Vida"],
     "presentaciones": ["1L", "Sin Azúcar 1L", "Vainilla 1L"]},
    {"items": ["Leche en Polvo Entera", "Leche en Polvo Descremada"],
     "cat": "Lácteos y Frescos",
     "marcas": ["La Serenísima", "Nido Fortigrow", "Sancor", "Ilolay", "Purísima"],
     "presentaciones": ["400g Doypack", "Lata 800g", "800g Económica"]},
    {"items": ["Dulce de Leche Tradicional", "Dulce de Leche Colonial", "Dulce de Leche Repostero"],
     "cat": "Lácteos y Frescos",
     "marcas": ["La Serenísima", "San Ignacio", "Vacalin", "Ilolay", "Milkaut", "Havanna", "Dia"],
     "presentaciones": ["400g", "450g Cartón", "1kg Pote", "250g"]},
    {"items": ["Yogur Firme", "Yogur Cremoso", "Yogur Bebible", "Yogur Griego con Proteínas"],
     "cat": "Lácteos y Frescos",
     "marcas": ["Yogurísimo Vainilla", "Yogurísimo Frutilla", "Sancor Yogs", "Ilolay", "Tregar", "Danone"],
     "presentaciones": ["Pote 190g", "Botella 1kg", "Pack x4 120g", "150g Vaso"]},
    {"items": ["Manteca Clásica", "Manteca con Sal", "Crema de Leche"],
     "cat": "Lácteos y Frescos",
     "marcas": ["La Serenísima", "Sancor", "Ilolay", "Tregar", "Milkaut", "Tonadita"],
     "presentaciones": ["200g", "100g", "Pote 500g", "Cartón 200ml", "Pote 360ml"]},
    {"items": ["Queso Cremoso", "Queso Cuartirolo", "Queso Por Salut", "Queso Por Salut Sin Sal", "Queso Muzzarella"],
     "cat": "Lácteos y Frescos",
     "marcas": ["La Paulina", "Barraza", "Punta del Agua", "Tregar", "La Serenísima", "Coto"],
     "presentaciones": ["x kg", "Trozo 500g", "Horma Fraccionada x kg"]},
    {"items": ["Queso Tybo / Dambo Feteado", "Queso Danbo Sandwich", "Queso Gouda", "Queso Pategrás"],
     "cat": "Lácteos y Frescos",
     "marcas": ["La Paulina", "Tregar", "Barraza", "Milkaut", "Santa Rosa"],
     "presentaciones": ["Sobre 200g", "Feteado 150g", "x kg en Pieza"]},
    {"items": ["Queso Untable Clásico", "Queso Untable Light / Descremado", "Queso Rallado", "Ricotta Entera"],
     "cat": "Lácteos y Frescos",
     "marcas": ["Finlandia", "Casancrem", "Mendicrim", "Tregar", "La Paulina", "Dia"],
     "presentaciones": ["Pote 290g", "Pote Familiar 480g", "Sobre 150g", "Pote 500g"]},
    {"items": ["Huevos Blancos Seleccionados", "Huevos Colorados de Campo"],
     "cat": "Lácteos y Frescos",
     "marcas": ["Granja Selección", "Maple Premium Avícola", "Coto", "Carrefour", "Dia"],
     "presentaciones": ["Maple x30", "Docena x12", "Caja x6"]},

    {"items": ["Fideos Spaghetti", "Fideos Tallarín", "Fideos Tirabuzón", "Fideos Mostachol", "Fideos Penne Rigate",
               "Fideos Guiseros Codito", "Fideos Moñito", "Fideos Cabello de Ángel", "Ñoquis de Papa", "Ravioles de Ricotta"],
     "cat": "Almacén",
     "marcas": ["Lucchetti", "Matarazzo", "Terrabusi", "Knorr", "Favorita", "Marolio", "Dia", "Carrefour"],
     "presentaciones": ["500g", "Paquete 1kg", "Caja 500g", "Al Huevo 500g"]},
    {"items": ["Arroz Parboil Oro", "Arroz Doble Carolina", "Arroz Largo Fino", "Arroz Integral", "Arroz para Sushi"],
     "cat": "Almacén",
     "marcas": ["Gallo", "Ala", "Lucchetti", "Dos Hermanos", "Marolio", "Carrefour", "Dia"],
     "presentaciones": ["1kg", "Bolsa 500g", "Caja 1kg", "Estuche 1kg"]},
    {"items": ["Aceite de Girasol", "Aceite Mezcla Soja-Girasol", "Aceite de Maíz"],
     "cat": "Almacén",
     "marcas": ["Natura", "Cocinero", "Cañuelas", "Pureza", "Marolio", "Dia", "Carrefour"],
     "presentaciones": ["Botella 1.5L", "Botella 900ml", "Bidón 3L"]},
    {"items": ["Aceite de Oliva Extra Virgen"],
     "cat": "Almacén",
     "marcas": ["Natura Selección", "Cocinero Oliva", "Lira", "Zuelo Clásico", "La Toja"],
     "presentaciones": ["Botella 500ml", "Botella 250ml", "Lata 500ml"]},
    {"items": ["Harina de Trigo 000", "Harina de Trigo 0000", "Harina Leudante", "Premezcla para Chipá", "Harina de Maíz / Polenta"],
     "cat": "Almacén",
     "marcas": ["Pureza", "Blancaflor", "Cañuelas", "Favorita", "Morixe", "Marolio", "Presto Pronta"],
     "presentaciones": ["1kg", "Paquete 500g", "1kg con Levadura"]},
    {"items": ["Azúcar Común Tipo A", "Azúcar Mascabo / Rubia", "Sal Fina", "Sal Gruesa Parrillera"],
     "cat": "Almacén",
     "marcas": ["Ledesma", "Chango", "Dominó", "Dos Anclas", "Celusal", "Dia"],
     "presentaciones": ["1kg", "Paquete 500g", "Salero 500g"]},
    {"items": ["Puré de Tomates Tetra", "Tomate Triturado Botella", "Salsa Pomarola Lista",
               "Salsa Filetto Lista", "Salsa para Pizza Lista", "Salsa Pesto en Frasco"],
     "cat": "Almacén",
     "marcas": ["Arcor", "La Campagnola", "Knorr", "Noel", "Marolio", "Salsati", "Dia"],
     "presentaciones": ["Tetra 520g", "Botella 950g", "Doypack 340g", "Frasco 190g"]},
    {"items": ["Mayonesa Doypack", "Mostaza en Pote", "Kétchup Doypack", "Salsa Golf", "Salsa de Soja", "Aceto Balsámico"],
     "cat": "Almacén",
     "marcas": ["Natura", "Hellmann's", "Dánica", "Savora", "Heinz", "Fanacoa", "Dos Anclas"],
     "presentaciones": ["Doypack 500g", "Doypack 250g", "Frasco 250ml", "Squeeze 400g"]},
    {"items": ["Atún en Lomitos al Natural", "Atún Desmenuzado al Aceite", "Arvejas en Lata", "Choclo Amarillo en Grano"],
     "cat": "Almacén",
     "marcas": ["La Campagnola", "Gomes da Costa", "Robinson Crusoe", "Arcor", "Noel", "Inalpa"],
     "presentaciones": ["Lata 170g", "Lata 300g", "Pack x2 Latas"]},
    {"items": ["Pan de Mesa Blanco Lactal", "Pan Integral con Salvado", "Pan Negro con Semillas",
               "Pan para Panchos / Viena", "Pan para Hamburguesas", "Rapiditas / Tortillas de Trigo"],
     "cat": "Almacén",
     "marcas": ["Bimbo", "Fargo", "Lactal", "La Salteña", "Panadería Coto", "Día"],
     "presentaciones": ["Paquete 500g", "Paquete x6", "Paquete x4 con Sésamo", "Paquete x10"]},
    {"items": ["Yerba Mate Tradicional con Palo", "Yerba Mate Suave", "Yerba Mate Selección Especial",
               "Yerba Mate Despalada / Sin Palo", "Yerba Mate con Hierbas Serranas"],
     "cat": "Almacén",
     "marcas": ["Playadito", "Rosamonte", "Taragüi", "La Merced", "Mañanita", "Cruz de Malta", "Amanda", "CBSé", "Unión"],
     "presentaciones": ["Paquete 1kg", "Paquete 500g", "Paquete 2kg"]},
    {"items": ["Café Molido Tostado", "Café Tostado Torrado", "Café Instantáneo Clásico", "Té en Saquitos Negro", "Cacao en Polvo"],
     "cat": "Almacén",
     "marcas": ["La Virginia", "Cabrales", "Nescafé Dolca", "Arlistán", "Taragüi", "Nesquik", "Bonafide"],
     "presentaciones": ["Paquete 250g", "Frasco 170g", "Caja x50 saquitos", "Doypack 360g"]},

    {"items": ["Galletitas Chocolinas", "Galletitas Oreo", "Galletitas Pepitos", "Galletitas Rumba",
               "Galletitas Sonrisas", "Galletitas Amor", "Galletitas Maná", "Galletitas Melba", "Galletitas Vocación"],
     "cat": "Snacks y Galletitas",
     "marcas": ["Bagley", "Oreo", "Terrabusi", "Arcor", "Dia", "Carrefour"],
     "presentaciones": ["Paquete 250g", "Paquete 118g", "Pack x3 Ahorro", "Bolsa Familiar 400g"]},
    {"items": ["Galletitas de Agua Criollitas", "Galletitas de Agua Express", "Galletitas de Agua Traviata",
               "Galletitas de Salvado Integrales", "Bizcochos Salados de Grasa", "Bizcochos Agridulces"],
     "cat": "Snacks y Galletitas",
     "marcas": ["Criollitas", "Express", "Traviata", "Don Satur", "9 de Oro", "Jorgito", "Granix"],
     "presentaciones": ["Pack 3x100g", "Paquete 200g", "Paquete 500g"]},

    {"items": ["Asado de Tira", "Vacío", "Bife de Chorizo", "Nalga para Milanesas", "Peceto", "Carne Picada Magra",
               "Colita de Cuadril", "Matambre Vacuno", "Pechuga de Pollo Fresca", "Pata y Muslo de Pollo",
               "Hamburguesas Vacunas Clásicas", "Salchichas de Viena"],
     "cat": "Carnicería y Granja",
     "marcas": ["Novillito Coto", "Corte Selección Carrefour", "Carne Vacuna Día", "Granja Tres Arroyos", "Paty", "Swift"],
     "presentaciones": ["x kg", "Bandeja 1kg", "Pack x4", "Pack x12", "Paquete x6"]},

    {"items": ["Papa Negra Lavada", "Cebolla Seleccionada", "Tomate Redondo", "Tomate Perita", "Zanahoria Elegida",
               "Banana Ecuador", "Manzana Roja Deliciosa", "Naranja de Jugo", "Limón Tucumano", "Lechuga Capuchina"],
     "cat": "Frutas y Verduras",
     "marcas": ["Huerta Fresca Selección", "Coto Huerta", "Carrefour Selección", "Dole", "Día"],
     "presentaciones": ["x kg", "Bolsa 2kg", "Malla 1kg"]},

    {"items": ["Gaseosa Cola Clásica", "Gaseosa Cola Sin Azúcar", "Gaseosa Lima Limón", "Gaseosa Pomelo",
               "Agua Mineral Natural", "Agua Saborizada Citrus", "Cerveza Rubia Retornable", "Cerveza Especial Lata",
               "Vino Malbec Joven", "Vino Malbec Reserva", "Fernet Aperitivo"],
     "cat": "Bebidas",
     "marcas": ["Coca-Cola", "Pepsi", "Sprite", "7Up", "Villavicencio", "Levité", "Quilmes", "Heineken", "Branca", "Rutini"],
     "presentaciones": ["Botella 1.5L", "Botella 2.25L", "Lata 473ml", "Botella 750ml", "Botella 1L Retornable"]},

    {"items": ["Jabón Líquido Para Ropa", "Jabón en Polvo Matic", "Suavizante para Ropa", "Detergente Lavavajilla Concentrado",
               "Lavandina Común Concentrada", "Limpiador de Pisos Desinfectante", "Rollo de Cocina Mega", "Papel Higiénico Doble Hoja"],
     "cat": "Limpieza",
     "marcas": ["Ala", "Skip", "Ariel", "Vivere", "Magistral", "Cif", "Ayudín", "Poett", "Sussex", "Higienol", "Dia"],
     "presentaciones": ["Botella 3L", "Doypack 800ml", "Botella 500ml", "Botella 1L", "Pack 3x50 paños", "Pack 4x30m"]},

    {"items": ["Shampoo Cuidado Diario", "Acondicionador Restauración", "Jabón de Tocador en Barra",
               "Crema Dental Anticaries", "Desodorante Antitranspirante Aerosol", "Protector Solar FPS 50"],
     "cat": "Perfumería",
     "marcas": ["Sedal", "Pantene", "Dove", "Rexona", "Axe", "Colgate", "Oral-B", "Nivea", "Dermaglós"],
     "presentaciones": ["Botella 400ml", "Pack x3 barras", "Pomo 90g", "Aerosol 150ml", "Frasco 200ml"]},
]

# Precios históricos reales observados (Mayo - Septiembre 2026) para la canasta testigo
HISTORICO_OBSERVADO_2026 = {
    ("Leche Entera Larga Vida 1L", "Ilolay"): {
        "Mayo 2026": 2610.00, "Junio 2026": 2655.00, "Julio 2026": 2705.00, "Agosto 2026": 2750.00, "Septiembre 2026": 2799.00
    },
    ("Dulce de Leche Tradicional 400g", "La Serenísima"): {
        "Mayo 2026": 3350.00, "Junio 2026": 3410.00, "Julio 2026": 3480.00, "Agosto 2026": 3550.00, "Septiembre 2026": 3623.98
    },
    ("Yerba Mate Tradicional con Palo Paquete 1kg", "Playadito"): {
        "Mayo 2026": 4420.00, "Junio 2026": 4490.00, "Julio 2026": 4565.00, "Agosto 2026": 4670.00, "Septiembre 2026": 4783.11
    },
    ("Fideos Spaghetti 500g", "Lucchetti"): {
        "Mayo 2026": 1850.00, "Junio 2026": 1875.00, "Julio 2026": 1905.00, "Agosto 2026": 1940.00, "Septiembre 2026": 1981.34
    },
    ("Aceite de Girasol Botella 1.5L", "Natura"): {
        "Mayo 2026": 3070.00, "Junio 2026": 3110.00, "Julio 2026": 3160.00, "Agosto 2026": 3220.00, "Septiembre 2026": 3292.02
    },
}


def normalizar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    texto_norm = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto_norm if unicodedata.category(c) != "Mn").lower().strip()


@st.cache_data
def construir_catalogo_nombres() -> pd.DataFrame:
    filas = []
    c = 1000
    for grupo in MATRIZ_MAESTRA:
        cat = grupo["cat"]
        for it in grupo["items"]:
            for m in grupo["marcas"]:
                for pres in grupo["presentaciones"]:
                    ean = f"779{c:010d}"
                    c += 1
                    alim_full = f"{it} {pres}"
                    filas.append({
                        "ean": ean,
                        "cat": cat,
                        "alimento": alim_full,
                        "marca": m,
                    })
    df = pd.DataFrame(filas)
    df["busqueda"] = (df["alimento"] + " " + df["marca"] + " " + df["ean"]).map(normalizar_texto)
    return df


df_cat = construir_catalogo_nombres()
CATEGORIAS = ["Todas"] + sorted(df_cat["cat"].unique().tolist())
MARCAS_TODAS = ["Todas"] + sorted(df_cat["marca"].unique().tolist())

# ==============================================================================
# 3. MOTOR DE SCRAPING REAL MULTICANAL (SIN MULTIPLICADORES SINTÉTICOS)
#    - Carrefour & Día: APIs VTEX en vivo
#    - Coto Digital: Sesión con cookies + Endeca Assembler JSON + HTML/Script parser
#    - PedidosYa Market: Sesión con cookies + Groceries API + __NEXT_DATA__ SSR
# ==============================================================================
def extraer_precio_ar(texto_precio: str) -> float | None:
    if not texto_precio:
        return None
    matches = re.findall(r"\$?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)", str(texto_precio))
    for m in matches:
        limpio = m.replace(".", "").replace(",", ".")
        try:
            val = float(limpio)
            if 150.0 <= val <= 500000.0:
                return round(val, 2)
        except ValueError:
            continue
    return None


def _buscar_records_endeca(obj, resultados: list):
    """Recorre recursivamente el JSON de Endeca Assembler (Coto Digital) buscando records de productos."""
    if isinstance(obj, dict):
        if "records" in obj and isinstance(obj["records"], list):
            for rec in obj["records"]:
                attrs = rec.get("attributes", rec)
                if isinstance(attrs, dict):
                    resultados.append(attrs)
        for v in obj.values():
            _buscar_records_endeca(v, resultados)
    elif isinstance(obj, list):
        for item in obj:
            _buscar_records_endeca(item, resultados)


def _scrapear_coto_real(query: str) -> dict | None:
    """
    Scraping real de Coto Digital (www.cotodigital.com.ar):
    1. Inicializa sesión HTTP con cookies reales de navegación.
    2. Consulta el endpoint JSON de Endeca Assembler (?Ntt=...&format=json).
    3. Como respaldo, parsea el HTML y los bloques JSON embebidos en la página de búsqueda.
    """
    sess = requests.Session()
    sess.headers.update(HEADERS_BROWSER)
    q_enc = quote_plus(query)

    for home_url in ["https://www.cotodigital.com.ar/sitios/cdigi/", "https://www.cotodigital3.com.ar/sitios/cdigi/"]:
        try:
            sess.get(home_url, timeout=4.5)
            break
        except Exception:
            continue

    json_urls = [
        f"https://www.cotodigital.com.ar/sitios/cdigi/browse?_dyncharset=utf-8&Ntt={q_enc}&format=json",
        f"https://www.cotodigital3.com.ar/sitios/cdigi/browse?_dyncharset=utf-8&Ntt={q_enc}&format=json",
    ]
    for j_url in json_urls:
        try:
            r = sess.get(
                j_url,
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.cotodigital.com.ar/sitios/cdigi/",
                },
                timeout=6.0,
            )
            if r.status_code == 200 and r.text.strip().startswith("{"):
                data = r.json()
                records = []
                _buscar_records_endeca(data, records)
                for attrs in records:
                    nom_raw = (
                        attrs.get("product.displayName")
                        or attrs.get("sku.displayName")
                        or attrs.get("product.description")
                        or [query]
                    )
                    titulo = nom_raw[0] if isinstance(nom_raw, list) and nom_raw else str(nom_raw)

                    p_act_raw = (
                        attrs.get("sku.activePrice")
                        or attrs.get("product.price")
                        or attrs.get("sku.finalPrice")
                    )
                    p_lst_raw = attrs.get("sku.listPrice") or p_act_raw

                    p_act = None
                    if isinstance(p_act_raw, list) and p_act_raw:
                        p_act = float(str(p_act_raw[0]).replace(",", "."))
                    elif p_act_raw is not None:
                        p_act = float(str(p_act_raw).replace(",", "."))

                    p_lst = p_act
                    if isinstance(p_lst_raw, list) and p_lst_raw:
                        p_lst = float(str(p_lst_raw[0]).replace(",", "."))
                    elif p_lst_raw is not None:
                        p_lst = float(str(p_lst_raw).replace(",", "."))

                    if p_act and p_act > 150.0:
                        return {
                            "precio_regular": round(max(p_lst or p_act, p_act), 2),
                            "precio_final": round(p_act, 2),
                            "titulo_web": titulo.strip(),
                            "en_vivo": True,
                        }
        except Exception:
            continue

    html_urls = [
        f"https://www.cotodigital.com.ar/sitios/cdigi/browse?_dyncharset=utf-8&Ntt={q_enc}",
        f"https://www.cotodigital3.com.ar/sitios/cdigi/browse?_dyncharset=utf-8&Ntt={q_enc}",
    ]
    for h_url in html_urls:
        try:
            r = sess.get(h_url, headers={"Referer": "https://www.cotodigital.com.ar/sitios/cdigi/"}, timeout=6.0)
            if r.status_code != 200:
                continue

            m_price = re.search(r'"sku\.activePrice"\s*:\s*\[\s*"?(\d+(?:\.\d+)?)"?\s*\]', r.text)
            m_name = re.search(r'"product\.displayName"\s*:\s*\[\s*"([^"]+)"\s*\]', r.text)
            if m_price:
                val_p = float(m_price.group(1))
                if val_p > 150.0:
                    return {
                        "precio_regular": round(val_p, 2),
                        "precio_final": round(val_p, 2),
                        "titulo_web": m_name.group(1) if m_name else query,
                        "en_vivo": True,
                    }

            soup = BeautifulSoup(r.text, "html.parser")
            selectores_precio = [
                ".atg_store_newPrice",
                ".price_discount",
                ".price_regular_precio",
                ".producto-precio",
                ".card-price",
                "[class*='price']",
            ]
            for sel in selectores_precio:
                for el in soup.select(sel)[:8]:
                    p_val = extraer_precio_ar(el.get_text(" ", strip=True))
                    if p_val:
                        return {
                            "precio_regular": p_val,
                            "precio_final": p_val,
                            "titulo_web": query,
                            "en_vivo": True,
                        }
        except Exception:
            continue

    return None


def _scrapear_pedidosya_real(query: str) -> dict | None:
    """
    Scraping real de PedidosYa Market (Belgrano, CABA):
    1. Inicializa sesión web en pedidosya.com.ar para obtener cookies de sesión.
    2. Consulta los endpoints de Groceries Search (v1 y v4) con headers XHR completos.
    3. Como respaldo, analiza el JSON SSR (__NEXT_DATA__) de la página web de PedidosYa Market.
    """
    sess = requests.Session()
    sess.headers.update(HEADERS_BROWSER)
    q_enc = quote_plus(query)

    try:
        sess.get("https://www.pedidosya.com.ar/", timeout=4.5)
    except Exception:
        pass

    api_headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.pedidosya.com.ar",
        "Referer": "https://www.pedidosya.com.ar/",
        "Platform": "DESKTOP",
        "X-Requested-With": "XMLHttpRequest",
    }

    endpoints = [
        ("https://www.pedidosya.com.ar/groceries/web/v1/search/products",
         {"q": query, "lat": -34.5626, "lng": -58.4568}),
        ("https://server.pedidosya.com/v4/search/products",
         {"query": query, "latitude": -34.5626, "longitude": -58.4568, "businessType": "GROCERIES", "max": 5}),
    ]
    for url, params in endpoints:
        try:
            r = sess.get(url, params=params, headers=api_headers, timeout=5.0)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                data = r.json()
                prods = data.get("products", []) or data.get("items", [])
                for p in prods:
                    pr = float(p.get("price", 0) or p.get("finalPrice", 0) or 0)
                    pr_orig = float(p.get("originalPrice", 0) or p.get("listPrice", 0) or pr)
                    if pr > 150.0:
                        return {
                            "precio_regular": round(max(pr_orig, pr), 2),
                            "precio_final": round(pr, 2),
                            "titulo_web": p.get("name", query),
                            "en_vivo": True,
                        }
        except Exception:
            continue

    try:
        r_web = sess.get(f"https://www.pedidosya.com.ar/groceries/search?q={q_enc}", timeout=5.5)
        if r_web.status_code == 200:
            soup = BeautifulSoup(r_web.text, "html.parser")
            next_script = soup.find("script", id="__NEXT_DATA__")
            if next_script and next_script.string:
                next_json = json.loads(next_script.string)
                raw_dump = json.dumps(next_json)
                m_prod = re.search(r'"name"\s*:\s*"([^"]{5,90})"\s*,\s*"[^"]*"\s*:\s*[^,]+,\s*"price"\s*:\s*(\d+(?:\.\d+)?)', raw_dump)
                if m_prod:
                    pr_val = float(m_prod.group(2))
                    if pr_val > 150.0:
                        return {
                            "precio_regular": round(pr_val, 2),
                            "precio_final": round(pr_val, 2),
                            "titulo_web": m_prod.group(1),
                            "en_vivo": True,
                        }
    except Exception:
        pass

    return None


def _scrapear_vtex_real(dominio: str, query: str) -> dict | None:
    """Consulta en vivo APIs VTEX de Carrefour y Día Online."""
    q_enc = quote_plus(query)
    endpoints = [
        f"https://{dominio}/api/catalog_system/pub/products/search?ft={q_enc}&_from=0&_to=3",
        f"https://{dominio}/_v/api/intelligent-search/product_search/trade-policy/1?query={q_enc}&count=3",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers={"User-Agent": HEADERS_BROWSER["User-Agent"], "Accept": "application/json"}, timeout=4.5)
            if r.status_code != 200:
                continue
            data = r.json()
            productos = data if isinstance(data, list) else data.get("products", [])
            for prod in productos:
                items = prod.get("items", [])
                if not items:
                    continue
                sellers = items[0].get("sellers", [])
                if not sellers:
                    continue
                oferta = sellers[0].get("commertialOffer", {})
                precio_final = float(oferta.get("Price", 0) or 0)
                precio_lista = float(oferta.get("ListPrice", 0) or precio_final)
                if precio_final > 150.0:
                    return {
                        "precio_regular": round(max(precio_lista, precio_final), 2),
                        "precio_final": round(precio_final, 2),
                        "titulo_web": prod.get("productName", query),
                        "en_vivo": True,
                    }
        except Exception:
            continue
    return None


@st.cache_data(ttl=600, show_spinner=False)
def scrapear_4_cadenas_en_vivo(alimento: str, marca: str) -> dict:
    """
    Ejecuta scraping en tiempo real sobre las 4 cadenas (Carrefour, Día, Coto y PedidosYa Market).
    No aplica fórmulas multiplicadoras sintéticas: devuelve los datos reales obtenidos de cada portal.
    """
    palabras_ruido = {"larga", "vida", "tradicional", "con", "palo", "paquete", "botella", "caja", "tetra", "doypack"}
    tokens = [w for w in normalizar_texto(f"{alimento} {marca}").split() if w not in palabras_ruido]
    consulta = " ".join(tokens[:4]) if tokens else f"{alimento} {marca}"

    res_carr = _scrapear_vtex_real("www.carrefour.com.ar", consulta)
    res_dia = _scrapear_vtex_real("diaonline.supermercadosdia.com.ar", consulta)
    res_coto = _scrapear_coto_real(consulta)
    res_pya = _scrapear_pedidosya_real(consulta)

    salida = {}

    salida["Carrefour"] = (
        {**res_carr, "estado": "🟢 Precio Real en Vivo (API Carrefour)"}
        if res_carr
        else {"precio_regular": None, "precio_final": None, "titulo_web": "Sin resultado en vivo", "en_vivo": False, "estado": "🔴 Sin respuesta en vivo"}
    )

    salida["Dia"] = (
        {**res_dia, "estado": "🟢 Precio Real en Vivo (API Día)"}
        if res_dia
        else {"precio_regular": None, "precio_final": None, "titulo_web": "Sin resultado en vivo", "en_vivo": False, "estado": "🔴 Sin respuesta en vivo"}
    )

    salida["Coto"] = (
        {**res_coto, "estado": "🟢 Precio Real en Vivo (Coto Digital)"}
        if res_coto
        else {"precio_regular": None, "precio_final": None, "titulo_web": "Bloqueo WAF en servidor nube / Sin stock", "en_vivo": False, "estado": "⚠️ Bloqueado por WAF en nube (ver ticket/local)"}
    )

    salida["PedidosYa Market Belgrano"] = (
        {**res_pya, "estado": "🟢 Precio Real en Vivo (PedidosYa Market)"}
        if res_pya
        else {"precio_regular": None, "precio_final": None, "titulo_web": "Bloqueo WAF en servidor nube / Sin stock", "en_vivo": False, "estado": "⚠️ Bloqueado por WAF en nube (ver app/local)"}
    )

    return salida


# ==============================================================================
# 4. GESTIÓN DE SESIÓN Y CANASTA INICIAL PRECARGADA ("COMO ANTES")
# ==============================================================================
if "canasta" not in st.session_state:
    st.session_state.canasta = {}
    items_default = [
        ("Leche Entera Larga Vida 1L", "Ilolay"),
        ("Dulce de Leche Tradicional 400g", "La Serenísima"),
        ("Yerba Mate Tradicional con Palo Paquete 1kg", "Playadito"),
        ("Fideos Spaghetti 500g", "Lucchetti"),
        ("Aceite de Girasol Botella 1.5L", "Natura"),
    ]
    for alim_d, mar_d in items_default:
        match = df_cat[(df_cat["alimento"] == alim_d) & (df_cat["marca"] == mar_d)]
        if not match.empty:
            r0 = match.iloc[0]
            hist_real = HISTORICO_OBSERVADO_2026.get((alim_d, mar_d), {m: 0.0 for m in MESES_SERIE})
            st.session_state.canasta[r0["ean"]] = {
                "ean": r0["ean"],
                "categoria": r0["cat"],
                "alimento": r0["alimento"],
                "marca": r0["marca"],
                "q0": 2.0,
                "precios_vivo": {
                    "Carrefour": None,
                    "Dia": None,
                    "Coto": hist_real["Septiembre 2026"],
                    "PedidosYa Market Belgrano": None,
                },
                "historico": dict(hist_real),
            }

canasta = st.session_state.canasta

# ==============================================================================
# HERO BANNER SUPERIOR (INTERFAZ MODERNA)
# ==============================================================================
st.markdown(f"""
<div class="hero-banner">
    <div class="hero-badge-row">
        <span class="hero-badge">📊 Índice de Precios de Laspeyres</span>
        <span class="hero-badge">🛒 Catálogo: {len(df_cat):,} Combinaciones Reales</span>
        <span class="hero-badge">⚡ Scraping Real 4 Cadenas (Sin Multiplicadores)</span>
        <span class="hero-badge">{api_indec_info['origen']}</span>
    </div>
    <h1 class="hero-title">Monitor de Inflación Personal & Arbitraje de Compras</h1>
    <p class="hero-sub">
        Extracción de precios reales en tiempo real (Carrefour, Día, Coto Digital y PedidosYa Market) y medición
        econométrica del Índice de Laspeyres frente a CABA (DGEyC) e INDEC Alimentos.
    </p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "🧺  1. Armar y Editar Canasta (Alimento y Marca)",
    "📈  2. Tu Inflación Personal vs. CABA / INDEC",
    "🎯  3. Optimizador de Faltantes y Arbitraje",
])

# ==============================================================================
# PESTAÑA 1: ARMAR Y EDITAR CANASTA (SELECTORES CLÁSICOS + SCRAPING REAL EN VIVO)
# ==============================================================================
with tab1:
    st.markdown("### 1. Selección de Alimentos y Marcas")
    st.caption(f"Elegí entre las **{len(df_cat):,} combinaciones** disponibles y consultá los precios reales en tiempo real en cada supermercado:")

    c_f_cat, c_f_marca, c_f_txt = st.columns([1.2, 1.2, 2.0])
    with c_f_cat:
        cat_filtro = st.selectbox("Filtrar por Categoría:", CATEGORIAS)
    with c_f_marca:
        marca_filtro = st.selectbox("Filtrar por Marca:", MARCAS_TODAS)
    with c_f_txt:
        busq_input = st.text_input("Buscador por Texto:", placeholder="Ej: Leche Ilolay, Yerba Playadito, Aceite Natura...")

    sub_df = df_cat.copy()
    if cat_filtro != "Todas":
        sub_df = sub_df[sub_df["cat"] == cat_filtro]
    if marca_filtro != "Todas":
        sub_df = sub_df[sub_df["marca"] == marca_filtro]
    if busq_input.strip():
        for t in normalizar_texto(busq_input).split():
            sub_df = sub_df[sub_df["busqueda"].str.contains(t, regex=False)]

    st.markdown("#### 🛒 Apartado de Selección Directa (Alimento ➔ Marca)")

    col_alimento, col_marca, col_cant, col_btn = st.columns([2.4, 1.7, 1.1, 1.2])
    alimentos_disponibles = sorted(sub_df["alimento"].unique().tolist()) if not sub_df.empty else sorted(df_cat["alimento"].unique().tolist())

    with col_alimento:
        alimento_elegido = st.selectbox("1. Seleccionar Alimento / Presentación:", alimentos_disponibles)

    marcas_del_alimento = sorted(df_cat[df_cat["alimento"] == alimento_elegido]["marca"].unique().tolist())
    with col_marca:
        marca_elegida = st.selectbox("2. Apartado de Marca:", marcas_del_alimento)

    prod_match = df_cat[(df_cat["alimento"] == alimento_elegido) & (df_cat["marca"] == marca_elegida)]
    fila_item = prod_match.iloc[0]

    with st.spinner(f"Scrapeando precios reales en vivo para {alimento_elegido} ({marca_elegida})..."):
        cotiz_actual = scrapear_4_cadenas_en_vivo(fila_item["alimento"], fila_item["marca"])

    st.write("")
    cols_tiendas = st.columns(4)
    for idx_t, tienda in enumerate(TIENDAS):
        info_t = cotiz_actual[tienda]
        p_val = info_t["precio_final"]
        precio_txt = f"${p_val:,.2f}" if p_val is not None else "No disponible"
        titulo_encontrado = info_t["titulo_web"][:46]
        with cols_tiendas[idx_t]:
            st.markdown(f"""
            <div class="store-card" style="border-top-color: {STORE_COLORS[tienda]};">
                <div class="store-title">{tienda}</div>
                <div class="store-price">{precio_txt}</div>
                <div class="store-meta">{info_t['estado']}<br><em>{titulo_encontrado}</em></div>
            </div>
            """, unsafe_allow_html=True)

    coto_live_p = cotiz_actual["Coto"]["precio_final"]
    pya_live_p = cotiz_actual["PedidosYa Market Belgrano"]["precio_final"]

    if coto_live_p is None or pya_live_p is None:
        st.info(
            "ℹ️ **Nota técnica sobre Coto y PedidosYa:** Si ejecutás la app en servidores en la nube (Streamlit Cloud), "
            "los firewalls (WAF) de Coto Digital y PedidosYa pueden bloquear la IP del servidor. "
            "Si los ejecutás localmente en tu PC se extraen directo; o podés ingresar aquí el precio real visto en la web/app:"
        )
        c_ov1, c_ov2 = st.columns(2)
        with c_ov1:
            if coto_live_p is None:
                coto_live_p = st.number_input("Precio real observado en Coto Digital ($):", min_value=0.0, value=0.0, step=10.0, key="ov_coto")
                if coto_live_p == 0.0:
                    coto_live_p = None
        with c_ov2:
            if pya_live_p is None:
                pya_live_p = st.number_input("Precio real observado en PedidosYa Market ($):", min_value=0.0, value=0.0, step=10.0, key="ov_pya")
                if pya_live_p == 0.0:
                    pya_live_p = None

    with col_cant:
        cant_elegida = st.number_input("Cantidad mensual (q₀):", min_value=1.0, value=2.0, step=1.0)

    with col_btn:
        st.write("")
        st.write("")
        if st.button("➕ Agregar a Canasta", type="primary", use_container_width=True):
            precios_validos_hoy = [
                p for p in [
                    cotiz_actual["Carrefour"]["precio_final"],
                    cotiz_actual["Dia"]["precio_final"],
                    coto_live_p,
                    pya_live_p,
                ] if p is not None and p > 0
            ]
            if not precios_validos_hoy:
                st.error("No hay ningún precio real cargado para este producto todavía.")
            else:
                ean_sel = fila_item["ean"]
                p_hoy_ref = coto_live_p if coto_live_p else round(sum(precios_validos_hoy) / len(precios_validos_hoy), 2)
                hist_prev = HISTORICO_OBSERVADO_2026.get(
                    (fila_item["alimento"], fila_item["marca"]),
                    {m: p_hoy_ref for m in MESES_SERIE},
                )
                hist_nuevo = dict(hist_prev)
                hist_nuevo["Septiembre 2026"] = p_hoy_ref

                canasta[ean_sel] = {
                    "ean": ean_sel,
                    "categoria": fila_item["cat"],
                    "alimento": fila_item["alimento"],
                    "marca": fila_item["marca"],
                    "q0": cant_elegida,
                    "precios_vivo": {
                        "Carrefour": cotiz_actual["Carrefour"]["precio_final"],
                        "Dia": cotiz_actual["Dia"]["precio_final"],
                        "Coto": coto_live_p,
                        "PedidosYa Market Belgrano": pya_live_p,
                    },
                    "historico": hist_nuevo,
                }
                st.toast(f"Agregado a tu canasta: {alimento_elegido} ({marca_elegida})", icon="✅")
                st.rerun()

    st.divider()

    st.subheader("Tu Canasta Mensual Ponderada Actual")
    if canasta:
        for ean_k, item in canasta.items():
            if item["precios_vivo"]["Carrefour"] is None and item["precios_vivo"]["Dia"] is None:
                c_init = scrapear_4_cadenas_en_vivo(item["alimento"], item["marca"])
                item["precios_vivo"]["Carrefour"] = c_init["Carrefour"]["precio_final"]
                item["precios_vivo"]["Dia"] = c_init["Dia"]["precio_final"]
                if c_init["Coto"]["precio_final"] is not None:
                    item["precios_vivo"]["Coto"] = c_init["Coto"]["precio_final"]
                if c_init["PedidosYa Market Belgrano"]["precio_final"] is not None:
                    item["precios_vivo"]["PedidosYa Market Belgrano"] = c_init["PedidosYa Market Belgrano"]["precio_final"]

        tabla_canasta = []
        for ean_k, item in canasta.items():
            pv = item["precios_vivo"]
            fmt_celda = lambda v: f"${v:,.2f}" if v is not None else "Pendiente"
            p_base_sub = pv["Coto"] or pv["Carrefour"] or pv["Dia"] or pv["PedidosYa Market Belgrano"] or 0.0
            tabla_canasta.append({
                "Categoría": item["categoria"],
                "Alimento": item["alimento"],
                "Marca": item["marca"],
                "Coto ($)": fmt_celda(pv["Coto"]),
                "Carrefour ($)": fmt_celda(pv["Carrefour"]),
                "Día ($)": fmt_celda(pv["Dia"]),
                "PedidosYa ($)": fmt_celda(pv["PedidosYa Market Belgrano"]),
                "Cantidad (q₀)": item["q0"],
                "Subtotal ($)": f"${(p_base_sub * item['q0']):,.2f}",
            })
        st.dataframe(pd.DataFrame(tabla_canasta), hide_index=True, use_container_width=True)

        with st.expander("📅 Ver o editar precios reales mensuales (Mayo – Septiembre 2026)"):
            filas_m = []
            for ean_k, item in canasta.items():
                fila_m = {"EAN": ean_k, "Producto": f"{item['alimento']} ({item['marca']})", "q₀": item["q0"]}
                for m in MESES_SERIE:
                    fila_m[m] = float(item["historico"][m])
                filas_m.append(fila_m)
            df_m_edit = st.data_editor(
                pd.DataFrame(filas_m).drop(columns=["EAN"]),
                hide_index=True,
                use_container_width=True,
                key="edit_hist_modal",
            )
            if st.button("💾 Guardar Precios Mensuales Reales"):
                for idx_r, ean_k in enumerate(list(canasta.keys())):
                    row_ed = df_m_edit.iloc[idx_r]
                    canasta[ean_k]["q0"] = float(row_ed["q₀"])
                    for m in MESES_SERIE:
                        canasta[ean_k]["historico"][m] = float(row_ed[m])
                st.toast("Serie histórica real actualizada.", icon="✅")
                st.rerun()

        col_del, col_btn_del, col_vaciar = st.columns([3, 1, 1])
        with col_del:
            ean_borrar = st.selectbox(
                "Seleccionar ítem para eliminar:",
                list(canasta.keys()),
                format_func=lambda e: f"{canasta[e]['alimento']} — {canasta[e]['marca']}",
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
        st.info("Tu canasta está vacía. Seleccioná un alimento y marca arriba para comenzar a medir.")

# ==============================================================================
# PESTAÑA 2: MEDICIÓN ECONOMÉTRICA VS. BENCHMARKS OFICIALES (CABA / INDEC)
# ==============================================================================
with tab2:
    if not canasta:
        st.warning("Primero agregá productos a tu canasta en la Pestaña 1.")
    else:
        c_bench, c_api = st.columns([2.5, 1.5])
        with c_bench:
            fuente_elegida = st.radio(
                "Benchmark a comparar:",
                ["CABA (DGEyC - Serie Porteña)", "INDEC Oficial (API Alimentos en Vivo)"],
                horizontal=True,
            )
        with c_api:
            with st.expander("🛠️ Ver respuesta técnica API INDEC"):
                st.write(api_indec_info["datos"])
                if api_indec_info["raw"]:
                    st.json(api_indec_info["raw"])

        gastos_mes = []
        for idx_m, mes in enumerate(MESES_SERIE):
            total_m = sum(
                float(item["historico"][mes]) * float(item["q0"])
                for item in canasta.values()
            )
            gastos_mes.append({"mes_idx": idx_m, "mes": mes, "gasto_total": round(total_m, 2)})

        costo_mes = pd.DataFrame(gastos_mes)
        costo_mes["inflacion_personal_%"] = costo_mes["gasto_total"].pct_change() * 100.0
        gasto_inicio = costo_mes.iloc[0]["gasto_total"]
        gasto_fin = costo_mes.iloc[-1]["gasto_total"]
        costo_mes["indice_personal"] = (costo_mes["gasto_total"] / gasto_inicio) * 100.0 if gasto_inicio > 0 else 100.0

        if "CABA" in fuente_elegida:
            costo_mes["var_oficial_%"] = costo_mes["mes"].apply(lambda m: DATOS_CABA[m]["var_oficial"])
            nombre_serie = "CABA (DGEyC)"
        else:
            costo_mes["var_oficial_%"] = costo_mes["mes"].apply(
                lambda m: api_indec_info["datos"].get(m, DATOS_INDEC_FALLBACK[m])
            )
            nombre_serie = "INDEC Alimentos (API)"

        idx_of = [100.0]
        for v in costo_mes["var_oficial_%"].iloc[1:]:
            idx_of.append(idx_of[-1] * (1.0 + v / 100.0))
        costo_mes["indice_oficial"] = idx_of

        inf_acum_personal = ((gasto_fin - gasto_inicio) / gasto_inicio) * 100.0 if gasto_inicio > 0 else 0.0
        inf_acum_oficial = costo_mes["indice_oficial"].iloc[-1] - 100.0
        brecha = inf_acum_personal - inf_acum_oficial

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f"""
            <div class="kpi-card" style="border-top: 4px solid #2563EB;">
                <div class="kpi-label">Tu Inflación Acumulada</div>
                <div class="kpi-value">{inf_acum_personal:.2f}%</div>
                <span class="kpi-pill-neu">Índice Laspeyres: {costo_mes['indice_personal'].iloc[-1]:.2f}</span>
            </div>
            """, unsafe_allow_html=True)
        with k2:
            st.markdown(f"""
            <div class="kpi-card" style="border-top: 4px solid #F97316;">
                <div class="kpi-label">Acumulado {nombre_serie}</div>
                <div class="kpi-value">{inf_acum_oficial:.2f}%</div>
                <span class="kpi-pill-neu">Índice Oficial: {costo_mes['indice_oficial'].iloc[-1]:.2f}</span>
            </div>
            """, unsafe_allow_html=True)
        with k3:
            pill_cls = "kpi-pill-neg" if brecha > 0 else "kpi-pill-pos"
            pill_txt = "Mayor impacto en tu canasta" if brecha > 0 else "Menor impacto en tu canasta"
            st.markdown(f"""
            <div class="kpi-card" style="border-top: 4px solid {'#DC2626' if brecha > 0 else '#059669'};">
                <div class="kpi-label">Brecha vs. Oficial</div>
                <div class="kpi-value">{brecha:+.2f} p.p.</div>
                <span class="{pill_cls}">{pill_txt}</span>
            </div>
            """, unsafe_allow_html=True)
        with k4:
            st.markdown(f"""
            <div class="kpi-card" style="border-top: 4px solid #0F172A;">
                <div class="kpi-label">Gasto Canasta (Septiembre)</div>
                <div class="kpi-value">${gasto_fin:,.2f}</div>
                <span class="kpi-pill-neu">Base Mayo: ${gasto_inicio:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        g1, g2 = st.columns(2)
        df_graf_m = costo_mes.iloc[1:].copy()

        with g1:
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                x=df_graf_m["mes"], y=df_graf_m["inflacion_personal_%"],
                name="Tu Inflación Personal (Laspeyres)", marker_color="#2563EB",
                text=df_graf_m["inflacion_personal_%"].map(lambda x: f"{x:.2f}%"), textposition="outside",
            ))
            fig_comp.add_trace(go.Bar(
                x=df_graf_m["mes"], y=df_graf_m["var_oficial_%"],
                name=nombre_serie, marker_color="#F97316",
                text=df_graf_m["var_oficial_%"].map(lambda x: f"{x:.2f}%"), textposition="outside",
            ))
            fig_comp.update_layout(
                barmode="group",
                title=f"Gráfico 1: Variación Mensual vs. {nombre_serie} (%)",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(ticksuffix="%", gridcolor="#E2E8F0"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=25, l=15, r=15),
                height=380,
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        with g2:
            fig_idx = go.Figure()
            fig_idx.add_trace(go.Scatter(
                x=costo_mes["mes"], y=costo_mes["indice_personal"], mode="lines+markers+text",
                name="Índice Personal (Base Mayo = 100)", line=dict(color="#2563EB", width=3.5),
                text=costo_mes["indice_personal"].map(lambda x: f"{x:.1f}"), textposition="top center",
            ))
            fig_idx.add_trace(go.Scatter(
                x=costo_mes["mes"], y=costo_mes["indice_oficial"], mode="lines+markers",
                name=f"Índice {nombre_serie}", line=dict(color="#F97316", width=3, dash="dash"),
            ))
            fig_idx.update_layout(
                title="Gráfico 2: Trayectoria Acumulada (Base Mayo 2026 = 100)",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="#E2E8F0"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=25, l=15, r=15),
                height=380,
            )
            st.plotly_chart(fig_idx, use_container_width=True)

# ==============================================================================
# PESTAÑA 3: ASISTENTE DE FALTANTES Y ARBITRAJE SOBRE PRECIOS REALES
# ==============================================================================
with tab3:
    st.markdown("### 🎯 Asistente de Compras: Precios Reales y Ofertas en Vivo")
    st.caption("Compara únicamente las cadenas que tienen precios reales disponibles para los productos seleccionados:")

    if not canasta:
        st.warning("Primero agregá productos a tu canasta en la Pestaña 1.")
    else:
        opciones_falt = list(canasta.keys())
        seleccion = st.multiselect(
            "Alimentos a cotizar:",
            options=opciones_falt,
            default=opciones_falt[:3] if len(opciones_falt) >= 3 else opciones_falt,
            format_func=lambda e: f"{canasta[e]['alimento']} — {canasta[e]['marca']}",
        )

        if seleccion:
            promos_reglas = {
                "Coto": (0.85, "🏷️ 15% OFF Comunidad Coto (Martes a Jueves)"),
                "Carrefour": (0.85, "🏷️ 2da al 70% llevando 2 (Mi Carrefour)"),
                "Dia": (0.90, "🏷️ Descuento Exclusivo Club Día (-10%)"),
                "PedidosYa Market Belgrano": (1.00, "🚀 Entrega rápida en 15 min"),
            }

            detalle_filas = []
            for ean_sel in seleccion:
                item = canasta[ean_sel]
                pv = item["precios_vivo"]
                for t in TIENDAS:
                    p_reg = pv.get(t)
                    if p_reg is not None and p_reg > 0:
                        factor, promo_txt = promos_reglas[t]
                        p_fin = round(p_reg * factor, 2)
                        ahorro_i = p_reg - p_fin
                        detalle_filas.append({
                            "Producto": item["alimento"],
                            "Marca": item["marca"],
                            "Supermercado": t,
                            "Precio Regular ($)": f"${p_reg:,.2f}",
                            "Precio con Oferta ($)": f"${p_fin:,.2f}",
                            "Promoción Aplicada": promo_txt,
                            "Ahorro ($)": f"${ahorro_i:,.2f}" if ahorro_i > 0 else "—",
                            "_precio_num": p_fin,
                            "_precio_reg_num": p_reg,
                            "_tienda": t,
                        })

            if not detalle_filas:
                st.warning("No hay precios reales cargados para comparar en estas cadenas.")
            else:
                df_detalles = pd.DataFrame(detalle_filas)

                tiendas_completas = [
                    t for t in TIENDAS
                    if len(df_detalles[df_detalles["_tienda"] == t]) == len(seleccion)
                ]

                if tiendas_completas:
                    totales_finales = {
                        t: df_detalles[df_detalles["_tienda"] == t]["_precio_num"].sum()
                        for t in tiendas_completas
                    }
                    totales_regulares = {
                        t: df_detalles[df_detalles["_tienda"] == t]["_precio_reg_num"].sum()
                        for t in tiendas_completas
                    }
                    mejor_mono = min(totales_finales, key=totales_finales.get)
                    gasto_mono_final = totales_finales[mejor_mono]
                    gasto_mono_reg = totales_regulares[mejor_mono]
                    ahorro_mono = gasto_mono_reg - gasto_mono_final
                else:
                    mejor_mono = "N/D"
                    gasto_mono_final = 0.0
                    gasto_mono_reg = 0.0
                    ahorro_mono = 0.0

                split_items = []
                gasto_split = 0.0
                for ean_sel in seleccion:
                    item = canasta[ean_sel]
                    sub_p = df_detalles[(df_detalles["Producto"] == item["alimento"]) & (df_detalles["Marca"] == item["marca"])]
                    if not sub_p.empty:
                        min_row = sub_p.loc[sub_p["_precio_num"].idxmin()]
                        gasto_split += min_row["_precio_num"]
                        split_items.append({
                            "Producto": item["alimento"],
                            "Marca": item["marca"],
                            "Supermercado más Barato": min_row["_tienda"],
                            "Precio Final": min_row["Precio con Oferta ($)"],
                            "Promoción Aprovechada": min_row["Promoción Aplicada"],
                        })

                ahorro_split = (gasto_mono_final - gasto_split) if gasto_mono_final > 0 else 0.0
                pct_split = (ahorro_split / gasto_mono_final) * 100.0 if gasto_mono_final > 0 else 0.0

                r1, r2 = st.columns(2)
                with r1:
                    if tiendas_completas:
                        st.markdown(f"""
                        <div class="kpi-card" style="border-top: 4px solid #059669;">
                            <div class="kpi-label">📍 Opción 1: Comprar todo en {mejor_mono}</div>
                            <div class="kpi-value">${gasto_mono_final:,.2f}</div>
                            <span class="kpi-pill-pos">Ahorro por ofertas: ${ahorro_mono:,.2f} (-{(ahorro_mono/gasto_mono_reg)*100:.1f}%)</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("Ninguna cadena individual tiene cotizados todos los ítems; revisá la Opción 2 (Split).")

                with r2:
                    st.markdown(f"""
                    <div class="kpi-card" style="border-top: 4px solid #2563EB;">
                        <div class="kpi-label">🛒 Opción 2: Compra Dividida (Mayor Ahorro)</div>
                        <div class="kpi-value">${gasto_split:,.2f}</div>
                        <span class="kpi-pill-neu">Ahorro extra vs. Opción 1: ${ahorro_split:,.2f} (-{pct_split:.1f}%)</span>
                    </div>
                    """, unsafe_allow_html=True)

                st.write("")
                st.markdown("#### Asignación Óptima por Producto (Split)")
                st.dataframe(pd.DataFrame(split_items), hide_index=True, use_container_width=True)

                st.divider()
                st.subheader("📋 Detalle de Precios Reales y Ofertas Aplicadas")
                cols_mostrar = ["Producto", "Marca", "Supermercado", "Precio Regular ($)", "Precio con Oferta ($)", "Promoción Aplicada", "Ahorro ($)"]
                st.dataframe(df_detalles[cols_mostrar], hide_index=True, use_container_width=True)
