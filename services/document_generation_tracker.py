"""Persistence of document generation counters by project and document key."""

from __future__ import annotations

import json

import mysql.connector

from services.database import DatabaseError, database_connection


class DocumentGenerationTracker:
    """Tracks document generations independently for every project."""

    def record(self, project_id: int, document_key: str) -> None:
        try:
            with database_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO documentos_proyecto (
                        proyecto_id, clave_documento, datos_formulario,
                        cantidad_generaciones, generado_en
                    ) VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                        cantidad_generaciones = cantidad_generaciones + 1,
                        generado_en = CURRENT_TIMESTAMP
                    """,
                    (project_id, document_key, json.dumps({})),
                )
                connection.commit()
                cursor.close()
        except mysql.connector.Error as error:
            raise DatabaseError(
                f"No fue posible registrar la generacion del documento: {error}"
            ) from error

    def counts_for_project(self, project_id: int) -> dict[str, int]:
        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT clave_documento, cantidad_generaciones
                    FROM documentos_proyecto
                    WHERE proyecto_id = %s
                    """,
                    (project_id,),
                )
                rows = cursor.fetchall()
                cursor.close()
        except mysql.connector.Error as error:
            raise DatabaseError(
                f"No fue posible consultar el avance documental: {error}"
            ) from error
        return {
            row["clave_documento"]: int(row["cantidad_generaciones"] or 0)
            for row in rows
        }
