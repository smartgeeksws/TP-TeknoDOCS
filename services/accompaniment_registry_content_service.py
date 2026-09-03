"""Generacion estructurada de actividades para GCDTP-F-022."""

from __future__ import annotations

import json
from typing import Any

from services.project_content_service import ProjectContentError, ProjectContentService


class AccompanimentRegistryContentService:
    """Genera actividades tecnicas en una sola llamada a OpenAI."""

    ALLOWED_TYPES = (
        "Accion de transferencia",
        "Acompanamiento",
        "Orientaciones",
        "Programa de fortalecimiento",
        "Otro",
    )

    def generate(
        self,
        project: dict[str, Any],
        form_data: dict[str, Any],
        equipments: list[dict[str, Any]],
        materials: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            from openai import OpenAI, OpenAIError
        except ImportError as error:
            raise ProjectContentError("La dependencia openai no esta instalada.") from error

        api_key = ProjectContentService._setting("OPENAI_API_KEY", "api_key")
        if not api_key:
            raise ProjectContentError(
                "Configura OPENAI_API_KEY en variables de entorno o secrets."
            )
        model = ProjectContentService._setting("OPENAI_MODEL", "model") or "gpt-5-mini"
        requested = int(form_data["technical_activity_count"])
        schema = {
            "type": "object",
            "properties": {
                "activities": {
                    "type": "array",
                    "minItems": requested,
                    "maxItems": requested,
                    "items": {
                        "type": "object",
                        "properties": {
                            "orden": {"type": "integer", "minimum": 1},
                            "titulo": {"type": "string", "minLength": 3},
                            "descripcion": {"type": "string", "minLength": 20},
                            "tipo_acompanamiento": {
                                "type": "string",
                                "enum": list(self.ALLOWED_TYPES),
                            },
                            "otro": {"type": "string"},
                            "equipos_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "materiales_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "orden",
                            "titulo",
                            "descripcion",
                            "tipo_acompanamiento",
                            "otro",
                            "equipos_ids",
                            "materiales_ids",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["activities"],
            "additionalProperties": False,
        }
        instructions = (
            "Actua como experto Tecnoparque que documenta acompanamientos tecnicos "
            "del SENA. Responde en espanol tecnico, concreto y realista. Usa solo "
            "la informacion recibida. No inventes reuniones, talentos, equipos, "
            "materiales, costos ni procesos ajenos al proyecto. Adapta la secuencia "
            "a la fase y al tipo real del proyecto. En actividades tecnicas evita "
            "mencionar acompanamiento directo o sesiones presenciales porque esas "
            "horas se asignan por fuera del modelo. Los tipos permitidos son "
            "Accion de transferencia, Acompanamiento, Orientaciones, Programa de "
            "fortalecimiento y Otro. Si usas Otro, llena obligatoriamente el campo "
            "otro con una etiqueta tecnica corta. Cuando un recurso no aplique, no "
            "lo asignes. Usa solo los ids de recursos entregados por el sistema."
        )
        request = {
            "model": model,
            "instructions": instructions,
            "input": json.dumps(
                {
                    "project": self._safe_context(project),
                    "document": {
                        "phase": form_data["phase"],
                        "technical_activity_count": requested,
                    },
                    "equipments": [
                        {"id": item["id"], "name": item["name"]}
                        for item in equipments
                    ],
                    "materials": [
                        {"id": item["id"], "name": item["name"]}
                        for item in materials
                    ],
                },
                ensure_ascii=False,
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "registro_acompanamientos",
                    "schema": schema,
                    "strict": True,
                }
            },
            "store": False,
        }
        try:
            response = OpenAI(api_key=api_key, timeout=120.0).responses.create(**request)
            payload = json.loads(response.output_text)
        except (OpenAIError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProjectContentError(
                f"No fue posible generar las actividades con OpenAI: {error}"
            ) from error

        activities = payload.get("activities", [])
        if len(activities) != requested:
            raise ProjectContentError(
                "OpenAI no devolvio la cantidad de actividades tecnicas solicitadas."
            )
        return self._normalize_activities(activities, equipments, materials)

    def _normalize_activities(
        self,
        activities: list[dict[str, Any]],
        equipments: list[dict[str, Any]],
        materials: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        equipment_ids = {item["id"] for item in equipments}
        material_ids = {item["id"] for item in materials}
        normalized: list[dict[str, Any]] = []
        for index, activity in enumerate(sorted(activities, key=lambda item: item["orden"])):
            activity_type = self._normalize_type(str(activity.get("tipo_acompanamiento", "")))
            other = str(activity.get("otro", "")).strip()
            if activity_type == "Otro" and not other:
                other = "Actividad tecnica especializada"
            normalized.append(
                {
                    "title": str(activity.get("titulo", "")).strip(),
                    "description": str(activity.get("descripcion", "")).strip(),
                    "type": activity_type,
                    "other": other,
                    "equipment_ids": [
                        value
                        for value in activity.get("equipos_ids", [])
                        if value in equipment_ids
                    ],
                    "material_ids": [
                        value
                        for value in activity.get("materiales_ids", [])
                        if value in material_ids
                    ],
                    "initial_order": index + 1,
                }
            )
        return normalized

    def _normalize_type(self, value: str) -> str:
        cleaned = (
            value.strip()
            .replace("ó", "o")
            .replace("Ó", "O")
            .replace("ñ", "n")
            .replace("Ñ", "N")
        )
        mapping = {
            "Accion de transferencia": "Accion de transferencia",
            "Acompanamiento": "Acompanamiento",
            "Orientaciones": "Orientaciones",
            "Programa de fortalecimiento": "Programa de fortalecimiento",
            "Otro": "Otro",
        }
        return mapping.get(cleaned, "Acompanamiento")

    @staticmethod
    def _safe_context(project: dict[str, Any]) -> dict[str, Any]:
        return {
            "code": project.get("code"),
            "name": project.get("name"),
            "description": project.get("description"),
            "technology_line": project.get("technology_line"),
            "city": project.get("city"),
            "research_group_name": project.get("research_group_name"),
            "team_roles": [
                item.get("role_name") or item.get("role")
                for item in project.get("talents", [])
            ],
        }
