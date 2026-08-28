"""Generacion asistida del contenido tecnico del proyecto base tecnologica."""

from __future__ import annotations

import json
import os
from typing import Any

import streamlit as st


class ProjectContentError(RuntimeError):
    """Error controlado al generar contenido con OpenAI."""


class ProjectContentService:
    """Genera contenido estructurado exclusivamente bajo accion del usuario."""

    FIELDS = (
        "main_approach",
        "general_objective",
        "specific_objective_1",
        "specific_objective_2",
        "specific_objective_3",
        "specific_objective_4",
        "scope",
    )

    def generate(self, project: dict[str, Any]) -> dict[str, str]:
        try:
            from openai import OpenAI, OpenAIError
        except ImportError as error:
            raise ProjectContentError(
                "La dependencia openai no esta instalada."
            ) from error

        api_key = self._setting("OPENAI_API_KEY", "api_key")
        if not api_key:
            raise ProjectContentError(
                "Configura OPENAI_API_KEY en variables de entorno o secrets."
            )
        model = self._setting("OPENAI_MODEL", "model") or "gpt-5-mini"
        schema = {
            "type": "object",
            "properties": {
                field: {"type": "string", "minLength": 1}
                for field in self.FIELDS
            },
            "required": list(self.FIELDS),
            "additionalProperties": False,
        }
        instructions = (
            "Actua como formulador tecnico de proyectos de innovacion y desarrollo "
            "tecnologico del SENA. Redacta en espanol profesional y concreto. "
            "Usa solamente los datos proporcionados; no inventes tecnologias, "
            "beneficiarios, resultados ni capacidades. Todos los objetivos deben "
            "comenzar con un verbo en infinitivo. Los cuatro objetivos especificos "
            "deben ser coherentes entre si, con el objetivo general y con los TRL. "
            "El alcance debe delimitar hasta donde llega el proyecto y el resultado "
            "tecnologico esperado. Si falta informacion, redacta de forma prudente "
            "sin completar datos inexistentes."
        )
        try:
            response = OpenAI(api_key=api_key, timeout=60.0).responses.create(
                model=model,
                instructions=instructions,
                input=(
                    "Genera el contenido estructurado para este proyecto:\n"
                    + json.dumps(self._safe_context(project), ensure_ascii=False)
                ),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "contenido_proyecto_base_tecnologica",
                        "schema": schema,
                        "strict": True,
                    }
                },
                store=False,
            )
            content = json.loads(response.output_text)
        except (OpenAIError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProjectContentError(
                f"No fue posible generar el contenido con OpenAI: {error}"
            ) from error

        if any(not str(content.get(field, "")).strip() for field in self.FIELDS):
            raise ProjectContentError("OpenAI no devolvio todos los campos requeridos.")
        return {field: str(content[field]).strip() for field in self.FIELDS}

    @staticmethod
    def _safe_context(project: dict[str, Any]) -> dict[str, Any]:
        """Excluye NIT, documentos, correos y nombres de personas."""

        return {
            "codigo": project.get("code"),
            "nombre": project.get("name"),
            "descripcion": project.get("description"),
            "linea_tecnologica": project.get("technology_line"),
            "trl_inicial": project.get("initial_trl"),
            "trl_objetivo": project.get("target_trl"),
            "roles_participantes": [
                talent.get("role_name") or talent.get("role")
                for talent in project.get("talents", [])
            ],
        }

    @staticmethod
    def _setting(environment_name: str, secret_name: str) -> str | None:
        environment_value = os.getenv(environment_name)
        if environment_value:
            return environment_value
        try:
            openai_secrets = st.secrets.get("openai", {})
            value = openai_secrets.get(secret_name)
            if value:
                return str(value)
            direct_value = st.secrets.get(environment_name)
            return str(direct_value) if direct_value else None
        except Exception:
            return None
