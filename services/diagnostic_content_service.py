"""Investigación verificable y redacción asistida del GCDTP-F-020."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from services.project_content_service import ProjectContentService


class DiagnosticContentError(RuntimeError):
    """Error controlado durante investigación, redacción o validación."""


ProgressCallback = Callable[[str], None]


class DiagnosticContentService:
    PARENTHETICAL_LINK_PATTERN = re.compile(
        r"\s*\(\s*\[[^\]\r\n]{1,200}\]"
        r"\((?:https?://)[^\s()\r\n]{1,2048}\)\s*\)",
        re.IGNORECASE,
    )
    MARKDOWN_LINK_PATTERN = re.compile(
        r"\[([^\]\r\n]{1,200})\]"
        r"\((?:https?://)[^\s()\r\n]{1,2048}\)",
        re.IGNORECASE,
    )
    RAW_URL_PATTERN = re.compile(
        r"\bhttps?://[^\s<>\[\]{}()]+(?<![.,;:!?])",
        re.IGNORECASE,
    )
    SOURCE_URL_PATTERN = re.compile(
        r"^\s*(?:\(\s*)?\[[^\]\r\n]{1,200}\]"
        r"\((https?://[^\s()\r\n]{1,2048})\)(?:\s*\))?\s*$",
        re.IGNORECASE,
    )
    TOOL_CITATION_PATTERN = re.compile(
        r"\s*cite[^\r\n]{1,500}"
    )
    TRACKING_QUERY_KEYS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid"})
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
            content = self._sanitize_generated_content(
                json.loads(response.output_text)
            )
            self._normalize_objectives(content)
            if self._contains_empty_string(content):
                raise DiagnosticContentError(
                    "La respuesta generada contiene un campo obligatorio vacío "
                    "después de normalizar y limpiar el contenido. Intenta generar "
                    "el diagnóstico nuevamente."
                )
        except (OpenAIError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise DiagnosticContentError(
                f"No fue posible investigar y generar el diagnóstico: {error}"
            ) from error

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
    def _sanitize_generated_content(
        cls,
        value: Any,
        path: tuple[str, ...] = (),
    ) -> Any:
        if isinstance(value, dict):
            return {
                key: cls._sanitize_generated_content(
                    item,
                    path + (str(key),),
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                cls._sanitize_generated_content(
                    item,
                    path + (str(index),),
                )
                for index, item in enumerate(value)
            ]
        if isinstance(value, str):
            field = path[-1] if path else ""
            if field == "url":
                return cls._canonical_source_url(value)
            text = cls.PARENTHETICAL_LINK_PATTERN.sub("", value)
            text = cls.MARKDOWN_LINK_PATTERN.sub(r"\1", text)
            text = cls.TOOL_CITATION_PATTERN.sub("", text)
            if field != "doi":
                text = cls.RAW_URL_PATTERN.sub("", text)
            text = re.sub(r"\(\s*\)", "", text)
            text = re.sub(r"[ \t]{2,}", " ", text)
            text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
            return text.strip()
        return value

    @classmethod
    def _canonical_source_url(cls, value: str) -> str:
        url = value.strip()
        markdown_match = cls.SOURCE_URL_PATTERN.fullmatch(url)
        if markdown_match is not None:
            url = markdown_match.group(1)
        elif url.startswith("(") and url.endswith(")"):
            url = url[1:-1].strip()
        try:
            parts = urlsplit(url)
        except ValueError:
            return ""
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            return ""
        query = [
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in cls.TRACKING_QUERY_KEYS
        ]
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc,
                parts.path,
                urlencode(query, doseq=True),
                parts.fragment,
            )
        )

    @classmethod
    def _contains_empty_string(
        cls,
        value: Any,
        path: tuple[str, ...] = (),
    ) -> bool:
        if isinstance(value, dict):
            return any(
                cls._contains_empty_string(item, path + (str(key),))
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(
                cls._contains_empty_string(item, path + (str(index),))
                for index, item in enumerate(value)
            )
        return (
            isinstance(value, str)
            and not value.strip()
            and (not path or path[-1] != "doi")
        )

    @classmethod
    def _schema(cls) -> dict[str, Any]:
        string = {"type": "string", "pattern": r"^[\s\S]+$"}
        narrative = {
            "type": "string",
            "pattern": r"^[\s\S]{1200,2200}$",
            "description": "Texto técnico normalmente de 160 a 250 palabras como guía de profundidad, sin declarar conteos ni incluir metadatos.",
        }
        surveillance = {
            "type": "string",
            "pattern": r"^[\s\S]{1700,4200}$",
            "description": "Vigilancia tecnológica normalmente de 280 a 500 palabras como guía de profundidad, sin declarar conteos ni incluir metadatos.",
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
Actúa como investigador y formulador técnico de proyectos SENA. Antes de redactar, interpreta prioritariamente la descripción del proyecto y determina si corresponde a software, diseño industrial, electrónica, agroindustria, biotecnología, prototipado, automatización, desarrollo de producto, desarrollo tecnológico u otra naturaleza. Usa como contexto principal el nombre, el código y la descripción registrados, las tecnologías disponibles, los roles y los beneficiarios mencionados en la descripción y el contexto técnico. El nombre y el código son identificadores literales: no los modifiques, resumas ni reinterpretes. No generes Regional, Centro de Formación ni Tecnoparque; el sistema los completa con valores institucionales constantes.

Investiga en la web antes de redactar. Usa exclusivamente fuentes reales y verificables: primarias, científicas, gubernamentales, normativas, universitarias, patentes o documentación oficial. No uses Wikipedia, wikis, blogs, foros, agregadores, contenido SEO ni fuentes de baja confiabilidad. Puedes emplear fuentes anteriores a 2022 cuando sean pertinentes por su vigencia, relevancia, carácter fundacional o aplicación al proyecto. No inventes autores, títulos, años, DOI, URL, normas, productos ni patentes.

Redacta en español técnico institucional y tercera persona. No copies literalmente las respuestas del usuario ni uses frases vacías. Usa normalmente entre 160 y 250 palabras en cada campo narrativo y entre 280 y 500 en technology_surveillance como guía de profundidad; no cuentes, declares ni muestres esas longitudes. La profundidad se aplica individualmente a todos los campos narrativos, incluidos problem_identified, problem_impact y expected_results: no entregues resúmenes breves ni compenses un campo corto con otro más extenso. No incluyas en ningún campo etiquetas o metadatos como «Palabras: 185», conteos de palabras, instrucciones o comentarios internos. Cada sección debe cumplir un propósito distinto y aportar información nueva: no repitas párrafos, argumentos, antecedentes, citas ni conclusiones entre apartados. Mantén coherencia problema→impacto→objetivos→solución→tecnologías→cronograma→resultados→conclusiones.

Formula objetivos generales, técnicos y metodológicos, adaptados a la naturaleza detectada y sin describir funcionalidades particulares que puedan cambiar. El objetivo general debe comenzar directamente con un verbo en infinitivo. Genera entre 3 y 5 objetivos específicos que también comiencen con infinitivo y representen una secuencia metodológica coherente. Para software, cubre de forma contextual etapas como identificar requisitos funcionales y no funcionales, modelar arquitectura/procesos/componentes, desarrollar la solución y validar el cumplimiento mediante pruebas. Para otros proyectos, selecciona solo las etapas pertinentes entre identificación de necesidades, diseño, modelado, desarrollo, construcción, prototipado, implementación, validación y pruebas. No copies ejemplos literalmente. No antepongas numeraciones, viñetas, títulos ni etiquetas como «Objetivo general» u «Objetivo específico».

Para similar_products, realiza búsquedas conceptuales amplias: no exijas coincidencia exacta con el producto. Selecciona referentes tecnológicos, metodológicos o funcionales suficientemente relacionados con el problema, el proceso, la función o la tecnología. Incluye obligatoriamente referentes nacionales e internacionales dentro del conjunto. En software considera sistemas de gestión, plataformas institucionales, compras, proveedores, contratación u otras categorías equivalentes según el contexto; en agroindustria, productos, procesos y tecnologías de procesamiento relacionados; en diseño industrial, funciones, prototipos y soluciones técnicas equivalentes. Genera entre 2 y 3 referentes cuando existan fuentes adecuadas.

Para scientific_references, amplía la búsqueda a cualquiera de estos ejes pertinentes: tipo de proyecto, problema, tecnologías, metodologías, arquitecturas, materiales, procesos productivos, técnicas de desarrollo, herramientas o tendencias tecnológicas. En software puede incluir arquitectura, sistemas de información, inteligencia artificial, bases de datos, desarrollo web, automatización, seguridad, experiencia de usuario o las tecnologías específicas declaradas. Elige de 2 a 3 artículos o referentes académicos reales cuando existan.

La viabilidad debe concluir siempre que el proyecto es viable, con sustento en su descripción, características técnicas, necesidades y recursos disponibles. Identifica el beneficiario principal a partir de la descripción y el contexto (institución, centro, programa, empresa, emprendedor, talento, comunidad, proceso productivo u otro actor realmente mencionado). Explica solo los beneficios directamente coherentes con el proyecto, como optimización, reducción de tiempos o errores, automatización, trazabilidad, productividad, conocimiento, validación, apropiación tecnológica o innovación. No enumeres beneficios no sustentados ni redactes conclusiones negativas, de baja viabilidad o de no recomendación.

Cada afirmación técnica que lo requiera debe contener una cita parentética APA 7 de autor y año, consistente con las fuentes consultadas. En campos narrativos y campos citation no incluyas enlaces Markdown, URL, dominios, parámetros UTM ni marcadores internos de herramientas de búsqueda; registra la URL canónica únicamente en sources[].url. Para una página institucional sin fecha usa {document_date.isoformat()} como fecha de consulta. Selecciona solo normas aplicables. El cronograma debe adaptarse al tipo real de proyecto y contener fases, actividades y entregables, sin fechas. Si glossary_requested es falso, devuelve glossary vacío; si es verdadero, define exclusivamente los términos solicitados. No incluyas datos personales que no sean necesarios ni los inventes. El usuario realizará la revisión final del contenido y las fuentes.
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
            "team_roles": [
                item.get("role_name") or item.get("role")
                for item in project.get("talents", [])
            ] + (["Experto Tecnoparque"] if project.get("expert") else []),
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