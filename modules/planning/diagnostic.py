"""Interfaz del Diagnóstico del Proyecto y Estado del Arte GCDTP-F-020."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from services.database import DatabaseError
from services.diagnostic_content_service import (
    DiagnosticContentError,
    DiagnosticContentService,
)
from services.diagnostic_repository import DiagnosticRepository
from services.document_generation.diagnostic_service import (
    DiagnosticDocumentError,
    DiagnosticDocumentService,
)
from services.project_service import ProjectService


MODULE_VERSION = 1

EDITABLE_SECTION_LABELS = {
    "introduction": "Introducción",
    "problem_statement": "Planteamiento del problema",
    "problem_identified": "Problema identificado",
    "problem_impact": "Impacto del problema",
    "solution": "Descripción de la solución",
    "state_of_art": "Estado del arte",
    "technology_narrative": "Descripción de las tecnologías",
    "technology_surveillance": "Vigilancia tecnológica y comercial",
    "legal_study": "Estudio legal y normativo",
    "viability": "Viabilidad del proyecto",
    "expected_results": "Resultados esperados",
    "conclusions": "Conclusiones",
}


def render_diagnostic(
    project_service: ProjectService,
    repository: DiagnosticRepository | None = None,
    content_service: DiagnosticContentService | None = None,
    document_service: DiagnosticDocumentService | None = None,
) -> None:
    project = project_service.get_active_project()
    st.caption("Planeación estratégica")
    st.title("Diagnóstico del proyecto y estado del arte")
    st.caption("Formato institucional GCDTP-F-020, versión 01")
    if project is None:
        st.warning("Debes abrir un proyecto antes de generar el documento.")
        return

    repository = repository or DiagnosticRepository()
    content_service = content_service or DiagnosticContentService()
    document_service = document_service or DiagnosticDocumentService()
    prefix = f"diagnostic_{project['id']}_v{MODULE_VERSION}"
    saved_key = f"{prefix}_saved"
    if saved_key in st.session_state:
        saved = st.session_state[saved_key]
    else:
        try:
            saved = repository.load(project["id"])
        except DatabaseError as error:
            st.error(str(error))
            return
        st.session_state[saved_key] = saved
    _initialize_state(prefix, saved)

    with st.container(border=True):
        st.subheader("Información recuperada del proyecto")
        st.write(f"**Código:** {project.get('code') or 'Sin código'}")
        st.write(f"**Proyecto:** {project.get('name')}")
        st.write(f"**Línea tecnológica:** {project.get('technology_line') or 'No registrada'}")
        st.write(f"**Descripción:** {project.get('description') or 'No registrada'}")

    st.info(
        "La investigación se realiza con búsqueda web y OpenAI. Solo se envían datos "
        "técnicos del proyecto y roles; no se envían documentos, correos, firmas ni NIT.",
        icon=":material/security:",
    )

    glossary_choice = st.segmented_control(
        "¿El documento requiere glosario? *",
        options=["No", "Sí"],
        key=f"{prefix}_glossary_choice",
        selection_mode="single",
        width="stretch",
    )
    with st.form(f"{prefix}_form"):
        document_date = st.date_input(
            "Fecha de elaboración del documento *",
            key=f"{prefix}_date",
            format="DD/MM/YYYY",
        )
        problem = st.text_area(
            "Describa con sus propias palabras el problema o necesidad principal que dio origen al proyecto. *",
            key=f"{prefix}_problem",
            height=150,
        )
        technologies = st.text_area(
            "¿Qué tecnologías, herramientas, equipos, materiales, metodologías, lenguajes, plataformas o procesos tecnológicos se prevé utilizar? *",
            key=f"{prefix}_technologies",
            height=150,
        )
        expected_products = st.text_area(
            "¿Cuáles son los principales productos, prototipos, desarrollos, entregables o resultados que espera obtener? *",
            key=f"{prefix}_expected_products",
            height=150,
        )
        glossary_terms = ""
        if glossary_choice == "Sí":
            glossary_terms = st.text_area(
                "Términos que desea incluir en el glosario *",
                key=f"{prefix}_glossary_terms",
                placeholder="Ingrese términos separados por coma o uno por línea.",
                height=110,
            )
        with st.container(horizontal=True, horizontal_alignment="right"):
            save = st.form_submit_button(
                "Guardar borrador",
                icon=":material/save:",
            )
            generate = st.form_submit_button(
                "Generar Diagnóstico / Estado del Arte",
                type="primary",
                icon=":material/auto_awesome:",
            )

    form_data = {
        "document_date": document_date.isoformat(),
        "problem": problem.strip(),
        "technologies": technologies.strip(),
        "expected_products": expected_products.strip(),
        "glossary_requested": glossary_choice == "Sí",
        "glossary_terms": glossary_terms.strip() if glossary_choice == "Sí" else "",
    }
    if save:
        try:
            _validate_form(form_data)
            repository.save_form(project["id"], form_data)
            cached_saved = st.session_state.get(saved_key) or {}
            st.session_state[saved_key] = {**cached_saved, "form": form_data}
        except (ValueError, DatabaseError) as error:
            st.error(str(error))
        else:
            st.toast("Borrador guardado correctamente.", icon=":material/check_circle:")

    if generate:
        try:
            _validate_form(form_data)
            repository.save_form(project["id"], form_data)
            with st.status("Iniciando generación...", expanded=True) as status:
                def report(message: str) -> None:
                    status.write(message)
                    status.update(label=message)

                report("Analizando problemática y contexto técnico...")
                content = content_service.generate(project, form_data, report)
                report("Generando cronograma y construyendo referencias...")
                word_data, filename = document_service.generate(project, form_data, content)
                report("Guardando formulario y auditoría de fuentes...")
                repository.save_generation(
                    project["id"], form_data, content, content["sources"]
                )
                status.update(
                    label="Diagnóstico generado correctamente.",
                    state="complete",
                    expanded=False,
                )
            st.session_state[f"{prefix}_word"] = word_data
            st.session_state[f"{prefix}_filename"] = filename
            st.session_state[f"{prefix}_sources"] = content["sources"]
            st.session_state[f"{prefix}_content"] = content
            st.session_state[saved_key] = {
                "form": form_data,
                "content": content,
                "sources": content["sources"],
            }
            _set_editor_state(prefix, content, force=True)
        except (ValueError, DatabaseError, DiagnosticContentError, DiagnosticDocumentError, OSError) as error:
            st.error(f"No fue posible generar el diagnóstico: {error}")

    _restore_saved_word(prefix, project, saved, document_service)
    content = st.session_state.get(f"{prefix}_content")
    if content:
        _render_content_editor(
            prefix=prefix,
            saved_key=saved_key,
            project=project,
            form_data=form_data,
            content=content,
            repository=repository,
            content_service=content_service,
            document_service=document_service,
        )

    word_data = st.session_state.get(f"{prefix}_word")
    filename = st.session_state.get(f"{prefix}_filename")
    if word_data and filename:
        st.success("Documento Word listo. Puedes editar el formulario y regenerarlo.")
        st.warning(
            "Antes de publicar o entregar el documento, revisa manualmente la "
            "redacción, extensión, coherencia, objetivos, datos técnicos, citas, "
            "referencias y la existencia y vigencia de todas las fuentes. La "
            "aplicación no bloquea la generación por estos criterios. Este aviso "
            "se muestra solo en la aplicación y no se incluye en el Word.",
            icon=":material/fact_check:",
        )
        st.download_button(
            "Descargar Diagnóstico / Estado del Arte",
            data=word_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
            icon=":material/download:",
            width="stretch",
        )
    sources = st.session_state.get(f"{prefix}_sources", [])
    if sources:
        with st.expander(
            f"Auditoría de fuentes ({len(sources)})",
            icon=":material/fact_check:",
        ):
            for source in sources:
                st.markdown(
                    f"**{source.get('title')}**  \n"
                    f"{source.get('author')} ({source.get('year')}) · "
                    f"[{source.get('source_type')}]({source.get('url')})"
                )
                st.caption(
                    "Secciones: " + ", ".join(source.get("sections", []))
                )


def _initialize_state(prefix: str, saved: dict[str, Any] | None) -> None:
    form = (saved or {}).get("form") or {}
    saved_date = form.get("document_date")
    try:
        initial_date = date.fromisoformat(saved_date) if saved_date else date.today()
    except ValueError:
        initial_date = date.today()
    defaults = {
        f"{prefix}_date": initial_date,
        f"{prefix}_problem": form.get("problem", ""),
        f"{prefix}_technologies": form.get("technologies", ""),
        f"{prefix}_expected_products": form.get("expected_products", ""),
        f"{prefix}_glossary_choice": "Sí" if form.get("glossary_requested") else "No",
        f"{prefix}_glossary_terms": form.get("glossary_terms", ""),
        f"{prefix}_sources": (saved or {}).get("sources", []),
        f"{prefix}_content": (saved or {}).get("content"),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _set_editor_state(
    prefix: str,
    content: dict[str, Any],
    *,
    force: bool = False,
) -> None:
    values = {
        **{field: str(content.get(field, "")) for field in EDITABLE_SECTION_LABELS},
        "general_objective": str(content.get("general_objective", "")),
    }
    for field, value in values.items():
        key = f"{prefix}_edit_{field}"
        if force or key not in st.session_state:
            st.session_state[key] = value
    for index, objective in enumerate(content.get("specific_objectives", [])):
        key = f"{prefix}_edit_specific_objective_{index}"
        if force or key not in st.session_state:
            st.session_state[key] = str(objective)


def _render_content_editor(
    *,
    prefix: str,
    saved_key: str,
    project: dict[str, Any],
    form_data: dict[str, Any],
    content: dict[str, Any],
    repository: DiagnosticRepository,
    content_service: DiagnosticContentService,
    document_service: DiagnosticDocumentService,
) -> None:
    _set_editor_state(prefix, content)
    with st.expander(
        "Revisar y editar contenido generado",
        expanded=True,
        icon=":material/edit_document:",
    ):
        st.caption(
            "Estos ajustes se procesan localmente y no realizan una nueva consulta a "
            "OpenAI. Revisa cuidadosamente el contenido antes de reconstruir el Word."
        )
        with st.form(f"{prefix}_content_editor"):
            edited_sections = {
                field: st.text_area(
                    f"{label} "
                    + (
                        "(280–500 palabras)"
                        if field == "technology_surveillance"
                        else "(160–250 palabras)"
                    ),
                    key=f"{prefix}_edit_{field}",
                    height=240 if field == "technology_surveillance" else 170,
                )
                for field, label in EDITABLE_SECTION_LABELS.items()
            }
            general_objective = st.text_area(
                "Objetivo general",
                key=f"{prefix}_edit_general_objective",
                height=90,
            )
            specific_objectives = [
                st.text_area(
                    f"Objetivo específico {index + 1}",
                    key=f"{prefix}_edit_specific_objective_{index}",
                    height=80,
                )
                for index, _objective in enumerate(
                    content.get("specific_objectives", [])
                )
            ]
            apply_edits = st.form_submit_button(
                "Guardar ajustes y regenerar Word",
                type="primary",
                icon=":material/save:",
                width="stretch",
            )

        if not apply_edits:
            return

        updated_content = dict(content)
        updated_content.update(
            {field: value.strip() for field, value in edited_sections.items()}
        )
        updated_content["general_objective"] = general_objective.strip()
        updated_content["specific_objectives"] = [
            objective.strip()
            for objective in specific_objectives
            if objective.strip()
        ]
        try:
            content_service.validate_content(
                updated_content,
                date.fromisoformat(form_data["document_date"]),
                form_data,
            )
            word_data, filename = document_service.generate(
                project, form_data, updated_content
            )
            repository.save_generation(
                project["id"],
                form_data,
                updated_content,
                updated_content["sources"],
            )
        except (
            ValueError,
            DatabaseError,
            DiagnosticContentError,
            DiagnosticDocumentError,
            OSError,
        ) as error:
            st.error(f"No fue posible guardar los ajustes: {error}")
            return

        st.session_state[f"{prefix}_content"] = updated_content
        st.session_state[f"{prefix}_word"] = word_data
        st.session_state[f"{prefix}_filename"] = filename
        st.session_state[f"{prefix}_sources"] = updated_content["sources"]
        st.session_state[saved_key] = {
            "form": form_data,
            "content": updated_content,
            "sources": updated_content["sources"],
        }
        st.toast(
            "Ajustes guardados y documento Word actualizado.",
            icon=":material/check_circle:",
        )


def _restore_saved_word(
    prefix: str,
    project: dict[str, Any],
    saved: dict[str, Any] | None,
    document_service: DiagnosticDocumentService,
) -> None:
    if st.session_state.get(f"{prefix}_word") or not saved or not saved.get("content"):
        return
    try:
        word_data, filename = document_service.generate(
            project, saved["form"], saved["content"]
        )
    except (DiagnosticDocumentError, OSError, ValueError):
        return
    st.session_state[f"{prefix}_word"] = word_data
    st.session_state[f"{prefix}_filename"] = filename


def _validate_form(form_data: dict[str, Any]) -> None:
    required = {
        "problem": "problema identificado",
        "technologies": "tecnologías previstas",
        "expected_products": "productos o resultados esperados",
    }
    missing = [label for field, label in required.items() if not form_data[field]]
    if missing:
        raise ValueError("Completa los campos obligatorios: " + ", ".join(missing) + ".")
    if form_data["glossary_requested"] and not form_data["glossary_terms"]:
        raise ValueError("Ingresa los términos que deseas incluir en el glosario.")