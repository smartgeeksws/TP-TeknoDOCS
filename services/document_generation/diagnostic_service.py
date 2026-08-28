"""Diligenciamiento de la plantilla Word GCDTP-F-020 V01."""

from __future__ import annotations

import io
import math
import re
import shutil
import tempfile
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from config.settings import DIAGNOSTIC_TEMPLATE


class DiagnosticDocumentError(RuntimeError):
    """Error controlado al construir o validar el GCDTP-F-020."""


class DiagnosticDocumentService:
    HEADING_MAP = {
        25: ("1. Información general del proyecto", "Heading 1"),
        29: ("1.1 Glosario (si aplica)", "Heading 2"),
        32: ("1.2 Introducción", "Heading 2"),
        35: ("1.3 Planteamiento del problema o necesidad", "Heading 2"),
        38: ("1.4 Problema identificado", "Heading 2"),
        41: ("1.5 Impacto del problema", "Heading 2"),
        44: ("2. Tipo de proyecto", "Heading 1"),
        47: ("3. Objetivos del proyecto", "Heading 1"),
        50: ("3.1 Objetivo General", "Heading 2"),
        53: ("3.2 Objetivos específicos", "Heading 2"),
        56: ("4. Solución planteada", "Heading 1"),
        59: ("5. Estado del arte y de la técnica", "Heading 1"),
        62: ("5.1 Productos similares (desarrollos tecnológicos actuales)", "Heading 2"),
        68: ("5.2 Tecnología involucrada", "Heading 2"),
        74: ("6. Vigilancia tecnológica y referentes científicos", "Heading 1"),
        77: ("7. Artículos científicos relevantes y/o patentes, entre otros", "Heading 1"),
        83: ("8. Estudio legal y normativo", "Heading 1"),
        90: ("9. Análisis de viabilidad", "Heading 1"),
        93: ("10. Resultados esperados", "Heading 1"),
        96: ("11. Cronograma del proyecto", "Heading 1"),
        99: ("12. Conclusiones", "Heading 1"),
        102: ("13. Referencias bibliográficas", "Heading 1"),
        105: ("14. Anexos", "Heading 1"),
    }

    def generate(
        self,
        project: dict[str, Any],
        form_data: dict[str, Any],
        content: dict[str, Any],
    ) -> tuple[bytes, str]:
        self._validate(project, form_data, content)
        with tempfile.TemporaryDirectory(prefix="tp_diagnostic_") as directory:
            path = Path(directory) / "diagnostico.docx"
            shutil.copy2(DIAGNOSTIC_TEMPLATE, path)
            self._complete(path, project, form_data, content)
            data = path.read_bytes()
        if not data.startswith(b"PK"):
            raise DiagnosticDocumentError("El archivo Word generado no es válido.")
        code = self._safe_filename(str(project.get("code") or "proyecto"))
        return data, f"Diagnostico_Estado_del_Arte_{code}.docx"

    def _complete(
        self,
        path: Path,
        project: dict[str, Any],
        form_data: dict[str, Any],
        content: dict[str, Any],
    ) -> None:
        document = Document(path)
        if len(document.paragraphs) < 107 or len(document.tables) < 6:
            raise DiagnosticDocumentError("La estructura de la plantilla GCDTP-F-020 cambió.")

        for index, (title, style) in self.HEADING_MAP.items():
            self._replace_paragraph(document.paragraphs[index], title, style=style)

        glossary = content.get("glossary", [])
        glossary_text = (
            "\n".join(
                f"{item['term']}: {item['definition']} {item['citation']}"
                for item in glossary
            )
            if form_data.get("glossary_requested")
            else "No aplica para el presente proyecto."
        )
        replacements = {
            30: glossary_text,
            33: content["introduction"],
            36: content["problem_statement"],
            39: content["problem_identified"],
            42: content["problem_impact"],
            45: content["project_type"],
            48: "Los objetivos se formulan en coherencia con el problema, la solución y los resultados previstos.",
            51: content["general_objective"],
            54: "\n".join(
                f"{index}. {objective}"
                for index, objective in enumerate(content["specific_objectives"], 1)
            ),
            57: content["solution"],
            60: content["state_of_art"],
            63: "Los desarrollos comparados se seleccionaron a partir de fuentes verificadas y por su relación técnica directa con el proyecto.",
            69: content["technology_narrative"],
            75: content["technology_surveillance"],
            78: "Los referentes siguientes sustentan decisiones técnicas, metodológicas y de validación del proyecto.",
            84: content["legal_study"],
            91: content["viability"],
            94: content["expected_results"],
            97: "Las actividades se organizan según la naturaleza técnica del proyecto y el periodo registrado.",
            100: content["conclusions"],
            103: "\n".join(content["references"]),
            106: "El presente documento no cuenta con anexos.",
        }
        for index, text in replacements.items():
            self._replace_paragraph(document.paragraphs[index], text, justify=index not in {45, 48, 54, 78, 97, 103, 106})

        document.tables[0].cell(5, 0).text = "[X] Pública"
        document.tables[0].cell(5, 1).text = "[ ] Pública Clasificada"
        document.tables[0].cell(5, 2).text = "[ ] Pública Reservada"
        self._fill_project_table(document.tables[1], project, form_data)
        self._fill_similar_products(document.tables[2], content["similar_products"])
        self._fill_technologies(document.tables[3], content["technologies"])
        self._fill_scientific_references(document.tables[4], content["scientific_references"])
        self._fill_regulations(document.tables[5], content["regulations"])
        self._insert_schedule(document, document.paragraphs[97], project, content["schedule"])
        self._enable_field_updates(document)
        document.core_properties.title = "GCDTP-F-020 V01 Diagnóstico del proyecto y estado del arte"
        document.core_properties.subject = str(project.get("code") or "")
        document.save(path)
        self._validate_saved(path)

    def _fill_project_table(self, table: Any, project: dict[str, Any], form_data: dict[str, Any]) -> None:
        expert = project.get("expert") or {}
        team = [
            f"{item.get('name') or 'N.A.'} — {item.get('role_name') or item.get('role') or 'Talento'}"
            for item in project.get("talents", [])
        ]
        if expert.get("name"):
            team.append(f"{expert['name']} — Experto Tecnoparque")
        values = (
            project.get("name") or "N.A.",
            project.get("code") or "N.A.",
            project.get("technopark") or project.get("node") or "No registrado en el proyecto",
            project.get("technology_line") or "No registrado en el proyecto",
            "\n".join(team) or "No registrado en el proyecto",
            date.fromisoformat(form_data["document_date"]).strftime("%d/%m/%Y"),
            project.get("training_center") or "No registrado en el proyecto",
            project.get("regional") or "No registrado en el proyecto",
        )
        for row, value in enumerate(values):
            table.cell(row, 1).text = str(value)
            self._format_cell(table.cell(row, 1))

    def _fill_similar_products(self, table: Any, values: list[dict[str, Any]]) -> None:
        rows = [
            [
                item["solution"],
                f"{item['description']} {item['citation']}",
                item["relationship"],
                item["differential"],
            ]
            for item in values
        ]
        self._replace_data_rows(table, rows)

    def _fill_technologies(self, table: Any, values: list[dict[str, Any]]) -> None:
        self._replace_data_rows(table, [[item["name"], item["use"]] for item in values])

    def _fill_scientific_references(self, table: Any, values: list[dict[str, Any]]) -> None:
        self._replace_data_rows(
            table,
            [[item["type"], item["author"], str(item["year"]), f"{item['result']} {item['citation']}", item["relationship"], item["country"], item["application"]] for item in values],
        )

    def _fill_regulations(self, table: Any, values: list[dict[str, Any]]) -> None:
        self._replace_data_rows(
            table,
            [
                [
                    item["name"],
                    f"{item['application']} {item['citation']}",
                    item["intellectual_property"],
                ]
                for item in values
            ],
        )

    def _insert_schedule(
        self,
        document: Document,
        anchor: Any,
        project: dict[str, Any],
        schedule: list[dict[str, Any]],
    ) -> None:
        table = document.add_table(rows=1, cols=6)
        table.style = "Table Grid"
        headers = ("Fase", "Actividad", "Fecha inicial", "Fecha final", "Duración", "Entregable")
        for index, header in enumerate(headers):
            table.cell(0, index).text = header
        dates = self._schedule_dates(project, len(schedule))
        for item, date_range in zip(schedule, dates):
            cells = table.add_row().cells
            start, end = date_range
            values = (
                item["phase"],
                item["activity"],
                start.strftime("%d/%m/%Y") if start else "Por definir",
                end.strftime("%d/%m/%Y") if end else "Por definir",
                str((end - start).days + 1) if start and end else "Por definir",
                item["deliverable"],
            )
            for cell, value in zip(cells, values):
                cell.text = value
                self._format_cell(cell)
        anchor._p.addnext(table._tbl)

    @staticmethod
    def _schedule_dates(project: dict[str, Any], count: int) -> list[tuple[date | None, date | None]]:
        start = DiagnosticDocumentService._as_date(project.get("start_date"))
        end = DiagnosticDocumentService._as_date(project.get("end_date"))
        if start is None or end is None or end < start:
            return [(None, None)] * count
        total = (end - start).days + 1
        ranges = []
        for index in range(count):
            start_offset = math.floor(index * total / count)
            end_offset = max(start_offset, math.floor((index + 1) * total / count) - 1)
            ranges.append((start + timedelta(days=start_offset), min(end, start + timedelta(days=end_offset))))
        return ranges

    @staticmethod
    def _replace_data_rows(table: Any, rows: list[list[str]]) -> None:
        prototype = deepcopy(table.rows[1]._tr)
        for row in list(table.rows)[1:]:
            table._tbl.remove(row._tr)
        for values in rows:
            table._tbl.append(deepcopy(prototype))
            current = table.rows[-1]
            for cell, value in zip(current.cells, values):
                cell.text = str(value)
                DiagnosticDocumentService._format_cell(cell)

    @staticmethod
    def _format_cell(cell: Any) -> None:
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in paragraph.runs:
                run.font.size = Pt(9)

    @staticmethod
    def _replace_paragraph(paragraph: Any, text: str, *, style: str | None = None, justify: bool = False) -> None:
        for child in list(paragraph._p):
            if child.tag != qn("w:pPr"):
                paragraph._p.remove(child)
        run = paragraph.add_run(text)
        if style:
            paragraph.style = style
        if justify:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.space_after = Pt(6)
        run.font.name = "Arial"
        if not style:
            run.font.size = Pt(10)

    @staticmethod
    def _enable_field_updates(document: Document) -> None:
        settings = document.settings._element
        update = settings.find(qn("w:updateFields"))
        if update is None:
            update = OxmlElement("w:updateFields")
            settings.append(update)
        update.set(qn("w:val"), "true")
        for field in document.element.body.xpath('.//w:fldChar[@w:fldCharType="begin"]'):
            field.set(qn("w:dirty"), "true")

    def _validate_saved(self, path: Path) -> None:
        document = Document(path)
        full_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        required = [title for title, _ in self.HEADING_MAP.values()]
        missing = [title for title in required if title not in full_text]
        if missing:
            raise DiagnosticDocumentError("Faltan títulos en el documento generado.")
        if "El presente documento no cuenta con anexos." not in full_text:
            raise DiagnosticDocumentError("No se diligenció correctamente el apartado de anexos.")
        if len(document.tables) < 7:
            raise DiagnosticDocumentError("No se generó la tabla de cronograma.")

    @staticmethod
    def _validate(project: dict[str, Any], form_data: dict[str, Any], content: dict[str, Any]) -> None:
        if not DIAGNOSTIC_TEMPLATE.is_file():
            raise DiagnosticDocumentError("No se encontró la plantilla GCDTP-F-020.")
        for key in ("id", "code", "name", "description"):
            if not project.get(key):
                raise DiagnosticDocumentError(f"Falta el dato del proyecto: {key}.")
        required_content = {
            "introduction", "problem_statement", "problem_identified",
            "problem_impact", "project_type", "general_objective",
            "specific_objectives", "solution", "state_of_art",
            "similar_products", "technology_narrative", "technologies",
            "technology_surveillance", "scientific_references", "legal_study",
            "regulations", "viability", "expected_results", "schedule",
            "conclusions", "references", "sources",
        }
        missing = sorted(required_content - set(content))
        if missing:
            raise DiagnosticDocumentError(
                "Falta contenido para diligenciar: " + ", ".join(missing) + "."
            )
    @staticmethod
    def _as_date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value:
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _safe_filename(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
        return cleaned.strip("_") or "proyecto"