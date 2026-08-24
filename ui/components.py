"""Componentes visuales reutilizables."""

import html

import streamlit as st


def project_context(project: dict | None) -> None:
    if project:
        name = html.escape(project["name"])
        code = html.escape(project.get("code") or "Sin código")
        city = html.escape(project.get("city") or "Sin ciudad")
        expert_data = project.get("expert") or {}
        expert_name = expert_data.get("name") or project.get("responsible_expert")
        expert = html.escape(expert_name or "Sin experto asignado")
        st.markdown(
            '<div class="tp-project-bar">'
            f'<div class="tp-project-main"><small>PROYECTO ACTIVO</small><strong>{name}</strong></div>'
            f'<div class="tp-project-detail"><small>CÓDIGO</small><span>{code}</span></div>'
            f'<div class="tp-project-detail"><small>CIUDAD</small><span>{city}</span></div>'
            f'<div class="tp-project-detail"><small>EXPERTO RESPONSABLE</small><span>{expert}</span></div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("No hay un proyecto activo. Crea uno o abre un proyecto existente.")


def metric_card(label: str, value: str, detail: str) -> None:
    st.markdown(
        f'<div class="tp-card"><div class="tp-card-label">{html.escape(label)}</div>'
        f'<div class="tp-card-value">{html.escape(value)}</div>'
        f'<small>{html.escape(detail)}</small></div>',
        unsafe_allow_html=True,
    )
