"""
agenda.py — Sección Agenda Pastoral
=====================================
Planificación y seguimiento semanal del ministerio juvenil.
Genera eventos pastorales a partir del ÚLTIMO registro de asistencia tomado,
los agrupa por semana (sábado a viernes) y persiste todo en BD.

Cada evento muestra: nombre, contacto (teléfono), prioridad, checkbox
"Realizado" (Sí/No), comentario editable y fecha de cumplimiento.

Por cada semana se muestran: Asistencia (nº de jóvenes), Nuevos (nº) y
% de agenda realizada. Las semanas pasadas se comprimen visualmente
y pueden desplegarse.
"""

from datetime import date, timedelta, datetime

import pandas as pd
import streamlit as st

from config import COLORS
from modules.db import ejecutar_query
from modules.helpers import auto_generate_agenda_tasks


# ================================================================
# UTILIDADES DE SEMANA
# ================================================================
def _get_saturday_week(d):
    """Devuelve el sábado que inicia la semana (sábado a viernes)."""
    days_ahead = 5 - d.weekday()  # Saturday = 5
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def _format_week_label(saturday):
    """Formatea una semana: 'Sáb 01/03 - Vie 07/03/2025'"""
    end = saturday + timedelta(days=6)
    return f"📅 {saturday.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"


def _format_fecha(fecha_str):
    """Formatea una fecha 'YYYY-MM-DD' a 'DD/MM/YYYY'."""
    if not fecha_str:
        return ""
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return fecha_str or ""


def _prioridad_label(prioridad):
    return {3: "🔴 Alta", 2: "🟡 Media", 1: "🔵 Baja"}.get(prioridad, "⚪")


def _prioridad_color(prioridad):
    return {
        3: ("#dc3545", "white"),
        2: ("#ffc107", "#131414"),
        1: ("#17a2b8", "white"),
    }.get(prioridad, ("#17a2b8", "white"))


# ================================================================
# ACCESO A DATOS
# ================================================================
def _load_datos():
    """Carga jóvenes y asistencia desde BD."""
    df_jovenes = pd.DataFrame(
        ejecutar_query("SELECT * FROM jovenes"),
        columns=["id", "nombre", "fec_nac", "celular", "es_nuevo", "fec_reg", "activo"],
    )
    df_asistencia = pd.DataFrame(
        ejecutar_query("SELECT * FROM asistencia"),
        columns=["id", "joven_id", "fecha", "asistio"],
    )
    return df_jovenes, df_asistencia


def _get_visited_recently_ids():
    """Devuelve ids de jóvenes con una visita pastoral completada en el último mes."""
    cutoff = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    rows = ejecutar_query(
        "SELECT joven_nombre, actividad FROM agenda_tareas "
        "WHERE completada = 1 AND fecha_completada >= ?",
        (cutoff,),
    )
    nombres = set()
    for nombre, actividad in rows:
        act = (actividad or "").lower()
        if "visita" in act or "cuidado" in act:
            if nombre:
                nombres.add(nombre)
    if not nombres:
        return set()
    jove = ejecutar_query("SELECT id, nombre FROM jovenes")
    return {i for i, n in jove if n in nombres}


def _generar_tareas(semana_inicio):
    """Genera las tareas/eventos de agenda para una semana."""
    df_jovenes, df_asistencia = _load_datos()
    visited = _get_visited_recently_ids()
    return auto_generate_agenda_tasks(
        df_jovenes, df_asistencia,
        visited_recently_ids=visited,
        semana_inicio=semana_inicio,
    )


def _semana_existe(semana_inicio):
    rows = ejecutar_query(
        "SELECT COUNT(*) FROM agenda_tareas WHERE semana_inicio = ?", (semana_inicio,)
    )
    return rows and rows[0][0] > 0


def _persistir_semana(tasks, semana_inicio):
    """Inserta en BD todos los eventos de una semana (completada=0)."""
    for t in tasks:
        ejecutar_query(
            "INSERT INTO agenda_tareas (actividad, descripcion, prioridad, joven_nombre, "
            "joven_celular, fecha_asignada, semana_inicio, completada, fecha_completada, comentario) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, '')",
            (
                t["actividad"],
                t.get("descripcion", ""),
                t["prioridad"],
                t.get("joven_nombre"),
                t.get("joven_celular"),
                t.get("fecha_asignada", date.today().strftime("%Y-%m-%d")),
                semana_inicio,
            ),
            commit=True, fetch=False,
        )


