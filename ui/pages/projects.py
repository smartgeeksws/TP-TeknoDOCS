"""Pantallas para crear y abrir proyectos."""

from __future__ import annotations

import re
from typing import Any

import streamlit as st

from config.settings import DOCUMENT_TYPES, TALENT_ROLES
from services.database import DatabaseError
from services.person_service import PersonService
from services.project_service import ProjectService


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _person_fields(
    prefix: str,
    title: str,
    *,
    require_email: bool,
) -> dict[str, Any]:
    st.markdown(f"#### {title}")
    name = st.text_input("Nombre completo *", key=f"{prefix}_name")
    first, second = st.columns([1, 2])
    with first:
        document_type = st.selectbox(
            "Tipo de documento *",
            DOCUMENT_TYPES,
            key=f"{prefix}_document_type",
        )
    with second:
        document_number = st.text_input(
            "Número de documento *",
            key=f"{prefix}_document_number",
        )
    document_issue_place = st.text_input(
        "Lugar de expedición *",
        key=f"{prefix}_document_issue_place",
    )
    email = st.text_input(
        f"Correo electrónico{' *' if require_email else ''}",
        key=f"{prefix}_email",
    )
    signature = st.file_uploader(
        "Firma *",
        type=["png", "jpg", "jpeg"],
        key=f"{prefix}_signature",
        help="Carga una imagen PNG, JPG o JPEG.",
    )
    return {
        "name": name,
        "email": email,
        "document_type": document_type,
        "document_number": document_number,
        "document_issue_place": document_issue_place,
        "signature": signature,
    }


def _person_assignment(
    prefix: str,
    title: str,
    people: list[dict[str, Any]],
    *,
    require_email: bool,
) -> dict[str, Any]:
    options = ["Registrar nuevo"]
    if people:
        options.insert(0, "Seleccionar existente")
    mode = st.radio(
        f"Cómo asociar {title.lower()}",
        options,
        horizontal=True,
        key=f"{prefix}_mode",
    )

    if mode == "Seleccionar existente":
        people_by_id = {person["id"]: person for person in people}
        person_id = st.selectbox(
            title,
            options=list(people_by_id),
            format_func=lambda current_id: (
                f"{people_by_id[current_id]['name']} · "
                f"{people_by_id[current_id]['document_type']} "
                f"{people_by_id[current_id]['document_number']}"
            ),
            key=f"{prefix}_existing",
        )
        person = people_by_id[person_id]
        details = (
            f"Documento expedido en: {person['document_issue_place']}"
            + (f" · Correo: {person['email']}" if person.get("email") else "")
        )
        st.info(details)
        return {"mode": "existing", "id": person_id, "person": person}

    data = _person_fields(
        prefix,
        f"Registrar {title.lower()}",
        require_email=require_email,
    )
    return {"mode": "new", "data": data}


def _validate_new_person(
    person: dict[str, Any],
    label: str,
    *,
    require_email: bool,
    require_signature: bool = True,
) -> list[str]:
    errors = []
    required = {
        "name": "nombre",
        "document_number": "número de documento",
        "document_issue_place": "lugar de expedición",
    }
    for field, field_label in required.items():
        if not person[field].strip():
            errors.append(f"Falta el {field_label} de {label}.")
    if require_email and not person["email"].strip():
        errors.append(f"Falta el correo electrónico de {label}.")
    elif person["email"].strip() and not EMAIL_PATTERN.match(person["email"].strip()):
        errors.append(f"El correo electrónico de {label} no es válido.")
    if require_signature and person["signature"] is None:
        errors.append(f"Falta la firma de {label}.")
    return errors


def _serialize_assignment(assignment: dict[str, Any]) -> dict[str, Any]:
    if assignment["mode"] == "existing":
        return {"mode": "existing", "id": assignment["id"]}
    data = assignment["data"]
    signature = data["signature"]
    return {
        "mode": "new",
        "data": {
            "name": data["name"],
            "email": data["email"],
            "document_type": data["document_type"],
            "document_number": data["document_number"],
            "document_issue_place": data["document_issue_place"],
            "signature_name": signature.name,
            "signature_data": signature.getvalue(),
        },
    }


