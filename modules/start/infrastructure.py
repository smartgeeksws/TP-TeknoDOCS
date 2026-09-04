"""Interfaz del Acta de Uso de Infraestructura y Compromiso."""

import base64
import json
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from services.document_generation.confidentiality_service import DocumentGenerationError
from services.document_generation.infrastructure_service import InfrastructureService
from services.document_generation_tracker import DocumentGenerationTracker
from services.database import DatabaseError
from services.project_service import ProjectService


def render_infrastructure_document(project_service: ProjectService) -> None:
    project = project_service.get_active_project()
    st.caption("Fase de Inicio")
    st.title("Acta de Uso de Infraestructura")
    if project is None:
        st.warning("Debes abrir un proyecto antes de generar el documento.")
        return
    titular = next((talent for talent in project.get("talents", []) if talent.get("role") == "titular"), None)
    if titular is None:
        st.error("Este documento requiere un talento titular. Edita el proyecto y asocia uno antes de continuar.")
        return
    if project.get("expert") is None:
        st.error("Este documento requiere un experto. Edita el proyecto y asocia uno antes de continuar.")
        return
    if project.get("start_date") is None:
        st.error("Este documento requiere la fecha de inicio del proyecto. Edita el proyecto y registra esa fecha antes de continuar.")
        return

    st.info("El documento incluirá el código y el nombre del proyecto, junto con los datos registrados del talento titular y del experto asignado.")
    document_date = st.date_input(
        "Fecha de realización del documento *",
        value=date.today(),
        key="infrastructure_document_date",
    )
    if st.button("Generar y descargar PDF", type="primary", use_container_width=True):
        try:
            pdf_path = InfrastructureService().generate(project, document_date)
        except (DocumentGenerationError, OSError) as error:
            st.error(f"No fue posible generar el documento: {error}")
            return
        try:
            DocumentGenerationTracker().record(project["id"], "uso_infraestructura")
        except DatabaseError as error:
            st.warning(str(error))
        encoded_pdf = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        filename = json.dumps(pdf_path.name)
        components.html(
            f"""<a id="tp-download-infrastructure" download={filename} href="data:application/pdf;base64,{encoded_pdf}"></a><script>document.getElementById("tp-download-infrastructure").click();</script>""",
            height=0,
        )
        st.success("Documento generado. Si la descarga no inicia, permite descargas automáticas para este sitio y vuelve a pulsar el botón.")
