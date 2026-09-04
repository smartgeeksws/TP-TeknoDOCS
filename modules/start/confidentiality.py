"""Interfaz del Acta de Confidencialidad y Compromiso."""

import base64
import json
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from services.document_generation.confidentiality_service import (
    ConfidentialityService,
    DocumentGenerationError,
)
from services.document_generation_tracker import DocumentGenerationTracker
from services.database import DatabaseError
from services.project_service import ProjectService


def render_confidentiality_document(project_service: ProjectService) -> None:
    project = project_service.get_active_project()
    st.caption("Fase de Inicio")
    st.title("Acta de Confidencialidad y Compromiso")

    if project is None:
        st.warning("Debes abrir un proyecto antes de generar el documento.")
        return

    talents_by_role = {
        talent["role"]: talent
        for talent in project.get("talents", [])
    }
    if "titular" not in talents_by_role:
        st.error(
            "Este documento requiere un talento titular. "
            "Edita el proyecto y asocia uno antes de continuar."
        )
        return

    st.info(
        "El documento utilizará la información y las firmas registradas del "
        "proyecto activo. Cada persona aparecerá una sola vez aunque asuma varios roles."
    )
    document_date = st.date_input(
        "Fecha de realización del documento *",
        value=date.today(),
        key="confidentiality_document_date",
    )

    if st.button(
        "Generar y descargar PDF",
        type="primary",
        use_container_width=True,
    ):
        try:
            pdf_path = ConfidentialityService().generate(project, document_date)
        except (DocumentGenerationError, OSError) as error:
            st.error(f"No fue posible generar el documento: {error}")
            return
        try:
            DocumentGenerationTracker().record(
                project["id"], "confidencialidad_compromiso"
            )
        except DatabaseError as error:
            st.warning(str(error))
        encoded_pdf = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        filename = json.dumps(pdf_path.name)
        components.html(
            f"""
            <a id="tp-download" download={filename}
               href="data:application/pdf;base64,{encoded_pdf}"></a>
            <script>
                document.getElementById("tp-download").click();
            </script>
            """,
            height=0,
        )
        st.success(
            "Documento generado. Si la descarga no inicia, permite descargas "
            "automáticas para este sitio y vuelve a pulsar el botón."
        )
