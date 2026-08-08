"""
helpers.py — Funciones auxiliares de cálculo, CSV, urgencia y evaluación
==========================================================================
"""

import io
import csv
from datetime import date, timedelta

import pandas as pd
import streamlit as st


def parse_csv_to_rows_from_text(csv_text):
    """Convierte texto CSV en una lista de diccionarios con datos de jóvenes."""
    rows = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        nombre = (row.get("nombre") or "").strip()
        if not nombre:
            continue

        fecha_nacimiento = (row.get("fecha_nacimiento") or "").strip()
        celular = (row.get("celular") or "").strip()
        es_nuevo_raw = (row.get("es_nuevo") or row.get("nuevo") or "0").strip().lower()
        es_nuevo = 1 if es_nuevo_raw in {"1", "si", "sí", "true", "t", "yes", "y"} else 0

        rows.append({
            "nombre": nombre,
            "fecha_nacimiento": fecha_nacimiento,
            "celular": celular,
            "es_nuevo": es_nuevo,
        })
    return rows


def calculate_evaluation_score(puntualidad, fidelidad, invitados=0, visitados=0):
    """
    Calcula el puntaje de evaluación del líder (0 a 5).
    Pesos: puntualidad 25%, fidelidad 25%, invitados 25%, visitados 25%.
    """
    weights = {
        "puntualidad": 0.25,
        "fidelidad": 0.25,
        "invitados": 0.25,
        "visitados": 0.25,
    }

    puntualidad_score = 1 if bool(puntualidad) else 0
    fidelidad_score = 1 if bool(fidelidad) else 0
    invitados_score = min(float(int(invitados)) / 3.0, 1.0) if invitados is not None else 0.0
    visitados_score = min(float(int(visitados)) / 3.0, 1.0) if visitados is not None else 0.0

    total_points = (
        puntualidad_score * weights["puntualidad"]
        + fidelidad_score * weights["fidelidad"]
        + invitados_score * weights["invitados"]
        + visitados_score * weights["visitados"]
    )
    return round((total_points / sum(weights.values())) * 5, 2)


def calculate_auto_evaluation_score(
    auto_programacion=False, auto_nuevos=False, auto_seguimiento=False,
    auto_invitados=0, auto_visitados=0
):
    """
    Calcula el puntaje de autoevaluación pastoral (0 a 5).
    Pesos iguales: 20% cada uno.
    """
    weights = {
        "auto_programacion": 0.2,
        "auto_nuevos": 0.2,
        "auto_seguimiento": 0.2,
        "auto_invitados": 0.2,
        "auto_visitados": 0.2,
    }

    programacion_score = 1 if bool(auto_programacion) else 0
    nuevos_score = 1 if bool(auto_nuevos) else 0
    seguimiento_score = 1 if bool(auto_seguimiento) else 0
    invitados_score = min(float(int(auto_invitados)) / 3.0, 1.0) if auto_invitados is not None else 0.0
    visitados_score = min(float(int(auto_visitados)) / 3.0, 1.0) if auto_visitados is not None else 0.0

    total_points = (
        programacion_score * weights["auto_programacion"]
        + nuevos_score * weights["auto_nuevos"]
        + seguimiento_score * weights["auto_seguimiento"]
        + invitados_score * weights["auto_invitados"]
        + visitados_score * weights["auto_visitados"]
    )
    return round((total_points / sum(weights.values())) * 5, 2)


def get_score_status(score):
    """Devuelve 'Aceptable' si score >= 4, de lo contrario 'Requiere mejora'."""
    return "Aceptable" if score >= 4 else "Requiere mejora"


