"""Interfaz del modulo Registro de acompanamientos GCDTP-F-022."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import Any

import streamlit as st

from services.accompaniment_registry_content_service import (
    AccompanimentRegistryContentService,
)
from services.accompaniment_registry_service import (
    AccompanimentRegistryError,
    AccompanimentRegistryService,
)
from services.document_generation.accompaniment_registry_service import (
    AccompanimentRegistryDocumentError,
    AccompanimentRegistryDocumentService,
)
from services.project_content_service import ProjectContentError
from services.project_service import ProjectService


MODULE_VERSION = 1


def render_accompaniment_registry(project_service: ProjectService) -> None:
    project = project_service.get_active_project()
    st.caption("Ejecucion y seguimiento")
    st.title("Registro de acompanamientos")
    st.caption("Formato institucional GCDTP-F-022, version 01")
    if project is None:
        st.warning("Debes abrir un proyecto antes de generar el documento.")
        return

    logic = AccompanimentRegistryService()
    try:
        logic.validate_project(project)
    except AccompanimentRegistryError as error:
        st.error(str(error))
        return

    prefix = f"accomp_{project['id']}_v{MODULE_VERSION}"
    _initialize_state(prefix)
    _render_project_summary(project, logic)
    st.info(
        "OpenAI recibe solo el contexto tecnico del proyecto, la fase y los ids de "
        "equipos/materiales. Las fechas, horas, distribuciones y validaciones se "
        "calculan localmente y no cambian en cada rerun.",
        icon=":material/security:",
    )
    _render_generator_form(prefix, project, logic)
    draft = st.session_state.get(f"{prefix}_draft")
    if not draft:
        st.info(
            "Completa el formulario y usa Generar con IA para construir la vista previa editable."
        )
        return

    _render_warnings(draft)
    _render_preview_editor(prefix, draft, logic)
    _render_generation_actions(prefix, project, draft, logic)


def _initialize_state(prefix: str) -> None:
    defaults = {
        f"{prefix}_document_date": date.today(),
        f"{prefix}_meeting_number": "",
        f"{prefix}_phase": "Ejecucion",
        f"{prefix}_phase_start_date": date.today(),
        f"{prefix}_phase_end_date": date.today(),
        f"{prefix}_worked_weekdays": ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"],
        f"{prefix}_technical_activity_count": 4,
        f"{prefix}_equipment_count": 0,
        f"{prefix}_material_count": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_project_summary(project: dict[str, Any], logic: AccompanimentRegistryService) -> None:
    summary = logic.project_summary(project)
    with st.container(border=True):
        st.subheader("Datos recuperados del proyecto")
        left, right = st.columns(2)
        with left:
            st.write(f"**Codigo:** {summary['Codigo']}")
            st.write(f"**Proyecto:** {summary['Proyecto']}")
            st.write(f"**Tecnoparque:** {summary['Tecnoparque']}")
            st.write(f"**Experto responsable:** {summary['Experto responsable']}")
        with right:
            st.write(f"**Regional y centro:** {summary['Regional y centro']}")
            st.write(f"**Linea tecnologica:** {summary['Linea tecnologica']}")
            st.write(f"**Descripcion:** {summary['Descripcion']}")


def _render_generator_form(
    prefix: str,
    project: dict[str, Any],
    logic: AccompanimentRegistryService,
) -> None:
    st.subheader("Datos del documento")
    document_date = st.date_input(
        "Fecha de elaboracion del documento *",
        key=f"{prefix}_document_date",
        format="DD/MM/YYYY",
    )
    meeting_number = st.text_input(
        "Numero de Acta/Reunion *",
        key=f"{prefix}_meeting_number",
    )
    phase = st.selectbox(
        "Fase a documentar *",
        options=list(logic.PHASE_OPTIONS),
        key=f"{prefix}_phase",
    )
    columns = st.columns(2)
    with columns[0]:
        phase_start_date = st.date_input(
            "Fecha de inicio de la fase *",
            key=f"{prefix}_phase_start_date",
            format="DD/MM/YYYY",
        )
    with columns[1]:
        phase_end_date = st.date_input(
            "Fecha de finalizacion de la fase *",
            key=f"{prefix}_phase_end_date",
            format="DD/MM/YYYY",
        )
    worked_weekdays = st.multiselect(
        "Dias de la semana trabajados *",
        options=[label for label, _ in logic.WEEKDAY_OPTIONS],
        key=f"{prefix}_worked_weekdays",
    )
    technical_activity_count = st.number_input(
        "Cantidad de actividades tecnicas a generar *",
        min_value=1,
        step=1,
        key=f"{prefix}_technical_activity_count",
    )

    st.subheader("Equipos o maquinaria especializada")
    equipment_count = int(
        st.number_input(
            "Cantidad de equipos o maquinas a registrar",
            min_value=0,
            step=1,
            key=f"{prefix}_equipment_count",
        )
    )
    equipment_rows = []
    for index in range(equipment_count):
        with st.container(border=True):
            st.caption(f"Equipo {index + 1}")
            name = st.text_input("Nombre", key=f"{prefix}_equipment_name_{index}")
            cols = st.columns(2)
            with cols[0]:
                hours = st.number_input(
                    "Horas totales de uso",
                    min_value=0.0,
                    step=1.0,
                    key=f"{prefix}_equipment_hours_{index}",
                )
            with cols[1]:
                wear = st.number_input(
                    "Valor total de desgaste/uso",
                    min_value=0.0,
                    step=1000.0,
                    key=f"{prefix}_equipment_value_{index}",
                )
            equipment_rows.append(
                {"name": name, "hours_total": hours, "value_total": wear}
            )

    st.subheader("Materiales e insumos")
    material_count = int(
        st.number_input(
            "Cantidad de materiales o insumos a registrar",
            min_value=0,
            step=1,
            key=f"{prefix}_material_count",
        )
    )
    material_rows = []
    for index in range(material_count):
        with st.container(border=True):
            st.caption(f"Material {index + 1}")
            name = st.text_input("Nombre", key=f"{prefix}_material_name_{index}")
            cols = st.columns(2)
            with cols[0]:
                quantity = st.number_input(
                    "Cantidad total",
                    min_value=0.0,
                    step=1.0,
                    key=f"{prefix}_material_quantity_{index}",
                )
            with cols[1]:
                value = st.number_input(
                    "Valor total",
                    min_value=0.0,
                    step=1000.0,
                    key=f"{prefix}_material_value_{index}",
                )
            material_rows.append(
                {"name": name, "quantity_total": quantity, "value_total": value}
            )

    with st.container(horizontal=True, horizontal_alignment="right"):
        regenerate = st.button(
            "Regenerar con IA",
            type="primary",
            icon=":material/auto_awesome:",
            key=f"{prefix}_regenerate",
        )

    if not regenerate:
        return

    form_data = {
        "document_date": document_date,
        "meeting_number": meeting_number.strip(),
        "phase": phase,
        "phase_start_date": phase_start_date,
        "phase_end_date": phase_end_date,
        "worked_weekdays": worked_weekdays,
        "technical_activity_count": int(technical_activity_count),
    }
    try:
        logic.validate_form_data(form_data)
        equipments = logic.build_resources(
            equipment_rows,
            prefix="EQ",
            quantity_key="hours_total",
            value_key="value_total",
            quantity_label="horas",
            value_label="desgaste",
        )
        materials = logic.build_resources(
            material_rows,
            prefix="MAT",
            quantity_key="quantity_total",
            value_key="value_total",
            quantity_label="cantidad",
            value_label="valor",
        )
        with st.spinner("Generando actividades tecnicas con OpenAI..."):
            generated = AccompanimentRegistryContentService().generate(
                project,
                form_data,
                equipments,
                materials,
            )
        draft = logic.build_draft(
            project=project,
            form_data=form_data,
            generated=generated,
            equipments=equipments,
            materials=materials,
        )
    except (AccompanimentRegistryError, ProjectContentError) as error:
        st.error(str(error))
        return

    st.session_state[f"{prefix}_draft"] = draft
    st.session_state.pop(f"{prefix}_xlsx", None)
    st.session_state.pop(f"{prefix}_pdf", None)
    st.session_state.pop(f"{prefix}_xlsx_name", None)
    st.session_state.pop(f"{prefix}_pdf_name", None)
    st.rerun()


def _render_warnings(draft: dict[str, Any]) -> None:
    warnings = draft.get("warnings") or []
    for warning in warnings:
        st.warning(warning)


def _render_preview_editor(
    prefix: str,
    draft: dict[str, Any],
    logic: AccompanimentRegistryService,
) -> None:
    st.subheader("Vista previa editable")
    st.caption(
        "Puedes ajustar tipos, fechas, horas, recursos, descripcion y orden antes de generar el Excel y el PDF."
    )
    st.caption(
        "Los equipos pueden seleccionarse en varias actividades y se distribuyen automaticamente. "
        "Cada material se asigna completo a una unica actividad."
    )
    logic.recalculate_assignments(draft)
    equipments = draft["equipments"]
    materials = draft["materials"]
    equipment_options = [item["id"] for item in equipments]
    material_options = [item["id"] for item in materials]
    equipment_labels = {item["id"]: f"{item['id']} - {item['name']}" for item in equipments}
    material_labels = {item["id"]: f"{item['id']} - {item['name']}" for item in materials}

    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button(
            "Agregar actividad",
            icon=":material/add:",
            key=f"{prefix}_add_activity",
        ):
            logic.add_manual_activity(draft)
            _clear_generated_files(prefix)
            st.rerun()

    for index, activity in enumerate(draft["activities"]):
        label = (
            "Socializacion final"
            if activity.get("is_socialization")
            else f"Actividad {index + 1}: {activity.get('title') or 'Sin titulo'}"
        )
        with st.expander(label, expanded=True, icon=":material/edit_document:"):
            cols = st.columns(3)
            with cols[0]:
                activity["type"] = st.selectbox(
                    "Tipo de acompanamiento",
                    options=list(logic.ALLOWED_TYPES),
                    index=list(logic.ALLOWED_TYPES).index(activity["type"]),
                    key=f"{prefix}_{activity['uid']}_type",
                )
            with cols[1]:
                activity["date"] = st.date_input(
                    "Fecha",
                    value=activity["date"],
                    key=f"{prefix}_{activity['uid']}_date",
                    format="DD/MM/YYYY",
                )
            with cols[2]:
                activity["other"] = st.text_input(
                    "Otros",
                    value=activity.get("other", ""),
                    key=f"{prefix}_{activity['uid']}_other",
                )
            cols = st.columns(2)
            with cols[0]:
                activity["direct_hours"] = Decimal(
                    str(
                        st.number_input(
                            "Horas de acompanamiento directo",
                            min_value=0.0,
                            step=1.0,
                            value=float(activity["direct_hours"]),
                            key=f"{prefix}_{activity['uid']}_direct",
                        )
                    )
                ).quantize(Decimal("0.01"))
            with cols[1]:
                activity["indirect_hours"] = Decimal(
                    str(
                        st.number_input(
                            "Horas de acompanamiento indirecto",
                            min_value=0.0,
                            step=1.0,
                            value=float(activity["indirect_hours"]),
                            key=f"{prefix}_{activity['uid']}_indirect",
                        )
                    )
                ).quantize(Decimal("0.01"))
            activity["equipment_ids"] = st.multiselect(
                "Equipos/maquinaria asignados",
                options=equipment_options,
                default=activity.get("equipment_ids", []),
                format_func=lambda resource_id: equipment_labels[resource_id],
                key=f"{prefix}_{activity['uid']}_equipments",
            )
            materials_assigned_elsewhere = {
                resource_id
                for other_activity in draft["activities"]
                if other_activity["uid"] != activity["uid"]
                for resource_id in other_activity.get("material_ids", [])
            }
            available_material_options = [
                resource_id
                for resource_id in material_options
                if resource_id in activity.get("material_ids", [])
                or resource_id not in materials_assigned_elsewhere
            ]
            activity["material_ids"] = st.multiselect(
                "Materiales/insumos asignados (una sola actividad por material)",
                options=available_material_options,
                default=activity.get("material_ids", []),
                format_func=lambda resource_id: material_labels[resource_id],
                key=f"{prefix}_{activity['uid']}_materials",
            )
            activity["description"] = st.text_area(
                "Descripcion tecnica",
                value=activity["description"],
                height=180,
                key=f"{prefix}_{activity['uid']}_description",
            )
            if activity.get("equipment_lines"):
                st.caption("Asignacion actual de equipos")
                st.code("\n".join(activity["equipment_lines"]))
            if activity.get("material_lines"):
                st.caption("Asignacion actual de materiales")
                st.code("\n".join(activity["material_lines"]))
            if not activity.get("is_socialization"):
                with st.container(horizontal=True, horizontal_alignment="right"):
                    move_up = st.button(
                        "Subir",
                        key=f"{prefix}_{activity['uid']}_up",
                        icon=":material/arrow_upward:",
                    )
                    move_down = st.button(
                        "Bajar",
                        key=f"{prefix}_{activity['uid']}_down",
                        icon=":material/arrow_downward:",
                    )
                    delete = st.button(
                        "Eliminar",
                        key=f"{prefix}_{activity['uid']}_delete",
                        icon=":material/delete:",
                    )
                if move_up:
                    logic.move_activity(draft, activity["uid"], -1)
                    _clear_generated_files(prefix)
                    st.rerun()
                if move_down:
                    logic.move_activity(draft, activity["uid"], 1)
                    _clear_generated_files(prefix)
                    st.rerun()
                if delete:
                    logic.remove_activity(draft, activity["uid"])
                    _clear_generated_files(prefix)
                    st.rerun()
    logic.recalculate_assignments(draft)


def _render_generation_actions(
    prefix: str,
    project: dict[str, Any],
    draft: dict[str, Any],
    logic: AccompanimentRegistryService,
) -> None:
    st.subheader("Generacion final")
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button(
            "Preparar Excel y PDF",
            type="primary",
            icon=":material/picture_as_pdf:",
            key=f"{prefix}_generate_files",
        ):
            try:
                logic.validate_draft(draft)
                xlsx_bytes, pdf_bytes, xlsx_name, pdf_name = (
                    AccompanimentRegistryDocumentService().generate(project, draft)
                )
            except (
                AccompanimentRegistryError,
                AccompanimentRegistryDocumentError,
                OSError,
            ) as error:
                st.error(f"No fue posible generar el documento: {error}")
            else:
                st.session_state[f"{prefix}_xlsx"] = xlsx_bytes
                st.session_state[f"{prefix}_pdf"] = pdf_bytes
                st.session_state[f"{prefix}_xlsx_name"] = xlsx_name
                st.session_state[f"{prefix}_pdf_name"] = pdf_name
                if pdf_bytes:
                    st.success("Excel y PDF generados en memoria.")
                else:
                    st.warning(
                        "El Excel se genero correctamente, pero esta sesion no pudo convertirlo a PDF. "
                        "La app intentara producir el PDF en una maquina con Excel o LibreOffice disponible."
                    )

    pdf_data = st.session_state.get(f"{prefix}_pdf")
    xlsx_data = st.session_state.get(f"{prefix}_xlsx")
    pdf_name = st.session_state.get(f"{prefix}_pdf_name")
    xlsx_name = st.session_state.get(f"{prefix}_xlsx_name")
    if pdf_data and pdf_name:
        st.download_button(
            "Descargar PDF",
            data=pdf_data,
            file_name=pdf_name,
            mime="application/pdf",
            type="primary",
            icon=":material/download:",
            width="stretch",
        )
    if xlsx_data and xlsx_name:
        st.download_button(
            "Descargar Excel",
            data=xlsx_data,
            file_name=xlsx_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/table_view:",
            width="stretch",
        )


def _clear_generated_files(prefix: str) -> None:
    st.session_state.pop(f"{prefix}_xlsx", None)
    st.session_state.pop(f"{prefix}_pdf", None)
    st.session_state.pop(f"{prefix}_xlsx_name", None)
    st.session_state.pop(f"{prefix}_pdf_name", None)
