"""Interfaz del formato Proyecto de Base Tecnologica GCDTP-F-019."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.document_generation.technology_base_project_service import (
    TechnologyBaseProjectError,
    TechnologyBaseProjectService,
)
from services.project_content_service import ProjectContentError, ProjectContentService
from services.project_service import ProjectService


CONTENT_FIELDS = (
    ("main_approach", "Enfoque principal del proyecto", 150),
    ("general_objective", "Objetivo general", 130),
    ("specific_objective_1", "Objetivo espec\u00edfico 1", 110),
    ("specific_objective_2", "Objetivo espec\u00edfico 2", 110),
    ("specific_objective_3", "Objetivo espec\u00edfico 3", 110),
    ("specific_objective_4", "Objetivo espec\u00edfico 4", 110),
    ("scope", "Alcance del proyecto", 160),
)


PDF_LAYOUT_VERSION = 2

def render_technology_base_project(project_service: ProjectService) -> None:
    project = project_service.get_active_project()
    st.caption("Planeaci\u00f3n Estrat\u00e9gica")
    st.title("Proyecto Base Tecnol\u00f3gica")
    st.caption("Formato institucional GCDTP-F-019, versi\u00f3n 01")
    if project is None:
        st.warning("Debes abrir un proyecto antes de generar el documento.")
        return

    _render_project_summary(project)
    st.info(
        "OpenAI recibe solamente c\u00f3digo, nombre, descripci\u00f3n, l\u00ednea "
        "tecnol\u00f3gica, TRL y roles sin nombres. No se env\u00edan NIT, documentos, "
        "correos, firmas ni nombres de personas."
    )
    prefix = f"pbt_{project['id']}"
    generated_key = f"{prefix}_generated"
    button_label = (
        "Regenerar contenido con OpenAI"
        if st.session_state.get(generated_key)
        else "Generar contenido con OpenAI"
    )
    if st.button(button_label, type="primary", use_container_width=True):
        try:
            with st.spinner("Generando contenido t\u00e9cnico..."):
                generated = ProjectContentService().generate(project)
        except ProjectContentError as error:
            st.error(str(error))
        else:
            for field, _, _ in CONTENT_FIELDS:
                st.session_state[f"{prefix}_{field}"] = generated[field]
            st.session_state[generated_key] = True
            st.session_state.pop(f"{prefix}_pdf_v{PDF_LAYOUT_VERSION}", None)
            st.session_state.pop(f"{prefix}_filename_v{PDF_LAYOUT_VERSION}", None)
            st.rerun()

    st.subheader("Contenido t\u00e9cnico editable")
    st.caption(
        "Revisa y modifica estos textos antes de producir el PDF. "
        "La edici\u00f3n manual no vuelve a consumir la API."
    )
    content: dict[str, str] = {}
    for field, label, height in CONTENT_FIELDS:
        key = f"{prefix}_{field}"
        st.session_state.setdefault(key, "")
        content[field] = st.text_area(label, key=key, height=height)

    if st.button("Generar PDF", type="primary", use_container_width=True):
        missing = [label for field, label, _ in CONTENT_FIELDS if not content[field].strip()]
        if missing:
            st.error("Completa todos los campos: " + ", ".join(missing) + ".")
        else:
            try:
                with st.spinner("Completando plantilla y generando PDF..."):
                    pdf_data, filename = TechnologyBaseProjectService().generate(
                        project,
                        content,
                    )
            except (TechnologyBaseProjectError, OSError) as error:
                st.error(f"No fue posible generar el documento: {error}")
            else:
                st.session_state[f"{prefix}_pdf_v{PDF_LAYOUT_VERSION}"] = pdf_data
                st.session_state[f"{prefix}_filename_v{PDF_LAYOUT_VERSION}"] = filename

    pdf_data = st.session_state.get(f"{prefix}_pdf_v{PDF_LAYOUT_VERSION}")
    filename = st.session_state.get(f"{prefix}_filename_v{PDF_LAYOUT_VERSION}")
    if pdf_data and filename:
        st.success("PDF generado en memoria. No se guard\u00f3 en la base de datos.")
        st.download_button(
            "Descargar PDF",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )


def _render_project_summary(project: dict[str, Any]) -> None:
    company = project.get("company") or {}
    expert = project.get("expert") or {}
    with st.container(border=True):
        st.subheader("Datos recuperados del proyecto")
        columns = st.columns(2)
        with columns[0]:
            st.write(f"**C\u00f3digo:** {project.get('code') or 'N.A.'}")
            st.write(f"**Nombre:** {project.get('name') or 'N.A.'}")
            st.write(
                f"**L\u00ednea tecnol\u00f3gica:** "
                f"{project.get('technology_line') or 'N.A.'}"
            )
            st.write(f"**Experto:** {expert.get('name') or 'N.A.'}")
        with columns[1]:
            st.write(f"**TRL inicial:** {project.get('initial_trl') or 'N.A.'}")
            st.write(f"**TRL objetivo:** {project.get('target_trl') or 'N.A.'}")
            st.write(f"**Empresa:** {company.get('legal_name') or 'N.A.'}")
            st.write(f"**Talentos:** {len(project.get('talents', []))}")