def auto_generate_agenda_tasks(
    df_jovenes, df_asistencia,
    visited_recently_ids=None,
    semana_inicio=None,
):
    """
    Genera automáticamente eventos de agenda pastoral a partir del
    ÚLTIMO registro de asistencia tomado.

    Lógica:
    - Toma la fecha más reciente de asistencia como referencia.
    - Evalúa si cada joven asistió en ese último registro.
    - Cuenta inasistencias consecutivas hacia atrás desde el último registro.
    - Prioridad según es_nuevo + cantidad de inasistencias:
        * es_nuevo=1 o >=3 inasistencias → Alta (3)
        * 2 inasistencias → Media (2)
        * 1 inasistencia → Baja (1)
        * asistió → sin evento de inasistencia
    - "Cuidado Pastoral" para quienes asistieron pero no han sido visitados
      en el último mes (visited_recently_ids).
    - Tareas semanales fijas: envío de programación, atención a líderes.
    Author: cada evento incluye joven_celular.
    """
    tasks = []
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    semana = semana_inicio or today_str

    def _celular(row):
        try:
            return str(row.get("celular") or "")
        except Exception:
            return ""

    # Tareas semanales fijas
    week_tasks = [
        ("📩 Envío de programación", "Enviar la programación del sábado a los líderes", 3, None),
        ("👥 Atención a Líderes", "Contactar y coordinar con los líderes del equipo", 3, None),
    ]
    for actividad, descripcion, prioridad, joven_id in week_tasks:
        tasks.append({
            "actividad": actividad,
            "descripcion": descripcion,
            "prioridad": prioridad,
            "joven_id": joven_id,
            "joven_nombre": None,
            "joven_celular": "",
            "fecha_asignada": today_str,
            "semana_inicio": semana,
        })

    if df_jovenes.empty or df_asistencia.empty:
        return tasks

    df = df_jovenes[df_jovenes["activo"] == 1].copy()
    if df.empty:
        return tasks

    df_asist = df_asistencia.copy()
    df_asist["fecha"] = pd.to_datetime(df_asist["fecha"], errors="coerce")
    df_asist = df_asist.dropna(subset=["fecha"])
    if df_asist.empty:
        return tasks

    fechas = sorted(df_asist["fecha"].unique())
    if not fechas:
        return tasks

    # Último registro de asistencia tomado
    ultima_fecha = fechas[-1]
    df_ultimo = df_asist[df_asist["fecha"] == ultima_fecha]
    presentes_ultimo = set(df_ultimo[df_ultimo["asistio"] == 1]["joven_id"])

    visited_ids = set(visited_recently_ids or [])

    for _, row in df.iterrows():
        joven_id = int(row["id"])
        nombre = row["nombre"]
        es_nuevo = int(row["es_nuevo"])
        celular = _celular(row)

        # Contar inasistencias consecutivas hacia atrás desde el último registro
        count_missed = 0
        for fecha in reversed(fechas):
            asis = df_asist[(df_asist["joven_id"] == joven_id) & (df_asist["fecha"] == fecha)]
            if asis.empty:
                continue
            estado = int(asis.iloc[0]["asistio"])
            if estado == 1:
                break
            count_missed += 1

        # Joven nuevo: contacto de bienvenida (prioridad alta)
        if es_nuevo == 1:
            tasks.append({
                "actividad": "📞 Contacto con joven nuevo",
                "descripcion": f"Contactar a {nombre} para darle seguimiento y bienvenida",
                "prioridad": 3,
                "joven_id": joven_id,
                "joven_nombre": nombre,
                "joven_celular": celular,
                "fecha_asignada": today_str,
                "semana_inicio": semana,
            })
            continue

        # ¿Asistió en el último registro?
        asistio_ultimo = joven_id in presentes_ultimo

        if not asistio_ultimo:
            if count_missed >= 3:
                tasks.append({
                    "actividad": "🏠 Visita con Líder",
                    "descripcion": f"Visitar a {nombre} con su líder — tiene {count_missed} sábados consecutivos sin asistir",
                    "prioridad": 3,
                    "joven_id": joven_id,
                    "joven_nombre": nombre,
                    "joven_celular": celular,
                    "fecha_asignada": today_str,
                    "semana_inicio": semana,
                })
            elif count_missed == 2:
                tasks.append({
                    "actividad": "🙏 Visita pastoral",
                    "descripcion": f"Visita pastoral a {nombre} — tiene 2 inasistencias consecutivas",
                    "prioridad": 2,
                    "joven_id": joven_id,
                    "joven_nombre": nombre,
                    "joven_celular": celular,
                    "fecha_asignada": today_str,
                    "semana_inicio": semana,
                })
            elif count_missed == 1:
                tasks.append({
                    "actividad": "📞 Llamada o mensaje",
                    "descripcion": f"Llamar o enviar mensaje a {nombre} — tiene 1 sábado sin contactar",
                    "prioridad": 1,
                    "joven_id": joven_id,
                    "joven_nombre": nombre,
                    "joven_celular": celular,
                    "fecha_asignada": today_str,
                    "semana_inicio": semana,
                })
        else:
            # Asistió pero no ha sido visitado en el mes → Cuidado Pastoral
            if joven_id not in visited_ids:
                tasks.append({
                    "actividad": "🙏 Cuidado Pastoral",
                    "descripcion": f"Visita de cuidado pastoral a {nombre} — asistió pero no ha sido visitado en el mes",
                    "prioridad": 2,
                    "joven_id": joven_id,
                    "joven_nombre": nombre,
                    "joven_celular": celular,
                    "fecha_asignada": today_str,
                    "semana_inicio": semana,
                })

    return tasks


