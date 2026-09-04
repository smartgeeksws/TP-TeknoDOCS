"""Streamlit interfaces for closure and certification documents."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from services.closure_content_service import ClosureContentService
from services.document_generation.closure_services import (
    BusinessModelPdfService,
    CertificationLetterDocumentService,
    ClosureDocumentError,
    FinalReportDocumentService,
    format_date,
)
from services.document_generation_tracker import DocumentGenerationTracker
from services.database import DatabaseError
from services.project_content_service import ProjectContentError
from services.project_service import ProjectService


REPORT_LABELS = {
    "introduccion": "Introducción",
    "planteamiento_problema": "Planteamiento del problema",
    "objetivo_general": "Objetivo general",
    "objetivos_especificos": "Objetivos específicos",
    "estado_arte": "Estado del arte y antecedentes",
    "metodologia": "Metodología",
    "desarrollo": "Desarrollo del proyecto",
    "normatividad": "Normatividad",
    "resultados": "Resultados",
    "analisis_viabilidad": "Análisis de viabilidad",
    "propiedad_transferencia": "Propiedad intelectual y transferencia",
    "impacto": "Impacto",
    "conclusiones": "Conclusiones",
    "referencias": "Referencias bibliográficas",
    "anexos": "Anexos",
}

CANVAS_LABELS = BusinessModelPdfService.LABELS
METODOLOGIAS_DESARROLLO = [
    "Metodologías ágiles",
    "Scrum",
    "Kanban",
    "Modelo en cascada",
    "Modelo espiral",
    "Design Thinking",
    "Doble Diamante",
    "Diseño Centrado en el Usuario (DCU)",
    "Diseño para Manufactura y Ensamble (DFMA)",
    "Lean Startup",
    "Stage-Gate",
    "Desarrollo iterativo de prototipos",
    "Ingeniería de sistemas y modelo V",
    "CRISP-DM para proyectos de datos e inteligencia artificial",
    "DMAIC / Six Sigma",
    "Investigación aplicada y validación experimental",
    "TRIZ para solución inventiva de problemas",
    "Otra",
]


def render_final_report(project_service: ProjectService) -> None:
    project = _project_or_warning(project_service, "Informe técnico final", "Formato institucional GCDTP-F-023, versión 01")
    if not project:
        return
    prefix = f"closure_report_{project['id']}"
    _project_details(project)
    methodologies_selected = st.multiselect(
        "Metodologías utilizadas *",
        options=METODOLOGIAS_DESARROLLO,
        key=f"{prefix}_methodologies_selected",
        placeholder="Selecciona una o más metodologías",
    )
    other_methodology = ""
    if "Otra" in methodologies_selected:
        other_methodology = st.text_input(
            "Otra metodología *",
            key=f"{prefix}_other_methodology",
            placeholder="Describe la metodología aplicada",
        )
    with st.form(f"{prefix}_form"):
        achieved = st.text_input("TRL realmente alcanzado *", value=str(project.get("target_trl") or ""), key=f"{prefix}_achieved")
        delivery = st.date_input("Fecha de entrega *", value=_as_date(project.get("end_date")), key=f"{prefix}_delivery", format="DD/MM/YYYY")
        deliverables = st.text_area("Entregables finales *", key=f"{prefix}_deliverables", placeholder="Escribe un entregable por línea: producto, prototipo, componente, documento, sistema o desarrollo obtenido al cierre.", height=130)
        innovation = st.text_area("Innovación desarrollada", key=f"{prefix}_innovation", placeholder="Explica el elemento diferencial, la mejora frente a alternativas existentes y el aporte técnico o funcional.", height=115)
        activities = st.text_area("Actividades ejecutadas *", key=f"{prefix}_activities", placeholder="Escribe una actividad por línea. Ejemplo:\n1. Levantamiento de requisitos con los usuarios.\n2. Diseño de la arquitectura de la solución.\n3. Desarrollo e integración de los componentes.\n4. Pruebas, ajustes y validación del prototipo.", height=170)
        impacts = st.text_area("Impactos o resultados adicionales", key=f"{prefix}_impacts", placeholder="Describe los beneficios, beneficiarios y efectos tecnológicos, sociales, económicos, ambientales o productivos identificados.", height=120)
        generate = st.form_submit_button("Regenerar con IA", type="primary", icon=":material/auto_awesome:")
    methodologies = [item for item in methodologies_selected if item != "Otra"]
    if other_methodology.strip():
        methodologies.append(other_methodology.strip())
    form_data = {"achieved_trl": achieved.strip(), "delivery_date": delivery.isoformat(), "deliverables": deliverables.strip(), "innovation": innovation.strip(), "methodologies": "; ".join(methodologies), "activities": activities.strip(), "additional_impacts": impacts.strip()}
    if generate:
        if not all(form_data[key] for key in ("achieved_trl", "deliverables", "methodologies", "activities")):
            st.error("Completa los campos requeridos para generar el informe.")
        else:
            _generate_content(prefix, lambda: ClosureContentService().generate_report(project, form_data))
    content = st.session_state.get(f"{prefix}_content")
    if content:
        edited = _content_editor(prefix, content, REPORT_LABELS)
        if st.button("Preparar Informe Técnico Final", type="primary", icon=":material/description:", key=f"{prefix}_document"):
            try:
                data, filename = FinalReportDocumentService().generate(project, form_data, edited)
            except ClosureDocumentError as error:
                st.error(f"No fue posible generar el documento: {error}")
            else:
                st.session_state[f"{prefix}_file"] = (data, filename)
                _record_generation(project["id"], "informe_tecnico_final")
        _download(prefix, "Descargar Informe Técnico Final", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def render_business_model(project_service: ProjectService) -> None:
    project = _project_or_warning(project_service, "Modelo de negocio", "Lean Canvas del proyecto")
    if not project:
        return
    prefix = f"closure_canvas_{project['id']}"
    _project_details(project)
    with st.form(f"{prefix}_form"):
        profile = st.text_area("Perfil de clientes o usuarios, si requiere precisarlo", key=f"{prefix}_profile", height=100)
        context = st.text_area("Información complementaria para el modelo", key=f"{prefix}_context", height=100)
        generate = st.form_submit_button("Regenerar con IA", type="primary", icon=":material/auto_awesome:")
    if generate:
        _generate_content(prefix, lambda: ClosureContentService().generate_canvas(project, {"customer_profile": profile.strip(), "additional_context": context.strip(), "target_trl": project.get("target_trl")}))
    content = st.session_state.get(f"{prefix}_content")
    if content:
        edited = _content_editor(prefix, content, CANVAS_LABELS)
        if st.button("Preparar Modelo de Negocio", type="primary", icon=":material/picture_as_pdf:", key=f"{prefix}_document"):
            try:
                st.session_state[f"{prefix}_file"] = BusinessModelPdfService().generate(project, edited)
            except ClosureDocumentError as error:
                st.error(f"No fue posible generar el PDF: {error}")
            else:
                _record_generation(project["id"], "modelo_negocio")
        _download(prefix, "Descargar Modelo de Negocio", "application/pdf")


def render_certification_letter(project_service: ProjectService) -> None:
    project = _project_or_warning(project_service, "Carta de certificación", "Certificación y participación en consultoría científico-tecnológica")
    if not project:
        return
    prefix = f"closure_letter_{project['id']}"
    values = _letter_values(project)
    values.update(st.session_state.get(f"{prefix}_values", {}))
    missing = [key for key, value in values.items() if not value and key in {"city", "beneficiary_name", "document_type", "document_number", "project_name", "project_code", "start_date", "end_date", "expert_name"}]
    _project_details(project)
    if missing:
        st.info("Completa únicamente los datos que no están registrados en el proyecto.")
        with st.form(f"{prefix}_missing"):
            for key in missing:
                values[key] = st.text_input(_field_label(key), key=f"{prefix}_{key}")
            submit_missing = st.form_submit_button("Guardar datos para la carta", type="primary")
        if submit_missing and all(values[key].strip() for key in missing):
            st.session_state[f"{prefix}_values"] = values
            st.rerun()
        return
    if not st.session_state.get(f"{prefix}_values"):
        st.session_state[f"{prefix}_values"] = values.copy()
    st.caption("Los datos existentes se recuperaron automáticamente. Solo se genera texto técnico al presionar el botón.")
    if st.button("Generar texto técnico con IA", type="primary", icon=":material/auto_awesome:", key=f"{prefix}_generate"):
        _generate_content(prefix, lambda: ClosureContentService().generate_letter_text(project, values))
    content = st.session_state.get(f"{prefix}_content")
    if content:
        labels = {"objetivo_acompanamiento": "Objetivo técnico del acompañamiento", "descripcion_consultoria": "Descripción técnica de la consultoría", "resultado_trl": "Resultado del TRL"}
        edited = _content_editor(prefix, content, labels)
        if st.button("Preparar Carta de Certificación", type="primary", icon=":material/description:", key=f"{prefix}_document"):
            try:
                st.session_state[f"{prefix}_file"] = CertificationLetterDocumentService().generate(values, edited)
            except ClosureDocumentError as error:
                st.error(f"No fue posible generar la carta: {error}")
            else:
                _record_generation(project["id"], "carta_certificacion")
        _download(prefix, "Descargar Carta de Certificación", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def _project_or_warning(project_service: ProjectService, title: str, subtitle: str) -> dict[str, Any] | None:
    st.caption("Cierre y certificación")
    st.title(title)
    st.caption(subtitle)
    project = project_service.get_active_project()
    if not project:
        st.warning("Debes abrir un proyecto antes de generar el documento.")
    return project


def _project_details(project: dict[str, Any]) -> None:
    with st.container(border=True):
        st.subheader("Información recuperada del proyecto")
        st.write(f"**Código:** {project.get('code') or 'Sin código'}")
        st.write(f"**Proyecto:** {project.get('name') or 'No registrado'}")
        st.write(f"**Línea tecnológica:** {project.get('technology_line') or 'No registrada'}")


def _generate_content(prefix: str, action: Any) -> None:
    try:
        with st.spinner("Generando contenido técnico..."):
            st.session_state[f"{prefix}_content"] = action()
    except ProjectContentError as error:
        st.error(str(error))
    else:
        st.success("Contenido generado. Revísalo y edítalo antes de preparar el documento.")


def _content_editor(prefix: str, content: dict[str, str], labels: dict[str, str]) -> dict[str, str]:
    st.subheader("Revisión del contenido")
    edited: dict[str, str] = {}
    for field, label in labels.items():
        edited[field] = st.text_area(label, value=content.get(field, ""), key=f"{prefix}_edit_{field}", height=150)
    return edited


def _download(prefix: str, label: str, mime: str) -> None:
    file_data = st.session_state.get(f"{prefix}_file")
    if file_data:
        st.download_button(label, data=file_data[0], file_name=file_data[1], mime=mime, type="primary", icon=":material/download:", width="stretch")


def _record_generation(project_id: int, document_key: str) -> None:
    try:
        DocumentGenerationTracker().record(project_id, document_key)
    except DatabaseError as error:
        st.warning(str(error))


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return date.today()


def _letter_values(project: dict[str, Any]) -> dict[str, str]:
    talent = next((item for item in project.get("talents", []) if item.get("role") == "titular"), None) or {}
    expert = project.get("expert") or {}
    return {"city": str(project.get("city") or ""), "issue_date": str(project.get("end_date") or date.today().isoformat()), "beneficiary_name": str(talent.get("name") or ""), "document_type": str(talent.get("document_type") or ""), "document_number": str(talent.get("document_number") or ""), "project_name": str(project.get("name") or ""), "project_code": str(project.get("code") or ""), "start_date": format_date(project.get("start_date")), "end_date": format_date(project.get("end_date")), "expert_name": str(expert.get("name") or ""), "expert_role": "Experto en innovación y desarrollo tecnológico", "achieved_trl": str(project.get("target_trl") or "No registrado"), "rating": "Excelente", "company": str((project.get("company") or {}).get("legal_name") or "")}


def _field_label(key: str) -> str:
    return {"city": "Ciudad", "beneficiary_name": "Nombre del beneficiario", "document_type": "Tipo de documento", "document_number": "Número de documento", "project_name": "Nombre del proyecto", "project_code": "Código del proyecto", "start_date": "Fecha inicial", "end_date": "Fecha final", "expert_name": "Nombre del experto"}[key]
