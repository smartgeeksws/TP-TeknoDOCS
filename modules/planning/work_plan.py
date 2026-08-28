"""Interfaz del Plan de Trabajo GCDTP-F-021."""

from __future__ import annotations

import streamlit as st

from services.document_generation.work_plan_service import (
    ScheduledActivity,
    WorkPlanError,
    WorkPlanService,
)
from services.project_service import ProjectService


WORK_PLAN_VERSION = 1


def render_work_plan(project_service: ProjectService) -> None:
    project = project_service.get_active_project()
    st.caption("Planeación Estratégica")
    st.title("Plan de Trabajo")
    st.caption("Formato institucional GCDTP-F-021, versión 01")
    if project is None:
        st.warning("Debes abrir un proyecto antes de generar el documento.")
        return

    service = WorkPlanService()
    try:
        start_date, end_date, talent, expert = service.validate_project(project)
    except WorkPlanError as error:
        st.error(str(error))
        return

    total_days = (end_date - start_date).days + 1
    with st.container(border=True):
        st.subheader("Datos recuperados del proyecto")
        st.write(f"**Proyecto:** {project.get('code')} - {project.get('name')}")
        st.write(f"**Fecha inicial:** {start_date.strftime('%d/%m/%Y')}")
        st.write(f"**Fecha final:** {end_date.strftime('%d/%m/%Y')}")
        st.write(f"**Duración total:** {total_days} días")
        st.write(f"**Talento asignado:** {service.short_name(talent.get('name'))}")
        st.write(f"**Responsable Tecnoparque:** {service.short_name(expert.get('name'))}")

    prefix = (
        f"work_plan_{project['id']}_{start_date:%Y%m%d}_{end_date:%Y%m%d}"
        f"_v{WORK_PLAN_VERSION}"
    )
    schedule_key = f"{prefix}_schedule"
    pdf_key = f"{prefix}_pdf"
    filename_key = f"{prefix}_filename"

    if st.button("Generar cronograma", type="primary", width="stretch"):
        try:
            schedule = service.build_schedule(project)
        except WorkPlanError as error:
            st.error(str(error))
        else:
            st.session_state[schedule_key] = schedule
            st.session_state.pop(pdf_key, None)
            st.session_state.pop(filename_key, None)
            st.rerun()

    schedule: list[ScheduledActivity] | None = st.session_state.get(schedule_key)
    if not schedule:
        st.info("Genera el cronograma para revisar las fechas antes de producir el PDF.")
        return

    st.subheader("Vista previa del cronograma")
    st.dataframe(
        [
            {
                "Actividad": item.code,
                "Descripción": item.description,
                "Categoría": item.category,
                "Fecha": item.date_label,
                "Duracion (días)": item.duration,
            }
            for item in schedule
        ],
        hide_index=True,
        width="stretch",
    )

    if st.button("Generar PDF", type="primary", width="stretch"):
        try:
            with st.spinner("Completando la plantilla y generando el PDF..."):
                pdf_data, filename = service.generate(project, schedule)
        except (WorkPlanError, OSError) as error:
            st.error(f"No fue posible generar el plan de trabajo: {error}")
        else:
            st.session_state[pdf_key] = pdf_data
            st.session_state[filename_key] = filename

    pdf_data = st.session_state.get(pdf_key)
    filename = st.session_state.get(filename_key)
    if pdf_data and filename:
        st.success("PDF generado en memoria. No se guardó en la base de datos.")
        st.download_button(
            "Descargar PDF",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="primary",
            width="stretch",
        )
