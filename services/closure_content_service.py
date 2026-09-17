"""OpenAI content generation for closure documents."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from services.project_content_service import ProjectContentError, ProjectContentService


logger = logging.getLogger(__name__)
ReportProgressCallback = Callable[[str, int, int], None]


class ClosureContentService:
    """Generates closure content only when invoked by the user."""

    REPORT_MAX_OUTPUT_TOKENS = 4000
    REPORT_RETRY_MAX_OUTPUT_TOKENS = 8000
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
    def generate_report(
        self,
        project: dict[str, Any],
        form_data: dict[str, Any],
        progress: ReportProgressCallback | None = None,
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
        total_fields = len(self.REPORT_FIELDS)
        for completed_fields, field in enumerate(self.REPORT_FIELDS):
            self._notify_report_progress(
                progress,
                f"Generando {self._field_label(field)}...",
                completed_fields,
                total_fields,
            )
            content.update(
                self._generate(
                    fields=(field,),
                    schema_name=f"informe_tecnico_final_{field}",
                    project=project,
                    extra=form_data,
                    instructions=(
                        instructions
                        + f" Redacta unicamente el campo {field} en esta respuesta."
                    ),
                    max_output_tokens=self.REPORT_MAX_OUTPUT_TOKENS,
                    on_retry=lambda: self._notify_report_progress(
                        progress,
                        f"Reintentando {self._field_label(field)}...",
                        completed_fields,
                        total_fields,
                    ),
                )
            )
            self._notify_report_progress(
                progress,
                f"Completado: {self._field_label(field)}.",
                completed_fields + 1,
                total_fields,
            )
        invalid = self._report_sections_outside_range(content)
        if invalid:
            for field in invalid:
                self._notify_report_progress(
                    progress,
                    f"Ajustando {self._field_label(field)}...",
                    total_fields,
                    total_fields,
                )
                content.update(
                    self._generate(
                        fields=(field,),
                        schema_name=f"apartado_informe_ajustado_{field}",
                        project=project,
                        extra=form_data,
                        instructions=(
                            instructions
                            + f" Redacta unicamente el campo {field}. Debe tener "
                            "estrictamente entre 220 y 240 palabras."
                        ),
                        max_output_tokens=self.REPORT_MAX_OUTPUT_TOKENS,
                        on_retry=lambda: self._notify_report_progress(
                            progress,
                            f"Reintentando ajuste de {self._field_label(field)}...",
                            total_fields,
                            total_fields,
                        ),
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
        on_retry: Callable[[], None] | None = None,
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
            model = ProjectContentService._setting("OPENAI_MODEL", "model") or "gpt-5-mini"
            request = {
                "model": model,
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
                if model.startswith("gpt-5"):
                    request["reasoning"] = {"effort": "low"}
            client = OpenAI(api_key=api_key, timeout=60.0)
            response = client.responses.create(**request)
            output_text = (response.output_text or "").strip()
            self._log_response_metadata(
                response=response,
                schema_name=schema_name,
                fields=fields,
                input_characters=len(request["input"]),
                output_characters=len(output_text),
                max_output_tokens=max_output_tokens,
            )
            if self._is_max_output_incomplete(response) and max_output_tokens:
                retry_max_output_tokens = max(
                    max_output_tokens + 1,
                    self.REPORT_RETRY_MAX_OUTPUT_TOKENS,
                )
                logger.warning(
                    "Retrying OpenAI response after max output limit: schema=%s "
                    "fields=%s max_output_tokens=%s",
                    schema_name,
                    ",".join(fields),
                    retry_max_output_tokens,
                )
                if on_retry:
                    on_retry()
                request["max_output_tokens"] = retry_max_output_tokens
                response = client.responses.create(**request)
                output_text = (response.output_text or "").strip()
                self._log_response_metadata(
                    response=response,
                    schema_name=schema_name,
                    fields=fields,
                    input_characters=len(request["input"]),
                    output_characters=len(output_text),
                    max_output_tokens=retry_max_output_tokens,
                )
            if getattr(response, "status", None) != "completed":
                raise ProjectContentError(self._incomplete_response_message(response))
            if not output_text:
                raise ProjectContentError(
                    "OpenAI no devolvio contenido para esta parte del informe."
                )
            content = json.loads(output_text)
        except (OpenAIError, json.JSONDecodeError, TypeError, ValueError) as error:
            logger.exception(
                "OpenAI generation failed: schema=%s fields=%s input_characters=%s "
                "max_output_tokens=%s error_type=%s",
                schema_name,
                ",".join(fields),
                len(json.dumps(payload, ensure_ascii=False)),
                max_output_tokens,
                type(error).__name__,
            )
            raise ProjectContentError(
                f"No fue posible generar el contenido con OpenAI: {error}"
            ) from error
        if any(not str(content.get(field, "")).strip() for field in fields):
            logger.warning(
                "OpenAI response has required fields without content: schema=%s fields=%s "
                "response_id=%s status=%s",
                schema_name,
                ",".join(fields),
                getattr(response, "id", None),
                getattr(response, "status", None),
            )
            raise ProjectContentError("OpenAI no devolvio todos los campos requeridos.")
        return {field: str(content[field]).strip() for field in fields}

    @staticmethod
    def _notify_report_progress(
        progress: ReportProgressCallback | None,
        message: str,
        completed_fields: int,
        total_fields: int,
    ) -> None:
        if progress:
            progress(message, completed_fields, total_fields)

    @staticmethod
    def _field_label(field: str) -> str:
        return field.replace("_", " ").capitalize()

    @staticmethod
    def _is_max_output_incomplete(response: Any) -> bool:
        incomplete_details = getattr(response, "incomplete_details", None)
        return (
            getattr(response, "status", None) == "incomplete"
            and getattr(incomplete_details, "reason", None) == "max_output_tokens"
        )

    @staticmethod
    def _incomplete_response_message(response: Any) -> str:
        incomplete_details = getattr(response, "incomplete_details", None)
        if getattr(incomplete_details, "reason", None) == "max_output_tokens":
            return (
                "OpenAI no completo el contenido porque se alcanzo el limite de "
                "generacion. Intenta nuevamente."
            )
        return "OpenAI no completo la respuesta solicitada. Intenta nuevamente."

    @staticmethod
    def _log_response_metadata(
        *,
        response: Any,
        schema_name: str,
        fields: tuple[str, ...],
        input_characters: int,
        output_characters: int,
        max_output_tokens: int | None,
    ) -> None:
        """Logs response metadata without recording project content or credentials."""

        usage = getattr(response, "usage", None)
        output_details = getattr(usage, "output_tokens_details", None)
        incomplete_details = getattr(response, "incomplete_details", None)
        log = logger.warning if getattr(response, "status", None) != "completed" else logger.info
        log(
            "OpenAI response metadata: schema=%s fields=%s response_id=%s "
            "model=%s status=%s incomplete_reason=%s input_characters=%s "
            "output_characters=%s input_tokens=%s output_tokens=%s reasoning_tokens=%s "
            "max_output_tokens=%s",
            schema_name,
            ",".join(fields),
            getattr(response, "id", None),
            getattr(response, "model", None),
            getattr(response, "status", None),
            getattr(incomplete_details, "reason", None),
            input_characters,
            output_characters,
            getattr(usage, "input_tokens", None),
            getattr(usage, "output_tokens", None),
            getattr(output_details, "reasoning_tokens", None),
            max_output_tokens,
        )

    def _report_sections_outside_range(self, content: dict[str, str]) -> list[str]:
        return [
            field
            for field in self.REPORT_NARRATIVE_FIELDS
            if not 220 <= len(content[field].split()) <= 240
        ]