def build_urgency_summary(df_jovenes, df_asistencia):
    """
    Construye un resumen de urgencia pastoral basado en inasistencias.
    Devuelve lista de dicts con {id, nombre, urgencia, detalle}.
    """
    if df_jovenes.empty:
        return []

    df = df_jovenes[df_jovenes["activo"] == 1].copy()
    if df.empty:
        return []

    if df_asistencia.empty:
        return [
            {
                "id": int(row["id"]),
                "nombre": row["nombre"],
                "urgencia": 3 if int(row["es_nuevo"]) == 1 else 0,
                "detalle": "Joven nuevo" if int(row["es_nuevo"]) == 1 else "Sin alertas",
            }
            for _, row in df.iterrows()
        ]

    df_asistencia = df_asistencia.copy()
    df_asistencia["fecha"] = pd.to_datetime(df_asistencia["fecha"], errors="coerce")
    df_asistencia = df_asistencia.dropna(subset=["fecha"])
    if df_asistencia.empty:
        return []

    fechas = sorted(df_asistencia["fecha"].unique())
    summary = []
    for _, row in df.iterrows():
        joven_id = int(row["id"])
        if int(row["es_nuevo"]) == 1:
            summary.append({
                "id": joven_id,
                "nombre": row["nombre"],
                "urgencia": 3,
                "detalle": "Joven nuevo",
            })
            continue

        count_missed = 0
        for fecha in reversed(fechas):
            asis = df_asistencia[(df_asistencia["joven_id"] == joven_id) & (df_asistencia["fecha"] == fecha)]
            if asis.empty:
                continue
            estado = int(asis.iloc[0]["asistio"])
            if estado == 1:
                break
            count_missed += 1

        if count_missed >= 3:
            urgencia = 3
            detalle = "3 sábados sin asistir"
        elif count_missed == 2:
            urgencia = 2
            detalle = "2 sábados sin asistir"
        elif count_missed == 1:
            urgencia = 1
            detalle = "1 sábado sin asistir"
        else:
            urgencia = 0
            detalle = "Sin alertas"

        if urgencia > 0:
            summary.append({
                "id": joven_id,
                "nombre": row["nombre"],
                "urgencia": urgencia,
                "detalle": detalle,
            })

    summary.sort(key=lambda item: (-item["urgencia"], item["nombre"]))
    return summary


