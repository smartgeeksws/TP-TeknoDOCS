"""Acceso MySQL a expertos Tecnoparque y talentos."""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any

import mysql.connector
import streamlit as st

from services.database import DatabaseError, database_connection
from services.signature_storage import SignatureStorage, SignatureStorageError


PERSON_TABLES = {
    "expert": "expertos_tecnoparque",
    "talent": "talentos",
}
LOGGER = logging.getLogger(__name__)


class PersonService:
    """Consulta personas y las resuelve dentro de transacciones de proyecto."""

    CACHE_SECONDS = 300

    def __init__(self, signature_storage: SignatureStorage | None = None) -> None:
        self.signature_storage = signature_storage or SignatureStorage()

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
        uploaded_signatures: list[str] | None = None,
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
        if uploaded_signatures is not None:
            uploaded_signatures.append(signature_path)
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
        uploaded_signatures: list[str] | None = None,
        replaced_signatures: list[str] | None = None,
    ) -> None:
        """Actualiza una persona reutilizable dentro de una transacción externa."""

        table = self._table_for(person_type)
        cursor.execute(
            f"""
            SELECT firma_ruta
            FROM {table}
            WHERE id = %s AND activo = TRUE
            FOR UPDATE
            """,
            (person_id,),
        )
        current = cursor.fetchone()
        if current is None:
            raise ValueError("La persona seleccionada ya no está disponible.")
        signature_path = (
            current.get("firma_ruta")
            if isinstance(current, dict)
            else current[0]
        )
        if data.get("signature_data"):
            new_signature_path = self._save_signature(
                data["signature_name"],
                data["signature_data"],
            )
            if uploaded_signatures is not None:
                uploaded_signatures.append(new_signature_path)
            if signature_path and replaced_signatures is not None:
                replaced_signatures.append(signature_path)
            signature_path = new_signature_path
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

    def _save_signature(self, original_name: str, data: bytes) -> str:
        return self.signature_storage.save(original_name, data)

    def discard_signatures(self, references: list[str]) -> None:
        """Limpia firmas FTPS sin ocultar el error principal de una operación."""

        for reference in dict.fromkeys(references):
            try:
                self.signature_storage.delete(reference)
            except SignatureStorageError as error:
                LOGGER.warning("No fue posible limpiar una firma FTPS: %s", error)
