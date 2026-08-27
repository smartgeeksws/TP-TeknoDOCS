"""Consulta y alta de empresas asociadas a proyectos."""

from __future__ import annotations

from typing import Any

import mysql.connector

from services.database import DatabaseError, database_connection


class CompanyService:
    """Centraliza el registro reutilizable de empresas."""

    def list_companies(self) -> list[dict[str, Any]]:
        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True, buffered=True)
                cursor.execute(
                    """
                    SELECT id, nit, nombre AS name, razon_social AS legal_name
                    FROM empresas
                    WHERE activo = TRUE
                    ORDER BY razon_social, nombre
                    """
                )
                companies = cursor.fetchall()
                cursor.close()
                return companies
        except mysql.connector.Error as error:
            raise DatabaseError(
                f"No fue posible consultar las empresas: {error}"
            ) from error

    @staticmethod
    def resolve_company(cursor: Any, assignment: dict[str, Any]) -> dict[str, Any]:
        if assignment["mode"] == "existing":
            cursor.execute(
                """
                SELECT id, nit, nombre AS name, razon_social AS legal_name
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
            INSERT INTO empresas (nit, nombre, razon_social)
            VALUES (%s, %s, %s)
            """,
            (nit, data["name"].strip(), data["legal_name"].strip()),
        )
        return {
            "id": cursor.lastrowid,
            "nit": nit,
            "name": data["name"].strip(),
            "legal_name": data["legal_name"].strip(),
        }
