"""OpenAI content generation for closure documents."""

from __future__ import annotations

import json
from typing import Any

from services.project_content_service import ProjectContentError, ProjectContentService


class ClosureContentService:
    """Generates closure content only when invoked by the user."""

    REPORT_FIELDS = (
        "introduccion",
        "planteamiento_problema",
        "objetivo_general",
        "objetivos_especificos",
        "estado_arte",
        "metodologia",
        "desarrollo",
        "resultados",
        "analisis_viabilidad",
        "propiedad_transferencia",
        "impacto",
        "conclusiones",
        "referencias",
        "anexos",
    )
    CANVAS_FIELDS = (
        "propuesta_valor",
        "segmento_clientes_adopcion",
        "canales_distribucion",
        "relaciones_clientes",
        "flujo_ingresos",
        "recursos_clave",
        "actividades_clave",
        "alianzas_clave",
        "estructura_costos",
    )
    LETTER_FIELDS = (
        "objetivo_acompanamiento",
        "descripcion_consultoria",
        "resultado_trl",
    )

    def generate_report(
        self, project: dict[str, Any], form_data: dict[str, Any]
    ) -> dict[str, str]:
        return self._generate(
            fields=self.REPORT_FIELDS,
            schema_name="informe_tecnico_final",
            project=project,
            extra=form_data,
            instructions=(
                "Redacta un informe tecnico final en espanol profesional para SENA. "
                "Usa solo el contexto recibido y no inventes tecnologias, cifras, "
                "pruebas, resultados, entregables ni referencias. Mantiene prudencia "
                "cuando falte evidencia. Los objetivos especificos deben presentarse "
                "como lista separada por saltos de linea."
            ),
        )

    def generate_canvas(
        self, project: dict[str, Any], form_data: dict[str, Any]
    ) -> dict[str, str]:
        content = self._generate(
            fields=self.CANVAS_FIELDS,
            schema_name="modelo_negocio_lean_canvas",
            project=project,
            extra=form_data,
            instructions=(
                "Redacta los nueve bloques de un Lean Canvas en espanol. Usa solo "
                "los datos proporcionados y no repitas el nombre ni el codigo del "
                "proyecto. Procura que cada bloque tenga entre 160 y 190 palabras, estar "
                "orientado a decisiones de negocio y reconocer prudentemente la "
                "incertidumbre cuando la evidencia sea insuficiente."
            ),
        )
        return content

    def generate_letter_text(
        self, project: dict[str, Any], form_data: dict[str, Any]
    ) -> dict[str, str]:
        return self._generate(
            fields=self.LETTER_FIELDS,
            schema_name="texto_tecnico_carta_certificacion",
            project=project,
            extra=form_data,
            instructions=(
                "Redacta solo los tres fragmentos solicitados para una carta de "
                "certificacion. Usa exclusivamente la informacion entregada; no "
                "inventes tecnologias, actividades, resultados, validaciones ni TRL. "
                "Si el contexto no soporta una afirmacion, usa una formulacion "
                "prudente y general."
            ),
        )

    def _generate(
        self,
        *,
        fields: tuple[str, ...],
        schema_name: str,
        project: dict[str, Any],
        extra: dict[str, Any],
        instructions: str,
    ) -> dict[str, str]:
        try:
            from openai import OpenAI, OpenAIError
        except ImportError as error:
            raise ProjectContentError("La dependencia openai no esta instalada.") from error

        api_key = ProjectContentService._setting("OPENAI_API_KEY", "api_key")
        if not api_key:
            raise ProjectContentError(
                "Configura OPENAI_API_KEY en variables de entorno o secrets."
            )
        schema = {
            "type": "object",
            "properties": {
                field: {"type": "string", "minLength": 1} for field in fields
            },
            "required": list(fields),
            "additionalProperties": False,
        }
        payload = {
            "proyecto": ProjectContentService._safe_context(project),
            "datos_adicionales": extra,
        }
        try:
            response = OpenAI(api_key=api_key, timeout=60.0).responses.create(
                model=ProjectContentService._setting("OPENAI_MODEL", "model")
                or "gpt-5-mini",
                instructions=instructions,
                input=json.dumps(payload, ensure_ascii=False),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
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
        if any(not str(content.get(field, "")).strip() for field in fields):
            raise ProjectContentError("OpenAI no devolvio todos los campos requeridos.")
        return {field: str(content[field]).strip() for field in fields}
