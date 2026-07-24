"""
dashboard.py — Sección Dashboard (vista ejecutiva)
====================================================
Panel de indicadores clave con KPIs, gráficos de asistencia,
evaluación de equipo, mapa de calor, urgencia pastoral y exportación.
"""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from config import COLORS, CUSTOM_CSS
from modules.db import ejecutar_query
from modules.helpers import (
    calculate_evaluation_score,
    calculate_auto_evaluation_score,
    get_score_status,
    build_urgency_summary,
)


def render_dashboard():
    """Renderiza el dashboard ejecutivo con KPIs, gráficos y tablas."""

    # ============================================================
    # CSS específico del Dashboard
    # ============================================================
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ============================================================
    # TÍTULO
    # ============================================================
    st.markdown(
        "<h1 style='color:#0f2645; margin-bottom:0;'>📊 Dashboard Ejecutivo</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#666; margin-top:0;'>Panel de indicadores clave del ministerio juvenil</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ============================================================
    # CARGA DE DATOS
    # ============================================================
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
        df_eval["estado"] = df_eval["score"].apply(get_score_status)

    if not df_asistencia.empty:
        df_asistencia["fecha"] = pd.to_datetime(
            df_asistencia["fecha"], errors="coerce"
        )
        df_asistencia = df_asistencia.dropna(subset=["fecha"])

    # ============================================================
    # FILTROS
    # ============================================================
    st.sidebar.markdown("### 🔍 Filtros del Dashboard")
    with st.sidebar:
        preset_elegido = "personalizado"
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            if st.button("📅 7d", key="preset_7d", use_container_width=True):
                preset_elegido = "7d"
        with col_p2:
            if st.button("📅 30d", key="preset_30d", use_container_width=True):
                preset_elegido = "30d"
        with col_p3:
            if st.button("📅 90d", key="preset_90d", use_container_width=True):
                preset_elegido = "90d"

        if preset_elegido == "7d":
            default_inicio = date.today() - timedelta(days=7)
        elif preset_elegido == "30d":
            default_inicio = date.today() - timedelta(days=30)
        elif preset_elegido == "90d":
            default_inicio = date.today() - timedelta(days=90)
        else:
            default_inicio = date.today() - timedelta(days=90)

        fecha_inicio = st.date_input(
            "Fecha inicial", value=default_inicio, key="dash_fecha_ini"
        )
        fecha_fin = st.date_input(
            "Fecha final", value=date.today(), key="dash_fecha_fin"
        )

        if isinstance(fecha_inicio, (list, tuple)):
            fecha_inicio = fecha_inicio[0]
        if isinstance(fecha_fin, (list, tuple)):
            fecha_fin = fecha_fin[0]
        if fecha_inicio > fecha_fin:
            fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

        if not df_eval.empty:
            lideres_disp = sorted(
                [v for v in df_eval["lider"].dropna().astype(str).unique() if v]
            )
            lideres_sel = st.multiselect(
                "Líderes", lideres_disp, default=lideres_disp, key="dash_lideres"
            )
        else:
            lideres_sel = []

    # --- Aplicar filtros ---
    df_eval_filtrado = df_eval.copy() if not df_eval.empty else df_eval
    if not df_eval_filtrado.empty:
        mask_fecha = (
            df_eval_filtrado["fecha"].dt.date >= fecha_inicio
        ) & (df_eval_filtrado["fecha"].dt.date <= fecha_fin)
        if lideres_sel:
            mask_lider = df_eval_filtrado["lider"].astype(str).isin(lideres_sel)
            df_eval_filtrado = df_eval_filtrado[mask_fecha & mask_lider]
        else:
            df_eval_filtrado = df_eval_filtrado[mask_fecha]

    df_asistencia_filtrada = (
        df_asistencia.copy() if not df_asistencia.empty else df_asistencia
    )
    if not df_asistencia_filtrada.empty:
        mask_asist = (
            df_asistencia_filtrada["fecha"].dt.date >= fecha_inicio
        ) & (df_asistencia_filtrada["fecha"].dt.date <= fecha_fin)
        df_asistencia_filtrada = df_asistencia_filtrada[mask_asist]

    # ============================================================
    # KPIs
    # ============================================================
    jovenes_activos = (
        len(df_jovenes[df_jovenes["activo"] == 1]) if not df_jovenes.empty else 0
    )
    total_nuevos = int(df_jovenes["es_nuevo"].sum()) if not df_jovenes.empty else 0

    prom_asistencia = 0
    if (
        not df_asistencia_filtrada.empty
        and (df_asistencia_filtrada["asistio"] == 1).any()
    ):
        prom_asistencia = (
            df_asistencia_filtrada[df_asistencia_filtrada["asistio"] == 1]
            .groupby("fecha")
            .size()
            .mean()
        )

    score_equipo = (
        float(df_eval_filtrado["score"].mean()) if not df_eval_filtrado.empty else 0
    )

    kpi_html = f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <div class="kpi-label">👥 Miembros Activos</div>
            <div class="kpi-value">{jovenes_activos}</div>
            <div class="kpi-sub">Total de jóvenes registrados</div>
        </div>
        <div class="kpi-card" style="background: linear-gradient(135deg, #1a3a6b 0%, {COLORS['secondary']}aa 100%);">
            <div class="kpi-label">⭐ Nuevos Captados</div>
            <div class="kpi-value">{total_nuevos}</div>
            <div class="kpi-sub">Histórico de nuevos creyentes</div>
        </div>
        <div class="kpi-card" style="background: linear-gradient(135deg, {COLORS['primary']} 0%, #2a5a9b 100%);">
            <div class="kpi-label">📊 Asistencia Promedio</div>
            <div class="kpi-value">{prom_asistencia:.1f}</div>
            <div class="kpi-sub">Por sábado (período seleccionado)</div>
        </div>
        <div class="kpi-card" style="background: linear-gradient(135deg, #1a3a6b 0%, #3a7abd 100%);">
            <div class="kpi-label">🏆 Score Equipo</div>
            <div class="kpi-value">{score_equipo:.1f}</div>
            <div class="kpi-sub">/ 5.0 · {"✅ Aceptable" if score_equipo >= 4 else "⚠️ Requiere mejora"}</div>
        </div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    # ============================================================
    # FILA 1: ASISTENCIA POR SEMANA + MAPA DE CALOR
    # ============================================================
    st.markdown(
        '<div class="dashboard-section-title">📅 Análisis de Asistencia</div>',
        unsafe_allow_html=True,
    )

    col_asist1, col_asist2 = st.columns(2)

    with col_asist1:
        st.markdown("**Asistencia por semana**")
        if (
            not df_asistencia_filtrada.empty
            and (df_asistencia_filtrada["asistio"] == 1).any()
        ):
            asist_semana = df_asistencia_filtrada[
                df_asistencia_filtrada["asistio"] == 1
            ].copy()
            asist_semana = asist_semana.sort_values("fecha")
            resumen_semanal = (
                asist_semana.groupby("fecha")
                .size()
                .reset_index(name="asistentes")
            )
            resumen_semanal["semana"] = resumen_semanal["fecha"].dt.strftime(
                "%Y-%m-%d"
            )

            fig_asist = px.bar(
                resumen_semanal,
                x="semana",
                y="asistentes",
                text="asistentes",
                color="asistentes",
                color_continuous_scale=[
                    COLORS["secondary"],
                    COLORS["primary"],
                ],
                labels={"semana": "Semana", "asistentes": "Jóvenes"},
            )
            fig_asist.update_traces(
                textposition="outside", marker_line_width=0
            )
            fig_asist.update_layout(
                height=280,
                margin=dict(l=10, r=10, t=10, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
                xaxis=dict(showgrid=False),
                yaxis=dict(
                    showgrid=True, gridcolor="rgba(0,0,0,0.06)"
                ),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_asist, use_container_width=True)

            with st.expander("📋 Ver lista de asistentes por semana"):
                for fecha, grupo in asist_semana.groupby("fecha"):
                    nombres = []
                    for _, row in grupo.iterrows():
                        joven = df_jovenes[
                            df_jovenes["id"] == int(row["joven_id"])
                        ]
                        if not joven.empty:
                            nombres.append(str(joven.iloc[0]["nombre"]))
                    st.markdown(
                        f"**{fecha.strftime('%Y-%m-%d')}** ({len(grupo)} asistentes): {', '.join(nombres)}"
                    )
        else:
            st.info("Sin datos de asistencia en el período.")

    with col_asist2:
        st.markdown("**Distribución de asistencia**")
        if not df_asistencia_filtrada.empty:
            total_registros = len(df_asistencia_filtrada)
            presentes = int(df_asistencia_filtrada["asistio"].sum())
            ausentes = total_registros - presentes
            dist_df = pd.DataFrame(
                {
                    "Estado": ["✅ Presentes", "❌ Ausentes"],
                    "Cantidad": [presentes, ausentes],
                }
            )
            fig_pie_asist = px.pie(
                dist_df,
                names="Estado",
                values="Cantidad",
                color="Estado",
                color_discrete_map={
                    "✅ Presentes": COLORS["success"],
                    "❌ Ausentes": COLORS["danger"],
                },
                hole=0.5,
            )
            fig_pie_asist.update_traces(
                textinfo="label+percent", textposition="outside"
            )
            fig_pie_asist.update_layout(
                height=280,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
                showlegend=False,
            )
            st.plotly_chart(fig_pie_asist, use_container_width=True)
        else:
            st.info("Sin datos de asistencia.")

    # ============================================================
    # HEATMAP DE ASISTENCIA POR JOVEN
    # ============================================================
    if not df_asistencia_filtrada.empty and not df_jovenes.empty:
        st.markdown(
            '<div class="dashboard-section-title">🔥 Mapa de Calor de Asistencia</div>',
            unsafe_allow_html=True,
        )
        asist_pivot = df_asistencia_filtrada.pivot_table(
            index="joven_id",
            columns="fecha",
            values="asistio",
            aggfunc="max",
            fill_value=0,
        )
        if not asist_pivot.empty:
            nombre_map = dict(zip(df_jovenes["id"], df_jovenes["nombre"]))
            asist_pivot.index = asist_pivot.index.map(
                lambda x: nombre_map.get(int(x), f"ID {x}")
            )
            asist_pivot.columns = [
                c.strftime("%Y-%m-%d") for c in asist_pivot.columns
            ]

            fig_heatmap = px.imshow(
                asist_pivot,
                text_auto=False,
                color_continuous_scale=[
                    COLORS["danger"],
                    COLORS["secondary"],
                    COLORS["success"],
                ],
                labels={
                    "color": "Asistió",
                    "x": "Fecha",
                    "y": "Joven",
                },
                aspect="auto",
            )
            fig_heatmap.update_layout(
                height=250 + (len(asist_pivot) * 20),
                margin=dict(l=10, r=10, t=10, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(size=10),
                xaxis=dict(side="top", tickangle=-45),
                yaxis=dict(tickfont=dict(size=9)),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)
            st.caption(
                "🟢 Verde = Asistió · 🟡 Amarillo = Ausente con historial · 🔴 Rojo = Ausente recurrente"
            )

    # ============================================================
    # FILA 2: EVALUACIÓN POR LÍDER
    # ============================================================
    st.markdown(
        '<div class="dashboard-section-title">🏆 Rendimiento del Equipo</div>',
        unsafe_allow_html=True,
    )

    col_eval1, col_eval2 = st.columns(2)

    with col_eval1:
        st.markdown("**Evaluación por líder (promedio)**")
        if not df_eval_filtrado.empty:
            lider_summary = (
                df_eval_filtrado.groupby("lider", as_index=False)
                .agg(
                    puntaje_promedio=("score", "mean"),
                    autoevaluacion_promedio=("auto_score", "mean"),
                )
                .sort_values("puntaje_promedio", ascending=False)
            )
            fig_lider = px.bar(
                lider_summary,
                x="lider",
                y=["puntaje_promedio", "autoevaluacion_promedio"],
                barmode="group",
                color_discrete_map={
                    "puntaje_promedio": COLORS["primary"],
                    "autoevaluacion_promedio": COLORS["secondary"],
                },
                labels={
                    "value": "Puntaje (0-5)",
                    "lider": "Líder",
                    "variable": "Tipo",
                },
            )
            fig_lider.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                ),
                yaxis=dict(
                    range=[0, 5.5], gridcolor="rgba(0,0,0,0.06)"
                ),
                xaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig_lider, use_container_width=True)
        else:
            st.info("Sin evaluaciones registradas.")

    with col_eval2:
        st.markdown("**Distribución de estados**")
        if not df_eval_filtrado.empty:
            estado_counts = (
                df_eval_filtrado["estado"]
                .value_counts()
                .reset_index()
            )
            estado_counts.columns = ["Estado", "Cantidad"]
            fig_estado = px.pie(
                estado_counts,
                names="Estado",
                values="Cantidad",
                color="Estado",
                color_discrete_map={
                    "Aceptable": COLORS["success"],
                    "Requiere mejora": COLORS["danger"],
                },
                hole=0.5,
            )
            fig_estado.update_traces(
                textinfo="label+percent", textposition="outside"
            )
            fig_estado.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
                showlegend=False,
            )
            st.plotly_chart(fig_estado, use_container_width=True)
        else:
            st.info("Sin evaluaciones registradas.")

    # ============================================================
    # FILA 3: TENDENCIAS
    # ============================================================
    if not df_eval_filtrado.empty:
        st.markdown(
            '<div class="dashboard-section-title">📈 Tendencias</div>',
            unsafe_allow_html=True,
        )
        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.markdown("**Tendencia de evaluación**")
            trend_eval = (
                df_eval_filtrado.groupby(
                    df_eval_filtrado["fecha"].dt.strftime("%Y-%m-%d"),
                    as_index=False,
                )
                .agg(Puntaje=("score", "mean"))
                .rename(columns={"fecha": "periodo"})
            )
            fig_trend = px.line(
                trend_eval,
                x="periodo",
                y="Puntaje",
                markers=True,
                color_discrete_sequence=[COLORS["primary"]],
            )
            fig_trend.update_traces(
                line=dict(width=3), marker=dict(size=8)
            )
            fig_trend.add_hline(
                y=4,
                line_dash="dash",
                line_color=COLORS["secondary"],
                annotation_text="Mínimo aceptable (4.0)",
                annotation_position="bottom right",
            )
            fig_trend.update_layout(
                height=280,
                margin=dict(l=10, r=10, t=10, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
                yaxis=dict(
                    range=[0, 5.5], gridcolor="rgba(0,0,0,0.06)"
                ),
                xaxis=dict(showgrid=False),
                hovermode="x unified",
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        with col_t2:
            st.markdown("**Tendencia de autoevaluación**")
            auto_trend = (
                df_eval_filtrado.groupby(
                    df_eval_filtrado["fecha"].dt.strftime("%Y-%m-%d"),
                    as_index=False,
                )
                .agg(Autoevaluación=("auto_score", "mean"))
                .rename(columns={"fecha": "periodo"})
            )
            fig_auto_trend = px.line(
                auto_trend,
                x="periodo",
                y="Autoevaluación",
                markers=True,
                color_discrete_sequence=[COLORS["secondary"]],
            )
            fig_auto_trend.update_traces(
                line=dict(width=3), marker=dict(size=8)
            )
            fig_auto_trend.add_hline(
                y=4,
                line_dash="dash",
                line_color=COLORS["primary"],
                annotation_text="Mínimo aceptable (4.0)",
                annotation_position="bottom right",
            )
            fig_auto_trend.update_layout(
                height=280,
                margin=dict(l=10, r=10, t=10, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(size=11),
                yaxis=dict(
                    range=[0, 5.5], gridcolor="rgba(0,0,0,0.06)"
                ),
                xaxis=dict(showgrid=False),
                hovermode="x unified",
            )
            st.plotly_chart(fig_auto_trend, use_container_width=True)
    else:
        st.info("No hay datos de evaluación para mostrar tendencias.")

    # ============================================================
    # FILA 4: CUMPLIMIENTO DE METAS
    # ============================================================
    if not df_eval_filtrado.empty:
        st.markdown(
            '<div class="dashboard-section-title">🎯 Cumplimiento de Metas por Líder</div>',
            unsafe_allow_html=True,
        )
        df_metas = (
            df_eval_filtrado.groupby("lider")
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
        df_metas["Puntualidad %"] = (
            df_metas["puntualidad"] * 100
        ).round(1)
        df_metas["Fidelidad %"] = (df_metas["fidelidad"] * 100).round(1)

        fig_metas = px.bar(
            df_metas,
            x="lider",
            y=["Puntualidad %", "Fidelidad %"],
            barmode="group",
            color_discrete_map={
                "Puntualidad %": COLORS["primary"],
                "Fidelidad %": COLORS["secondary"],
            },
            text_auto=".1f",
            labels={
                "value": "Porcentaje",
                "lider": "Líder",
                "variable": "Métrica",
            },
        )
        fig_metas.update_traces(textposition="outside")
        fig_metas.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=10, b=30),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            yaxis=dict(
                range=[0, 110], gridcolor="rgba(0,0,0,0.06)"
            ),
            xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_metas, use_container_width=True)

        st.markdown("**Invitados y visitados por líder**")
        inv_vis_df = df_metas[["lider", "invitados", "visitados"]].copy()
        inv_vis_df.columns = ["Líder", "👥 Invitados", "🏠 Visitados"]
        st.dataframe(
            inv_vis_df, use_container_width=True, hide_index=True
        )

    # ============================================================
    # FILA 5: URGENCIA PASTORAL
    # ============================================================
    st.markdown(
        '<div class="dashboard-section-title">🚨 Prioridad de Seguimiento Pastoral</div>',
        unsafe_allow_html=True,
    )
    urgencia = build_urgency_summary(df_jovenes, df_asistencia)
    if urgencia:
        urgencia_df = pd.DataFrame(urgencia)

        def badge_html(nivel):
            if nivel == 3:
                return '<span class="urgency-badge badge-alta">🔴 Alta</span>'
            elif nivel == 2:
                return '<span class="urgency-badge badge-media">🟡 Media</span>'
            elif nivel == 1:
                return '<span class="urgency-badge badge-baja">🔵 Baja</span>'
            return '<span class="urgency-badge badge-ok">🟢 Sin novedad</span>'

        urgencia_df["Prioridad"] = urgencia_df["urgencia"].apply(
            badge_html
        )
        urgencia_display = urgencia_df[
            ["nombre", "Prioridad", "detalle"]
        ].copy()
        urgencia_display.columns = ["Joven", "Prioridad", "Detalle"]

        html_rows = ""
        for _, row in urgencia_display.iterrows():
            html_rows += f"<tr><td>{row['Joven']}</td><td>{row['Prioridad']}</td><td>{row['Detalle']}</td></tr>"

        st.markdown(
            f"""
            <table style="width:100%; border-collapse: collapse; font-size:0.9rem;">
                <thead>
                    <tr style="background: {COLORS['primary']}; color: white;">
                        <th style="padding:8px 12px; text-align:left;">Joven</th>
                        <th style="padding:8px 12px; text-align:center;">Prioridad</th>
                        <th style="padding:8px 12px; text-align:left;">Detalle</th>
                    </tr>
                </thead>
                <tbody>
                    {html_rows}
                </tbody>
            </table>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.success(
            "✅ No hay jóvenes que requieran seguimiento urgente en este momento."
        )

    # ============================================================
    # FILA 6: REGISTROS DETALLADOS
    # ============================================================
    st.markdown(
        '<div class="dashboard-section-title">🧾 Registros Detallados de Evaluación</div>',
        unsafe_allow_html=True,
    )

    if not df_eval_filtrado.empty:
        display_df = df_eval_filtrado[
            ["lider", "fecha", "score", "auto_score", "estado"]
        ].copy()
        display_df["fecha"] = display_df["fecha"].dt.strftime("%Y-%m-%d")
        display_df["estado_eval"] = display_df["estado"]
        display_df["estado_auto"] = display_df["auto_score"].apply(
            get_score_status
        )
        display_df = display_df.rename(
            columns={
                "lider": "Líder",
                "fecha": "Fecha",
                "score": "Evaluación",
                "auto_score": "Autoevaluación",
            }
        )
        display_df = display_df[
            [
                "Líder",
                "Fecha",
                "Evaluación",
                "Autoevaluación",
                "estado_eval",
                "estado_auto",
            ]
        ]
        display_df["Evaluación"] = display_df["Evaluación"].round(2)
        display_df["Autoevaluación"] = display_df[
            "Autoevaluación"
        ].round(2)

        def color_status(val):
            if val == "Aceptable":
                return f'<span class="status-acceptable">✅ {val}</span>'
            return f'<span class="status-improve">⚠️ {val}</span>'

        html_table = "<table style='width:100%; border-collapse: collapse; font-size:0.85rem;'>"
        html_table += "<thead><tr style='background: #0f2645; color: white;'><th style='padding:8px;'>Líder</th><th style='padding:8px;'>Fecha</th><th style='padding:8px;'>Evaluación</th><th style='padding:8px;'>Autoevaluación</th><th style='padding:8px;'>Estado Eval</th><th style='padding:8px;'>Estado Auto</th></tr></thead><tbody>"
        for _, row in display_df.sort_values(
            "Fecha", ascending=False
        ).iterrows():
            html_table += "<tr style='border-bottom: 1px solid #e2e2df;'>"
            html_table += f"<td style='padding:6px 8px;'>{row['Líder']}</td>"
            html_table += f"<td style='padding:6px 8px;'>{row['Fecha']}</td>"
            html_table += f"<td style='padding:6px 8px;'>{row['Evaluación']}</td>"
            html_table += f"<td style='padding:6px 8px;'>{row['Autoevaluación']}</td>"
            html_table += f"<td style='padding:6px 8px;'>{color_status(row['estado_eval'])}</td>"
            html_table += f"<td style='padding:6px 8px;'>{color_status(row['estado_auto'])}</td>"
            html_table += "</tr>"
        html_table += "</tbody></table>"
        st.markdown(html_table, unsafe_allow_html=True)
    else:
        st.info("No hay registros de evaluación para mostrar.")

    # ============================================================
    # EXPORTAR DATOS
    # ============================================================
    st.markdown("---")
    st.markdown(
        '<div class="dashboard-section-title">📥 Exportar Datos</div>',
        unsafe_allow_html=True,
    )

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if not df_eval_filtrado.empty:
            csv_eval = (
                df_eval_filtrado[
                    [
                        "lider",
                        "fecha",
                        "score",
                        "auto_score",
                        "puntualidad",
                        "fidelidad",
                        "invitados",
                        "visitados",
                    ]
                ]
                .to_csv(index=False)
                .encode("utf-8")
            )
            st.download_button(
                label="📄 Descargar Evaluación (CSV)",
                data=csv_eval,
                file_name=f"evaluacion_equipo_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with col_dl2:
        if not df_asistencia_filtrada.empty and not df_jovenes.empty:
            asist_export = df_asistencia_filtrada.copy()
            asist_export["nombre"] = asist_export["joven_id"].map(
                dict(zip(df_jovenes["id"], df_jovenes["nombre"]))
            )
            asist_export["fecha"] = asist_export["fecha"].dt.strftime(
                "%Y-%m-%d"
            )
            asist_export["asistio"] = asist_export["asistio"].map(
                {1: "Sí", 0: "No"}
            )
            csv_asist = (
                asist_export[["nombre", "fecha", "asistio"]]
                .to_csv(index=False)
                .encode("utf-8")
            )
            st.download_button(
                label="📄 Descargar Asistencia (CSV)",
                data=csv_asist,
                file_name=f"asistencia_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

