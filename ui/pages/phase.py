"""Pantalla temporal de fase, sin módulos documentales."""

import streamlit as st

from config.settings import PHASE_DOCUMENTS, PHASES


def render_phase(phase_id: str) -> None:
    phase_name = PHASES.get(phase_id, "Fase")
    st.title(phase_name)
    st.markdown(
        '<div class="tp-empty"><h3>Documentos de la fase</h3>'
        '<p>Próximamente se agregarán los documentos de esta fase.</p></div>',
        unsafe_allow_html=True,
    )


def render_document_placeholder(phase_id: str, document_id: str) -> None:
    document_name = PHASE_DOCUMENTS.get(phase_id, {}).get(
        document_id,
        "Documento",
    )
    st.caption(f"Fase de {PHASES.get(phase_id, 'Inicio')}")
    st.title(document_name)
    st.info(
        "La opción ya está disponible en el menú. "
        "El formulario y la generación del documento se implementarán posteriormente."
    )
