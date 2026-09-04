"""Dashboard del proyecto activo."""

import streamlit as st

from config.settings import PHASE_DOCUMENTS, PHASES
from services.database import DatabaseError
from services.document_generation_tracker import DocumentGenerationTracker
from services.project_service import ProjectService
from ui.components import metric_card


def _navigate(page: str) -> None:
    st.session_state.current_page = page

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
        st.button(
            "Crear nuevo proyecto",
            type="primary",
            on_click=_navigate,
            args=("create_project",),
        )
        return

    try:
        generation_counts = DocumentGenerationTracker().counts_for_project(project["id"])
    except DatabaseError as error:
        st.error(str(error))
        return
    document_states = [
        (document_name, "Generado" if generation_counts.get(document_id, 0) > 0 else "Pendiente")
        for documents in PHASE_DOCUMENTS.values()
        for document_id, document_name in documents.items()
    ]
    generated = sum(state == "Generado" for _, state in document_states)
    pending = len(document_states) - generated
    progress = int((generated / len(document_states)) * 100)

    columns = st.columns(4)
    values = [
        ("Proyecto activo", project["name"], project.get("code") or "Sin código"),
        ("Documentos generados", str(generated), f"De {len(document_states)} documentos"),
        ("Documentos pendientes", str(pending), f"De {len(document_states)} documentos"),
        ("Avance documental", f"{progress}%", "Documentación completada"),
    ]
    for column, value in zip(columns, values):
        with column:
            metric_card(*value)

    st.button(
        "Editar información del proyecto",
        type="primary",
        on_click=_navigate,
        args=("edit_project",),
    )

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
                st.button(
                    "Abrir fase",
                    key=f"dashboard-phase-{phase_id}",
                    icon=":material/arrow_forward:",
                    width="stretch",
                    on_click=_navigate,
                    args=(f"phase:{phase_id}",),
                )
                for document_id, document_name in documents.items():
                    st.button(
                        document_name,
                        key=f"dashboard-document-{phase_id}-{document_id}",
                        icon=":material/description:",
                        type="tertiary",
                        width="stretch",
                        on_click=_navigate,
                        args=(f"document:{phase_id}:{document_id}",),
                    )