def _editable_person_fields(
    prefix: str,
    person: dict[str, Any],
    *,
    require_email: bool,
) -> dict[str, Any]:
    name = st.text_input(
        "Nombre completo *",
        value=person.get("name") or "",
        key=f"{prefix}_edit_name",
    )
    columns = st.columns([1, 2])
    document_types = list(DOCUMENT_TYPES)
    current_document_type = person.get("document_type")
    document_index = (
        document_types.index(current_document_type)
        if current_document_type in document_types
        else 0
    )
    with columns[0]:
        document_type = st.selectbox(
            "Tipo de documento *",
            document_types,
            index=document_index,
            key=f"{prefix}_edit_document_type",
        )
    with columns[1]:
        document_number = st.text_input(
            "Número de documento *",
            value=person.get("document_number") or "",
            key=f"{prefix}_edit_document_number",
        )
    document_issue_place = st.text_input(
        "Lugar de expedición *",
        value=person.get("document_issue_place") or "",
        key=f"{prefix}_edit_issue_place",
    )
    email = st.text_input(
        f"Correo electrónico{' *' if require_email else ''}",
        value=person.get("email") or "",
        key=f"{prefix}_edit_email",
    )
    signature = st.file_uploader(
        "Reemplazar firma",
        type=["png", "jpg", "jpeg"],
        key=f"{prefix}_edit_signature",
        help="Es opcional. Si no cargas otra imagen, se conserva la firma actual.",
    )
    if person.get("signature_path"):
        st.caption("La persona ya tiene una firma registrada.")
    return {
        "name": name,
        "email": email,
        "document_type": document_type,
        "document_number": document_number,
        "document_issue_place": document_issue_place,
        "signature": signature,
        "signature_path": person.get("signature_path"),
    }


def _serialize_person_update(data: dict[str, Any]) -> dict[str, Any]:
    signature = data.get("signature")
    return {
        "name": data["name"],
        "email": data["email"],
        "document_type": data["document_type"],
        "document_number": data["document_number"],
        "document_issue_place": data["document_issue_place"],
        "signature_path": data.get("signature_path"),
        "signature_name": signature.name if signature else None,
        "signature_data": signature.getvalue() if signature else None,
    }


