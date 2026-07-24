"""
app.py — Orquestador principal de la aplicación
==================================================
Carga la configuración global, inicializa la base de datos,
gestiona la autenticación y renderiza el menú de navegación
con las 4 secciones principales.
"""

import streamlit as st

from config import COLORS, CUSTOM_CSS, APP_TITLE, APP_ICON, PATH_LOGO
from modules.db import init_db
from modules.auth import inicializar_sesion, login_form, sidebar_user_info, mostrar_logo_redondo
from modules.dashboard import render_dashboard
from modules.asistencia import render_asistencia
from modules.evaluacion import render_evaluacion_equipo
from modules.agenda import render_agenda

# ================================================================
# CONFIGURACIÓN INICIAL DE LA PÁGINA
# ================================================================
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================================================
# ESTILOS CSS GLOBALES
# ================================================================
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ================================================================
# INICIALIZAR BASE DE DATOS
# ================================================================
init_db()

# ================================================================
# INICIALIZAR SESIÓN
# ================================================================
inicializar_sesion()

# ================================================================
# LOGO EN SIDEBAR
# ================================================================
mostrar_logo_redondo()

# ================================================================
# PANTALLA DE LOGIN
# ================================================================
if not st.session_state["autenticado"]:
    login_form()
    st.stop()  # No renderizar nada más si no está autenticado

# ================================================================
# INFORMACIÓN DEL USUARIO EN SIDEBAR
# ================================================================
sidebar_user_info()

# ================================================================
# MENÚ DE NAVEGACIÓN
# ================================================================
st.sidebar.markdown("---")
st.sidebar.markdown("### 📍 Navegación")

# Filtrar secciones según el rol del usuario
# - Pastor: acceso completo a todas las secciones
# - Otros roles: acceso únicamente a Asistencia
rol_usuario = st.session_state.get("rol", "")
if rol_usuario == "Pastor":
    opciones_nav = ["Dashboard", "Asistencia", "Evaluación de Equipo", "Agenda"]
    indice_default = 0
else:
    opciones_nav = ["Asistencia"]
    indice_default = 0

seccion = st.sidebar.radio(
    "Ir a:",
    options=opciones_nav,
    index=indice_default,
    key="nav_principal",
    label_visibility="collapsed",
    horizontal=False,
)

st.sidebar.markdown("---")

# ================================================================
# RENDERIZADO DE SECCIONES
# ================================================================

if seccion == "Dashboard":
    render_dashboard()

elif seccion == "Asistencia":
    render_asistencia()

elif seccion == "Evaluación de Equipo":
    render_evaluacion_equipo()

elif seccion == "Agenda":
    render_agenda()

