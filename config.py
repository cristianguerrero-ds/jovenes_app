"""
config.py — Configuración global de la aplicación
==================================================
Define la paleta de colores, estilos CSS, constantes y configuración de usuarios.
"""

import os

# ============================================================
# PALETA DE COLORES GLOBAL
# ============================================================
COLORS = {
    "primary": "#0f2645",
    "secondary": "#e4be18",
    "light": "#e2e2df",
    "dark": "#131414",
    "success": "#28a745",
    "warning": "#ffc107",
    "danger": "#dc3545",
    "info": "#17a2b8",
}

# ============================================================
# CONSTANTES DE LA APLICACIÓN
# ============================================================
APP_TITLE = "Jóvenes - Panel de Control"
APP_ICON = "🙏"
APP_SUBTITLE = "Sistema de Gestión de Jóvenes"

# ============================================================
# RUTAS DE IMÁGENES
# ============================================================
PATH_LOGO = os.path.join("images", "logo.png")
PATH_AVATAR = os.path.join("images", "avatar.png")
PATH_JOVENES = os.path.join("images", "jovenes.png")

# ============================================================
# USUARIOS DEL SISTEMA
# ============================================================
USUARIOS = {
    "pastor@": {"pass": "447449", "rol": "Pastor"},
    "sandy@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "lizbeth@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "juan@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "arthur@": {"pass": "12345678", "rol": "Líder Juvenil"},
    "sharin@": {"pass": "12345678", "rol": "Líder Juvenil"},
}

USER_AVATARS = {
    "pastor@": "pastor.png",
    "sandy@": "sandy.png",
    "lizbeth@": "lizbeth.png",
    "juan@": "juan.png",
    "arthur@": "arthur.png",
    "sharin@": "sharin.png",
}

# ============================================================
# EQUIPO DE LÍDERES
# ============================================================
EQUIPO = ["Arthur", "Jannice", "Juan", "Lizbeth", "Sandy"]

# ============================================================
# MAPEO DE USUARIOS A NOMBRES EN EVALUACIÓN
# ============================================================
USER_DISPLAY_NAMES = {
    "pastor@": "Pastor",
    "sandy@": "Sandy",
    "lizbeth@": "Lizbeth",
    "juan@": "Juan",
    "arthur@": "Arthur",
    "sharin@": "Sharin",
}

# ============================================================
# ESTILOS CSS GLOBALES
# ============================================================
CUSTOM_CSS = f"""
<style>
.stApp {{ background-color: #f8f9fa; }}
.main-title {{ color: {COLORS['primary']}; font-size: 1.8rem; font-weight: 700; }}
.main-subtitle {{ color: #666; font-size: 0.9rem; }}
.kpi-container {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; }}
.kpi-card {{
    flex: 1; min-width: 180px;
    background: linear-gradient(135deg, {COLORS['primary']} 0%, #1a3a6b 100%);
    border-radius: 12px; padding: 1.2rem 1rem;
    box-shadow: 0 4px 15px rgba(15,38,69,0.3);
    border: 1px solid rgba(228,190,24,0.2);
    transition: transform 0.2s;
}}
.kpi-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(15,38,69,0.4);
}}
.kpi-card .kpi-label {{
    color: {COLORS['secondary']};
    font-size: 0.75rem; text-transform: uppercase;
    letter-spacing: 1px; font-weight: 600;
}}
.kpi-card .kpi-value {{
    color: #ffffff; font-size: 2rem;
    font-weight: 700; margin: 0.2rem 0;
}}
.kpi-card .kpi-sub {{
    color: rgba(255,255,255,0.6);
    font-size: 0.7rem;
}}
.dashboard-section-title {{
    color: {COLORS['primary']};
    font-size: 1.1rem; font-weight: 700;
    margin: 1.5rem 0 0.8rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid {COLORS['secondary']};
    display: flex; align-items: center; gap: 0.5rem;
}}
.status-acceptable {{ color: {COLORS['success']}; font-weight: 600; }}
.status-improve {{ color: {COLORS['danger']}; font-weight: 600; }}
.metric-highlight {{ font-size: 1.1rem; font-weight: 700; color: {COLORS['primary']}; }}
.custom-table {{
    width: 100%; border-collapse: collapse; font-size: 0.85rem;
}}
.custom-table th {{
    background: {COLORS['primary']}; color: white;
    padding: 8px 12px; text-align: left;
}}
.custom-table td {{
    padding: 6px 12px; border-bottom: 1px solid {COLORS['light']};
}}
.custom-table tr:hover td {{
    background: rgba(228, 190, 24, 0.05);
}}
.agenda-item {{
    display: flex; align-items: center; gap: 0.8rem;
    padding: 0.6rem 0.8rem; border-radius: 8px;
    background: white; border: 1px solid #eee;
    margin-bottom: 0.4rem; transition: all 0.2s;
}}
.agenda-item:hover {{
    border-color: {COLORS['secondary']};
    box-shadow: 0 2px 8px rgba(228, 190, 24, 0.15);
}}
.agenda-item.done {{
    background: #f0f9f0; border-color: {COLORS['success']}; opacity: 0.8;
}}
.agenda-priority-high {{ border-left: 4px solid {COLORS['danger']}; }}
.agenda-priority-medium {{ border-left: 4px solid {COLORS['warning']}; }}
.agenda-priority-low {{ border-left: 4px solid {COLORS['info']}; }}

/* =========================================================
   SECCIÓN HEADER (compartido: Asistencia, Evaluación, etc.)
   ========================================================= */
.section-header {{
    background: linear-gradient(135deg, {COLORS['primary']} 0%, #1a3a6b 100%);
    color: white; padding: 1.2rem 1.5rem; border-radius: 12px;
    margin-bottom: 1.5rem; box-shadow: 0 4px 15px rgba(15,38,69,0.3);
}}
.section-header h2 {{ color: white; margin: 0; font-size: 1.5rem; }}
.section-header p {{ color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; font-size: 0.85rem; }}

/* =========================================================
   CONTENT CARD (compartido: Asistencia, Evaluación, etc.)
   ========================================================= */
.content-card {{
    background: white; border-radius: 12px; padding: 1.5rem;
    border: 1px solid #eef0f4; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    margin-bottom: 1rem; transition: box-shadow 0.2s;
}}
.content-card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.08); }}

/* =========================================================
   TABS (compartido)
   ========================================================= */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0.5rem; background: {COLORS['light']};
    padding: 0.4rem; border-radius: 10px;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 500;
}}
.stTabs [aria-selected="true"] {{
    background: white !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
}}

.urgency-badge {{
    display: inline-block; padding: 0.15rem 0.6rem;
    border-radius: 20px; font-size: 0.7rem; font-weight: 600;
}}
.badge-alta {{ background: #dc3545; color: white; }}
.badge-media {{ background: #ffc107; color: #131414; }}
.badge-baja {{ background: #17a2b8; color: white; }}
.badge-ok {{ background: #28a745; color: white; }}
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
.fade-in {{ animation: fadeIn 0.3s ease-out; }}
</style>
"""

