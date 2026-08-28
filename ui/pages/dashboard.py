"""Dashboard del proyecto activo."""

import streamlit as st

from config.settings import PHASE_DOCUMENTS, PHASES
from services.document_generation.confidentiality_service import ConfidentialityService
from services.document_generation.infrastructure_service import InfrastructureService
from services.diagnostic_repository import DiagnosticRepository
from services.project_service import ProjectService
from ui.components import metric_card


def render_dashboard(project_service: ProjectService) -> None:
    project = project_service.get_active_project()
    st.title("Dashboard")
    st.caption("Vista general del estado documental del proyecto")

    if not project:
        st.markdown(
            '<div class="tp-empty"><h3>Comienza creando o abriendo un proyecto</h3>'
            '<p>Los documentos y su avance estarán siempre asociados al proyecto activo.</p></div>',
            unsafe_allow_html=True,
        )
        if st.button("Crear nuevo proyecto", type="primary"):
            st.session_state.current_page = "create_project"
            st.rerun()
        return

    confidentiality_generated = ConfidentialityService.output_path(project).is_file()
    infrastructure_generated = InfrastructureService.output_path(project).is_file()
    diagnostic_saved = DiagnosticRepository().load(project["id"])
    document_states = [
        (
            "Acta de Confidencialidad y Compromiso",
            "Generado" if confidentiality_generated else "Pendiente",
        ),
        ("Acta de Uso de Infraestructura", "Generado" if infrastructure_generated else "Pendiente"),
        (
            "Diagnóstico del proyecto y estado del arte",
            "Generado"
            if diagnostic_saved and diagnostic_saved.get("content")
            else "Pendiente",
        ),
    ]
    generated = sum(state == "Generado" for _, state in document_states)
    pending = len(document_states) - generated
    progress = int((generated / len(document_states)) * 100)

    columns = st.columns(4)
    values = [
        ("Proyecto activo", project["name"], project.get("code") or "Sin código"),
        ("Documentos generados", str(generated), "Valor inicial"),
        ("Documentos pendientes", str(pending), "Valor inicial"),
        ("Avance documental", f"{progress}%", "Documentación completada"),
    ]
    for column, value in zip(columns, values):
        with column:
            metric_card(*value)

    if st.button("Editar información del proyecto", type="primary"):
        st.session_state.current_page = "edit_project"
        st.rerun()

    st.subheader("Estado documental")
    for document_name, document_state in document_states:
        icon = "✅" if document_state == "Generado" else "○"
        st.write(f"{icon} **{document_name}:** {document_state}")

    st.subheader("Fases y documentos")
    st.caption("Selecciona una fase o abre directamente el documento que deseas generar.")
    phase_columns = st.columns(2)
    for index, (phase_id, phase_name) in enumerate(PHASES.items()):
        with phase_columns[index % 2]:
            with st.container(key=f"phase-card-{phase_id}"):
                st.subheader(phase_name)
                documents = PHASE_DOCUMENTS.get(phase_id, {})
                st.caption(
                    f"{len(documents)} documento(s) disponible(s)"
                    if documents
                    else "Documentos próximamente"
                )
                if st.button(
                    "Abrir fase",
                    key=f"dashboard-phase-{phase_id}",
                    icon=":material/arrow_forward:",
                    width="stretch",
                ):
                    st.session_state.current_page = f"phase:{phase_id}"
                    st.rerun()
                for document_id, document_name in documents.items():
                    if st.button(
                        document_name,
                        key=f"dashboard-document-{phase_id}-{document_id}",
                        icon=":material/description:",
                        type="tertiary",
                        width="stretch",
                    ):
                        st.session_state.current_page = (
                            f"document:{phase_id}:{document_id}"
                        )
                        st.rerun()
