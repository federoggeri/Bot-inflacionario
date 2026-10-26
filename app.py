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
    {"items": ["Queso Cremoso", "Queso Por Salut", "Queso Muzzarella", "Queso Pategrás", "Queso Reggianito Rallado"], "marcas": ["La Paulina", "La Serenísima", "Tregar", "Punta del Agua", "Barraza"], "medidas": ["x kg", "150g"],
