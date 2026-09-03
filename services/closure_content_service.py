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
        "normatividad",
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
    REPORT_NARRATIVE_FIELDS = (
        "introduccion",
        "planteamiento_problema",
        "estado_arte",
        "metodologia",
        "desarrollo",
        "normatividad",
        "resultados",
        "analisis_viabilidad",
        "propiedad_transferencia",
        "impacto",
        "conclusiones",
    )
    REPORT_GROUPS = (
        (
            "introduccion",
            "planteamiento_problema",
            "objetivo_general",
            "objetivos_especificos",
        ),
        ("estado_arte", "metodologia", "desarrollo"),
        ("normatividad", "resultados", "analisis_viabilidad"),
        (
            "propiedad_transferencia",
            "impacto",
            "conclusiones",
            "referencias",
            "anexos",
        ),
    )

    def generate_report(
        self, project: dict[str, Any], form_data: dict[str, Any]
    ) -> dict[str, str]:
        instructions = (
            "Redacta un informe tecnico final de un Proyecto de Base Tecnologica "
            "del SENA, con tono tecnico, verificable y propio de un proceso de "
            "innovacion, desarrollo tecnologico y validacion de un Producto Minimo "
            "Viable cuando aplique. Usa solamente los datos suministrados y no "
            "inventes tecnologias, cifras, pruebas, resultados, entregables, "
            "certificaciones ni referencias. Redacta entre 220 y 240 palabras en "
            "cada apartado narrativo: introduccion, planteamiento del problema, "
            "estado del arte, metodologia, desarrollo, normatividad, resultados, "
            "analisis de viabilidad, propiedad y transferencia, impacto y "
            "conclusiones. El objetivo general debe ser una sola oracion precisa; "
            "los objetivos especificos deben ser una lista separada por saltos de "
            "linea. En normatividad identifica y explica exclusivamente normas "
            "colombianas y estandares internacionales pertinentes al tipo de "
            "proyecto, indicando si su aplicacion es obligatoria o de referencia."
        )
        content: dict[str, str] = {}
        for index, fields in enumerate(self.REPORT_GROUPS, start=1):
            content.update(
                self._generate(
                    fields=fields,
                    schema_name=f"informe_tecnico_final_parte_{index}",
                    project=project,
                    extra=form_data,
                    instructions=instructions,
                    max_output_tokens=2800,
                )
            )
        invalid = self._report_sections_outside_range(content)
        if invalid:
            for index, group in enumerate(self.REPORT_GROUPS, start=1):
                fields = tuple(field for field in group if field in invalid)
                if not fields:
                    continue
                content.update(
                    self._generate(
                        fields=fields,
                        schema_name=f"apartados_informe_ajustados_{index}",
                        project=project,
                        extra=form_data,
                        instructions=(
                            instructions
                            + " Redacta unicamente los apartados fuera de rango: "
                            + ", ".join(fields)
                            + ". Cada uno debe tener estrictamente entre 220 y 240 palabras."
                        ),
                        max_output_tokens=1800,
                    )
                )
        return content

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
        max_output_tokens: int | None = None,
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
            request = {
                "model": ProjectContentService._setting("OPENAI_MODEL", "model")
                or "gpt-5-mini",
                "instructions": instructions,
                "input": json.dumps(payload, ensure_ascii=False),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
                "store": False,
            }
            if max_output_tokens:
                request["max_output_tokens"] = max_output_tokens
            response = OpenAI(api_key=api_key, timeout=60.0).responses.create(**request)
            output_text = response.output_text.strip()
            if not output_text:
                raise ProjectContentError(
                    "OpenAI no devolvio contenido para esta parte del informe."
                )
            content = json.loads(output_text)
        except (OpenAIError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProjectContentError(
                f"No fue posible generar el contenido con OpenAI: {error}"
            ) from error
        if any(not str(content.get(field, "")).strip() for field in fields):
            raise ProjectContentError("OpenAI no devolvio todos los campos requeridos.")
        return {field: str(content[field]).strip() for field in fields}

    def _report_sections_outside_range(self, content: dict[str, str]) -> list[str]:
        return [
            field
            for field in self.REPORT_NARRATIVE_FIELDS
            if not 220 <= len(content[field].split()) <= 240
        ]
