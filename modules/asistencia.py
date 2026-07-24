"""
asistencia.py — Sección Asistencia
====================================
Control de asistencia semanal con diseño profesional: tomar asistencia,
registrar nuevos jóvenes y desactivar miembros de la lista activa.
Estilos consistentes con la sección Dashboard.
"""

import os
from datetime import date

import streamlit as st

from config import COLORS, PATH_JOVENES
from modules.db import ejecutar_query


def render_asistencia():
    """Renderiza la sección de asistencia con 3 tabs y diseño profesional."""

    # ================================================================
    # ENCABEZADO PROFESIONAL
    # ================================================================
    st.markdown(f"""
    <div class="section-header">
        <h2>📋 Control de Asistencia</h2>
        <p>Registro y seguimiento de la asistencia semanal del ministerio juvenil</p>
    </div>
    """, unsafe_allow_html=True)

    # ================================================================
    # TABS
    # ================================================================
    tabs = st.tabs([
        "✅ Tomar Asistencia",
        "➕ Registrar Nuevo Integrante",
        "🗑️ Gestionar Lista Activa"
    ])

    # ================================================================
    # TAB 1: TOMAR ASISTENCIA
    # ================================================================
    with tabs[0]:
        col_img, col_info = st.columns([1, 2])
        with col_img:
            if PATH_JOVENES and os.path.exists(PATH_JOVENES):
                st.image(PATH_JOVENES, use_container_width=True)

        with col_info:
            st.markdown(f"""
            <div class="content-card">
                <h4 style="color:{COLORS['primary']}; margin:0 0 0.5rem 0;">📅 Registro Semanal</h4>
                <p style="color:#666; font-size:0.9rem; margin:0;">
                    Selecciona a los jóvenes que asistieron al culto. 
                    Los cambios se guardan automáticamente al confirmar el registro.
                </p>
            </div>
            """, unsafe_allow_html=True)

        # Selector de fecha
        fecha_asistencia = st.date_input(
            "📆 Fecha del Culto:", date.today(), key="fecha_asistencia"
        )
        fecha_str = fecha_asistencia.strftime("%Y-%m-%d")

        # Obtener jóvenes activos
        jovenes = ejecutar_query(
            "SELECT id, nombre FROM jovenes WHERE activo = 1 ORDER BY nombre ASC"
        )

        if not jovenes:
            st.warning("No hay jóvenes activos registrados en el sistema.")
        else:
            # Cargar asistencias existentes para esta fecha
            asistencias_existentes = ejecutar_query(
                "SELECT joven_id FROM asistencia WHERE fecha = ? AND asistio = 1",
                (fecha_str,),
            )
            ids_presentes = [row[0] for row in asistencias_existentes]
            total_activos = len(jovenes)
            presentes_hoy = len(ids_presentes)
            ausentes_hoy = total_activos - presentes_hoy

            # KPIs
            st.markdown("### 📊 Resumen rápido")
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">👥 Miembros Activos</div>
                    <div class="kpi-value">{total_activos}</div>
                    <div class="kpi-sub">Total registrados</div>
                </div>
                """, unsafe_allow_html=True)
            with col_s2:
                st.markdown(f"""
                <div class="kpi-card" style="background: linear-gradient(135deg, #1a6b3a 0%, #28a745 100%);">
                    <div class="kpi-label">✅ Presentes</div>
                    <div class="kpi-value">{presentes_hoy}</div>
                    <div class="kpi-sub">Asistieron hoy</div>
                </div>
                """, unsafe_allow_html=True)
            with col_s3:
                st.markdown(f"""
                <div class="kpi-card" style="background: linear-gradient(135deg, #6b1a1a 0%, #dc3545 100%);">
                    <div class="kpi-label">❌ Ausentes</div>
                    <div class="kpi-value">{ausentes_hoy}</div>
                    <div class="kpi-sub">No asistieron hoy</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Formulario de asistencia
            with st.form("form_asistencia_tab"):
                st.markdown(
                    f'<h5 style="color:{COLORS["primary"]};">👤 Selecciona los que asistieron:</h5>',
                    unsafe_allow_html=True
                )

                cols_check = st.columns(2)
                lista_checks = {}
                for idx, (j_id, nombre) in enumerate(jovenes):
                    with cols_check[idx % 2]:
                        lista_checks[j_id] = st.checkbox(
                            nombre,
                            value=(j_id in ids_presentes),
                            key=f"check_asist_{j_id}",
                        )

                st.markdown("<br>", unsafe_allow_html=True)

                guardar = st.form_submit_button(
                    "💾 Guardar Registro de Asistencia", use_container_width=True
                )
                if guardar:
                    ejecutar_query(
                        "DELETE FROM asistencia WHERE fecha = ?",
                        (fecha_str,), commit=True, fetch=False,
                    )
                    for j_id, presente in lista_checks.items():
                        estado = 1 if presente else 0
                        ejecutar_query(
                            "INSERT INTO asistencia (joven_id, fecha, asistio) VALUES (?, ?, ?)",
                            (j_id, fecha_str, estado), commit=True, fetch=False,
                        )
                    st.success(f"✅ Asistencia registrada exitosamente para el {fecha_str}")
                    st.rerun()

    # ================================================================
    # TAB 2: REGISTRAR JOVEN NUEVO
    # ================================================================
    with tabs[1]:
        st.markdown(f"""
        <div class="content-card">
            <h4 style="color:{COLORS['primary']}; margin:0 0 0.5rem 0;">➕ Nuevo Integrante</h4>
            <p style="color:#666; font-size:0.9rem; margin:0;">
                Da de alta a un nuevo miembro del ministerio. 
                Quedará disponible de inmediato para el registro de asistencia semanal.
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("form_nuevo_joven", clear_on_submit=True):
            col_n1, col_n2 = st.columns(2)
            with col_n1:
                nombre = st.text_input(
                    "👤 Nombre completo:",
                    placeholder="Ej: Juan Pérez"
                )
                fec_nac = st.date_input(
                    "🎂 Fecha de nacimiento:",
                    min_value=date(1990, 1, 1),
                    max_value=date.today(),
                )
            with col_n2:
                celular = st.text_input(
                    "📱 Número de celular:",
                    placeholder="Ej: 3001234567"
                )
                es_nuevo_check = st.checkbox(
                    "🌟 ¿Es su primer sábado en el culto?",
                    value=True,
                    help="Marca esta opción si el joven nunca antes había asistido",
                )

            enviar = st.form_submit_button(
                "➕ Registrar Joven", use_container_width=True
            )
            if enviar:
                if not nombre.strip():
                    st.error("Por favor ingresa un nombre válido.")
                else:
                    nuevo_val = 1 if es_nuevo_check else 0
                    ejecutar_query(
                        """INSERT INTO jovenes
                           (nombre, fecha_nacimiento, celular, es_nuevo, fecha_registro, activo)
                           VALUES (?, ?, ?, ?, ?, 1)""",
                        (
                            nombre.strip(),
                            fec_nac.strftime("%Y-%m-%d"),
                            celular.strip(),
                            nuevo_val,
                            date.today().strftime("%Y-%m-%d"),
                        ),
                        commit=True,
                        fetch=False,
                    )
                    st.success(f"✅ ¡{nombre.strip()} ha sido registrado exitosamente!")
                    st.rerun()

    # ================================================================
    # TAB 3: DESACTIVAR MIEMBRO
    # ================================================================
    with tabs[2]:
        st.markdown(f"""
        <div class="content-card">
            <h4 style="color:{COLORS['danger']}; margin:0 0 0.5rem 0;">🗑️ Baja de la Lista Activa</h4>
            <p style="color:#666; font-size:0.9rem; margin:0;">
                Da de baja a un joven de la lista de asistencia activa. 
                <strong>El historial de asistencias pasadas se conserva</strong>
                y continúa disponible para las estadísticas globales.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.info(
            "⚡ Esta operación requiere autorización del Pastor. "
            "Ante cualquier duda, consulta antes de proceder."
        )

        jovenes_del = ejecutar_query(
            "SELECT id, nombre FROM jovenes WHERE activo = 1 ORDER BY nombre ASC"
        )

        if not jovenes_del:
            st.info("No hay miembros activos disponibles para remover.")
        else:
            opciones = {row[1]: row[0] for row in jovenes_del}
            joven_seleccionado = st.selectbox(
                "Selecciona el joven que deseas retirar:",
                list(opciones.keys()),
                key="del_asistencia",
            )

            with st.form("form_eliminar_asistencia"):
                st.markdown(
                    f'<div style="background:#fff3cd; border:1px solid #ffc107; border-radius:8px; padding:0.8rem; margin-bottom:0.8rem; font-size:0.85rem;">'
                    f'⚠️ Al retirar a <strong>{joven_seleccionado}</strong> de la lista activa, '
                    f'ya no aparecerá en la toma de asistencia. Su historial se conserva.'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                confirmar = st.checkbox(
                    "Confirmo que deseo retirar a este miembro de la lista de asistencia activa."
                )
                btn_eliminar = st.form_submit_button(
                    "❌ Retirar de la Lista Activa", use_container_width=True
                )

                if btn_eliminar:
                    if confirmar:
                        j_id = opciones[joven_seleccionado]
                        ejecutar_query(
                            "UPDATE jovenes SET activo = 0 WHERE id = ?",
                            (j_id,), commit=True, fetch=False,
                        )
                        st.success(
                            f"✅ {joven_seleccionado} ha sido retirado de la lista activa exitosamente."
                        )
                        st.rerun()
                    else:
                        st.error("Debes marcar la casilla de confirmación para continuar.")
