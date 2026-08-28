"""Acceso MySQL a expertos Tecnoparque y talentos."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

import mysql.connector
import streamlit as st

from config.settings import DATA_DIR, SIGNATURES_DIR
from services.database import DatabaseError, database_connection


PERSON_TABLES = {
    "expert": "expertos_tecnoparque",
    "talent": "talentos",
}


class PersonService:
    """Consulta personas y las resuelve dentro de transacciones de proyecto."""

    CACHE_SECONDS = 300

    def __init__(self) -> None:
        SIGNATURES_DIR.mkdir(parents=True, exist_ok=True)

    def list_people(self, person_type: str) -> list[dict[str, Any]]:
        table = self._table_for(person_type)
        cache_key = f"people_cache_{person_type}"
        time_key = f"people_cache_time_{person_type}"
        cached = st.session_state.get(cache_key)
        cached_at = st.session_state.get(time_key, 0.0)
        if cached is not None and monotonic() - cached_at < self.CACHE_SECONDS:
            return cached

        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True, buffered=True)
                cursor.execute(
                    f"""
                    SELECT
                        id,
                        nombre_completo AS name,
                        tipo_documento AS document_type,
                        numero_documento AS document_number,
                        lugar_expedicion AS document_issue_place,
                        correo_electronico AS email,
                        firma_ruta AS signature_path
                    FROM {table}
                    WHERE activo = TRUE
                    ORDER BY nombre_completo
                    """
                )
                people = cursor.fetchall()
                cursor.close()
        except mysql.connector.Error as error:
            raise DatabaseError(f"No fue posible consultar las personas: {error}") from error

        for person in people:
            person["person_type"] = person_type
        st.session_state[cache_key] = people
        st.session_state[time_key] = monotonic()
        return people

    @staticmethod
    def invalidate_cache(person_type: str | None = None) -> None:
        person_types = (person_type,) if person_type else tuple(PERSON_TABLES)
        for current_type in person_types:
            st.session_state.pop(f"people_cache_{current_type}", None)
            st.session_state.pop(f"people_cache_time_{current_type}", None)

    def resolve_person(
        self,
        cursor: Any,
        person_type: str,
        assignment: dict[str, Any],
    ) -> dict[str, Any]:
        """Obtiene una persona existente o la inserta usando el cursor recibido."""

        table = self._table_for(person_type)
        if assignment["mode"] == "existing":
            cursor.execute(
                f"""
                SELECT
                    id,
                    nombre_completo AS name,
                    tipo_documento AS document_type,
                    numero_documento AS document_number,
                    lugar_expedicion AS document_issue_place,
                    correo_electronico AS email,
                    firma_ruta AS signature_path
                FROM {table}
                WHERE id = %s AND activo = TRUE
                """,
                (assignment["id"],),
            )
            person = cursor.fetchone()
            if person is None:
                raise ValueError("La persona seleccionada ya no está disponible.")
            person["person_type"] = person_type
            return person

        data = assignment["data"]
        cursor.execute(
            f"""
            SELECT
                id,
                nombre_completo AS name,
                tipo_documento AS document_type,
                numero_documento AS document_number,
                lugar_expedicion AS document_issue_place,
                correo_electronico AS email,
                firma_ruta AS signature_path
            FROM {table}
            WHERE tipo_documento = %s
              AND numero_documento = %s
            LIMIT 1
            """,
            (data["document_type"], data["document_number"].strip()),
        )
        person = cursor.fetchone()
        if person:
            if not person.get("email") and data.get("email"):
                cursor.execute(
                    f"UPDATE {table} SET correo_electronico = %s WHERE id = %s",
                    (data["email"].strip(), person["id"]),
                )
                person["email"] = data["email"].strip()
                self.invalidate_cache(person_type)
            person["person_type"] = person_type
            return person

        signature_path = self._save_signature(
            data["signature_name"],
            data["signature_data"],
        )
        cursor.execute(
            f"""
            INSERT INTO {table} (
                nombre_completo,
                tipo_documento,
                numero_documento,
                lugar_expedicion,
                correo_electronico,
                firma_ruta
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                data["name"].strip(),
                data["document_type"],
                data["document_number"].strip(),
                data["document_issue_place"].strip(),
                data.get("email", "").strip() or None,
                signature_path,
            ),
        )
        self.invalidate_cache(person_type)
        return {
            "id": cursor.lastrowid,
            "person_type": person_type,
            "name": data["name"].strip(),
            "document_type": data["document_type"],
            "document_number": data["document_number"].strip(),
            "document_issue_place": data["document_issue_place"].strip(),
            "email": data.get("email", "").strip() or None,
            "signature_path": signature_path,
        }

    def update_person(
        self,
        cursor: Any,
        person_type: str,
        person_id: int,
        data: dict[str, Any],
    ) -> None:
        """Actualiza una persona reutilizable dentro de una transacción externa."""

        table = self._table_for(person_type)
        signature_path = data.get("signature_path")
        if data.get("signature_data"):
            signature_path = self._save_signature(
                data["signature_name"],
                data["signature_data"],
            )
        cursor.execute(
            f"""
            UPDATE {table}
            SET
                nombre_completo = %s,
                tipo_documento = %s,
                numero_documento = %s,
                lugar_expedicion = %s,
                correo_electronico = %s,
                firma_ruta = %s
            WHERE id = %s
              AND activo = TRUE
            """,
            (
                data["name"].strip(),
                data["document_type"],
                data["document_number"].strip(),
                data["document_issue_place"].strip(),
                data.get("email", "").strip() or None,
                signature_path,
                person_id,
            ),
        )
        self.invalidate_cache(person_type)

    @staticmethod
    def _table_for(person_type: str) -> str:
        try:
            return PERSON_TABLES[person_type]
        except KeyError as error:
            raise ValueError(f"Tipo de persona no válido: {person_type}.") from error

    @staticmethod
    def _save_signature(original_name: str, data: bytes) -> str:
        extension = Path(original_name).suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg"}:
            raise ValueError("La firma debe ser una imagen PNG, JPG o JPEG.")
        filename = f"{uuid4()}{extension}"
        path = SIGNATURES_DIR / filename
        path.write_bytes(data)
        return str(path.relative_to(DATA_DIR.parent))
