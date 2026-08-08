"""
db.py — Conexión e inicialización de la base de datos
=======================================================
Soporta SQLite (local) y PostgreSQL (Nube / Neon).
"""

import os
import sqlite3
import re

import streamlit as st

# psycopg2 es opcional — solo se necesita para PostgreSQL
try:
    import psycopg2
    PSYCOPG2_DISPONIBLE = True
except ImportError:
    psycopg2 = None
    PSYCOPG2_DISPONIBLE = False


def load_env_file():
    """Carga variables de entorno desde un archivo .env (si existe)."""
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
    """Obtiene la URL de la base de datos (prioriza variable de entorno sobre secrets de Streamlit)."""
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


def get_connection():
    """Devuelve una conexión a la base de datos (SQLite o PostgreSQL)."""
    if IS_POSTGRES:
        if not PSYCOPG2_DISPONIBLE:
            raise ImportError(
                "Has configurado PostgreSQL como base de datos, pero "
                "psycopg2 no está instalado. Ejecuta: pip install psycopg2-binary"
            )
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        return conn
    return sqlite3.connect(DB_NAME)


def column_exists(conn, table_name, column_name):
    """Verifica si una columna existe en una tabla."""
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
    """Inicializa las tablas de la base de datos y carga datos de prueba si está vacía."""
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

        # --- Tabla agenda_tareas ---
        if IS_POSTGRES:
            c.execute('''
                CREATE TABLE IF NOT EXISTS agenda_tareas (
                    id BIGSERIAL PRIMARY KEY,
                    actividad TEXT NOT NULL,
                    descripcion TEXT,
                    prioridad INTEGER DEFAULT 1,
                    joven_nombre TEXT,
                    joven_celular TEXT,
                    fecha_asignada TEXT,
                    semana_inicio TEXT,
                    completada INTEGER DEFAULT 0,
                    fecha_completada TEXT,
                    comentario TEXT
                )
            ''')
        else:
            c.execute('''
                CREATE TABLE IF NOT EXISTS agenda_tareas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actividad TEXT NOT NULL,
                    descripcion TEXT,
                    prioridad INTEGER DEFAULT 1,
                    joven_nombre TEXT,
                    joven_celular TEXT,
                    fecha_asignada TEXT,
                    semana_inicio TEXT,
                    completada INTEGER DEFAULT 0,
                    fecha_completada TEXT,
                    comentario TEXT
                )
            ''')

        # Migraciones: agregar columnas faltantes
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

        # Migraciones agenda_tareas: agregar columnas faltantes
        for column_name, column_sql in [
            ("joven_celular", "joven_celular TEXT"),
            ("semana_inicio", "semana_inicio TEXT"),
            ("comentario", "comentario TEXT"),
        ]:
            if not column_exists(conn, "agenda_tareas", column_name):
                try:
                    c.execute(f"ALTER TABLE agenda_tareas ADD COLUMN {column_sql}")
                except Exception as exc:
                    mensaje = str(exc).lower()
                    if "already exists" not in mensaje and "duplicate column" not in mensaje and "column already exists" not in mensaje:
                        raise

        # Datos de prueba si la tabla está vacía
        c.execute("SELECT COUNT(*) FROM jovenes")
        if c.fetchone()[0] == 0:
            jovenes_prueba = [
                ("Mateo Gómez", "2008-05-14", "3151234567", 0, "2026-06-01", 1),
                ("Valeria Rojas", "2009-11-22", "3109876543", 0, "2026-06-01", 1),
                ("Santiago Pérez", "2007-01-30", "3204567890", 0, "2026-06-01", 1),
                ("Lucas Silva", "2010-08-12", "3123456789", 1, "2026-07-11", 1),
                ("Camila Torres", "2008-03-19", "3176543210", 1, "2026-07-18", 1),
            ]
            placeholder = "%s" if IS_POSTGRES else "?"
            c.executemany(
                f"INSERT INTO jovenes (nombre, fecha_nacimiento, celular, es_nuevo, fecha_registro, activo) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                jovenes_prueba,
            )

            asistencias_prueba = [
                (1, "2026-07-04", 1), (2, "2026-07-04", 1), (3, "2026-07-04", 0),
                (1, "2026-07-11", 1), (2, "2026-07-11", 1), (3, "2026-07-11", 1), (4, "2026-07-11", 1),
            ]
            c.executemany(
                f"INSERT INTO asistencia (joven_id, fecha, asistio) VALUES ({placeholder}, {placeholder}, {placeholder})",
                asistencias_prueba,
            )

        conn.commit()
    finally:
        conn.close()


def ejecutar_query(query, params=(), commit=False, fetch=True):
    """
    Ejecuta una consulta SQL y opcionalmente hace commit y devuelve resultados.
    Adapta automáticamente los placeholders para PostgreSQL.
    """
    conn = get_connection()
    c = conn.cursor()

    if IS_POSTGRES:
        query = re.sub(r"(?<!:)(\?)", "%s", query)

    c.execute(query, params)
    result = None
    if commit:
        conn.commit()
    if fetch:
        result = c.fetchall()
    conn.close()
    return result

