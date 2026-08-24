"""Constantes centrales de TP- TeknoDOCS."""

from pathlib import Path

APP_NAME = "TP- TeknoDOCS"
APP_SUBTITLE = "Sistema modular de documentación de proyectos SENA"
APP_ICON = "📄"

ROOT_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = ROOT_DIR / "resources"
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
SIGNATURES_DIR = DATA_DIR / "signatures"
LOGO_PATH = RESOURCES_DIR / "logosm.png"
CONFIDENTIALITY_TEMPLATE = (
    RESOURCES_DIR
    / "templates"
    / "GCDTP-F-017_V01_Confidencialidad_y_compromiso.docx"
)
INFRASTRUCTURE_TEMPLATE = (
    RESOURCES_DIR
    / "templates"
    / "GCDTP-F-018_V01_Uso_infraestructura_y_compromiso.docx"
)
FIXED_SIGNATURES_DIR = RESOURCES_DIR / "firmas"

DOCUMENT_TYPES = ("CC", "TI", "NIT")
TALENT_ROLES = {
    "titular": "Titular",
    "ejecutor": "Ejecutor",
    "interlocutor": "Interlocutor",
}

PHASE_DOCUMENTS = {
    "inicio": {
        "confidencialidad_compromiso": "Acta de Confidencialidad y Compromiso",
        "uso_infraestructura": "Acta de Uso de Infraestructura",
    },
}

PHASES = {
    "inicio": "Inicio",
    "ejecucion": "Ejecución",
    "seguimiento": "Seguimiento",
    "cierre": "Cierre",
}

COLORS = {
    "primary": "#39A900",
    "primary_dark": "#007832",
    "navy": "#00304D",
    "purple": "#71277A",
    "cyan": "#50E5F9",
    "yellow": "#FDC300",
    "background": "#F4F7F5",
    "surface": "#FFFFFF",
    "text": "#173026",
    "muted": "#66756D",
    "border": "#DDE7E1",
}