def _load_weeks():
    """Carga todas las semanas de agenda agrupadas por semana_inicio."""
    rows = ejecutar_query(
        "SELECT id, actividad, descripcion, prioridad, joven_nombre, joven_celular, "
        "fecha_asignada, semana_inicio, completada, fecha_completada, comentario "
        "FROM agenda_tareas ORDER BY semana_inicio DESC"
    )
    if not rows:
        return {}
    semanas = {}
    for r in rows:
        sem = r[7]
        if not sem:
            continue  # Ignorar filas antiguas sin semana
        semanas.setdefault(sem, []).append({
            "id": r[0],
            "actividad": r[1],
            "descripcion": r[2] or "",
            "prioridad": r[3],
            "joven_nombre": r[4],
            "joven_celular": r[5] or "",
            "fecha_asignada": r[6] or "",
            "semana_inicio": r[7] or "",
            "completada": r[8],
            "fecha_completada": r[9] or "",
            "comentario": r[10] or "",
        })
    return semanas


def _update_completada(task_id, valor):
    fecha = date.today().strftime("%Y-%m-%d") if valor else None
    ejecutar_query(
        "UPDATE agenda_tareas SET completada = ?, fecha_completada = ? WHERE id = ?",
        (1 if valor else 0, fecha, task_id), commit=True, fetch=False,
    )


def _update_comentario(task_id, comentario):
    ejecutar_query(
        "UPDATE agenda_tareas SET comentario = ? WHERE id = ?",
        (comentario, task_id), commit=True, fetch=False,
    )


def _stats_semana(semana_inicio):
    """Calcula (asistencia, nuevos) para una semana según el último registro de asistencia."""
    sat = datetime.strptime(semana_inicio, "%Y-%m-%d").date()
    end = sat + timedelta(days=6)
    df_jovenes, df_asistencia = _load_datos()
    if df_asistencia.empty:
        return 0, 0
    df_a = df_asistencia.copy()
    df_a["fecha"] = pd.to_datetime(df_a["fecha"], errors="coerce")
    df_a = df_a.dropna(subset=["fecha"])
    if df_a.empty:
        return 0, 0
    df_week = df_a[
        (df_a["fecha"] >= pd.Timestamp(sat.isoformat()))
        & (df_a["fecha"] <= pd.Timestamp(end.isoformat()))
    ]
    if df_week.empty:
        return 0, 0
    ultima = df_week["fecha"].max()
    df_ult = df_week[df_week["fecha"] == ultima]
    presentes = set(df_ult[df_ult["asistio"] == 1]["joven_id"])
    count_asistencia = len(presentes)
    count_nuevos = 0
    if not df_jovenes.empty:
        nuevos = set(df_jovenes[df_jovenes["es_nuevo"] == 1]["id"])
        count_nuevos = len(presentes & nuevos)
    return count_asistencia, count_nuevos


