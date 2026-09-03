"""Persistencia MySQL y manejo del proyecto activo."""

from __future__ import annotations

from time import monotonic
from typing import Any

import mysql.connector
import streamlit as st

from services.company_service import CompanyService
from services.database import DatabaseError, database_connection
from services.person_service import PersonService


class ProjectService:
    """Centraliza las operaciones de proyectos."""

    PROJECT_LIST_CACHE_SECONDS = 60

    def __init__(
        self,
        person_service: PersonService,
        company_service: CompanyService,
    ) -> None:
        self.person_service = person_service
        self.company_service = company_service

    def initialize_session(self) -> None:
        st.session_state.setdefault("active_project_id", None)
        st.session_state.setdefault("active_project_cache_id", None)
        st.session_state.setdefault("active_project_cache", None)
        st.session_state.setdefault("project_list_cache", None)
        st.session_state.setdefault("project_list_cache_time", 0.0)
        st.session_state.setdefault("current_page", "dashboard")

    def list_projects(self) -> list[dict[str, Any]]:
        cached = st.session_state.get("project_list_cache")
        cached_at = st.session_state.get("project_list_cache_time", 0.0)
        if cached is not None and monotonic() - cached_at < self.PROJECT_LIST_CACHE_SECONDS:
            return cached

        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True, buffered=True)
                cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.codigo AS code,
                        p.nombre AS name,
                        p.descripcion AS description,
                        p.ciudad AS city,
                        p.estado AS state,
                        p.fecha_inicio AS start_date,
                        p.fecha_finalizacion AS end_date,
                        p.linea_tecnologica AS technology_line,
                        p.grupo_investigacion_propietario_pi AS research_group_name,
                        p.trl_inicial AS initial_trl,
                        p.trl_objetivo AS target_trl,
                        c.id AS company_id,
                        c.nit AS company_nit,
                        c.razon_social AS company_legal_name,
                        p.creado_en AS created_at,
                        p.actualizado_en AS updated_at,
                        e.id AS expert_id,
                        e.nombre_completo AS expert_name,
                        e.tipo_documento AS expert_document_type,
                        e.numero_documento AS expert_document_number,
                        e.lugar_expedicion AS expert_document_issue_place,
                        e.correo_electronico AS expert_email,
                        e.firma_ruta AS expert_signature_path
                    FROM proyectos p
                    LEFT JOIN expertos_tecnoparque e ON e.id = p.experto_id
                    LEFT JOIN empresas c ON c.id = p.empresa_propietaria_id
                    WHERE p.eliminado_en IS NULL
                    ORDER BY p.creado_en DESC
                    """
                )
                projects = [self._map_project(row) for row in cursor.fetchall()]
                self._attach_talents(cursor, projects)
                cursor.close()
        except mysql.connector.Error as error:
            raise DatabaseError(f"No fue posible consultar los proyectos: {error}") from error
        st.session_state.project_list_cache = projects
        st.session_state.project_list_cache_time = monotonic()
        return projects

    def create_project(
        self,
        project_data: dict[str, Any],
        expert_assignment: dict[str, Any],
        talent_assignments: dict[str, dict[str, Any]],
        company_assignment: dict[str, Any],
    ) -> dict[str, Any]:
        if not talent_assignments:
            raise ValueError("Debes asociar al menos un talento al proyecto.")
        allowed_roles = {"titular", "ejecutor", "interlocutor"}
        if not set(talent_assignments).issubset(allowed_roles):
            raise ValueError("Se recibió un tipo de talento no válido.")

        uploaded_signatures: list[str] = []
        # Tras iniciar el commit, su resultado puede ser incierto si se corta la red.
        commit_attempted = False
        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True, buffered=True)
                expert = self.person_service.resolve_person(
                    cursor,
                    "expert",
                    expert_assignment,
                    uploaded_signatures,
                )
                company = self.company_service.resolve_company(
                    cursor, company_assignment
                )
                talents = []
                for role, assignment in talent_assignments.items():
                    talent = self.person_service.resolve_person(
                        cursor,
                        "talent",
                        assignment,
                        uploaded_signatures,
                    )
                    talents.append(
                        {
                            **talent,
                            "role": role,
                            "role_name": {
                                "titular": "Titular",
                                "ejecutor": "Ejecutor",
                                "interlocutor": "Interlocutor",
                            }[role],
                        }
                    )

                cursor.execute(
                    """
                    INSERT INTO proyectos (
                        codigo,
                        nombre,
                        descripcion,
                        ciudad,
                        experto_id,
                        estado,
                        fecha_inicio,
                        fecha_finalizacion,
                        linea_tecnologica,
                        trl_inicial,
                        trl_objetivo,
                        empresa_propietaria_id
                    ) VALUES (%s, %s, %s, %s, %s, 'activo', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        project_data["code"].strip(),
                        project_data["name"].strip(),
                        project_data["description"].strip(),
                        project_data["city"].strip(),
                        expert["id"],
                        project_data.get("start_date"),
                        project_data.get("end_date"),
                        project_data["technology_line"],
                        project_data["initial_trl"],
                        project_data["target_trl"],
                        company["id"] if company else None,
                    ),
                )
                project_id = cursor.lastrowid
                for talent in talents:
                    cursor.execute(
                        """
                        INSERT INTO proyecto_talentos (
                            proyecto_id,
                            talento_id,
                            tipo_talento
                        ) VALUES (%s, %s, %s)
                        """,
                        (project_id, talent["id"], talent["role"]),
                    )
                cursor.close()
                commit_attempted = True
                connection.commit()
        except mysql.connector.IntegrityError as error:
            if not commit_attempted:
                self.person_service.discard_signatures(uploaded_signatures)
            if error.errno == 1062:
                raise ValueError(
                    f"Ya existe un proyecto con el código {project_data['code'].strip()}."
                ) from error
            raise DatabaseError(f"No fue posible relacionar el proyecto: {error}") from error
        except mysql.connector.Error as error:
            if not commit_attempted:
                self.person_service.discard_signatures(uploaded_signatures)
            raise DatabaseError(f"No fue posible guardar el proyecto: {error}") from error
        except Exception:
            if not commit_attempted:
                self.person_service.discard_signatures(uploaded_signatures)
            raise

        self.invalidate_project_list_cache()
        self.set_active_project(project_id)
        return {
            "id": project_id,
            "code": project_data["code"].strip(),
            "name": project_data["name"].strip(),
            "description": project_data["description"].strip(),
            "city": project_data["city"].strip(),
            "state": "activo",
            "start_date": project_data.get("start_date"),
            "end_date": project_data.get("end_date"),
            "technology_line": project_data["technology_line"],
            "initial_trl": project_data["initial_trl"],
            "target_trl": project_data["target_trl"],
            "company_id": company["id"] if company else None,
            "company": company,
            "expert_id": expert["id"],
            "expert": expert,
            "talents": talents,
            "document_status": {"pending": 0, "draft": 0, "generated": 0},
        }

    def get_active_project(self) -> dict[str, Any] | None:
        """Retorna el proyecto activo reutilizando la copia de esta sesión."""

        project_id = st.session_state.get("active_project_id")
        if project_id is None:
            return None
        if (
            st.session_state.get("active_project_cache_id") == project_id
            and st.session_state.get("active_project_cache") is not None
        ):
            return st.session_state.active_project_cache

        project = self.get_project(project_id)
        if project is None:
            self.clear_active_project()
            return None
        self._cache_active_project(project)
        return project

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        """Consulta directamente un proyecto por ID sin cargar toda la colección."""

        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True, buffered=True)
                cursor.execute(
                    """
                    SELECT
                        p.id,
                        p.codigo AS code,
                        p.nombre AS name,
                        p.descripcion AS description,
                        p.ciudad AS city,
                        p.estado AS state,
                        p.fecha_inicio AS start_date,
                        p.fecha_finalizacion AS end_date,
                        p.linea_tecnologica AS technology_line,
                        p.grupo_investigacion_propietario_pi AS research_group_name,
                        p.trl_inicial AS initial_trl,
                        p.trl_objetivo AS target_trl,
                        c.id AS company_id,
                        c.nit AS company_nit,
                        c.razon_social AS company_legal_name,
                        p.creado_en AS created_at,
                        p.actualizado_en AS updated_at,
                        e.id AS expert_id,
                        e.nombre_completo AS expert_name,
                        e.tipo_documento AS expert_document_type,
                        e.numero_documento AS expert_document_number,
                        e.lugar_expedicion AS expert_document_issue_place,
                        e.correo_electronico AS expert_email,
                        e.firma_ruta AS expert_signature_path
                    FROM proyectos p
                    LEFT JOIN expertos_tecnoparque e ON e.id = p.experto_id
                    LEFT JOIN empresas c ON c.id = p.empresa_propietaria_id
                    WHERE p.id = %s
                      AND p.eliminado_en IS NULL
                    """,
                    (project_id,),
                )
                row = cursor.fetchone()
                projects = [self._map_project(row)] if row else []
                self._attach_talents(cursor, projects)
                cursor.close()
        except mysql.connector.Error as error:
            raise DatabaseError(f"No fue posible consultar el proyecto activo: {error}") from error
        return projects[0] if projects else None

    def delete_project(self, project_id: int, confirmation_code: str) -> None:
        """Marca un proyecto como eliminado tras validar su codigo exacto."""

        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True, buffered=True)
                cursor.execute(
                    """
                    SELECT codigo AS code
                    FROM proyectos
                    WHERE id = %s AND eliminado_en IS NULL
                    """,
                    (project_id,),
                )
                project = cursor.fetchone()
                if project is None:
                    raise ValueError("El proyecto ya no esta disponible.")
                if confirmation_code != project["code"]:
                    raise ValueError("El codigo ingresado no coincide con el proyecto.")
                cursor.execute(
                    """
                    UPDATE proyectos
                    SET eliminado_en = CURRENT_TIMESTAMP,
                        estado = 'archivado'
                    WHERE id = %s AND eliminado_en IS NULL
                    """,
                    (project_id,),
                )
                if cursor.rowcount != 1:
                    raise ValueError("No fue posible eliminar el proyecto.")
                connection.commit()
                cursor.close()
        except mysql.connector.Error as error:
            raise DatabaseError(
                f"No fue posible eliminar el proyecto: {error}"
            ) from error

        self.invalidate_project_list_cache()
        if st.session_state.get("active_project_id") == project_id:
            self.clear_active_project()

    def update_project(
        self,
        project_id: int,
        project_data: dict[str, Any],
        expert_id: int,
        talent_ids_by_role: dict[str, int],
        expert_update: dict[str, Any] | None = None,
        talent_updates: dict[int, dict[str, Any]] | None = None,
    ) -> None:
        """Actualiza datos y asociaciones del proyecto en una sola transacción."""

        if not talent_ids_by_role:
            raise ValueError("Debes asociar al menos un talento al proyecto.")
        allowed_roles = {"titular", "ejecutor", "interlocutor"}
        if not set(talent_ids_by_role).issubset(allowed_roles):
            raise ValueError("Se recibió un tipo de talento no válido.")

        uploaded_signatures: list[str] = []
        replaced_signatures: list[str] = []
        # No se eliminan archivos si MySQL pudo confirmar antes de desconectarse.
        commit_attempted = False
        committed = False
        try:
            with database_connection() as connection:
                cursor = connection.cursor()
                if expert_update is not None:
                    self.person_service.update_person(
                        cursor,
                        "expert",
                        expert_id,
                        expert_update,
                        uploaded_signatures,
                        replaced_signatures,
                    )
                for talent_id, talent_data in (talent_updates or {}).items():
                    self.person_service.update_person(
                        cursor,
                        "talent",
                        talent_id,
                        talent_data,
                        uploaded_signatures,
                        replaced_signatures,
                    )
                cursor.execute(
                    """
                    UPDATE proyectos
                    SET
                        codigo = %s,
                        nombre = %s,
                        descripcion = %s,
                        ciudad = %s,
                        experto_id = %s,
                        fecha_inicio = %s,
                        fecha_finalizacion = %s
                    WHERE id = %s
                      AND eliminado_en IS NULL
                    """,
                    (
                        project_data["code"].strip(),
                        project_data["name"].strip(),
                        project_data["description"].strip(),
                        project_data["city"].strip(),
                        expert_id,
                        project_data.get("start_date"),
                        project_data.get("end_date"),
                        project_id,
                    ),
                )
                cursor.execute(
                    "DELETE FROM proyecto_talentos WHERE proyecto_id = %s",
                    (project_id,),
                )
                for role, talent_id in talent_ids_by_role.items():
                    cursor.execute(
                        """
                        INSERT INTO proyecto_talentos (
                            proyecto_id,
                            talento_id,
                            tipo_talento
                        ) VALUES (%s, %s, %s)
                        """,
                        (project_id, talent_id, role),
                    )
                cursor.close()
                commit_attempted = True
                connection.commit()
                committed = True
        except mysql.connector.IntegrityError as error:
            if not commit_attempted:
                self.person_service.discard_signatures(uploaded_signatures)
            if error.errno == 1062:
                if "uk_proyecto_codigo" in error.msg:
                    message = (
                        f"Ya existe otro proyecto con el código "
                        f"{project_data['code'].strip()}."
                    )
                else:
                    message = (
                        "Ya existe otra persona con el tipo y número "
                        "de documento ingresados."
                    )
                raise ValueError(message) from error
            raise DatabaseError(f"No fue posible actualizar las relaciones: {error}") from error
        except mysql.connector.Error as error:
            if not commit_attempted:
                self.person_service.discard_signatures(uploaded_signatures)
            raise DatabaseError(f"No fue posible actualizar el proyecto: {error}") from error
        except Exception:
            if not commit_attempted:
                self.person_service.discard_signatures(uploaded_signatures)
            elif committed:
                self.person_service.discard_signatures(replaced_signatures)
            raise

        self.person_service.discard_signatures(replaced_signatures)

        self.invalidate_project_list_cache()
        if st.session_state.get("active_project_id") == project_id:
            self.invalidate_active_project_cache()

    def set_active_project(
        self,
        project_id: int,
        project: dict[str, Any] | None = None,
    ) -> None:
        st.session_state.active_project_id = project_id
        if project is None:
            self.invalidate_active_project_cache()
        else:
            self._cache_active_project(project)

    def invalidate_active_project_cache(self) -> None:
        st.session_state.active_project_cache_id = None
        st.session_state.active_project_cache = None

    def invalidate_project_list_cache(self) -> None:
        st.session_state.project_list_cache = None
        st.session_state.project_list_cache_time = 0.0

    def clear_active_project(self) -> None:
        st.session_state.active_project_id = None
        self.invalidate_active_project_cache()

    @staticmethod
    def _cache_active_project(project: dict[str, Any]) -> None:
        st.session_state.active_project_cache_id = project["id"]
        st.session_state.active_project_cache = project

    @staticmethod
    def _map_project(row: dict[str, Any]) -> dict[str, Any]:
        expert = None
        if row.get("expert_id") is not None:
            expert = {
                "id": row["expert_id"],
                "person_type": "expert",
                "name": row["expert_name"],
                "document_type": row["expert_document_type"],
                "document_number": row["expert_document_number"],
                "document_issue_place": row["expert_document_issue_place"],
                "email": row["expert_email"],
                "signature_path": row["expert_signature_path"],
            }
        return {
            "id": row["id"],
            "code": row["code"],
            "name": row["name"],
            "description": row["description"],
            "city": row["city"],
            "state": row["state"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "technology_line": row["technology_line"],
            "initial_trl": row["initial_trl"],
            "target_trl": row["target_trl"],
            "research_group_name": row["research_group_name"],
            "company_id": row["company_id"],
            "company": (
                {
                    "id": row["company_id"],
                    "nit": row["company_nit"],
                    "legal_name": row["company_legal_name"],
                }
                if row.get("company_id") is not None
                else None
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "expert_id": row["expert_id"],
            "expert": expert,
            "talents": [],
            "document_status": {"pending": 0, "draft": 0, "generated": 0},
        }

    @staticmethod
    def _attach_talents(cursor: Any, projects: list[dict[str, Any]]) -> None:
        if not projects:
            return
        project_ids = [project["id"] for project in projects]
        placeholders = ", ".join(["%s"] * len(project_ids))
        cursor.execute(
            f"""
            SELECT
                pt.proyecto_id AS project_id,
                pt.tipo_talento AS role,
                t.id,
                t.nombre_completo AS name,
                t.tipo_documento AS document_type,
                t.numero_documento AS document_number,
                t.lugar_expedicion AS document_issue_place,
                t.correo_electronico AS email,
                t.firma_ruta AS signature_path
            FROM proyecto_talentos pt
            INNER JOIN talentos t ON t.id = pt.talento_id
            WHERE pt.proyecto_id IN ({placeholders})
              AND t.activo = TRUE
            ORDER BY pt.proyecto_id, pt.tipo_talento
            """,
            tuple(project_ids),
        )
        projects_by_id = {project["id"]: project for project in projects}
        role_names = {
            "titular": "Titular",
            "interlocutor": "Interlocutor",
            "ejecutor": "Ejecutor",
        }
        for talent in cursor.fetchall():
            project_id = talent.pop("project_id")
            talent["person_type"] = "talent"
            talent["role_name"] = role_names[talent["role"]]
            projects_by_id[project_id]["talents"].append(talent)
