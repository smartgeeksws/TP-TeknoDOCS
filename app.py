"""Punto de entrada de TP- TeknoDOCS."""

import streamlit as st

from config.settings import APP_ICON, APP_NAME, APP_SUBTITLE
from services.company_service import CompanyService
from services.database import DatabaseError, initialize_schema
from services.person_service import PersonService
from services.project_service import ProjectService
from modules.start.confidentiality import render_confidentiality_document
from modules.start.infrastructure import render_infrastructure_document
from ui.components import project_context
from ui.navigation import render_sidebar
from ui.pages.dashboard import render_dashboard
from ui.pages.phase import render_document_placeholder, render_phase
from ui.pages.projects import render_create_project, render_edit_project, render_projects
from ui.styles import apply_global_styles


@st.dialog("Proyecto creado correctamente")
def show_project_created_dialog(project: dict) -> None:
    """Confirma la creaci?n despu?s de navegar al proyecto activo."""

    st.success("El proyecto fue registrado y guardado en la base de datos.")
    st.write(f"**C?digo:** {project['code']}")
    st.write(f"**Proyecto:** {project['name']}")
    if st.button("Continuar al dashboard", type="primary", use_container_width=True):
        st.session_state.pop("project_created_confirmation", None)
        st.rerun()


st.set_page_config(
    page_title=APP_NAME,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()

person_service = PersonService()
company_service = CompanyService()
project_service = ProjectService(person_service, company_service)
project_service.initialize_session()

try:
    initialize_schema()
    page = render_sidebar(project_service)
    active_project = project_service.get_active_project()
    if active_project:
        project_context(active_project)
    confirmation = st.session_state.get("project_created_confirmation")
    if confirmation:
        show_project_created_dialog(confirmation)

    if page == "dashboard":
        render_dashboard(project_service)
    elif page == "create_project":
        render_create_project(project_service, person_service, company_service)
    elif page == "projects":
        render_projects(project_service)
    elif page == "edit_project":
        render_edit_project(project_service, person_service)
    elif page.startswith("document:"):
        _, phase_id, document_id = page.split(":", maxsplit=2)
        if document_id == "confidencialidad_compromiso":
            render_confidentiality_document(project_service)
        elif document_id == "uso_infraestructura":
            render_infrastructure_document(project_service)
        else:
            render_document_placeholder(phase_id, document_id)
    elif page.startswith("phase:"):
        render_phase(page.split(":", maxsplit=1)[1])
    else:
        st.title(APP_NAME)
        st.info(APP_SUBTITLE)
except DatabaseError as error:
    st.error(str(error))
    st.info(
        "Verifica la sección [mysql] de .streamlit/secrets.toml "
        "y que el servidor permita conexiones remotas."
    )
