"""
agenda.py — Sección Agenda
============================
Planificación y seguimiento de tareas semanales del ministerio juvenil.
Genera tareas automáticas basadas en inasistencias, permite marcar
tareas como completadas, agregar tareas manuales y filtrar por prioridad.
Las tareas completadas se persisten en BD con fecha de cumplimiento
y se agrupan por semanas (sábado a sábado).
"""

from datetime import date, timedelta, datetime

import pandas as pd
import streamlit as st

from config import COLORS
from modules.db import ejecutar_query
from modules.helpers import auto_generate_agenda_tasks


def _get_saturday_week(d):
    """Devuelve el sábado más cercano que inicia la semana (sábado a viernes)."""
    days_ahead = 5 - d.weekday()  # Saturday = 5
    if days_ahead <= 0:
        days_ahead += 7
    saturday = d + timedelta(days=days_ahead)
    return saturday


def _format_week_label(saturday):
    """Formatea una semana: 'Sáb 01/03 - Vie 07/03/2025'"""
    end = saturday + timedelta(days=6)
    return f"📅 {saturday.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"


def _load_completed_tasks():
    """Carga las tareas completadas desde la BD."""
    rows = ejecutar_query(
        "SELECT id, actividad, descripcion, prioridad, joven_nombre, "
        "fecha_asignada, completada, fecha_completada "
        "FROM agenda_tareas WHERE completada = 1 ORDER BY fecha_completada DESC"
    )
    if not rows:
        return []
    return [
        {
            "id": r[0],
            "actividad": r[1],
            "descripcion": r[2] or "",
            "prioridad": r[3],
            "joven_nombre": r[4],
            "fecha_asignada": r[5] or "",
            "fecha_completada": r[7] or "",
        }
        for r in rows
    ]


def _save_completed_task(task_data):
    """Persiste una tarea completada en BD (insert o update)."""
    # Upsert: si ya existe con misma actividad+fecha_asignada, actualizar
    existing = ejecutar_query(
        "SELECT id FROM agenda_tareas WHERE actividad = ? AND fecha_asignada = ? AND completada = 0",
        (task_data["actividad"], task_data.get("fecha_asignada", "")),
    )
    today_str = date.today().strftime("%Y-%m-%d")

    if existing:
        ejecutar_query(
            "UPDATE agenda_tareas SET completada = 1, fecha_completada = ? WHERE id = ?",
            (today_str, existing[0][0]),
            commit=True, fetch=False,
        )
    else:
        ejecutar_query(
            "INSERT INTO agenda_tareas (actividad, descripcion, prioridad, joven_nombre, "
            "fecha_asignada, completada, fecha_completada) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (
                task_data["actividad"],
                task_data.get("descripcion", ""),
                task_data["prioridad"],
                task_data.get("joven_nombre"),
                task_data.get("fecha_asignada", today_str),
                today_str,
            ),
            commit=True, fetch=False,
        )


def _uncomplete_task(task_data):
    """Marca una tarea como NO completada (elimina el registro de BD o marca 0)."""
    existing = ejecutar_query(
        "SELECT id FROM agenda_tareas WHERE actividad = ? AND fecha_asignada = ? AND completada = 1",
        (task_data["actividad"], task_data.get("fecha_asignada", "")),
    )
    if existing:
        ejecutar_query(
            "UPDATE agenda_tareas SET completada = 0, fecha_completada = NULL WHERE id = ?",
            (existing[0][0],),
            commit=True, fetch=False,
        )


def _init_agenda_state():
    if "agenda_tareas_manuales" not in st.session_state:
        st.session_state["agenda_tareas_manuales"] = []


def _generar_tareas():
    """Obtiene los datos de BD y genera las tareas de agenda automáticas."""
    df_jovenes = pd.DataFrame(
        ejecutar_query("SELECT * FROM jovenes"),
        columns=["id", "nombre", "fec_nac", "celular", "es_nuevo", "fec_reg", "activo"],
    )
    df_asistencia = pd.DataFrame(
        ejecutar_query("SELECT * FROM asistencia"),
        columns=["id", "joven_id", "fecha", "asistio"],
    )
    return auto_generate_agenda_tasks(df_jovenes, df_asistencia)


