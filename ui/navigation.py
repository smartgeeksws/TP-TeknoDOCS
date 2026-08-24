"""Navegación lateral persistente."""

import streamlit as st

from config.settings import APP_NAME, LOGO_PATH, PHASE_DOCUMENTS, PHASES
from services.project_service import ProjectService


def _navigate(page: str) -> None:
    st.session_state.current_page = page


def render_sidebar(project_service: ProjectService) -> str:
    with st.sidebar:
        st.image(str(LOGO_PATH), width=190)
        st.markdown(f"## {APP_NAME}")
        st.caption("Documentación de proyectos SENA")

        active = project_service.get_active_project()
        if active:
            st.success(f"Activo: {active['name']}")
        else:
            st.info("Sin proyecto activo")

        if st.button("⌂  Inicio / Dashboard"):
            _navigate("dashboard")

        with st.expander("▣  Proyectos", expanded=True):
            if st.button("＋ Crear proyecto", key="nav_create"):
                _navigate("create_project")
            if st.button("☷ Mis proyectos", key="nav_projects"):
                _navigate("projects")
            if active and st.button("✎ Editar proyecto", key="nav_edit_project"):
                _navigate("edit_project")

        for phase_id, phase_name in PHASES.items():
            with st.expander(f"◇  Fase de {phase_name}"):
                documents = PHASE_DOCUMENTS.get(phase_id, {})
                if documents:
                    for document_id, document_name in documents.items():
                        if st.button(
                            document_name,
                            key=f"nav_document_{document_id}",
                        ):
                            _navigate(f"document:{phase_id}:{document_id}")
                else:
                    st.caption("Próximamente se agregarán documentos.")
                if st.button("Ver fase", key=f"nav_{phase_id}"):
                    _navigate(f"phase:{phase_id}")

        st.markdown("---")
        st.caption("Identidad institucional SENA")

    return st.session_state.current_page
