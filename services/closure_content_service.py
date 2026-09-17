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
        "metodologia",
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
        instructions = self._report_base_instructions()
        content: dict[str, str] = {}
        total_fields = len(self.REPORT_FIELDS)
        for completed_fields, field in enumerate(self.REPORT_FIELDS):
            self._notify_report_progress(
                progress,
                f"Generando {self._field_label(field)}...",
                completed_fields,
                total_fields,
            )
            if field == "estado_arte":
                content.update(
                    self._generate_state_of_art(
                        project=project,
                        form_data=form_data,
                        previous_sections=content,
                        on_retry=lambda: self._notify_report_progress(
                            progress,
                            "Reintentando Estado del arte...",
                            completed_fields,
                            total_fields,
                        ),
                    )
                )
            elif field != "referencias":
                content.update(
                    self._generate(
                        fields=(field,),
                        schema_name=f"informe_tecnico_final_{field}",
                        project=project,
                        extra=self._report_extra(form_data, content),
                        instructions=(
                            instructions
                            + self._section_instructions(field)
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
                        extra=self._report_extra(form_data, content),
                        instructions=(
                            instructions
                            + self._section_instructions(field)
                            + f" Redacta unicamente el campo {field}. Debe tener entre "
                            "180 y 260 palabras."
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
        content.setdefault("referencias", "")
        content["anexos"] = ""
        return content

    @staticmethod
    def _report_base_instructions() -> str:
        return (
            "Redacta un Informe Tecnico Final de un Proyecto de Base Tecnologica "
            "del SENA. El contexto contiene datos del proyecto, del formulario de "
            "cierre y, cuando existe, informacion ya validada del diagnostico. Usa "
            "solo esos datos y las fuentes externas consultadas mediante la herramienta "
            "de busqueda cuando se soliciten. No inventes tecnologias, cifras, pruebas, "
            "resultados, entregables, validaciones, evidencias, enlaces, certificaciones "
            "ni referencias. Cada apartado tiene un proposito propio: desarrolla solo "
            "la informacion pertinente y no repitas literalmente ni reformules de forma "
            "innecesaria los contenidos de los apartados previos incluidos en el contexto. "
            "Mantiene un tono tecnico, verificable y prudente. Conserva literalmente los "
            "nombres de actividades, entregables, objetivos y el impacto aportados por la "
            "persona usuaria."
        )

    @staticmethod
    def _section_instructions(field: str) -> str:
        instructions = {
            "introduccion": (
                " Seccion: introduccion. Explica el contexto, proposito y alcance sin "
                "anticipar actividades, resultados ni conclusiones. Extension aproximada: 180 a 230 palabras."
            ),
            "planteamiento_problema": (
                " Seccion: planteamiento del problema. Delimita necesidad, causas, consecuencias "
                "y beneficiarios; no describas la solucion como si ya fuera un resultado. Extension: 180 a 230 palabras."
            ),
            "objetivo_general": (
                " Seccion: objetivo general. Entrega una unica oracion precisa, sin titulo ni vineta."
            ),
            "objetivos_especificos": (
                " Seccion: objetivos especificos. Entrega un objetivo por linea, sin numeracion, "
                "sin vinetas y sin encabezados. Conserva su redaccion original si el contexto la aporta; "
                "solo corrige presentacion minima."
            ),
            "metodologia": (
                " Seccion: metodologia. Explica exclusivamente el enfoque y las fases de las metodologias "
                "seleccionadas, sin repetir el detalle de cada actividad. Extension: 180 a 240 palabras."
            ),
            "desarrollo": (
                " Seccion: desarrollo del proyecto. Usa todas las actividades registradas, en el mismo orden. "
                "Para cada actividad escribe exactamente un encabezado con el formato `### Actividad: nombre literal`, "
                "una linea `**Fase metodologica:** nombre de una fase coherente con las metodologias seleccionadas` y "
                "un parrafo de 70 a 110 palabras sobre lo realizado, como se desarrollo, el proposito y su contribucion. "
                "No inventes herramientas, procedimientos, resultados o evidencias que no esten en el contexto. No agregues "
                "espacios de evidencia: el documento los incorporara automaticamente."
            ),
            "normatividad": (
                " Seccion: normatividad. Incluye solo normas colombianas o estandares internacionales pertinentes "
                "y aclara con prudencia si son obligatorios o de referencia. No listes normas sin relacion demostrable. "
                "Extension: 160 a 220 palabras."
            ),
            "resultados": (
                " Seccion: resultados. Describe exclusivamente los entregables y resultados registrados, su relacion "
                "con los objetivos y las validaciones realmente informadas. No agregues resultados nuevos. Extension: 180 a 240 palabras."
            ),
            "analisis_viabilidad": (
                " Seccion: analisis de viabilidad. Evalua solo dimensiones pertinentes al tipo de proyecto: tecnica, "
                "tecnologica, operativa, productiva, economica, implementacion, infraestructura, talento, equipos, materiales "
                "y escalamiento. Cierra con una conclusion explicita y adaptada sobre continuidad, adopcion o escalamiento. "
                "Menciona los recursos de Tecnoparque solo cuando el contexto los respalde. Extension: 200 a 260 palabras."
            ),
            "propiedad_transferencia": (
                " Seccion: propiedad intelectual y transferencia tecnologica en Colombia. Analiza la viabilidad de "
                "proteccion de los desarrollos segun su naturaleza, por ejemplo derecho de autor, registro de software, obra, "
                "diseno industrial, marca, secreto empresarial, patente o modelo de utilidad cuando proceda. No enumeres entregables. "
                "Usa formulaciones responsables como 'podria ser susceptible de proteccion', 'se recomienda evaluar' y "
                "'debera realizarse un analisis de novedad y antecedentes'; nunca afirmes que algo es patentable o registrable. "
                "Extension: 180 a 240 palabras."
            ),
            "impacto": (
                " Seccion: impacto del proyecto. Usa como insumo prioritario el campo additional_impacts del formulario; "
                "amplialo sin cambiar su intencion. Incluye solo impactos tecnologicos, productivos, empresariales, economicos, "
                "sociales, ambientales, culturales o institucionales que el contexto soporte. No uses impactos genericos. "
                "Extension: 180 a 240 palabras."
            ),
            "conclusiones": (
                " Seccion: conclusiones. Declara con claridad lo desarrollado, resultados, validaciones o aceptaciones solo "
                "si fueron registradas, y el nivel de cumplimiento de objetivos con base en la evidencia disponible. Cuando sea "
                "coherente con el tipo de proyecto y el TRL alcanzado, plantea prudentemente una nueva idea o proyecto para avanzar "
                "hacia TRL 7 u 8; no lo afirmes como resultado automatico. Extension: 180 a 240 palabras."
            ),
        }
        return instructions.get(field, "")

    @staticmethod
    def _report_extra(
        form_data: dict[str, Any], previous_sections: dict[str, str]
    ) -> dict[str, Any]:
        extra = dict(form_data)
        previous = {
            field: value
            for field, value in previous_sections.items()
            if field not in {"referencias", "anexos"} and str(value).strip()
        }
        if previous:
            extra["apartados_previos_para_evitar_repeticion"] = previous
        return extra

    def _generate_state_of_art(
        self,
        *,
        project: dict[str, Any],
        form_data: dict[str, Any],
        previous_sections: dict[str, str],
        on_retry: Callable[[], None] | None,
    ) -> dict[str, str]:
        instructions = (
            self._report_base_instructions()
            + " Seccion: estado del arte y estado de la tecnica. Consulta fuentes externas reales y selecciona entre "
            "tres y cinco referentes directamente relacionados con la descripcion, tecnologias previstas o actividades "
            "del proyecto. Incluye desarrollos, tecnologias, articulos o soluciones comparables cuando existan fuentes "
            "adecuadas. Explica las coincidencias, diferencias y el posible aporte innovador sin afirmar novedades no verificadas. "
            "Incluye citas parenteticas APA 7 en los parrafos. Despues de los parrafos entrega una tabla Markdown con exactamente "
            "estas seis columnas: Proyecto / Tecnologia | Organizacion / Autor | Caracteristicas principales | Relacion con el proyecto "
            "| Diferencias / aporte innovador | Fuente. En Fuente usa una cita breve y la URL canonica verificable. "
            "En referencias, incluye una referencia APA 7 por linea para cada fuente consultada, con responsable, fecha, titulo y URL "
            "cuando corresponda. No inventes autor, fecha, URL, cita ni referencia; si no hay una fuente suficiente, no la incluyas. "
            "No uses 'Autor desconocido', 'Sin autor confirmado' ni 's.f.' cuando la fuente muestre datos verificables."
        )
        return self._generate(
            fields=("estado_arte", "referencias"),
            schema_name="informe_tecnico_final_estado_arte",
            project=project,
            extra=self._report_extra(form_data, previous_sections),
            instructions=instructions,
            max_output_tokens=self.REPORT_RETRY_MAX_OUTPUT_TOKENS,
            on_retry=on_retry,
            tools=[{
                "type": "web_search",
                "search_context_size": "high",
                "user_location": {
                    "type": "approximate",
                    "country": "CO",
                    "timezone": "America/Bogota",
                },
            }],
            timeout=300.0,
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
        max_output_tokens: int | None = None,
        on_retry: Callable[[], None] | None = None,
        tools: list[dict[str, Any]] | None = None,
        timeout: float = 60.0,
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
            if tools:
                request["tools"] = tools
            if max_output_tokens:
                request["max_output_tokens"] = max_output_tokens
                if model.startswith("gpt-5"):
                    request["reasoning"] = {"effort": "low"}
            client = OpenAI(api_key=api_key, timeout=timeout)
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
