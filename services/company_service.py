"""Consulta y alta de empresas asociadas a proyectos."""

from __future__ import annotations

from time import monotonic
from typing import Any

import mysql.connector
import streamlit as st

from services.database import DatabaseError, database_connection


class CompanyService:
    """Centraliza el registro reutilizable de empresas."""

    CACHE_SECONDS = 300

    def list_companies(self) -> list[dict[str, Any]]:
        cached = st.session_state.get("company_list_cache")
        cached_at = st.session_state.get("company_list_cache_time", 0.0)
        if cached is not None and monotonic() - cached_at < self.CACHE_SECONDS:
            return cached

        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True, buffered=True)
                cursor.execute(
                    """
                    SELECT id, nit, razon_social AS legal_name
                    FROM empresas
                    WHERE activo = TRUE
                    ORDER BY razon_social, nombre
                    """
                )
                companies = cursor.fetchall()
                cursor.close()
                st.session_state.company_list_cache = companies
                st.session_state.company_list_cache_time = monotonic()
                return companies
        except mysql.connector.Error as error:
            raise DatabaseError(
                f"No fue posible consultar las empresas: {error}"
            ) from error

    @staticmethod
    def invalidate_cache() -> None:
        st.session_state.pop("company_list_cache", None)
        st.session_state.pop("company_list_cache_time", None)

    @classmethod
    def resolve_company(cls, cursor: Any, assignment: dict[str, Any]) -> dict[str, Any]:
        if assignment["mode"] == "existing":
            cursor.execute(
                """
                SELECT id, nit, razon_social AS legal_name
                FROM empresas
                WHERE id = %s AND activo = TRUE
                """,
                (assignment["id"],),
            )
            company = cursor.fetchone()
            if company is None:
                raise ValueError("La empresa seleccionada ya no est\u00e1 disponible.")
            return company

        data = assignment["data"]
        nit = data["nit"].strip()
        cursor.execute(
            """
            SELECT id
            FROM empresas
            WHERE nit = %s
            LIMIT 1
            """,
            (nit,),
        )
        if cursor.fetchone() is not None:
            raise ValueError(
                "Ya existe una empresa con ese NIT. B\u00fascala y selecci\u00f3nala."
            )
        cursor.execute(
            """
            INSERT INTO empresas (nit, razon_social)
            VALUES (%s, %s)
            """,
            (nit, data["legal_name"].strip()),
        )
        cls.invalidate_cache()
        return {
            "id": cursor.lastrowid,
            "nit": nit,
            "legal_name": data["legal_name"].strip(),
        }
