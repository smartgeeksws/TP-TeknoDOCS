"""Investigación verificable y redacción asistida del GCDTP-F-020."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Callable

from services.project_content_service import ProjectContentService


class DiagnosticContentError(RuntimeError):
    """Error controlado durante investigación, redacción o validación."""


ProgressCallback = Callable[[str], None]


class DiagnosticContentService:
    NARRATIVE_FIELDS = {
        "introduction": (160, 250),
        "problem_statement": (160, 250),
        "problem_identified": (160, 250),
        "problem_impact": (160, 250),
        "solution": (160, 250),
        "state_of_art": (160, 250),
        "technology_narrative": (160, 250),
        "legal_study": (160, 250),
        "viability": (160, 250),
        "expected_results": (160, 250),
        "conclusions": (160, 250),
        "technology_surveillance": (280, 500),
    }

    def generate(
        self,
        project: dict[str, Any],
        form_data: dict[str, Any],
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        self._notify(progress, "Recuperando información del proyecto...")
        self._validate_input(project, form_data)
        try:
            from openai import OpenAI, OpenAIError
        except ImportError as error:
            raise DiagnosticContentError("La dependencia openai no está instalada.") from error

        api_key = ProjectContentService._setting("OPENAI_API_KEY", "api_key")
        if not api_key:
            raise DiagnosticContentError(
                "Configura OPENAI_API_KEY en variables de entorno o secrets."
            )
        model = ProjectContentService._setting("OPENAI_MODEL", "model") or "gpt-5-mini"
        document_date = date.fromisoformat(form_data["document_date"])
        self._notify(progress, "Consultando referentes y fuentes verificables...")
        request = {
            "model": model,
            "instructions": self._instructions(document_date),
            "input": json.dumps(
                {
                    "proyecto": self._safe_context(project),
                    "formulario": form_data,
                },
                ensure_ascii=False,
            ),
            "tools": [{
                "type": "web_search",
                "search_context_size": "high",
                "user_location": {
                    "type": "approximate",
                    "country": "CO",
                    "timezone": "America/Bogota",
                },
            }],
            "max_output_tokens": 30000,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "diagnostico_estado_arte",
                    "schema": self._schema(),
                    "strict": True,
                }
            },
            "store": False,
        }
        client = OpenAI(api_key=api_key, timeout=300.0)
        try:
            response = client.responses.create(**request)
            content = json.loads(response.output_text)
        except (OpenAIError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise DiagnosticContentError(
                f"No fue posible investigar y generar el diagnóstico: {error}"
            ) from error

        self._normalize_objectives(content)
        self._notify(progress, "Preparando contenido para revisión manual...")
        return content

    @staticmethod
    def _normalize_objective(value: Any) -> str:
        normalized = str(value or "").strip().strip("*# ")
        prefixes = (
            r"^(?:[-•*]\s*|\d+(?:\.\d+)*[.)-]?\s*)",
            r"^objetivo(?:\s+(?:general|espec[ií]fico)(?:\s+\d+)?)?\s*[:.\-–]?\s*",
        )
        previous = None
        while normalized != previous:
            previous = normalized
            for pattern in prefixes:
                normalized = re.sub(
                    pattern,
                    "",
                    normalized,
                    count=1,
                    flags=re.IGNORECASE,
                ).strip().strip("*# ")
        return normalized

    @classmethod
    def _normalize_objectives(cls, content: dict[str, Any]) -> None:
        content["general_objective"] = cls._normalize_objective(
            content.get("general_objective", "")
        )
        content["specific_objectives"] = [
            cls._normalize_objective(objective)
            for objective in content.get("specific_objectives", [])
        ]

    @classmethod
    def _schema(cls) -> dict[str, Any]:
        string = {"type": "string", "minLength": 1}
        narrative = {
            "type": "string",
            "minLength": 1,
            "description": "Texto técnico de 190 a 220 palabras; contar antes de responder.",
        }
        surveillance = {
            "type": "string",
            "minLength": 1,
            "description": "Vigilancia tecnológica de 330 a 420 palabras; contar antes de responder.",
        }
        source = {
            "type": "object",
            "properties": {
                "title": string,
                "author": string,
                "year": {"type": "integer"},
                "source_type": string,
                "url": string,
                "doi": {"type": "string"},
                "consulted_on": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
                "sections": {"type": "array", "items": string, "minItems": 1},
                "apa_reference": string,
            },
            "required": [
                "title", "author", "year", "source_type", "url", "doi",
                "consulted_on", "sections", "apa_reference",
            ],
            "additionalProperties": False,
        }
        similar = {
            "type": "object",
            "properties": {
                "solution": string,
                "description": string,
                "relationship": string,
                "differential": string,
                "citation": string,
            },
            "required": ["solution", "description", "relationship", "differential", "citation"],
            "additionalProperties": False,
        }
        technology = {
            "type": "object",
            "properties": {"name": string, "use": string},
            "required": ["name", "use"],
            "additionalProperties": False,
        }
        reference = {
            "type": "object",
            "properties": {
                "type": string, "author": string, "year": {"type": "integer"},
                "result": string, "relationship": string, "country": string,
                "application": string, "citation": string,
            },
            "required": ["type", "author", "year", "result", "relationship", "country", "application", "citation"],
            "additionalProperties": False,
        }
        regulation = {
            "type": "object",
            "properties": {
                "name": string, "application": string, "intellectual_property": string,
                "citation": string,
            },
            "required": ["name", "application", "intellectual_property", "citation"],
            "additionalProperties": False,
        }
        glossary = {
            "type": "object",
            "properties": {"term": string, "definition": string, "citation": string},
            "required": ["term", "definition", "citation"],
            "additionalProperties": False,
        }
        schedule = {
            "type": "object",
            "properties": {"phase": string, "activity": string, "deliverable": string},
            "required": ["phase", "activity", "deliverable"],
            "additionalProperties": False,
        }
        properties: dict[str, Any] = {
            field: (surveillance if field == "technology_surveillance" else narrative)
            for field in cls.NARRATIVE_FIELDS
        }
        properties.update(
            {
                "glossary": {"type": "array", "items": glossary},
                "project_type": string,
                "general_objective": string,
                "specific_objectives": {"type": "array", "items": string, "minItems": 3, "maxItems": 5},
                "similar_products": {"type": "array", "items": similar, "minItems": 1, "maxItems": 3},
                "technologies": {"type": "array", "items": technology, "minItems": 1, "maxItems": 10},
                "scientific_references": {"type": "array", "items": reference, "minItems": 1, "maxItems": 3},
                "regulations": {"type": "array", "items": regulation, "minItems": 1, "maxItems": 3},
                "schedule": {"type": "array", "items": schedule, "minItems": 6, "maxItems": 14},
                "references": {"type": "array", "items": string, "minItems": 1},
                "sources": {"type": "array", "items": source, "minItems": 1},
            }
        )
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    @staticmethod
    def _instructions(document_date: date) -> str:
        return f"""