def get_leader_motivation(lider_nombre, df_eval):
    """
    Retorna un dict con {'promedio', 'debilidad', 'mensaje'} para un líder
    basado en su evaluación histórica.
    - Si es "Pastor", analiza auto_score.
    - Si es un líder, analiza score y sus componentes.
    """
    import pandas as pd

    if df_eval.empty:
        return {
            "promedio": 0,
            "debilidad": None,
            "mensaje": "Aún no tienes evaluaciones registradas. ¡Sigue esforzándote! 💪",
        }

    df = df_eval.copy()

    if lider_nombre == "Pastor":
        # Pastor: analiza auto_score (autoevaluación pastoral)
        df_pastor = df[df["lider"] == "Pastor"].copy()
        if df_pastor.empty:
            return {
                "promedio": 0,
                "debilidad": None,
                "mensaje": "Aún no has registrado tu autoevaluación. ¡Anímate a hacerlo! 🙏",
            }
        promedio = float(df_pastor["auto_score"].mean())
        # Analizar componentes
        prom_programacion = float(df_pastor["auto_eval_programacion"].mean())
        prom_nuevos = float(df_pastor["auto_eval_nuevos"].mean())
        prom_seguimiento = float(df_pastor["auto_eval_seguimiento"].mean())
        prom_invitados = 0
        if "auto_eval_invitados" in df_pastor.columns:
            prom_invitados = float(df_pastor["auto_eval_invitados"].mean())
        prom_visitados = 0
        if "auto_eval_visitados" in df_pastor.columns:
            prom_visitados = float(df_pastor["auto_eval_visitados"].mean())

        areas = {
            "📅 Programación": prom_programacion,
            "👋 Contacto nuevos": prom_nuevos,
            "📞 Seguimiento líderes": prom_seguimiento,
            "🙌 Invitar al culto": prom_invitados,
            "🏠 Visitas pastorales": prom_visitados,
            "✍️ Resumen semanal": prom_programacion,
        }
        area_debil = min(areas, key=areas.get)
        valor_debil = areas[area_debil]
    else:
        # Líder: analiza score
        df_lider = df[df["lider"] == lider_nombre].copy()
        if df_lider.empty:
            return {
                "promedio": 0,
                "debilidad": None,
                "mensaje": "Aún no tienes evaluaciones registradas. ¡Sigue esforzándote! 💪",
            }
        promedio = float(df_lider["score"].mean())
        prom_puntualidad = float(df_lider["puntualidad"].mean())
        prom_fidelidad = float(df_lider["fidelidad"].mean())
        prom_invitados = float(df_lider["invitados"].mean())
        prom_visitados = float(df_lider["visitados"].mean())

        areas = {
            "⏱️ Puntualidad": prom_puntualidad,
            "📜 Fidelidad": prom_fidelidad,
            "👥 Invitar jóvenes": prom_invitados / 3.0 if prom_invitados else 0,
            "🏠 Visitar jóvenes": prom_visitados / 3.0 if prom_visitados else 0,
        }
        area_debil = min(areas, key=areas.get)
        valor_debil = areas[area_debil]

    # Generar mensaje motivacional
    if promedio >= 4.5:
        mensaje = f"🎉 ¡Excelente trabajo! Tu promedio es {promedio:.2f}/5.0. Sigue siendo un ejemplo para los jóvenes. ¡Dios te bendiga! 🙌"
    elif promedio >= 4.0:
        mensaje = f"👍 Buen desempeño con {promedio:.2f}/5.0. En {area_debil} puedes mejorar un poco más. ¡Tú puedes! 💪"
    elif promedio >= 3.0:
        mensaje = f"📈 Tu promedio es {promedio:.2f}/5.0. En {area_debil} hay oportunidad de crecimiento. ¡No te desanimes, cada paso cuenta! 🌟"
    elif promedio >= 2.0:
        mensaje = f"💪 Estás en proceso con {promedio:.2f}/5.0. Tu área a reforzar es {area_debil}. Recuerda: 'Todo lo puedo en Cristo que me fortalece'. ¡Ánimo! 🙏"
    else:
        mensaje = f"🫂 Hermano, tu promedio es {promedio:.2f}/5.0. En {area_debil} necesitas enfocarte. Cuenta con el apoyo del equipo para mejorar. ¡Juntos somos más fuertes! 🤝"

    return {
        "promedio": promedio,
        "debilidad": area_debil,
        "mensaje": mensaje,
    }


def get_theme_mode():
    """Detecta si el tema de Streamlit es oscuro o claro."""
    try:
        base = st.get_option("theme.base")
        if base in {"dark", "light"}:
            return base
    except Exception:
        pass

    try:
        bg = st.get_option("theme.backgroundColor")
        if isinstance(bg, str) and bg.startswith("#"):
            hex_color = bg.lstrip("#")
            if len(hex_color) == 3:
                hex_color = "".join(c * 2 for c in hex_color)
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
            return "dark" if luminance < 0.5 else "light"
    except Exception:
        pass

    return "light"

