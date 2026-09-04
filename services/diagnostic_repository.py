"""Persistencia por proyecto del formulario y fuentes del GCDTP-F-020."""

from __future__ import annotations

import json
from typing import Any

import mysql.connector

from services.database import DatabaseError, database_connection


class DiagnosticRepository:
    DOCUMENT_KEY = "diagnostico_estado_arte"

    def load(self, project_id: int) -> dict[str, Any] | None:
        try:
            with database_connection() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT datos_formulario, contenido_generado, fuentes_json,
                           generado_en, actualizado_en
                    FROM documentos_proyecto
                    WHERE proyecto_id = %s AND clave_documento = %s
                    """,
                    (project_id, self.DOCUMENT_KEY),
                )
                row = cursor.fetchone()
                cursor.close()
        except mysql.connector.Error as error:
            raise DatabaseError(
                f"No fue posible consultar el diagnóstico guardado: {error}"
            ) from error
        if row is None:
            return None
        return {
            "form": self._loads(row["datos_formulario"], {}),
            "content": self._loads(row["contenido_generado"], None),
            "sources": self._loads(row["fuentes_json"], []),
            "generated_at": row["generado_en"],
            "updated_at": row["actualizado_en"],
        }

    def save_form(self, project_id: int, form_data: dict[str, Any]) -> None:
        self._upsert(project_id, form_data, None, None, generated=False)

    def save_generation(
        self,
        project_id: int,
        form_data: dict[str, Any],
        content: dict[str, Any],
        sources: list[dict[str, Any]],
    ) -> None:
        self._upsert(project_id, form_data, content, sources, generated=True)

    def _upsert(
        self,
        project_id: int,
        form_data: dict[str, Any],
        content: dict[str, Any] | None,
        sources: list[dict[str, Any]] | None,
        *,
        generated: bool,
    ) -> None:
        try:
            with database_connection() as connection:
                cursor = connection.cursor()
                if generated:
                    cursor.execute(
                        """
                        INSERT INTO documentos_proyecto (
                            proyecto_id, clave_documento, datos_formulario,
                            contenido_generado, fuentes_json, generado_en,
                            cantidad_generaciones
                        ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 1)
                        ON DUPLICATE KEY UPDATE
                            datos_formulario = VALUES(datos_formulario),
                            contenido_generado = VALUES(contenido_generado),
                            fuentes_json = VALUES(fuentes_json),
                            generado_en = CURRENT_TIMESTAMP,
                            cantidad_generaciones = cantidad_generaciones + 1
                        """,
                        (
                            project_id,
                            self.DOCUMENT_KEY,
                            self._dumps(form_data),
                            self._dumps(content),
                            self._dumps(sources),
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO documentos_proyecto (
                            proyecto_id, clave_documento, datos_formulario
                        ) VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            datos_formulario = VALUES(datos_formulario)
                        """,
                        (project_id, self.DOCUMENT_KEY, self._dumps(form_data)),
                    )
                connection.commit()
                cursor.close()
        except mysql.connector.Error as error:
            raise DatabaseError(
                f"No fue posible guardar el diagnóstico: {error}"
            ) from error

    @staticmethod
    def _dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _loads(value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
