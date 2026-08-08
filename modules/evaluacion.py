"""
evaluacion.py — Sección Evaluación de Equipo
===============================================
Permite al Pastor evaluar el desempeño de los líderes, registrar
asistencia de líderes, autoevaluación pastoral y calcular scores.
Diseño profesional consistente con Dashboard.
"""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS, EQUIPO
from modules.db import ejecutar_query
from modules.helpers import (
    calculate_evaluation_score,
    calculate_auto_evaluation_score,
    get_score_status,
    build_urgency_summary,
)


def render_evaluacion_equipo():
    """
    Renderiza la sección de evaluación de equipo (vista del Pastor).
    Incluye formulario de evaluación, métricas, KPIs, tendencias y urgencia.
    """

    # ================================================================
    # ENCABEZADO
    # ================================================================
    st.markdown(f"""
    <div class="section-header">
        <h2>📊 Evaluación de Equipo</h2>
        <p>Monitoreo de compromisos, rendimiento de líderes y autoevaluación pastoral</p>
    </div>
    """, unsafe_allow_html=True)

    # ================================================================
    # CARGAR DATOS
    # ================================================================
    df_jovenes = pd.DataFrame(
        ejecutar_query("SELECT * FROM jovenes"),
        columns=["id", "nombre", "fec_nac", "celular", "es_nuevo", "fec_reg", "activo"],
    )
    df_asistencia = pd.DataFrame(
        ejecutar_query("SELECT * FROM asistencia"),
        columns=["id", "joven_id", "fecha", "asistio"],
    )
    df_eval = pd.DataFrame(
        ejecutar_query("SELECT * FROM evaluacion_equipo"),
        columns=[
            "id", "lider", "fecha", "puntualidad", "fidelidad",
            "invitados", "visitados", "resumen", "asistio_lider",
            "motivo_no_asistencia", "auto_eval_visitados",
            "auto_eval_programacion", "auto_eval_seguimiento",
            "auto_eval_invitados", "auto_eval_nuevos", "auto_eval_resumen",
        ],
    )

    if not df_eval.empty:
        df_eval["fecha"] = pd.to_datetime(df_eval["fecha"], errors="coerce")
        df_eval = df_eval.dropna(subset=["fecha"]).copy()
        df_eval["score"] = df_eval.apply(
            lambda row: calculate_evaluation_score(
                row.get("puntualidad", 0),
                row.get("fidelidad", 0),
                row.get("invitados", 0),
                row.get("visitados", 0),
            ),
            axis=1,
        )
        df_eval["auto_score"] = df_eval.apply(
            lambda row: calculate_auto_evaluation_score(
                row.get("auto_eval_programacion", 0),
                row.get("auto_eval_nuevos", 0),
                row.get("auto_eval_seguimiento", 0),
                row.get("auto_eval_invitados", 0),
                row.get("auto_eval_visitados", 0),
            ),
            axis=1,
        )

    if not df_asistencia.empty:
        df_asistencia["fecha"] = pd.to_datetime(df_asistencia["fecha"], errors="coerce")
        df_asistencia = df_asistencia.dropna(subset=["fecha"])

    # ================================================================
    # KPIS
    # ================================================================
    jovenes_activos = len(df_jovenes[df_jovenes["activo"] == 1]) if not df_jovenes.empty else 0
    total_nuevos = int(df_jovenes["es_nuevo"].sum()) if not df_jovenes.empty else 0
    if not df_asistencia.empty and (df_asistencia["asistio"] == 1).any():
        prom_asist = df_asistencia[df_asistencia["asistio"] == 1].groupby("fecha").size().mean()
    else:
        prom_asist = 0
    score_equipo = float(df_eval["score"].mean()) if not df_eval.empty else 0

    st.markdown("### 📈 Indicadores Clave")
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    with col_k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">👥 Miembros Activos</div>
            <div class="kpi-value">{jovenes_activos}</div>
            <div class="kpi-sub">Total registrados</div>
        </div>
        """, unsafe_allow_html=True)
    with col_k2:
        st.markdown(f"""
        <div class="kpi-card" style="background: linear-gradient(135deg, #1a3a6b 0%, {COLORS['secondary']}aa 100%);">
            <div class="kpi-label">⭐ Nuevos Contactos</div>
            <div class="kpi-value">{total_nuevos}</div>
            <div class="kpi-sub">Histórico de nuevos contactos</div>
        </div>
        """, unsafe_allow_html=True)
    with col_k3:
        st.markdown(f"""
        <div class="kpi-card" style="background: linear-gradient(135deg, {COLORS['primary']} 0%, #2a5a9b 100%);">
            <div class="kpi-label">📊 Asistencia Promedio</div>
            <div class="kpi-value">{prom_asist:.1f}</div>
            <div class="kpi-sub">Por sábado</div>
        </div>
        """, unsafe_allow_html=True)
    with col_k4:
        st.markdown(f"""
        <div class="kpi-card" style="background: linear-gradient(135deg, #1a3a6b 0%, #3a7abd 100%);">
            <div class="kpi-label">🏆 Score del Equipo</div>
            <div class="kpi-value">{score_equipo:.1f}</div>
            <div class="kpi-sub">/ 5.0 · {"✅ Aceptable" if score_equipo >= 4 else "⚠️ Requiere mejora"}</div>
        </div>
        """, unsafe_allow_html=True)

    # ================================================================
    # PROMEDIOS POR LÍDER Y PASTOR
    # ================================================================
    st.markdown(f'<div class="dashboard-section-title">📊 Promedio de Notas por Líder y Pastor</div>', unsafe_allow_html=True)

    if not df_eval.empty:
        # Calcular promedios por cada líder (score)
        lider_promedios = {}
        for lider in EQUIPO:
            df_lider = df_eval[df_eval["lider"] == lider]
            prom = float(df_lider["score"].mean()) if not df_lider.empty else 0
            lider_promedios[lider] = prom

        # Calcular promedio del Pastor (auto_score)
        df_pastor = df_eval[df_eval["lider"] == "Pastor"]
        prom_pastor = float(df_pastor["auto_score"].mean()) if not df_pastor.empty else 0

        # Mostrar KPIs en filas de 4
        todos = list(lider_promedios.items()) + [("Pastor", prom_pastor)]
        cols_kpi = st.columns(len(todos))
        for idx, (nombre, prom) in enumerate(todos):
            emoji_icon = "👩" if nombre == ("Jannice","Lizbeth") else ("👑" if nombre == "Pastor" else "👨")
            color_style = (
                "background: linear-gradient(135deg, #1a3a6b 0%, #3a7abd 100%);"
                if nombre == "Pastor"
                else ""
            )
            estado = "✅ Aceptable" if prom >= 4 else ("⚠️ Requiere mejora" if prom > 0 else "📋 Sin datos")
            with cols_kpi[idx]:
                st.markdown(f"""
                <div class="kpi-card" style="{color_style}">
                    <div class="kpi-label">{emoji_icon} {nombre}</div>
                    <div class="kpi-value">{prom:.2f}</div>
                    <div class="kpi-sub">/ 5.0 · {estado}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("📋 No hay datos de evaluación para mostrar promedios. ¡Registra evaluaciones para ver las notas de cada líder!")

    st.markdown("---")

    # ================================================================
    # FORMULARIO DE EVALUACIÓN
    # ================================================================
    st.markdown(f'<div class="dashboard-section-title">✍️ Registrar Evaluación del Líder</div>', unsafe_allow_html=True)

    col_lider, col_fecha = st.columns(2)
    with col_lider:
        lider_sel = st.selectbox("Selecciona el Líder a evaluar:", EQUIPO)
    with col_fecha:
        fecha_eval = st.date_input("📆 Fecha de Evaluación:", date.today(), key="fecha_eval_eq")
        fecha_eval_str = fecha_eval.strftime("%Y-%m-%d")

    # Cargar evaluación previa si existe
    eval_previo = ejecutar_query(
        """SELECT puntualidad, fidelidad, invitados, visitados, resumen,
                  asistio_lider, motivo_no_asistencia
           FROM evaluacion_equipo WHERE lider = ? AND fecha = ?""",
        (lider_sel, fecha_eval_str),
    )

    init_punt = eval_previo[0][0] == 1 if eval_previo else True
    init_fid = eval_previo[0][1] == 1 if eval_previo else True
    init_inv = int(eval_previo[0][2]) if eval_previo else 0
    init_vis = int(eval_previo[0][3]) if eval_previo else 0
    init_res = eval_previo[0][4] if eval_previo else ""
    init_asistio = int(eval_previo[0][5]) if eval_previo else 1
    init_motivo = eval_previo[0][6] if eval_previo else "asistio"
    # Si el líder no asistió, los indicadores deben mostrar valores en cero
    if init_asistio == 0:
        init_punt = False
        init_fid = False
        init_inv = 0
        init_vis = 0

    st.markdown(f'<div class="content-card">', unsafe_allow_html=True)

    # ──────── FORMULARIO 1: EVALUACIÓN DEL LÍDER ────────
    with st.form("form_evaluacion_lider"):
        st.caption(
            "Si el líder no asistió, puedes guardar la evaluación "
            "sin completar los indicadores de cumplimiento."
        )

        lider_asistio = st.radio(
            "🙋 ¿El líder asistió?",
            ["✅ Sí", "🟨 No (Excusa justificada)", "🟥 No (Inasistencia injustificada)"],
            horizontal=True,
            index=0 if init_asistio == 1 else 1 if init_motivo == "con_excusa" else 2,
        )
        no_asistio = lider_asistio != "✅ Sí"
        if no_asistio:
            st.info("📝 Se registrará la evaluación sin datos de cumplimiento para este sábado.")

        st.markdown("### 📋 Indicadores de Cumplimiento")
        col1, col2 = st.columns(2)
        with col1:
            puntualidad = st.checkbox("⏱️ Puntualidad", value=init_punt, disabled=no_asistio)
            fidelidad = st.checkbox("📜 Fidelidad", value=init_fid, disabled=no_asistio)
        with col2:
            invitados = st.number_input(
                "👥 Jóvenes Nuevos Invitados:", min_value=0, step=1,
                value=init_inv, disabled=no_asistio,
            )
            visitados = st.number_input(
                "🏠 Jóvenes Visitados:", min_value=0, step=1,
                value=init_vis, disabled=no_asistio,
            )
        resumen = st.text_area("📝 Resumen General:", value=init_res, placeholder="Notas y observaciones...")

        # Score en vivo
        if no_asistio:
            score_actual = 0.0
        else:
            score_actual = calculate_evaluation_score(puntualidad, fidelidad, invitados, visitados)
        st.metric("📊 Evaluación del Líder (0–5)", f"{score_actual:.2f}", help="4.0 es la nota mínima aceptable")

        guardar_eval = st.form_submit_button("💾 Guardar Evaluación del Líder", use_container_width=True)

        if guardar_eval:
            p_val = 0 if no_asistio else (1 if puntualidad else 0)
            f_val = 0 if no_asistio else (1 if fidelidad else 0)
            invit_val = 0 if no_asistio else invitados
            visit_val = 0 if no_asistio else visitados

            if lider_asistio == "✅ Sí":
                motivo_val = "asistio"
                asistio_val = 1
            elif lider_asistio == "🟨 No (Excusa justificada)":
                motivo_val = "con_excusa"
                asistio_val = 0
            else:
                motivo_val = "sin_excusa"
                asistio_val = 0

            if eval_previo:
                ejecutar_query(
                    """UPDATE evaluacion_equipo
                       SET puntualidad=?, fidelidad=?, invitados=?, visitados=?,
                           resumen=?, asistio_lider=?, motivo_no_asistencia=?
                       WHERE lider=? AND fecha=?""",
                    (p_val, f_val, invit_val, visit_val, resumen,
                     asistio_val, motivo_val,
                     lider_sel, fecha_eval_str),
                    commit=True, fetch=False,
                )
            else:
                ejecutar_query(
                    """INSERT INTO evaluacion_equipo
                       (lider, fecha, puntualidad, fidelidad, invitados, visitados,
                        resumen, asistio_lider, motivo_no_asistencia)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (lider_sel, fecha_eval_str,
                     p_val, f_val, invit_val, visit_val, resumen,
                     asistio_val, motivo_val),
                    commit=True, fetch=False,
                )
            st.success(f"✅ Evaluación de {lider_sel} guardada exitosamente.")
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # ──────── FORMULARIO 2: AUTOEVALUACIÓN PASTORAL ────────
    st.markdown(f'<div class="dashboard-section-title">🧭 Autoevaluación Pastoral</div>', unsafe_allow_html=True)

    # La autoevaluación pertenece al Pastor (usuario autenticado), no al líder seleccionado
    pastor_usuario = st.session_state.get("usuario", "pastor@")
    # Convertir "pastor@" a "Pastor" para guardar en BD
    nombre_pastor = "Pastor"

    # Selector de fecha independiente para la autoevaluación
    col_auto_fecha = st.columns(1)
    with col_auto_fecha[0]:
        fecha_auto_eval = st.date_input(
            "📆 Fecha de Autoevaluación:",
            date.today(),
            key="fecha_auto_eval",
        )
        fecha_auto_eval_str = fecha_auto_eval.strftime("%Y-%m-%d")

    # Cargar autoevaluación previa si existe
    auto_previo = ejecutar_query(
        """SELECT auto_eval_visitados, auto_eval_programacion,
                  auto_eval_seguimiento, auto_eval_invitados,
                  auto_eval_nuevos, auto_eval_resumen
           FROM evaluacion_equipo WHERE lider = ? AND fecha = ?""",
        (nombre_pastor, fecha_auto_eval_str),
    )

    init_auto_visitados = auto_previo[0][0] == 1 if auto_previo else False
    init_auto_programacion = auto_previo[0][1] == 1 if auto_previo else False
    init_auto_seguimiento = auto_previo[0][2] == 1 if auto_previo else False
    init_auto_invitados = auto_previo[0][3] if auto_previo else 0
    init_auto_nuevos = auto_previo[0][4] if auto_previo else False
    init_auto_resumen = auto_previo[0][5] if auto_previo else ""

    st.markdown(f'<div class="content-card">', unsafe_allow_html=True)

    with st.form("form_autoevaluacion"):
        col3, col4 = st.columns(2)
        with col3:
            auto_programacion = st.checkbox("🗓️ Programación enviada a tiempo", value=init_auto_programacion)
            auto_nuevos = st.checkbox("👋 Jóvenes Nuevos contactados", value=init_auto_nuevos)
            auto_seguimiento = st.checkbox("📞 Seguimiento a los líderes", value=init_auto_seguimiento)
        with col4:
            auto_invitados = st.number_input(
                "🙌 Jóvenes nuevos invitados al culto:", min_value=0, step=1,
                value=int(init_auto_invitados) if init_auto_invitados is not None else 0,
            )
            auto_visitados = st.number_input(
                "🏠 Jóvenes visitados (pastoral):", min_value=0, step=1,
                value=int(init_auto_visitados) if init_auto_visitados is not None else 0,
            )
        auto_resumen = st.text_area("📝 Resumen de autoevaluación:", value=init_auto_resumen)

        # Score en vivo
        auto_score_actual = calculate_auto_evaluation_score(
            auto_programacion, auto_nuevos, auto_seguimiento, auto_invitados, auto_visitados
        )
        st.metric("📊 Autoevaluación Pastoral (0–5)", f"{auto_score_actual:.2f}", help="4.0 es la nota mínima aceptable")

        guardar_auto = st.form_submit_button("💾 Guardar Autoevaluación", use_container_width=True)

        if guardar_auto:
            if auto_previo:
                ejecutar_query(
                    """UPDATE evaluacion_equipo
                       SET auto_eval_visitados=?, auto_eval_programacion=?,
                           auto_eval_seguimiento=?, auto_eval_invitados=?,
                           auto_eval_nuevos=?, auto_eval_resumen=?
                       WHERE lider=? AND fecha=?""",
                    (1 if auto_visitados else 0, 1 if auto_programacion else 0,
                     1 if auto_seguimiento else 0, 1 if auto_invitados else 0,
                     1 if auto_nuevos else 0, auto_resumen,
                     nombre_pastor, fecha_auto_eval_str),
                    commit=True, fetch=False,
                )
            else:
                ejecutar_query(
                    """INSERT INTO evaluacion_equipo
                       (lider, fecha, puntualidad, fidelidad, invitados, visitados,
                        resumen, asistio_lider, motivo_no_asistencia,
                        auto_eval_visitados, auto_eval_programacion,
                        auto_eval_seguimiento, auto_eval_invitados,
                        auto_eval_nuevos, auto_eval_resumen)
                       VALUES (?, ?, 0, 0, 0, 0, '', 1, 'asistio',
                               ?, ?, ?, ?, ?, ?)""",
                    (nombre_pastor, fecha_auto_eval_str,
                     1 if auto_visitados else 0, 1 if auto_programacion else 0,
                     1 if auto_seguimiento else 0, 1 if auto_invitados else 0,
                     1 if auto_nuevos else 0, auto_resumen),
                    commit=True, fetch=False,
                )
            st.success("✅ Autoevaluación guardada exitosamente.")
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # ================================================================
    # FILTROS Y GRÁFICOS
    # ================================================================
    st.markdown(f'<div class="dashboard-section-title">📈 Análisis y Tendencias</div>', unsafe_allow_html=True)

    # FILTROS
    st.sidebar.markdown("### 🔍 Filtros de reportes")
    if not df_eval.empty:
        lideres_disponibles = sorted([
            v for v in df_eval["lider"].dropna().astype(str).unique() if v
        ])
        lideres_seleccionados = st.sidebar.multiselect(
            "Líderes", lideres_disponibles, default=lideres_disponibles,
        )
        fecha_inicio = st.sidebar.date_input("Fecha inicial", value=(date.today() - timedelta(days=90)))
        fecha_fin = st.sidebar.date_input("Fecha final", value=date.today())

        if isinstance(fecha_inicio, (list, tuple)):
            fecha_inicio = fecha_inicio[0]
        if isinstance(fecha_fin, (list, tuple)):
            fecha_fin = fecha_fin[0]
        if fecha_inicio > fecha_fin:
            fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

        df_eval_filtrado = df_eval[
            (df_eval["fecha"].dt.date >= fecha_inicio)
            & (df_eval["fecha"].dt.date <= fecha_fin)
            & (df_eval["lider"].astype(str).isin(lideres_seleccionados))
        ].copy()
    else:
        df_eval_filtrado = df_eval.copy()
        st.sidebar.info("No hay registros de evaluación para filtrar.")

    if df_eval_filtrado.empty:
        st.info("No hay datos de evaluación para el rango seleccionado.")
    else:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("**📊 Evaluación por líder (promedio)**")
            lider_summary = (
                df_eval_filtrado.groupby("lider", as_index=False)
                .agg(puntaje_promedio=("score", "mean"), autoevaluacion=("auto_score", "mean"))
                .sort_values("puntaje_promedio", ascending=False)
            )
            fig_lider = px.bar(
                lider_summary, x="lider", y=["puntaje_promedio", "autoevaluacion"],
                barmode="group",
                color_discrete_map={"puntaje_promedio": COLORS["primary"], "autoevaluacion": COLORS["secondary"]},
                labels={"value": "Puntaje (0–5)", "lider": "Líder", "variable": "Tipo"},
            )
            fig_lider.update_layout(
                height=300, margin=dict(l=10, r=10, t=10, b=30),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(range=[0, 5.5]), legend=dict(orientation="h", y=1.02, x=1),
            )
            st.plotly_chart(fig_lider, use_container_width=True)

        with col_g2:
            st.markdown("**📈 Tendencia de evaluación**")
            trend_df = (
                df_eval_filtrado.groupby(df_eval_filtrado["fecha"].dt.strftime("%Y-%m-%d"), as_index=False)
                .agg(Evaluación=("score", "mean"), Autoevaluación=("auto_score", "mean"))
                .rename(columns={"fecha": "periodo"})
            )
            fig_trend = px.line(
                trend_df, x="periodo", y=["Evaluación", "Autoevaluación"],
                markers=True,
                color_discrete_map={"Evaluación": COLORS["primary"], "Autoevaluación": COLORS["secondary"]},
            )
            fig_trend.add_hline(y=4, line_dash="dash", line_color=COLORS["secondary"],
                                annotation_text="Mínimo aceptable (4.0)", annotation_position="bottom right")
            fig_trend.update_layout(
                height=300, margin=dict(l=10, r=10, t=10, b=30),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(range=[0, 5.5]), legend=dict(orientation="h", y=1.02, x=1),
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # Tabla
        st.markdown("**🧾 Registros detallados**")
        display_df = df_eval_filtrado[["lider", "fecha", "score", "auto_score"]].copy()
        display_df["fecha"] = display_df["fecha"].dt.strftime("%Y-%m-%d")
        display_df["Evaluación"] = display_df["score"].round(2)
        display_df["Autoevaluación"] = display_df["auto_score"].round(2)
        display_df["Estado"] = display_df["score"].apply(get_score_status)
        st.dataframe(
            display_df[["lider", "fecha", "Evaluación", "Autoevaluación", "Estado"]]
            .sort_values("fecha", ascending=False)
            .rename(columns={"lider": "Líder", "fecha": "Fecha"}),
            use_container_width=True, hide_index=True,
        )

    # ================================================================
    # URGENCIA PASTORAL
    # ================================================================
    st.markdown(f'<div class="dashboard-section-title">🚨 Prioridad de Seguimiento Pastoral</div>', unsafe_allow_html=True)
    urgencia = build_urgency_summary(df_jovenes, df_asistencia)
    if urgencia:
        urgencia_df = pd.DataFrame(urgencia)[["nombre", "urgencia", "detalle"]]
        urgencia_df.columns = ["Joven", "Urgencia", "Detalle"]

        def badge_html(nivel):
            if nivel == 3:
                return '<span style="background:#dc3545;color:white;padding:2px 10px;border-radius:12px;font-size:0.75rem;">🔴 Alta</span>'
            elif nivel == 2:
                return '<span style="background:#ffc107;color:#131414;padding:2px 10px;border-radius:12px;font-size:0.75rem;">🟡 Media</span>'
            elif nivel == 1:
                return '<span style="background:#17a2b8;color:white;padding:2px 10px;border-radius:12px;font-size:0.75rem;">🔵 Baja</span>'
            return '<span style="background:#28a745;color:white;padding:2px 10px;border-radius:12px;font-size:0.75rem;">🟢 Sin novedad</span>'

        urgencia_df["Prioridad"] = urgencia_df["Urgencia"].apply(badge_html)
        html_rows = "".join(
            f"<tr><td style='padding:6px 12px;'>{row['Joven']}</td>"
            f"<td style='padding:6px 12px;text-align:center;'>{row['Prioridad']}</td>"
            f"<td style='padding:6px 12px;'>{row['Detalle']}</td></tr>"
            for _, row in urgencia_df.iterrows()
        )
        st.markdown(f"""
        <table style="width:100%; border-collapse: collapse; font-size:0.9rem;">
            <thead>
                <tr style="background: {COLORS['primary']}; color: white;">
                    <th style="padding:8px 12px; text-align:left;">Joven</th>
                    <th style="padding:8px 12px; text-align:center;">Prioridad</th>
                    <th style="padding:8px 12px; text-align:left;">Detalle</th>
                </tr>
            </thead>
            <tbody>{html_rows}</tbody>
        </table>
        """, unsafe_allow_html=True)
    else:
        st.success("✅ No hay jóvenes que requieran seguimiento urgente en este momento.")

    # ================================================================
    # CUMPLIMIENTO DE METAS
    # ================================================================
    st.markdown(f'<div class="dashboard-section-title">🎯 Cumplimiento de Metas por Líder</div>', unsafe_allow_html=True)

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("**📅 Asistencia por semana**")
        if not df_asistencia.empty and (df_asistencia["asistio"] == 1).any():
            asistencia_semana = df_asistencia[df_asistencia["asistio"] == 1].copy()
            asistencia_semana["fecha"] = pd.to_datetime(asistencia_semana["fecha"])
            resumen_semanal = (
                asistencia_semana.groupby("fecha").size()
                .reset_index(name="asistentes")
            )

    # ============================================================
    # ASISTENCIA POR SEMANA + CUMPLIMIENTO
    # ============================================================
    st.markdown("---")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("📅 Asistencia por semana")
        if (
            not df_asistencia.empty
            and (df_asistencia["asistio"] == 1).any()
        ):
            asistencia_semana = df_asistencia[
                df_asistencia["asistio"] == 1
            ].copy()
            asistencia_semana["fecha"] = pd.to_datetime(
                asistencia_semana["fecha"]
            )
            asistencia_semana = asistencia_semana.sort_values(by="fecha")
            resumen_semanal = []
            for fecha, grupo in asistencia_semana.groupby("fecha"):
                nombres = []
                for _, row in grupo.iterrows():
                    joven = df_jovenes[
                        df_jovenes["id"] == int(row["joven_id"])
                    ]
                    if not joven.empty:
                        nombres.append(str(joven.iloc[0]["nombre"]))
                resumen_semanal.append(
                    {
                        "semana": fecha.strftime("%Y-%m-%d"),
                        "asistentes": len(grupo),
                        "nombres": ", ".join(nombres),
                    }
                )
            df_semana = pd.DataFrame(resumen_semanal)
            st.dataframe(
                df_semana, use_container_width=True, hide_index=True
            )
            fig_weekly = px.bar(
                df_semana,
                x="semana",
                y="asistentes",
                title="Asistentes por semana",
            )
            st.plotly_chart(fig_weekly, use_container_width=True)
        else:
            st.info("Sin datos suficientes para graficar asistencia.")
    with col_g2:
        st.subheader("🎯 Cumplimiento de Metas por Líder")
        if not df_eval.empty:
            df_lideres = (
                df_eval.groupby("lider")
                .agg(
                    {
                        "puntualidad": "mean",
                        "fidelidad": "mean",
                        "invitados": "sum",
                        "visitados": "sum",
                    }
                )
                .reset_index()
            )
            df_lideres["Puntualidad %"] = (
                df_lideres["puntualidad"] * 100
            )
            df_lideres["Fidelidad %"] = df_lideres["fidelidad"] * 100
            fig_bar = px.bar(
                df_lideres,
                x="lider",
                y=["Puntualidad %", "Fidelidad %"],
                barmode="group",
                title="Porcentaje de cumplimiento de Acuerdos (%)",
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info(
                "Sin datos suficientes para graficar desempeño del equipo."
            )