# ================================================================
# RENDER DE EVENTOS
# ================================================================
def _display_tarea(t):
    """Renderiza un solo evento con nombre, contacto, prioridad, realizado y comentario."""
    task_id = t["id"]
    is_done = bool(t["completada"])

    prio_class = {
        3: "agenda-priority-high",
        2: "agenda-priority-medium",
        1: "agenda-priority-low",
    }.get(t["prioridad"], "agenda-priority-low")
    done_class = "done" if is_done else ""
    prio_color, prio_text = _prioridad_color(t["prioridad"])
    prio_label = _prioridad_label(t["prioridad"])

    nombre = t.get("joven_nombre") or "—"
    celular = t.get("joven_celular") or "—"

    fecha_comp_html = ""
    if is_done and t.get("fecha_completada"):
        fecha_comp_html = (
            f'<div style="font-size:0.75rem; color:{COLORS["success"]}; margin-top:2px;">'
            f'✅ Realizado el {_format_fecha(t["fecha_completada"])}</div>'
        )

    descripcion_html = ""
    if t.get("descripcion"):
        descripcion_html = (
            f'<div style="font-size:0.8rem; color:#999; margin-top:2px;">{t["descripcion"]}</div>'
        )

    estado_html = (
        f'<span style="font-size:0.7rem; color:{COLORS["success"]};">✅ Sí</span>'
        if is_done else
        f'<span style="font-size:0.7rem; color:{COLORS["danger"]};">⬜ No</span>'
    )

    col_chk, col_content = st.columns([0.15, 0.85])
    with col_chk:
        checked = st.checkbox(
            "Realizado", value=is_done, key=f"done_{task_id}",
            label_visibility="collapsed",
        )
        if checked != is_done:
            _update_completada(task_id, checked)
            st.rerun()

    with col_content:
        st.markdown(
            f'<div class="agenda-item {prio_class} {done_class}">'
            f'<div style="flex:1; min-width:0;">'
            f'<div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">'
            f'<span style="font-weight:600; font-size:0.95rem;">👤 {nombre}</span>'
            f'<span style="font-size:0.65rem; padding:1px 6px; border-radius:10px; '
            f'background:{prio_color}; color:{prio_text};">{prio_label}</span>'
            f'{estado_html}'
            f'</div>'
            f'<div style="font-size:0.8rem; color:#666; margin-top:2px;">'
            f'📱 {celular} · <strong>{t["actividad"]}</strong></div>'
            f'{descripcion_html}'
            f'{fecha_comp_html}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    # Fila de comentario
    col_cmt, col_btn = st.columns([0.85, 0.15])
    with col_cmt:
        st.text_input(
            "Comentario", value=t.get("comentario", ""),
            key=f"com_{task_id}", placeholder="Agregar comentario...",
        )
    with col_btn:
        if st.button("💾", key=f"save_{task_id}", help="Guardar comentario", use_container_width=True):
            _update_comentario(task_id, st.session_state.get(f"com_{task_id}", ""))
            st.rerun()

    st.markdown('<div style="height:0.4rem;"></div>', unsafe_allow_html=True)


def _display_semana(tareas, filtro_prioridad):
    """Renderiza la lista de eventos de una semana aplicando filtros."""
    tareas_f = [t for t in tareas if t["prioridad"] in filtro_prioridad]
    if not tareas_f:
        st.caption("Sin eventos para los filtros seleccionados.")
        return
    tareas_f.sort(key=lambda t: (-t["prioridad"], t.get("joven_nombre") or ""))
    for t in tareas_f:
        _display_tarea(t)


# ================================================================
# RENDER PRINCIPAL
# ================================================================
def render_agenda():
    """Renderiza la sección de Agenda Pastoral agrupada por semana."""
    st.markdown("""
    <style>
    .agenda-item {
        display: flex; align-items: center; gap: 0.8rem;
        padding: 0.6rem 0.8rem; border-radius: 8px;
        background: white; border: 1px solid #eee;
        margin-bottom: 0.4rem; transition: all 0.2s;
    }
    .agenda-item.done {
        background: #f0f9f0; border-color: #28a745; opacity: 0.85;
    }
    .agenda-priority-high { border-left: 4px solid #dc3545; }
    .agenda-priority-medium { border-left: 4px solid #ffc107; }
    .agenda-priority-low { border-left: 4px solid #17a2b8; }
    .week-group-header {
        background: linear-gradient(135deg, #0f2645 0%, #1a3a6b 100%);
        color: white; padding: 0.7rem 1rem; border-radius: 8px;
        margin: 1rem 0 0.5rem 0;
    }
    .week-stats {
        display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.4rem;
    }
    .week-stat {
        background: rgba(255,255,255,0.15); border-radius: 6px;
        padding: 0.2rem 0.8rem; font-size: 0.8rem;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="section-header">
        <h2>📋 Agenda Pastoral</h2>
        <p>Eventos de seguimiento semanal generados desde el último registro de asistencia</p>
    </div>
""", unsafe_allow_html=True)

    # Semana actual basada en el ÚLTIMO registro de asistencia tomado.
    # Si no hay asistencias, se usa la fecha de hoy.
    hoy = date.today()
    df_ref, df_asist_ref = _load_datos()
    fecha_referencia = hoy
    if not df_asist_ref.empty:
        df_tmp = df_asist_ref.copy()
        df_tmp["fecha"] = pd.to_datetime(df_tmp["fecha"], errors="coerce")
        df_tmp = df_tmp.dropna(subset=["fecha"])
        if not df_tmp.empty:
            fecha_referencia = df_tmp["fecha"].max().date()

    semana_actual = _get_saturday_week(fecha_referencia)
    semana_inicio = semana_actual.strftime("%Y-%m-%d")

    # Generar la semana actual si aún no existe en BD
    if not _semana_existe(semana_inicio):
        tasks = _generar_tareas(semana_inicio)
        _persistir_semana(tasks, semana_inicio)

    semanas = _load_weeks()

    # Filtro por prioridad
    st.sidebar.markdown("### 📅 Filtros de Agenda")
    filtro_prioridad = st.sidebar.multiselect(
        "Prioridad",
        options=[1, 2, 3],
        format_func=lambda x: {1: "🔵 Baja", 2: "🟡 Media", 3: "🔴 Alta"}.get(x, str(x)),
        default=[1, 2, 3],
        key="agenda_filtro_prioridad",
    )

    # Agregar evento manual (semana actual)
    with st.expander("➕ Agregar evento manual", expanded=False):
        with st.form("form_nuevo_evento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                man_nombre = st.text_input("Nombre:", placeholder="Ej: Juan Pérez")
                man_actividad = st.text_input("Actividad:", placeholder="Ej: Visita especial")
            with col2:
                man_contacto = st.text_input("📱 Contacto:", placeholder="Ej: 3001234567")
                man_descripcion = st.text_input("Descripción:", placeholder="Contexto del evento")
            man_prioridad = st.selectbox(
                "Prioridad:", options=[1, 2, 3],
                format_func=lambda x: {1: "🔵 Baja", 2: "🟡 Media", 3: "🔴 Alta"}.get(x, str(x)),
            )
            man_btn = st.form_submit_button("➕ Agregar", use_container_width=True)
        if man_btn and (man_nombre.strip() or man_actividad.strip()):
            ejecutar_query(
                "INSERT INTO agenda_tareas (actividad, descripcion, prioridad, joven_nombre, "
                "joven_celular, fecha_asignada, semana_inicio, completada, fecha_completada, comentario) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, '')",
                (
                    man_actividad.strip() or "Evento manual",
                    man_descripcion.strip() or "",
                    man_prioridad,
                    man_nombre.strip() or None,
                    man_contacto.strip() or None,
                    hoy.strftime("%Y-%m-%d"),
                    semana_inicio,
                ),
                commit=True, fetch=False,
            )
            st.success("✅ Evento agregado exitosamente.")
            st.rerun()

    st.markdown("---")

    if not semanas:
        st.info("No hay eventos en la agenda. 🎉")
        return

    # Mostrar semanas (actual expandida, pasadas colapsadas)
    for sem in list(semanas.keys()):
        tareas = semanas[sem]
        sat = _get_saturday_week(datetime.strptime(sem, "%Y-%m-%d").date())
        label = _format_week_label(sat)
        asistencia_count, nuevos_count = _stats_semana(sem)
        total = len(tareas)
        realizadas = sum(1 for t in tareas if t["completada"] == 1)
        pct = round((realizadas / total) * 100) if total else 0
        is_current = (sem == semana_inicio)

        st.markdown(
            f'<div class="week-group-header">'
            f'<div style="font-weight:600;">{label}'
            f'{"" if is_current else " · " + str(pct) + "% realizado"}</div>'
            f'<div class="week-stats">'
            f'<span class="week-stat">👥 Asistencia: {asistencia_count}</span>'
            f'<span class="week-stat">🌟 Nuevos: {nuevos_count}</span>'
            f'<span class="week-stat">📌 Total agenda: {total}</span>'
            f'<span class="week-stat">✅ Realizado: {realizadas} ({pct}%)</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if is_current:
            _display_semana(tareas, filtro_prioridad)
        else:
            with st.expander(f"Ver detalles de esta semana", expanded=False):
                _display_semana(tareas, filtro_prioridad)