Actúa como investigador y formulador técnico de proyectos SENA. Investiga en la web antes de redactar. Usa exclusivamente fuentes primarias, científicas, gubernamentales, normativas, universitarias, patentes o documentación oficial verificable. Prohíbe Wikipedia, blogs, foros, agregadores y contenido SEO. Prioriza publicaciones entre 2022 y {document_date.year}; usa anteriores solo para normas vigentes o fundamentos imprescindibles. No inventes autores, títulos, años, DOI, URL, normas, productos ni patentes.

Redacta en español técnico institucional, tercera persona, sin copiar literalmente las respuestas del usuario, sin frases vacías como «En la actualidad», «Hoy en día», «Es importante destacar» o «Cabe resaltar». Cada afirmación técnica que lo requiera debe contener cita APA 7 y todas las citas deben corresponder exactamente con references y sources. Nunca uses «s.f.» ni «sin fecha»: para una página institucional sin fecha usa {document_date.isoformat()} como fecha de consulta y año {document_date.year}. Cuenta las palabras antes de responder. Redacta cada campo narrativo con 190–220 palabras y technology_surveillance con 330–420 palabras. Como guía de redacción, procura mantener rangos de 160–250 y 280–500 palabras, respectivamente; el usuario realizará la revisión final.

Cada sección debe desarrollar un propósito diferente y aportar información nueva. No repitas párrafos, argumentos, antecedentes, citas ni conclusiones entre secciones; tampoco uses referencias como «ver sección anterior», «como se indicó previamente» o equivalentes. Genera un objetivo general breve que comience directamente con un verbo en infinitivo y entre 3 y 5 objetivos específicos medibles, también iniciados directamente en infinitivo y en secuencia lógica. No antepongas numeraciones, viñetas ni etiquetas como «Objetivo general» u «Objetivo específico». Incluye 2–3 productos similares y 2–3 referentes científicos solo cuando existan; si la investigación arroja menos fuentes verificables, usa únicamente las encontradas. Selecciona 2–3 normas realmente aplicables. El cronograma debe adaptarse al tipo real de proyecto y contener fases, actividades y entregables, sin fechas (el sistema las asignará solo si existen fechas del proyecto). Si glossary_requested es falso, devuelve glossary vacío. Si es verdadero, define exclusivamente los términos solicitados con citas verificables. Mantén coherencia problema→impacto→objetivos→solución→tecnologías→cronograma→resultados→conclusiones. No incluyas datos personales ni los inventes.
""".strip()

    @staticmethod
    def _safe_context(project: dict[str, Any]) -> dict[str, Any]:
        return {
            "code": project.get("code"),
            "name": project.get("name"),
            "description": project.get("description"),
            "city": project.get("city"),
            "technology_line": project.get("technology_line"),
            "initial_trl": project.get("initial_trl"),
            "target_trl": project.get("target_trl"),
            "start_date": str(project.get("start_date") or ""),
            "end_date": str(project.get("end_date") or ""),
            "team_roles": [item.get("role_name") or item.get("role") for item in project.get("talents", [])],
        }

    def validate_content(
        self,
        content: dict[str, Any],
        document_date: date,
        form_data: dict[str, Any],
    ) -> None:
        """Normaliza el contenido editado sin bloquear la revisión humana."""

        self._normalize_objectives(content)

    @staticmethod
    def _validate_input(project: dict[str, Any], form_data: dict[str, Any]) -> None:
        missing_project = [key for key in ("id", "code", "name", "description") if not project.get(key)]
        missing_form = [key for key in ("document_date", "problem", "technologies", "expected_products") if not str(form_data.get(key, "")).strip()]
        if missing_project:
            raise DiagnosticContentError("Faltan datos del proyecto: " + ", ".join(missing_project))
        if missing_form:
            raise DiagnosticContentError("Completa todos los campos obligatorios del formulario.")
        try:
            date.fromisoformat(str(form_data["document_date"]))
        except ValueError as error:
            raise DiagnosticContentError("La fecha de elaboración no es válida.") from error
        if form_data.get("glossary_requested") and not str(form_data.get("glossary_terms", "")).strip():
            raise DiagnosticContentError("Ingresa los términos que debe contener el glosario.")

    @staticmethod
    def _notify(callback: ProgressCallback | None, message: str) -> None:
        if callback:
            callback(message)