def render_create_project(
    project_service: ProjectService,
    person_service: PersonService,
) -> None:
    st.title("Crear proyecto")
    st.caption("Registra la información general y las personas vinculadas al proyecto.")

    with st.container(border=True):
        st.subheader("1. Información del proyecto")
        first, second = st.columns(2)
        with first:
            code = st.text_input("Código del proyecto *")
        with second:
            name = st.text_input("Nombre del proyecto *")
        city = st.text_input("Ciudad del proyecto o firma de documentos *")
        description = st.text_area(
            "Descripción del proyecto *",
            height=240,
            placeholder="Describe ampliamente el alcance y contexto del proyecto.",
        )
        date_columns = st.columns(2)
        with date_columns[0]:
            start_date = st.date_input("Fecha de inicio", value=None)
        with date_columns[1]:
            end_date = st.date_input("Fecha de finalización", value=None)

    experts = person_service.list_people("expert")
    talents = person_service.list_people("talent")

    with st.container(border=True):
        st.subheader("2. Experto Tecnoparque")
        expert_assignment = _person_assignment(
            "expert",
            "Experto Tecnoparque",
            experts,
            require_email=True,
        )

    with st.container(border=True):
        st.subheader("3. Talentos asociados al proyecto")
        selected_roles = st.multiselect(
            "Selecciona al menos un tipo de talento *",
            options=list(TALENT_ROLES),
            format_func=lambda role: TALENT_ROLES[role],
            placeholder="Titular, ejecutor o interlocutor",
        )
        if not selected_roles:
            st.warning("Debes seleccionar al menos un talento.")

        talent_assignments: dict[str, dict[str, Any]] = {}
        for role in selected_roles:
            st.markdown("---")
            talent_assignments[role] = _person_assignment(
                f"talent_{role}",
                f"Talento {TALENT_ROLES[role]}",
                talents,
                require_email=True,
            )

    if st.button("Crear proyecto", type="primary", use_container_width=True):
        errors = []
        project_fields = {
            "código del proyecto": code,
            "nombre del proyecto": name,
            "ciudad del proyecto": city,
            "descripción del proyecto": description,
        }
        for label, value in project_fields.items():
            if not value.strip():
                errors.append(f"Falta el {label}.")
        if start_date and end_date and end_date < start_date:
            errors.append("La fecha de finalización no puede ser anterior a la fecha de inicio.")
        if not selected_roles:
            errors.append("Debes seleccionar al menos un talento.")

        if expert_assignment["mode"] == "new":
            errors.extend(
                _validate_new_person(
                    expert_assignment["data"],
                    "el experto",
                    require_email=True,
                )
            )
        elif not expert_assignment["person"].get("email"):
            errors.append(
                "El experto seleccionado no tiene correo electrónico registrado."
            )

        for role, assignment in talent_assignments.items():
            label = f"el talento {TALENT_ROLES[role]}"
            if assignment["mode"] == "new":
                errors.extend(
                    _validate_new_person(
                        assignment["data"],
                        label,
                        require_email=True,
                    )
                )
            elif not assignment["person"].get("email"):
                errors.append(
                    f"El talento {TALENT_ROLES[role].lower()} seleccionado "
                    "no tiene correo electrónico registrado."
                )

        if errors:
            st.error("\n".join(f"• {error}" for error in errors))
            return

        try:
            project_service.create_project(
                {
                    "code": code,
                    "name": name,
                    "city": city,
                    "description": description,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                _serialize_assignment(expert_assignment),
                {
                    role: _serialize_assignment(assignment)
                    for role, assignment in talent_assignments.items()
                },
            )
        except (DatabaseError, OSError, ValueError) as error:
            st.error(f"No fue posible crear el proyecto: {error}")
            return

        st.session_state.current_page = "dashboard"
        st.success("Proyecto creado correctamente.")
        st.rerun()


def render_projects(project_service: ProjectService) -> None:
    st.title("Mis proyectos")
    st.caption("Selecciona el proyecto sobre el que deseas trabajar.")
    projects = project_service.list_projects()

    if not projects:
        st.markdown(
            '<div class="tp-empty"><h3>No hay proyectos registrados</h3>'
            '<p>Crea el primer proyecto para comenzar.</p></div>',
            unsafe_allow_html=True,
        )
        return

    filter_columns = st.columns([2, 2])
    with filter_columns[0]:
        code_filter = st.text_input(
            "Filtrar por código",
            placeholder="Escribe todo o parte del código",
            key="projects_code_filter",
        )
    expert_names = sorted(
        {
            project["expert"]["name"]
            for project in projects
            if project.get("expert") and project["expert"].get("name")
        },
        key=str.casefold,
    )
    with filter_columns[1]:
        expert_filter = st.selectbox(
            "Filtrar por experto",
            options=["Todos los expertos", *expert_names],
            key="projects_expert_filter",
        )

    normalized_code = code_filter.strip().casefold()
    filtered_projects = [
        project
        for project in projects
        if (
            not normalized_code
            or normalized_code in (project.get("code") or "").casefold()
        )
        and (
            expert_filter == "Todos los expertos"
            or (
                project.get("expert")
                and project["expert"].get("name") == expert_filter
            )
        )
    ]

    st.caption(
        f"{len(filtered_projects)} de {len(projects)} proyectos encontrados"
    )
    if not filtered_projects:
        st.info("No hay proyectos que coincidan con los filtros seleccionados.")
        return

    for project in filtered_projects:
        with st.container(border=True):
            details, action = st.columns([4, 1])
            with details:
                st.subheader(project["name"])
                st.caption(project.get("code") or "Sin código")
                st.write(f"**Ciudad:** {project.get('city') or 'Sin ciudad'}")
                expert = project.get("expert") or {}
                st.write(
                    f"**Experto responsable:** "
                    f"{expert.get('name') or 'Sin experto asignado'}"
                )
                talent_names = [
                    talent.get("role_name", talent.get("role", "Talento"))
                    for talent in project.get("talents", [])
                ]
                st.write(
                    f"**Talentos:** {', '.join(talent_names) if talent_names else 'Sin talentos'}"
                )
            with action:
                is_active = project["id"] == st.session_state.get("active_project_id")
                st.write("Proyecto activo" if is_active else "")
                if st.button(
                    "Abrir proyecto",
                    key=f"open_{project['id']}",
                    disabled=is_active,
                ):
                    project_service.set_active_project(project["id"])
                    st.session_state.current_page = "dashboard"
                    st.rerun()


def render_edit_project(
    project_service: ProjectService,
    person_service: PersonService,
) -> None:
    project = project_service.get_active_project()
    if project is None:
        st.warning("Debes abrir un proyecto antes de editarlo.")
        if st.button("Ir a Mis proyectos"):
            st.session_state.current_page = "projects"
            st.rerun()
        return

    st.title("Editar proyecto")
    st.caption("Actualiza la información y las asociaciones del proyecto activo.")

    with st.container(border=True):
        st.subheader("1. Información del proyecto")
        columns = st.columns(2)
        with columns[0]:
            code = st.text_input(
                "Código del proyecto *",
                value=project.get("code") or "",
                key="edit_project_code",
            )
        with columns[1]:
            name = st.text_input(
                "Nombre del proyecto *",
                value=project.get("name") or "",
                key="edit_project_name",
            )
        city = st.text_input(
            "Ciudad del proyecto o firma de documentos *",
            value=project.get("city") or "",
            key="edit_project_city",
        )
        description = st.text_area(
            "Descripción del proyecto *",
            value=project.get("description") or "",
            height=240,
            key="edit_project_description",
        )
        date_columns = st.columns(2)
        with date_columns[0]:
            start_date = st.date_input(
                "Fecha de inicio",
                value=project.get("start_date"),
                key="edit_project_start_date",
            )
        with date_columns[1]:
            end_date = st.date_input(
                "Fecha de finalización",
                value=project.get("end_date"),
                key="edit_project_end_date",
            )

    experts = person_service.list_people("expert")
    talents = person_service.list_people("talent")
    if not experts:
        st.error("No hay expertos activos disponibles para asociar.")
        return
    if not talents:
        st.error("No hay talentos activos disponibles para asociar.")
        return

    with st.container(border=True):
        st.subheader("2. Experto Tecnoparque")
        experts_by_id = {expert["id"]: expert for expert in experts}
        expert_ids = list(experts_by_id)
        current_expert_id = project.get("expert_id")
        expert_index = (
            expert_ids.index(current_expert_id)
            if current_expert_id in expert_ids
            else 0
        )
        expert_id = st.selectbox(
            "Experto responsable *",
            options=expert_ids,
            index=expert_index,
            format_func=lambda current_id: (
                f"{experts_by_id[current_id]['name']} · "
                f"{experts_by_id[current_id]['document_type']} "
                f"{experts_by_id[current_id]['document_number']}"
            ),
            key="edit_project_expert",
        )

    with st.container(border=True):
        st.subheader("3. Talentos asociados al proyecto")
        current_talents = {
            talent["role"]: talent
            for talent in project.get("talents", [])
        }
        selected_roles = st.multiselect(
            "Selecciona al menos un tipo de talento *",
            options=list(TALENT_ROLES),
            default=[
                role
                for role in TALENT_ROLES
                if role in current_talents
            ],
            format_func=lambda role: TALENT_ROLES[role],
            key="edit_project_roles",
        )
        if not selected_roles:
            st.warning("Debes conservar al menos un talento asociado.")

        talents_by_id = {talent["id"]: talent for talent in talents}
        talent_ids = list(talents_by_id)
        talent_ids_by_role: dict[str, int] = {}
        for role in selected_roles:
            current_talent_id = current_talents.get(role, {}).get("id")
            talent_index = (
                talent_ids.index(current_talent_id)
                if current_talent_id in talent_ids
                else 0
            )
            talent_ids_by_role[role] = st.selectbox(
                f"Talento {TALENT_ROLES[role]} *",
                options=talent_ids,
                index=talent_index,
                format_func=lambda current_id: (
                    f"{talents_by_id[current_id]['name']} · "
                    f"{talents_by_id[current_id]['document_type']} "
                    f"{talents_by_id[current_id]['document_number']}"
                ),
                key=f"edit_project_talent_{role}",
            )

    expert_update = None
    talent_updates: dict[int, dict[str, Any]] = {}
    with st.container(border=True):
        st.subheader("4. Datos de expertos y talentos")
        edit_people = st.checkbox(
            "Editar los datos personales asociados",
            key="edit_project_people_enabled",
        )
        if edit_people:
            st.warning(
                "Estos son registros reutilizables. Los cambios se reflejarán "
                "en todos los proyectos donde participe la persona."
            )
            with st.expander("Editar experto Tecnoparque"):
                expert_update = _editable_person_fields(
                    "project_expert",
                    experts_by_id[expert_id],
                    require_email=True,
                )

            unique_talents: dict[int, dict[str, Any]] = {}
            roles_by_talent: dict[int, list[str]] = {}
            for role, talent_id in talent_ids_by_role.items():
                unique_talents[talent_id] = talents_by_id[talent_id]
                roles_by_talent.setdefault(talent_id, []).append(role)

            for talent_id, talent in unique_talents.items():
                roles = roles_by_talent[talent_id]
                role_labels = ", ".join(TALENT_ROLES[role] for role in roles)
                with st.expander(f"Editar talento · {role_labels}"):
                    talent_updates[talent_id] = _editable_person_fields(
                        f"project_talent_{talent_id}",
                        talent,
                        require_email=True,
                    )

    actions = st.columns([1, 1, 3])
    with actions[0]:
        save = st.button(
            "Guardar cambios",
            type="primary",
            use_container_width=True,
        )
    with actions[1]:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.current_page = "dashboard"
            st.rerun()

    if not save:
        return

    errors = []
    for label, value in {
        "código del proyecto": code,
        "nombre del proyecto": name,
        "ciudad del proyecto": city,
        "descripción del proyecto": description,
    }.items():
        if not value.strip():
            errors.append(f"Falta el {label}.")
    if start_date and end_date and end_date < start_date:
        errors.append("La fecha de finalización no puede ser anterior a la fecha de inicio.")
    if not talent_ids_by_role:
        errors.append("Debes asociar al menos un talento.")
    if not experts_by_id[expert_id].get("email"):
        if not expert_update or not expert_update["email"].strip():
            errors.append("El experto seleccionado no tiene correo electrónico.")
    for talent_id in set(talent_ids_by_role.values()):
        if not talents_by_id[talent_id].get("email"):
            pending_talent = talent_updates.get(talent_id)
            if not pending_talent or not pending_talent["email"].strip():
                errors.append(
                    f"El talento {talents_by_id[talent_id]['name']} no tiene "
                    "correo electrónico."
                )

    if expert_update is not None:
        errors.extend(
            _validate_new_person(
                expert_update,
                "el experto",
                require_email=True,
                require_signature=False,
            )
        )
    for talent_id, talent_update in talent_updates.items():
        errors.extend(
            _validate_new_person(
                talent_update,
                "el talento",
                require_email=True,
                require_signature=False,
            )
        )

    if errors:
        st.error("\n".join(f"• {error}" for error in errors))
        return

    try:
        project_service.update_project(
            project["id"],
            {
                "code": code,
                "name": name,
                "city": city,
                "description": description,
                "start_date": start_date,
                "end_date": end_date,
            },
            expert_id,
            talent_ids_by_role,
            _serialize_person_update(expert_update) if expert_update else None,
            {
                talent_id: _serialize_person_update(data)
                for talent_id, data in talent_updates.items()
            },
        )
    except (DatabaseError, ValueError) as error:
        st.error(f"No fue posible actualizar el proyecto: {error}")
        return

    st.session_state.current_page = "dashboard"
    st.success("Proyecto actualizado correctamente.")
    st.rerun()
