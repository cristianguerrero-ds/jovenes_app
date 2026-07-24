"""
auth.py — Sistema de autenticación y gestión de usuarios
==========================================================
"""

import os
import base64

import streamlit as st

from config import COLORS, USUARIOS, USER_AVATARS, PATH_AVATAR
from modules.helpers import get_theme_mode


def get_user_avatar_path(usuario):
    """Devuelve la ruta al avatar del usuario, o el avatar por defecto."""
    if usuario in USER_AVATARS:
        path = os.path.join("images", USER_AVATARS[usuario])
        if os.path.exists(path):
            return path
    return PATH_AVATAR


def mostrar_logo_redondo(path=None, width=180):
    """
    Muestra el logo de la aplicación en formato circular.
    Se adapta al tema claro/oscuro.
    """
    if path is None:
        from config import PATH_LOGO
        path = PATH_LOGO

    if not os.path.exists(path):
        return

    with open(path, "rb") as archivo:
        datos = base64.b64encode(archivo.read()).decode("utf-8")

    mime_type = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    tema = get_theme_mode()
    filtro = "filter: invert(1);" if tema == "dark" else ""
    borde = "#ffffff" if tema == "dark" else "#1f1f1f"

    st.markdown(
        f"""
        <div style="display:flex; justify-content:center; margin-bottom:1rem;">
            <img src="data:{mime_type};base64,{datos}"
                 style="width:{width}px; height:{width}px; object-fit:cover; border-radius:50%; border:3px solid {borde}; box-shadow:0 4px 12px rgba(0,0,0,0.2); {filtro}" />
        </div>
        """,
        unsafe_allow_html=True,
    )


def mostrar_avatar_usuario(usuario):
    """Muestra el avatar circular del usuario autenticado en la sidebar."""
    avatar_path = get_user_avatar_path(usuario)
    if os.path.exists(avatar_path):
        with open(avatar_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        st.markdown(
            f"""
            <div style="display:flex; justify-content:center;">
                <img src="data:image/png;base64,{img_b64}"
                     style="width:70px; height:70px; object-fit:cover; border-radius:50%; border:2px solid #ffffff; box-shadow:0 2px 8px rgba(0,0,0,0.2);" />
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="display:flex; justify-content:center;">
                <img src="https://cdn-icons-png.flaticon.com/512/147/147144.png"
                     style="width:70px; height:70px; object-fit:cover; border-radius:50%; border:2px solid #ffffff; box-shadow:0 2px 8px rgba(0,0,0,0.2);" />
            </div>
            """,
            unsafe_allow_html=True,
        )


def inicializar_sesion():
    """Inicializa las variables de sesión de autenticación si no existen."""
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["rol"] = None
        st.session_state["usuario"] = None


def login_form():
    """
    Renderiza el formulario de inicio de sesión.
    Devuelve True si el usuario se autenticó exitosamente en este ciclo.
    """
    from config import APP_SUBTITLE

    col_centered_1, col_form, col_centered_2 = st.columns([1, 2, 1])
    with col_form:
        st.markdown(
            f"<div style='text-align:center; margin-bottom:0.5rem;'><h3>{APP_SUBTITLE}</h3></div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        with st.form("main_login_form"):
            usuario_input = st.text_input("Usuario (Email):")
            pass_input = st.text_input("Contraseña:", type="password")
            boton_login = st.form_submit_button("🚀 Ingresar al Sistema", use_container_width=True)
            if boton_login:
                if usuario_input in USUARIOS and USUARIOS[usuario_input]["pass"] == pass_input:
                    st.session_state["autenticado"] = True
                    st.session_state["rol"] = USUARIOS[usuario_input]["rol"]
                    st.session_state["usuario"] = usuario_input
                    st.success("¡Inicio de sesión exitoso!")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
    return st.session_state["autenticado"]


def sidebar_user_info():
    """Muestra la información del usuario autenticado en la sidebar."""
    if not st.session_state["autenticado"]:
        return

    col_avatar, col_txt = st.sidebar.columns([1, 2])
    with col_avatar:
        mostrar_avatar_usuario(st.session_state["usuario"])
    with col_txt:
        st.subheader("Jóvenes Iglesia Alianza Central")
        st.markdown(f"**Usuario:** `{st.session_state['usuario']}`")
        st.markdown(f"**Rol:** {st.session_state['rol']}")
        st.markdown(
            "*No nos cansemos, pues, de hacer bien; "
            "porque a su tiempo segaremos, si no desmayamos. Gálatas 6:9*"
        )

    # Mostrar promedio y mensaje motivacional debajo del perfil
    usuario_actual = st.session_state["usuario"]
    from config import USER_DISPLAY_NAMES
    from modules.db import ejecutar_query
    import pandas as pd
    from modules.helpers import (
        calculate_evaluation_score,
        calculate_auto_evaluation_score,
        get_leader_motivation,
    )

    display_name = USER_DISPLAY_NAMES.get(usuario_actual, "")
    if display_name:
        df_eval_sidebar = pd.DataFrame(
            ejecutar_query("SELECT * FROM evaluacion_equipo"),
            columns=[
                "id", "lider", "fecha", "puntualidad", "fidelidad",
                "invitados", "visitados", "resumen", "asistio_lider",
                "motivo_no_asistencia", "auto_eval_visitados",
                "auto_eval_programacion", "auto_eval_seguimiento",
                "auto_eval_invitados", "auto_eval_nuevos", "auto_eval_resumen",
            ],
        )
        if not df_eval_sidebar.empty:
            df_eval_sidebar["fecha"] = pd.to_datetime(df_eval_sidebar["fecha"], errors="coerce")
            df_eval_sidebar = df_eval_sidebar.dropna(subset=["fecha"]).copy()
            df_eval_sidebar["score"] = df_eval_sidebar.apply(
                lambda row: calculate_evaluation_score(
                    row.get("puntualidad", 0), row.get("fidelidad", 0),
                    row.get("invitados", 0), row.get("visitados", 0),
                ), axis=1,
            )
            df_eval_sidebar["auto_score"] = df_eval_sidebar.apply(
                lambda row: calculate_auto_evaluation_score(
                    row.get("auto_eval_programacion", 0),
                    row.get("auto_eval_nuevos", 0),
                    row.get("auto_eval_seguimiento", 0),
                    row.get("auto_eval_invitados", 0),
                    row.get("auto_eval_visitados", 0),
                ), axis=1,
            )
            

        motivacion = get_leader_motivation(display_name, df_eval_sidebar)

        st.sidebar.markdown(" ")
        st.sidebar.markdown(f"### 📊 Mi Evaluación")

        score_color = "🟢" if motivacion["promedio"] >= 4 else ("🟡" if motivacion["promedio"] >= 2.5 else "🔴")
        st.sidebar.markdown()
        st.sidebar.markdown(
            f"<div style='text-align:center; font-size:1.8rem; font-weight:bold; "
            f"color:#e4be18;'>{score_color} {motivacion['promedio']:.2f}/5.0</div>",
            unsafe_allow_html=True,
        )
        # Mensaje motivacional en un contenedor estilizado
        st.sidebar.markdown(
            f"<div style='background: rgba(228,190,24,0.1); border-left: 3px solid #e4be18; "
            f"padding: 0.6rem 0.8rem; border-radius: 6px; font-size:0.8rem; line-height:1.4; "
            f"margin: 0.3rem 0;'>{motivacion['mensaje']}</div>",
            unsafe_allow_html=True,
        )
    st.sidebar.markdown(" ")
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["rol"] = None
        st.session_state["usuario"] = None
        st.rerun()