def render_agenda():
    """
    Renderiza la sección de Agenda con:
    - Tareas automáticas (generadas por inasistencias)
    - Tareas manuales (agregadas por el usuario)
    - Checkbox para marcar como completadas (persistencia en BD)
    - Filtros por prioridad
    - Estadísticas rápidas
    - Historial de completadas agrupado por semanas (sábado a sábado)
    """

    # Inyectar CSS necesario para los estilos de agenda
    st.markdown("""
    <style>
    .agenda-item {
        display: flex; align-items: center; gap: 0.8rem;
        padding: 0.6rem 0.8rem; border-radius: 8px;
        background: white; border: 1px solid #eee;
        margin-bottom: 0.4rem; transition: all 0.2s;
    }
    .agenda-item:hover {
        border-color: #e4be18;
        box-shadow: 0 2px 8px rgba(228, 190, 24, 0.15);
    }
    .agenda-item.done {
        background: #f0f9f0; border-color: #28a745; opacity: 0.8;
    }
    .agenda-priority-high { border-left: 4px solid #dc3545; }
    .agenda-priority-medium { border-left: 4px solid #ffc107; }
    .agenda-priority-low { border-left: 4px solid #17a2b8; }
    .week-group-header {
        background: linear-gradient(135deg, #0f2645 0%, #1a3a6b 100%);
        color: white; padding: 0.6rem 1rem; border-radius: 8px;
        margin: 1rem 0 0.5rem 0; font-weight: 600; font-size: 0.95rem;
    }
    </style>
    """, unsafe_allow_html=True)

    _init_agenda_state()

    # ============================================================
    # TABS: PENDIENTES / HISTORIAL
    # ============================================================
    tab_pendientes, tab_historial = st.tabs(["📋 Tareas Pendientes", "📜 Historial de Completadas"])

    # ============================================================
    # TAB 1: TAREAS PENDIENTES
    # ============================================================
    with tab_pendientes:
        st.markdown("""
        <div class="section-header">
            <h2>📋 Agenda Semanal</h2>
            <p>Gestión de tareas pendientes y seguimiento del ministerio juvenil</p>
        </div>
        """, unsafe_allow_html=True)

        # --- GENERAR TAREAS ---
        tareas_auto = _generar_tareas()
        tareas_manuales = st.session_state.get("agenda_tareas_manuales", [])

        # Combinar tareas (auto + manuales) con IDs únicos
        todas_tareas = []
        for i, t in enumerate(tareas_auto):
            todas_tareas.append({**t, "id": f"auto_{i}", "tipo": "auto"})
        for i, t in enumerate(tareas_manuales):
            todas_tareas.append({**t, "id": f"manual_{i}", "tipo": "manual"})

        # Obtener IDs de tareas completadas en BD para las automáticas
        completed_ids_db = set()
        for t in todas_tareas:
            if t["tipo"] == "auto":
                existing = ejecutar_query(
                    "SELECT id FROM agenda_tareas WHERE actividad = ? AND fecha_asignada = ? AND completada = 1",
                    (t["actividad"], t.get("fecha_asignada", "")),
                )
                if existing:
                    completed_ids_db.add(t["id"])

        # ============================================================
        # FILTROS
        # ============================================================
        st.sidebar.markdown("### 📅 Filtros de Agenda")
        filtro_prioridad = st.sidebar.multiselect(
            "Prioridad",
            options=[1, 2, 3],
            format_func=lambda x: {1: "🔵 Baja", 2: "🟡 Media", 3: "🔴 Alta"}.get(x, str(x)),
            default=[1, 2, 3],
            key="agenda_filtro_prioridad",
        )

        mostrar_completadas = st.sidebar.checkbox(
            "Mostrar completadas", value=False, key="agenda_show_done_pend"
        )

        # ============================================================
        # ESTADÍSTICAS RÁPIDAS
        # ============================================================
        done_ids = completed_ids_db.copy()
        total_pendientes = len([t for t in todas_tareas if t["id"] not in done_ids])
        total_completadas = len([t for t in todas_tareas if t["id"] in done_ids])
        total_altas = len([t for t in todas_tareas if t["prioridad"] == 3 and t["id"] not in done_ids])

        col_est1, col_est2, col_est3, col_est4 = st.columns(4)
        with col_est1:
            st.metric("📌 Pendientes", total_pendientes)
        with col_est2:
            st.metric("✅ Completadas", total_completadas)
        with col_est3:
            st.metric("🔴 Alta prioridad", total_altas)
        with col_est4:
            st.metric("📋 Total", len(todas_tareas))

        # ============================================================
        # AGREGAR TAREA MANUAL
        # ============================================================
        with st.expander("➕ Agregar tarea manual", expanded=False):
            with st.form("form_nueva_tarea", clear_on_submit=True):
                col_t1, col_t2 = st.columns([3, 1])
                with col_t1:
                    nueva_actividad = st.text_input("Actividad:", placeholder="Ej: Reunión con líderes")
                    nueva_descripcion = st.text_input("Descripción:", placeholder="Ej: Coordinar horarios")
                with col_t2:
                    nueva_prioridad = st.selectbox(
                        "Prioridad:", options=[1, 2, 3],
                        format_func=lambda x: {1: "🔵 Baja", 2: "🟡 Media", 3: "🔴 Alta"}.get(x, str(x)),
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    agregar_btn = st.form_submit_button("➕ Agregar", use_container_width=True)

                if agregar_btn and nueva_actividad.strip():
                    nueva_tarea = {
                        "actividad": nueva_actividad.strip(),
                        "descripcion": nueva_descripcion.strip() or "Sin descripción",
                        "prioridad": nueva_prioridad,
                        "joven_id": None,
                        "joven_nombre": None,
                        "fecha_asignada": date.today().strftime("%Y-%m-%d"),
                    }
                    st.session_state["agenda_tareas_manuales"].append(nueva_tarea)
                    st.success("✅ Tarea agregada exitosamente.")
                    st.rerun()

        # ============================================================
        # LISTA DE TAREAS
        # ============================================================
        st.markdown("---")

        if not todas_tareas:
            st.info("No hay tareas pendientes. ¡Disfruta tu semana! 🎉")
        else:
            tareas_filtradas = [t for t in todas_tareas if t["prioridad"] in filtro_prioridad]

            if not mostrar_completadas:
                tareas_filtradas = [t for t in tareas_filtradas if t["id"] not in done_ids]

            if not tareas_filtradas:
                st.info("No hay tareas con los filtros seleccionados.")
            else:
                tareas_filtradas.sort(key=lambda t: (-t["prioridad"], t.get("fecha_asignada", "")))

                for tarea in tareas_filtradas:
                    tarea_id = tarea["id"]
                    is_done = tarea_id in done_ids

                    prioridad_class = {
                        3: "agenda-priority-high",
                        2: "agenda-priority-medium",
                        1: "agenda-priority-low",
                    }.get(tarea["prioridad"], "agenda-priority-low")

                    done_class = "done" if is_done else ""

                    prioridad_color = {
                        3: ("#dc3545", "white"),
                        2: ("#ffc107", "#131414"),
                        1: ("#17a2b8", "white"),
                    }.get(tarea["prioridad"], ("#17a2b8", "white"))

                    prioridad_label = {3: "🔴 Alta", 2: "🟡 Media", 1: "🔵 Baja"}.get(tarea["prioridad"], "⚪")

                    info_extra = ""
                    if tarea.get("joven_nombre"):
                        info_extra = f"<span style='font-size:0.8rem; color:#666;'> — 👤 {tarea['joven_nombre']}</span>"

                    descripcion_html = ""
                    if tarea.get("descripcion"):
                        descripcion_html = f"<div style='font-size:0.8rem; color:#999; margin-top:2px;'>{tarea['descripcion']}</div>"

                    col_chk, col_content = st.columns([0.1, 0.9])

                    with col_chk:
                        checked = st.checkbox(" ", value=is_done, key=f"chk_{tarea_id}", label_visibility="collapsed")
                        if checked != is_done:
                            if checked:
                                _save_completed_task(tarea)
                            else:
                                _uncomplete_task(tarea)
                            st.rerun()

                    with col_content:
                        st.markdown(
                            f'<div class="agenda-item {prioridad_class} {done_class}">'
                            f'<div style="flex:1;">'
                            f'<div style="display:flex; align-items:center; gap:0.5rem;">'
                            f'<span style="font-weight:600; font-size:0.95rem;">{tarea["actividad"]}</span>'
                            f'<span style="font-size:0.65rem; padding:1px 6px; border-radius:10px; '
                            f'background:{prioridad_color[0]}; color:{prioridad_color[1]};">{prioridad_label}</span>'
                            f'{info_extra}'
                            f'</div>{descripcion_html}</div>',
                            unsafe_allow_html=True,
                        )

                    # Botón eliminar (solo manuales)
                    if tarea["tipo"] == "manual":
                        if st.button("🗑️", key=f"del_{tarea_id}", help="Eliminar tarea"):
                            idx = int(tarea_id.split("_")[1])
                            if idx < len(st.session_state["agenda_tareas_manuales"]):
                                st.session_state["agenda_tareas_manuales"].pop(idx)
                            st.rerun()

                # ============================================================
                # BOTONES DE LIMPIEZA
                # ============================================================
                st.markdown("---")
                col_clean1, col_clean2, _ = st.columns([1, 1, 2])

                with col_clean1:
                    if st.button("🔄 Reiniciar completadas", use_container_width=True):
                        ejecutar_query(
                            "UPDATE agenda_tareas SET completada = 0, fecha_completada = NULL WHERE completada = 1",
                            commit=True, fetch=False,
                        )
                        st.rerun()

                with col_clean2:
                    if st.button("🗑️ Reiniciar todo", use_container_width=True):
                        ejecutar_query(
                            "DELETE FROM agenda_tareas",
                            commit=True, fetch=False,
                        )
                        st.session_state["agenda_tareas_manuales"] = []
                        st.rerun()

    # ============================================================
    # TAB 2: HISTORIAL DE TAREAS COMPLETADAS (agrupadas por semana)
    # ============================================================
    with tab_historial:
        st.markdown("""
        <div class="section-header">
            <h2>📜 Historial de Tareas Completadas</h2>
            <p>Registro de tareas finalizadas agrupadas por semana de sábado a sábado</p>
        </div>
        """, unsafe_allow_html=True)

        tareas_completadas = _load_completed_tasks()

        if not tareas_completadas:
            st.info("📭 No hay tareas completadas registradas aún.")
        else:
            # Agrupar por semana (sábado a viernes)
            semanas = {}
            for t in tareas_completadas:
                try:
                    fc = datetime.strptime(t["fecha_completada"], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    continue
                sat = _get_saturday_week(fc)
                key = sat.isoformat()
                if key not in semanas:
                    semanas[key] = {"saturday": sat, "tareas": []}
                semanas[key]["tareas"].append(t)

            # Mostrar semanas en orden descendente
            for key in sorted(semanas.keys(), reverse=True):
                grupo = semanas[key]
                sat = grupo["saturday"]
                label = _format_week_label(sat)
                tareas_semana = grupo["tareas"]

                st.markdown(f'<div class="week-group-header">{label}  ·  {len(tareas_semana)} tareas</div>',
                            unsafe_allow_html=True)

                for t in tareas_semana:
                    prioridad_color = {
                        3: ("#dc3545", "white"),
                        2: ("#ffc107", "#131414"),
                        1: ("#17a2b8", "white"),
                    }.get(t["prioridad"], ("#17a2b8", "white"))

                    prioridad_label = {3: "🔴 Alta", 2: "🟡 Media", 1: "🔵 Baja"}.get(t["prioridad"], "⚪")

                    fecha_comp = t["fecha_completada"]
                    try:
                        fecha_obj = datetime.strptime(fecha_comp, "%Y-%m-%d").date()
                        fecha_formateada = fecha_obj.strftime("%d/%m/%Y")
                    except (ValueError, TypeError):
                        fecha_formateada = fecha_comp

                    info_extra = ""
                    if t.get("joven_nombre"):
                        info_extra = f"<span style='font-size:0.8rem; color:#666;'> — 👤 {t['joven_nombre']}</span>"

                    st.markdown(
                        f'<div class="agenda-item agenda-item done" style="display:flex; align-items:center; gap:0.5rem;">'
                        f'<div style="flex:1;">'
                        f'<div style="display:flex; align-items:center; gap:0.5rem;">'
                        f'<span style="font-weight:600; font-size:0.9rem; text-decoration:line-through; opacity:0.7;">{t["actividad"]}</span>'
                        f'<span style="font-size:0.65rem; padding:1px 6px; border-radius:10px; '
                        f'background:{prioridad_color[0]}; color:{prioridad_color[1]};">{prioridad_label}</span>'
                        f'{info_extra}'
                        f'</div>'
                        f'<div style="font-size:0.75rem; color:#999;">✅ Completada el {fecha_formateada}</div>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

