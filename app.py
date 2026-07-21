import streamlit as st
import pandas as pd
import sqlite3
import psycopg2
from datetime import datetime, date
import plotly.express as px
import os
import base64
import re
import io
import csv

# Configuración de la página
st.set_page_config(
    page_title="Jóvenes - Panel de Control",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def load_env_file():
    dotenv_path = ".env"
    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            key, value = linea.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

DB_NAME = os.getenv("SQLITE_DB_NAME", "jovenes_control.db")


def get_database_url():
    url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
    if url:
        return url

    try:
        url = st.secrets["DATABASE_URL"]
        if url:
            return url
    except Exception:
        pass

    return None


DB_URL = get_database_url()
IS_POSTGRES = bool(DB_URL and DB_URL.startswith(("postgres://", "postgresql://")))


def parse_csv_to_rows_from_text(csv_text):
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


def build_urgency_summary(df_jovenes, df_asistencia):
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


def get_connection():
    if IS_POSTGRES:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        return conn
    return sqlite3.connect(DB_NAME)


def column_exists(conn, table_name, column_name):
    if IS_POSTGRES:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
            """,
            (table_name, column_name),
        )
        return cur.fetchone() is not None

    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    rows = cur.fetchall()
    return any(row[1] == column_name for row in rows)


def init_db():
    conn = get_connection()
    c = conn.cursor()

    try:
        if IS_POSTGRES:
            c.execute('''
                CREATE TABLE IF NOT EXISTS jovenes (
                    id BIGSERIAL PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    fecha_nacimiento TEXT,
                    celular TEXT,
                    es_nuevo INTEGER DEFAULT 0,
                    fecha_registro TEXT,
                    activo INTEGER DEFAULT 1
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS asistencia (
                    id BIGSERIAL PRIMARY KEY,
                    joven_id BIGINT,
                    fecha TEXT,
                    asistio INTEGER,
                    FOREIGN KEY (joven_id) REFERENCES jovenes(id)
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS evaluacion_equipo (
                    id BIGSERIAL PRIMARY KEY,
                    lider TEXT,
                    fecha TEXT,
                    puntualidad INTEGER,
                    fidelidad INTEGER,
                    invitados INTEGER,
                    visitados INTEGER,
                    resumen TEXT,
                    asistio_lider INTEGER DEFAULT 1,
                    motivo_no_asistencia TEXT,
                    auto_eval_visitados INTEGER DEFAULT 0,
                    auto_eval_programacion INTEGER DEFAULT 0,
                    auto_eval_seguimiento INTEGER DEFAULT 0,
                    auto_eval_invitados INTEGER DEFAULT 0,
                    auto_eval_nuevos INTEGER DEFAULT 0,
                    auto_eval_resumen TEXT
                )
            ''')
        else:
            c.execute('''
                CREATE TABLE IF NOT EXISTS jovenes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    fecha_nacimiento TEXT,
                    celular TEXT,
                    es_nuevo INTEGER DEFAULT 0,
                    fecha_registro TEXT,
                    activo INTEGER DEFAULT 1
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS asistencia (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    joven_id INTEGER,
                    fecha TEXT,
                    asistio INTEGER,
                    FOREIGN KEY (joven_id) REFERENCES jovenes(id)
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS evaluacion_equipo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lider TEXT,
                    fecha TEXT,
                    puntualidad INTEGER,
                    fidelidad INTEGER,
                    invitados INTEGER,
                    visitados INTEGER,
                    resumen TEXT,
                    asistio_lider INTEGER DEFAULT 1,
                    motivo_no_asistencia TEXT,
                    auto_eval_visitados INTEGER DEFAULT 0,
                    auto_eval_programacion INTEGER DEFAULT 0,
                    auto_eval_seguimiento INTEGER DEFAULT 0,
                    auto_eval_invitados INTEGER DEFAULT 0,
                    auto_eval_nuevos INTEGER DEFAULT 0,
                    auto_eval_resumen TEXT
                )
            ''')

        if not column_exists(conn, "jovenes", "activo"):
            try:
                c.execute("ALTER TABLE jovenes ADD COLUMN activo INTEGER DEFAULT 1")
            except Exception as exc:
                mensaje = str(exc).lower()
                if "already exists" not in mensaje and "duplicate column" not in mensaje and "column already exists" not in mensaje:
                    raise

        for column_name, column_sql in [
            ("asistio_lider", "asistio_lider INTEGER DEFAULT 1"),
            ("motivo_no_asistencia", "motivo_no_asistencia TEXT"),
            ("auto_eval_visitados", "auto_eval_visitados INTEGER DEFAULT 0"),
            ("auto_eval_programacion", "auto_eval_programacion INTEGER DEFAULT 0"),
            ("auto_eval_seguimiento", "auto_eval_seguimiento INTEGER DEFAULT 0"),
            ("auto_eval_invitados", "auto_eval_invitados INTEGER DEFAULT 0"),
            ("auto_eval_nuevos", "auto_eval_nuevos INTEGER DEFAULT 0"),
            ("auto_eval_resumen", "auto_eval_resumen TEXT"),
        ]:
            if not column_exists(conn, "evaluacion_equipo", column_name):
                try:
                    c.execute(f"ALTER TABLE evaluacion_equipo ADD COLUMN {column_sql}")
                except Exception as exc:
                    mensaje = str(exc).lower()
                    if "already exists" not in mensaje and "duplicate column" not in mensaje and "column already exists" not in mensaje:
                        raise

        c.execute("SELECT COUNT(*) FROM jovenes")
        if c.fetchone()[0] == 0:
            jovenes_prueba = [
                ("Mateo Gómez", "2008-05-14", "3151234567", 0, "2026-06-01", 1),
                ("Valeria Rojas", "2009-11-22", "3109876543", 0, "2026-06-01", 1),
                ("Santiago Pérez", "2007-01-30", "3204567890", 0, "2026-06-01", 1),
                ("Lucas Silva", "2010-08-12", "3123456789", 1, "2026-07-11", 1),
                ("Camila Torres", "2008-03-19", "3176543210", 1, "2026-07-18", 1)
            ]
            c.executemany(
                "INSERT INTO jovenes (nombre, fecha_nacimiento, celular, es_nuevo, fecha_registro, activo) VALUES (%s, %s, %s, %s, %s, %s)"
                if IS_POSTGRES
                else "INSERT INTO jovenes (nombre, fecha_nacimiento, celular, es_nuevo, fecha_registro, activo) VALUES (?, ?, ?, ?, ?, ?)",
                jovenes_prueba,
            )

            asistencias_prueba = [
                (1, "2026-07-04", 1), (2, "2026-07-04", 1), (3, "2026-07-04", 0),
                (1, "2026-07-11", 1), (2, "2026-07-11", 1), (3, "2026-07-11", 1), (4, "2026-07-11", 1)
            ]
            c.executemany(
                "INSERT INTO asistencia (joven_id, fecha, asistio) VALUES (%s, %s, %s)"
                if IS_POSTGRES
                else "INSERT INTO asistencia (joven_id, fecha, asistio) VALUES (?, ?, ?)",
                asistencias_prueba,
            )

        conn.commit()
    finally:
        conn.close()

init_db()

# --- RUTAS DE IMÁGENES ---
PATH_LOGO = os.path.join("images", "logo.png")
PATH_AVATAR = os.path.join("images", "avatar.png")
PATH_JOVENES = os.path.join("images", "jovenes.png")


def get_theme_mode():
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


def mostrar_logo_redondo(path=PATH_LOGO, width=180):
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

# --- CONTROL DE USUARIOS Y LOGIN ---
USUARIOS = {
    "pastor@": {"pass": "447449", "rol": "Pastor"},
    "sandy@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "lizbeth@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "juan@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "arhur@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "arthur@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "sharin@": {"pass": "12345678", "rol": "Líder Juvenil"},
}

USER_AVATARS = {
    "pastor@": "pastor.png",
    "sandy@": "sandy.png",
    "lizbeth@": "lizbeth.png",
    "juan@": "juan.png",
    "arthur@": "arthur.png",
    "arhur@": "arthur.png",
    "sharin@": "sharin.png",
}


def get_user_avatar_path(usuario):
    if usuario in USER_AVATARS:
        path = os.path.join("images", USER_AVATARS[usuario])
        if os.path.exists(path):
            return path
    return PATH_AVATAR


if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["rol"] = None
    st.session_state["usuario"] = None

st.sidebar.markdown("---")

if st.session_state["autenticado"]:
    col_avatar, col_txt = st.sidebar.columns([1, 2])
    with col_avatar:
        
        avatar_path = get_user_avatar_path(st.session_state["usuario"])
        if os.path.exists(avatar_path):
            st.markdown(
                f"""
                <div style="display:flex; justify-content:center;">
                    <img src="data:image/png;base64,{base64.b64encode(open(avatar_path, 'rb').read()).decode('utf-8')}"
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
    with col_txt:
        st.subheader("Jóvenes Iglesia Alianza Central")
        st.markdown(f"**Usuario:** `{st.session_state['usuario']}`")
        st.markdown(f"**Rol:** {st.session_state['rol']}")
        st.markdown("***No nos cansemos, pues, de hacer bien; porque a su tiempo segaremos, si no desmayamos. Gálatas 6:9***")
        
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["rol"] = None
        st.session_state["usuario"] = None
        st.rerun()

st.sidebar.markdown("---")
EQUIPO = ["Arthur", "Jannice", "Juan", "Sandy"]

def ejecutar_query(query, params=(), commit=False, fetch=True):
    conn = get_connection()
    c = conn.cursor()

    if isinstance(DB_URL, str) and DB_URL.startswith(("postgres://", "postgresql://")):
        query = re.sub(r"(?<!:)(\?)", "%s", query)

    c.execute(query, params)
    result = None
    if commit:
        conn.commit()
    if fetch:
        result = c.fetchall()
    conn.close()
    return result

mostrar_logo_redondo()

# --- PANTALLA PRINCIPAL DE LOGIN ---
if not st.session_state["autenticado"]:
    col_centered_1, col_form, col_centered_2 = st.columns([1, 2, 1])
    with col_form:
        st.markdown(
            "<div style='text-align:center; margin-bottom:0.5rem;'><h3>Sistema de Gestión de Jóvenes</h3></div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        with st.form("main_login_form"):
            usuario_input = st.text_input("Usuario (Email):")
            pass_input = st.text_input("Contraseña:", type="password")
            boton_login = st.form_submit_button("*🚀 Ingresar al Sistema*", use_container_width=True)
            if boton_login:
                if usuario_input in USUARIOS and USUARIOS[usuario_input]["pass"] == pass_input:
                    st.session_state["autenticado"] = True
                    st.session_state["rol"] = USUARIOS[usuario_input]["rol"]
                    st.session_state["usuario"] = usuario_input
                    st.success("¡Inicio de sesión exitoso!")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

# --- RENDERIZADO DE INTERFAZ POST-AUTENTICACIÓN ---
else:
    rol = st.session_state["rol"]
    rol_normalizado = (rol or "").lower()

    # --- VISTA 1: AUXILIARES DE ASISTENCIA / LÍDERES ---
    if "pastor" not in rol_normalizado:
        st.subheader("📋 Registro de Asistencia y Miembros")
        
        tab_asistencia, tab_nuevos, tab_eliminar = st.tabs([
            "✅ Tomar Asistencia", 
            "➕ Registrar Joven Nuevo",
            "❌ Desactivar Miembro"
        ])
        
        with tab_asistencia:
            st.subheader("Control de Asistencia Semanal")
            if os.path.exists(PATH_JOVENES):
                st.image(PATH_JOVENES, caption="Juventud de la Congregación", use_container_width=True)
                
            fecha_asistencia = st.date_input("Fecha del Culto:", date.today(), key="fecha_aux")
            fecha_str = fecha_asistencia.strftime("%Y-%m-%d")
            
            # FILTRO CRÍTICO: Aquí solo llamamos a los que tienen activo = 1
            jovenes = ejecutar_query("SELECT id, nombre FROM jovenes WHERE activo = 1 ORDER BY nombre ASC")
            
            if not jovenes:
                st.warning("No hay jóvenes activos registrados en el sistema.")
            else:
                st.info("Marca la casilla para los jóvenes que están presentes hoy:")
                asistencias_existentes = ejecutar_query(
                    "SELECT joven_id FROM asistencia WHERE fecha = ? AND asistio = 1", (fecha_str,)
                )
                ids_presentes = [row[0] for row in asistencias_existentes]
                
                with st.form("form_asistencia"):
                    lista_checks = {}
                    for j_id, nombre in jovenes:
                        lista_checks[j_id] = st.checkbox(nombre, value=(j_id in ids_presentes))
                    
                    guardar_asistencia = st.form_submit_button("💾 Guardar Asistencia de Hoy")
                    if guardar_asistencia:
                        # Borramos solo las asistencias de esta fecha para reescribir
                        ejecutar_query("DELETE FROM asistencia WHERE fecha = ?", (fecha_str,), commit=True, fetch=False)
                        for j_id, presente in lista_checks.items():
                            estado = 1 if presente else 0
                            ejecutar_query(
                                "INSERT INTO asistencia (joven_id, fecha, asistio) VALUES (?, ?, ?)",
                                (j_id, fecha_str, estado), commit=True, fetch=False
                            )
                        st.success(f"¡Asistencia para el {fecha_str} guardada con éxito!")
                        st.rerun()
                        
        with tab_nuevos:
            st.subheader("Agregar Nuevo Integrante al Culto")
            with st.form("form_nuevo_joven", clear_on_submit=True):
                nombre = st.text_input("Nombre Completo:")
                fec_nac = st.date_input("Fecha de Nacimiento:", min_value=date(1990, 1, 1), max_value=date.today())
                celular = st.text_input("Número de Celular:")
                es_nuevo_check = st.checkbox("¿Es su primer sábado en el culto?", value=True)
                
                enviar_nuevo = st.form_submit_button("➕ Registrar Joven")
                if enviar_nuevo:
                    if nombre.strip() == "":
                        st.error("Por favor ingresa un nombre válido.")
                    else:
                        nuevo_val = 1 if es_nuevo_check else 0
                        # Por defecto se crean con activo = 1
                        ejecutar_query(
                            '''INSERT INTO jovenes (nombre, fecha_nacimiento, celular, es_nuevo, fecha_registro, activo) 
                               VALUES (?, ?, ?, ?, ?, 1)''',
                            (nombre, fec_nac.strftime("%Y-%m-%d"), celular, nuevo_val, date.today().strftime("%Y-%m-%d")),
                            commit=True, fetch=False
                        )
                        st.success(f"¡{nombre} ha sido registrado exitosamente!")
                        st.rerun()

        with tab_eliminar:
            st.subheader("🗑️ Ocultar Miembro de la Lista de Asistencia")
            st.info("Nota: El historial de asistencias pasadas de este joven NO se borrará y se mantendrá en las estadísticas globales.")
            
            # Solo listamos los que están activos para poder darles de baja
            jovenes_del = ejecutar_query("SELECT id, nombre FROM jovenes WHERE activo = 1 ORDER BY nombre ASC")
            if not jovenes_del:
                st.info("No hay miembros activos disponibles para remover.")
            else:
                opciones_del = {row[1]: row[0] for row in jovenes_del}
                joven_a_borrar = st.selectbox("Selecciona el joven que deseas quitar de las listas:", list(opciones_del.keys()), key="del_aux")
                
                with st.form("form_eliminar_aux"):
                    confirmar_check = st.checkbox("Confirmo que deseo quitar a este miembro de la toma de asistencia activa.")
                    btn_eliminar = st.form_submit_button("❌ Quitar de la Lista", use_container_width=True)
                    
                    if btn_eliminar:
                        if confirmar_check:
                            j_id = opciones_del[joven_a_borrar]
                            # MODIFICACIÓN: Hacemos un UPDATE en lugar de un DELETE
                            ejecutar_query("UPDATE jovenes SET activo = 0 WHERE id = ?", (j_id,), commit=True, fetch=False)
                            st.success(f"¡{joven_a_borrar} ha sido removido de la lista de asistencia activa con éxito!")
                            st.rerun()
                        else:
                            st.error("Debes marcar la casilla de confirmación.")

    # --- VISTA 2: PASTOR ---
    elif "Pastor" in rol:
        st.title("⛪ Panel de Control General del Pastor")
        
        tab_eval, tab_asist_pastor, tab_eliminar_pastor, tab_csv, tab_dash = st.tabs([
            "📊 Evaluación de Equipo", 
            "🔄 Asistencia", 
            "🗑️ Gestionar Listas de Miembros",
            "📥 Importar CSV",
            "📈 Dashboard Estratégico"
        ])
        
        with tab_eval:
            st.subheader("Monitoreo de Compromisos del Equipo de Trabajo")
            col_lider, col_fecha = st.columns(2)
            with col_lider:
                lider_sel = st.selectbox("Selecciona el Líder:", EQUIPO)
            with col_fecha:
                fecha_eval = st.date_input("Fecha de Evaluación:", date.today(), key="fecha_eval_pastor")
                fecha_eval_str = fecha_eval.strftime("%Y-%m-%d")
                
            st.markdown("---")
            eval_previo = ejecutar_query(
                "SELECT puntualidad, fidelidad, invitados, visitados, resumen, asistio_lider, motivo_no_asistencia, auto_eval_visitados, auto_eval_programacion, auto_eval_seguimiento, auto_eval_invitados, auto_eval_nuevos, auto_eval_resumen FROM evaluacion_equipo WHERE lider = ? AND fecha = ?",
                (lider_sel, fecha_eval_str)
            )
            
            init_punt = eval_previo[0][0] == 1 if eval_previo else True
            init_fid = eval_previo[0][1] == 1 if eval_previo else True
            init_inv = int(eval_previo[0][2]) if eval_previo else 0
            init_vis = int(eval_previo[0][3]) if eval_previo else 0
            init_res = eval_previo[0][4] if eval_previo else ""
            init_asistio = int(eval_previo[0][5]) if eval_previo else 1
            init_motivo = eval_previo[0][6] if eval_previo else "asistio"
            init_auto_visitados = eval_previo[0][7] == 1 if eval_previo else False
            init_auto_programacion = eval_previo[0][8] == 1 if eval_previo else False
            init_auto_seguimiento = eval_previo[0][9] == 1 if eval_previo else False
            init_auto_invitados = eval_previo[0][10] == 1 if eval_previo else False
            init_auto_nuevos = eval_previo[0][11] == 1 if eval_previo else False
            init_auto_resumen = eval_previo[0][12] if eval_previo else ""
            
            with st.form("form_evaluacion"):
                st.caption("Si el líder no asistió, puedes guardar la evaluación sin completar los indicadores de cumplimiento.")
                lider_asistio = st.radio(
                    "¿El líder asistió?",
                    ["Sí", "No con excusa", "No sin excusa"],
                    horizontal=True,
                    index=0 if init_asistio == 1 else 1 if init_motivo == "con_excusa" else 2,
                )
                no_asistio = lider_asistio != "Sí"
                if no_asistio:
                    st.info("Se registrará la evaluación sin datos de cumplimiento para este sábado.")

                col1, col2 = st.columns(2)
                with col1:
                    puntualidad = st.checkbox("⏱️ Puntualidad", value=init_punt, disabled=no_asistio)
                    fidelidad = st.checkbox("📜 Fidelidad", value=init_fid, disabled=no_asistio)
                with col2:
                    invitados = st.number_input("👥 Jóvenes Invitados:", min_value=0, step=1, value=init_inv, disabled=no_asistio)
                    visitados = st.number_input("🏠 Jóvenes Visitados:", min_value=0, step=1, value=init_vis, disabled=no_asistio)

                st.markdown("---")
                st.subheader("🧭 Autoevaluación de mi trabajo")
                auto_visitados = st.checkbox("🏠 Jóvenes visitados", value=init_auto_visitados)
                auto_programacion = st.checkbox("🗓️ Envíé la programación a tiempo", value=init_auto_programacion)
                auto_seguimiento = st.checkbox("📞 Contacté o hice seguimiento a los líderes entre semana", value=init_auto_seguimiento)
                auto_invitados = st.checkbox("🙌 Jóvenes invitados al culto", value=init_auto_invitados)
                auto_nuevos = st.checkbox("👋 Contacté a los jóvenes nuevos del culto pasado", value=init_auto_nuevos)

                auto_resumen = st.text_area("📝 Resumen de la autoevaluación:", value=init_auto_resumen)
                resumen = st.text_area("📝 Casilla de Resumen General:", value=init_res)
                guardar_eval = st.form_submit_button("💾 Guardar Evaluación")
                
                if guardar_eval:
                    p_val = 0 if no_asistio else (1 if puntualidad else 0)
                    f_val = 0 if no_asistio else (1 if fidelidad else 0)
                    invit_val = 0 if no_asistio else invitados
                    visit_val = 0 if no_asistio else visitados
                    motivo_val = "asistio" if lider_asistio == "Sí" else "con_excusa" if lider_asistio == "No con excusa" else "sin_excusa"
                    asistio_val = 1 if lider_asistio == "Sí" else 0
                    if eval_previo:
                        ejecutar_query(
                            '''UPDATE evaluacion_equipo SET puntualidad = ?, fidelidad = ?, invitados = ?, visitados = ?, resumen = ?, asistio_lider = ?, motivo_no_asistencia = ?, auto_eval_visitados = ?, auto_eval_programacion = ?, auto_eval_seguimiento = ?, auto_eval_invitados = ?, auto_eval_nuevos = ?, auto_eval_resumen = ?
                               WHERE lider = ? AND fecha = ?''',
                            (p_val, f_val, invit_val, visit_val, resumen, asistio_val, motivo_val, 1 if auto_visitados else 0, 1 if auto_programacion else 0, 1 if auto_seguimiento else 0, 1 if auto_invitados else 0, 1 if auto_nuevos else 0, auto_resumen, lider_sel, fecha_eval_str), commit=True, fetch=False
                        )
                    else:
                        ejecutar_query(
                            '''INSERT INTO evaluacion_equipo (lider, fecha, puntualidad, fidelidad, invitados, visitados, resumen, asistio_lider, motivo_no_asistencia, auto_eval_visitados, auto_eval_programacion, auto_eval_seguimiento, auto_eval_invitados, auto_eval_nuevos, auto_eval_resumen)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (lider_sel, fecha_eval_str, p_val, f_val, invit_val, visit_val, resumen, asistio_val, motivo_val, 1 if auto_visitados else 0, 1 if auto_programacion else 0, 1 if auto_seguimiento else 0, 1 if auto_invitados else 0, 1 if auto_nuevos else 0, auto_resumen), commit=True, fetch=False
                        )
                    st.success(f"Evaluación de {lider_sel} guardada.")
                        
        with tab_asist_pastor:
            st.subheader("Control de Asistencia Rápida (Rol de Respaldo)")
            if os.path.exists(PATH_JOVENES):
                st.image(PATH_JOVENES, caption="*Nuestros Jóvenes*", use_container_width=True)
                
            fecha_asistencia_p = st.date_input("Fecha del Culto (Pastor):", date.today(), key="fecha_pastor_asist")
            fecha_p_str = fecha_asistencia_p.strftime("%Y-%m-%d")
            
            # FILTRO CRÍTICO PASTOR: Solo los activos se listan para marcar
            jovenes_p = ejecutar_query("SELECT id, nombre, es_nuevo FROM jovenes WHERE activo = 1 ORDER BY nombre ASC")
            
            if not jovenes_p:
                st.warning("No hay jóvenes activos registrados.")
            else:
                asist_exist_p = ejecutar_query("SELECT joven_id FROM asistencia WHERE fecha = ? AND asistio = 1", (fecha_p_str,))
                ids_p_presentes = [row[0] for row in asist_exist_p]
                asistencias_previas = ejecutar_query("SELECT joven_id FROM asistencia WHERE fecha < ? AND asistio = 1", (fecha_p_str,))
                ids_previos = {row[0] for row in asistencias_previas}
                
                with st.form("form_asistencia_pastor"):
                    checks_p = {}
                    for j_id, nombre, es_nuevo in jovenes_p:
                        checks_p[j_id] = st.checkbox(nombre, value=(j_id in ids_p_presentes), key=f"p_check_{j_id}")
                    
                    guardar_p = st.form_submit_button("💾 Actualizar Asistencia")
                    if guardar_p:
                        ejecutar_query("DELETE FROM asistencia WHERE fecha = ?", (fecha_p_str,), commit=True, fetch=False)
                        for j_id, presente in checks_p.items():
                            estado = 1 if presente else 0
                            ejecutar_query(
                                "INSERT INTO asistencia (joven_id, fecha, asistio) VALUES (?, ?, ?)",
                                (j_id, fecha_p_str, estado), commit=True, fetch=False
                            )
                        st.success("¡Asistencia actualizada!")
                        st.rerun()

                st.markdown("---")
                st.subheader("📞 Prioridad de seguimiento pastoral")
                st.caption(f"Revisión para el {fecha_p_str}")

                ausentes = [nombre for j_id, nombre, _ in jovenes_p if j_id not in ids_p_presentes]
                primeros = [
                    nombre for j_id, nombre, es_nuevo in jovenes_p
                    if j_id in ids_p_presentes and es_nuevo == 1 and j_id not in ids_previos
                ]

                col_ausentes, col_primeros = st.columns(2)
                with col_ausentes:
                    st.warning(f"🚫 No asistieron ({len(ausentes)})")
                    if ausentes:
                        for nombre in ausentes:
                            st.write(f"- {nombre}")
                    else:
                        st.success("Todos asistieron.")

                with col_primeros:
                    st.info(f"✨ Asistieron por primera vez ({len(primeros)})")
                    if primeros:
                        for nombre in primeros:
                            st.write(f"- {nombre}")
                    else:
                        st.info("No hay registros nuevos para esta fecha.")

        with tab_eliminar_pastor:
            st.subheader("🗑️ Control de Membresía del Pastor")
            st.write("Quita miembros desvinculados de las listas activas manteniendo intacto su récord histórico.")
            
            jovenes_del_p = ejecutar_query("SELECT id, nombre FROM jovenes WHERE activo = 1 ORDER BY nombre ASC")
            if not jovenes_del_p:
                st.info("No hay miembros activos registrados.")
            else:
                opciones_del_p = {row[1]: row[0] for row in jovenes_del_p}
                joven_a_borrar_p = st.selectbox("Selecciona el joven que deseas ocultar:", list(opciones_del_p.keys()), key="del_pastor")
                
                with st.form("form_eliminar_pastor"):
                    confirmar_check_p = st.checkbox("Confirmo la baja de la lista activa de este perfil salvaguardando sus asistencias pasadas.")
                    btn_eliminar_p = st.form_submit_button("💥 Desactivar de las Listas", use_container_width=True)
                    
                    if btn_eliminar_p:
                        if confirmar_check_p:
                            j_id_p = opciones_del_p[joven_a_borrar_p]
                            # MODIFICACIÓN: Cambiamos a inactivo
                            ejecutar_query("UPDATE jovenes SET activo = 0 WHERE id = ?", (j_id_p,), commit=True, fetch=False)
                            st.success(f"Se ha archivado el perfil de {joven_a_borrar_p}.")
                            st.rerun()
                        else:
                            st.error("Por seguridad, debes marcar la casilla de verificación.")

        with tab_csv:
            st.subheader("📥 Cargar múltiples jóvenes desde CSV")
            st.caption("El archivo debe contener columnas: nombre, fecha_nacimiento, celular, es_nuevo")
            uploaded_file = st.file_uploader("Selecciona un archivo CSV", type=["csv"], key="upload_csv_pastor")
            if uploaded_file is not None:
                csv_text = uploaded_file.getvalue().decode("utf-8")
                rows = parse_csv_to_rows_from_text(csv_text)
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    if st.button("💾 Registrar jóvenes desde CSV", key="registrar_csv_pastor"):
                        insertados = 0
                        for row in rows:
                            ejecutar_query(
                                '''INSERT INTO jovenes (nombre, fecha_nacimiento, celular, es_nuevo, fecha_registro, activo)
                                   VALUES (?, ?, ?, ?, ?, 1)''',
                                (row["nombre"], row["fecha_nacimiento"], row["celular"], row["es_nuevo"], date.today().strftime("%Y-%m-%d")),
                                commit=True, fetch=False
                            )
                            insertados += 1
                        st.success(f"Se registraron {insertados} jóvenes desde el CSV.")
                        st.rerun()
                else:
                    st.warning("No se encontraron filas válidas en el archivo. Verifica las columnas y el formato.")

        with tab_dash:
            st.subheader("📈 Métricas Clave y Rendimiento del Ministerio")
            df_jovenes = pd.DataFrame(ejecutar_query("SELECT * FROM jovenes"), columns=["id", "nombre", "fec_nac", "celular", "es_nuevo", "fec_reg", "activo"])
            df_asistencia = pd.DataFrame(ejecutar_query("SELECT * FROM asistencia"), columns=["id", "joven_id", "fecha", "asistio"])
            df_eval = pd.DataFrame(ejecutar_query("SELECT * FROM evaluacion_equipo"), columns=["id", "lider", "fecha", "puntualidad", "fidelidad", "invitados", "visitados", "resumen", "asistio_lider", "motivo_no_asistencia", "auto_eval_visitados", "auto_eval_programacion", "auto_eval_seguimiento", "auto_eval_invitados", "auto_eval_nuevos", "auto_eval_resumen"])
            
            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            with col_kpi1:
                # El total de jóvenes registrados puede seguir mosStrando TODOS (los históricos) o solo los activos. Aquí cuenta los activos.
                jovenes_activos = len(df_jovenes[df_jovenes['activo'] == 1]) if not df_jovenes.empty else 0
                st.metric("Miembros Activos Actualmente", jovenes_activos)
            with col_kpi2:
                st.metric("Jóvenes Nuevos Captados (Histórico)", int(df_jovenes['es_nuevo'].sum()) if not df_jovenes.empty else 0)
            with col_kpi3:
                # El promedio de asistencia histórica funciona perfectamente porque lee directamente de la tabla de asistencias guardadas
                if not df_asistencia.empty and (df_asistencia['asistio'] == 1).any():
                    prom_asist = df_asistencia[df_asistencia['asistio'] == 1].groupby('fecha').size().mean()
                    st.metric("Promedio de Asistencia por Sábado", f"{prom_asist:.1f} jóvenes")
                else:
                    st.metric("Promedio de Asistencia por Sábado", "0")
                    
            st.markdown("---")
            st.subheader("🚨 Lista de urgencia pastoral")
            urgencia = build_urgency_summary(df_jovenes, df_asistencia)
            if urgencia:
                st.dataframe(pd.DataFrame(urgencia), columns=["nombre", "urgencia", "detalle"], use_container_width=True, hide_index=True)
            else:
                st.info("No hay registros que requieran seguimiento urgente en este momento.")

            st.markdown("---")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("📅 Asistencia por semana")
                if not df_asistencia.empty and (df_asistencia['asistio'] == 1).any():
                    asistencia_semana = df_asistencia[df_asistencia['asistio'] == 1].copy()
                    asistencia_semana['fecha'] = pd.to_datetime(asistencia_semana['fecha'])
                    asistencia_semana = asistencia_semana.sort_values(by='fecha')
                    resumen_semanal = []
                    for fecha, grupo in asistencia_semana.groupby('fecha'):
                        nombres = []
                        for _, row in grupo.iterrows():
                            joven = df_jovenes[df_jovenes['id'] == int(row['joven_id'])]
                            if not joven.empty:
                                nombres.append(str(joven.iloc[0]['nombre']))
                        resumen_semanal.append({
                            'semana': fecha.strftime('%Y-%m-%d'),
                            'asistentes': len(grupo),
                            'nombres': ', '.join(nombres),
                        })
                    df_semana = pd.DataFrame(resumen_semanal)
                    st.dataframe(df_semana, use_container_width=True, hide_index=True)
                    fig_weekly = px.bar(df_semana, x='semana', y='asistentes', title='Asistentes por semana')
                    st.plotly_chart(fig_weekly, use_container_width=True)
                else:
                    st.info("Sin datos suficientes para graficar asistencia.")
            with col_g2:
                st.subheader("🎯 Cumplimiento de Metas por Líder")
                if not df_eval.empty:
                    df_lideres = df_eval.groupby('lider').agg({'puntualidad': 'mean', 'fidelidad': 'mean', 'invitados': 'sum', 'visitados': 'sum'}).reset_index()
                    df_lideres['Puntualidad %'] = df_lideres['puntualidad'] * 100
                    df_lideres['Fidelidad %'] = df_lideres['fidelidad'] * 100
                    fig_bar = px.bar(df_lideres, x='lider', y=['Puntualidad %', 'Fidelidad %'], barmode='group', title="Porcentaje de cumplimiento de Acuerdos (%)")
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("Sin datos suficientes para graficar desempeño del equipo.")