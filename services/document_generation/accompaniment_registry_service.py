"""Generacion de Excel y PDF para GCDTP-F-022 preservando la plantilla."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from config.settings import ACCOMPANIMENT_REGISTRY_TEMPLATE
from services.accompaniment_registry_service import AccompanimentRegistryService
from services.document_generation.spreadsheet_pdf import (
    SpreadsheetPdfError,
    convert_xlsx_to_pdf,
)


class AccompanimentRegistryDocumentError(RuntimeError):
    """Error controlado al producir el formato GCDTP-F-022."""


class AccompanimentRegistryDocumentService:
    SHEET_XML_PATH = "xl/worksheets/sheet1.xml"
    XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    X14_NS = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
    XM_NS = "http://schemas.microsoft.com/office/excel/2006/main"

    def __init__(self) -> None:
        self.logic = AccompanimentRegistryService()
        ET.register_namespace("", self.XML_NS)
        ET.register_namespace("x14", self.X14_NS)
        ET.register_namespace("xm", self.XM_NS)

    def generate(
        self,
        project: dict[str, Any],
        draft: dict[str, Any],
    ) -> tuple[bytes, bytes | None, str, str]:
        if not ACCOMPANIMENT_REGISTRY_TEMPLATE.is_file():
            raise AccompanimentRegistryDocumentError(
                "No se encontro la plantilla GCDTP-F-022."
            )

        form_data = draft["form_data"]
        excel_name = self.logic.export_filename(
            form_data,
            project.get("code") or "",
            "xlsx",
        )
        pdf_name = self.logic.export_filename(
            form_data,
            project.get("code") or "",
            "pdf",
        )
        with tempfile.TemporaryDirectory(prefix="tp_f022_") as temp_dir:
            directory = Path(temp_dir)
            xlsx_path = directory / excel_name
            pdf_path = directory / pdf_name
            shutil.copy2(ACCOMPANIMENT_REGISTRY_TEMPLATE, xlsx_path)
            self._fill_workbook(xlsx_path, project, draft)
            pdf_data: bytes | None = None
            try:
                convert_xlsx_to_pdf(xlsx_path, pdf_path, sheet_name="GCDTP-F-022")
            except SpreadsheetPdfError:
                pdf_data = None
            else:
                pdf_data = pdf_path.read_bytes()
            return xlsx_path.read_bytes(), pdf_data, excel_name, pdf_name

    def _fill_workbook(self, path: Path, project: dict[str, Any], draft: dict[str, Any]) -> None:
        with tempfile.TemporaryDirectory(prefix="tp_f022_zip_") as extract_dir:
            extract_path = Path(extract_dir)
            with zipfile.ZipFile(path, "r") as archive:
                archive.extractall(extract_path)
            sheet_path = extract_path / self.SHEET_XML_PATH
            tree = ET.parse(sheet_path)
            root = tree.getroot()
            self._replace_sheet_rows(root, project, draft)
            tree.write(sheet_path, encoding="utf-8", xml_declaration=True)
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                for file_path in extract_path.rglob("*"):
                    if file_path.is_file():
                        archive.write(
                            file_path,
                            file_path.relative_to(extract_path).as_posix(),
                        )

    def _replace_sheet_rows(
        self,
        root: ET.Element,
        project: dict[str, Any],
        draft: dict[str, Any],
    ) -> None:
        ns = {"a": self.XML_NS, "x14": self.X14_NS, "xm": self.XM_NS}
        sheet_data = root.find("a:sheetData", ns)
        if sheet_data is None:
            raise AccompanimentRegistryDocumentError(
                "La plantilla GCDTP-F-022 no contiene sheetData."
            )
        rows = sheet_data.findall("a:row", ns)
        row_18 = next((row for row in rows if row.attrib.get("r") == "18"), None)
        row_19 = next((row for row in rows if row.attrib.get("r") == "19"), None)
        if row_18 is None or row_19 is None:
            raise AccompanimentRegistryDocumentError(
                "La plantilla no contiene las filas base esperadas."
            )

        for row in list(rows):
            if int(row.attrib["r"]) >= 18:
                sheet_data.remove(row)

        for row in rows:
            row_number = int(row.attrib["r"])
            if row_number == 8:
                self._set_inline_text(self._cell_by_ref(row, "A8"), "Publica  X")
                self._set_inline_text(self._cell_by_ref(row, "E8"), "Publica Clasificada")
                self._set_inline_text(self._cell_by_ref(row, "H8"), "Publica Reservada")
            elif row_number == 11:
                self._set_inline_text(self._cell_by_ref(row, "D11"), project.get("code") or "")
                self._set_inline_text(
                    self._cell_by_ref(row, "H11"),
                    str(draft["form_data"].get("meeting_number") or ""),
                )
            elif row_number == 12:
                self._set_inline_text(
                    self._cell_by_ref(row, "D12"),
                    self.logic.TECHNO_PARK,
                )
            elif row_number == 13:
                self._set_inline_text(
                    self._cell_by_ref(row, "D13"),
                    self.logic.REGIONAL_CENTER,
                )
            elif row_number == 14:
                self._set_inline_text(
                    self._cell_by_ref(row, "D14"),
                    (project.get("expert") or {}).get("name") or "",
                )
            elif row_number == 15:
                self._set_inline_text(self._cell_by_ref(row, "D15"), project.get("name") or "")
                self._set_inline_text(
                    self._cell_by_ref(row, "H15"),
                    str(draft["form_data"].get("phase") or ""),
                )

        activities = draft["activities"]
        for index, activity in enumerate(activities):
            target_row_number = 18 + index
            template = deepcopy(row_18 if index == 0 else row_19)
            self._populate_activity_row(
                template,
                target_row_number,
                activity,
                (project.get("expert") or {}).get("name") or "",
            )
            sheet_data.append(template)

        last_row = 17 + len(activities)
        self._update_dimension(root, last_row)
        self._update_validations(root, last_row)
        self._update_print_area(root, last_row)

    def _populate_activity_row(
        self,
        row: ET.Element,
        row_number: int,
        activity: dict[str, Any],
        expert_name: str,
    ) -> None:
        row.attrib["r"] = str(row_number)
        row.attrib["ht"] = self._estimated_row_height(activity)
        row.attrib["customHeight"] = "1"
        for cell in row.findall(f"{{{self.XML_NS}}}c"):
            reference = cell.attrib["r"]
            column = "".join(character for character in reference if character.isalpha())
            cell.attrib["r"] = f"{column}{row_number}"
            if column == "A":
                self._set_inline_text(cell, activity["type"])
            elif column == "B":
                self._set_inline_text(cell, activity.get("other", ""))
            elif column == "C":
                self._set_inline_text(cell, self._format_date(activity["date"]))
            elif column == "D":
                self._set_number(cell, float(activity["direct_hours"]))
            elif column == "E":
                self._set_number(cell, float(activity["indirect_hours"]))
            elif column == "F":
                self._set_inline_text(cell, "\n".join(activity.get("equipment_lines", [])))
            elif column == "G":
                self._set_inline_text(cell, "\n".join(activity.get("material_lines", [])))
            elif column == "H":
                self._set_inline_text(cell, activity["description"])
            elif column == "I":
                self._set_inline_text(cell, expert_name)

    def _update_dimension(self, root: ET.Element, last_row: int) -> None:
        dimension = root.find(f"{{{self.XML_NS}}}dimension")
        if dimension is not None:
            dimension.attrib["ref"] = f"A1:I{last_row}"

    def _update_validations(self, root: ET.Element, last_row: int) -> None:
        for validation in root.findall(f".//{{{self.XML_NS}}}dataValidation"):
            sqref = validation.attrib.get("sqref")
            if sqref == "B18:B30":
                validation.attrib["sqref"] = f"B18:B{last_row}"
        for sqref in root.findall(f".//{{{self.XM_NS}}}sqref"):
            text = (sqref.text or "").strip()
            if text.startswith("A18") or text.startswith("A19:"):
                sqref.text = f"A18:A{last_row}"

    def _update_print_area(self, root: ET.Element, last_row: int) -> None:
        ns = {"a": self.XML_NS}
        defined_names = root.find("a:definedNames", ns)
        if defined_names is None:
            defined_names = ET.SubElement(root, f"{{{self.XML_NS}}}definedNames")
        print_area = None
        for item in defined_names.findall("a:definedName", ns):
            if item.attrib.get("name") == "_xlnm.Print_Area":
                print_area = item
                break
        if print_area is None:
            print_area = ET.SubElement(
                defined_names,
                f"{{{self.XML_NS}}}definedName",
                {"name": "_xlnm.Print_Area", "localSheetId": "0"},
            )
        print_area.text = f"'GCDTP-F-022'!$A$1:$I${last_row}"

        print_titles = None
        for item in defined_names.findall("a:definedName", ns):
            if item.attrib.get("name") == "_xlnm.Print_Titles":
                print_titles = item
                break
        if print_titles is None:
            print_titles = ET.SubElement(
                defined_names,
                f"{{{self.XML_NS}}}definedName",
                {"name": "_xlnm.Print_Titles", "localSheetId": "0"},
            )
        print_titles.text = "'GCDTP-F-022'!$1:$17"

    def _cell_by_ref(self, row: ET.Element, reference: str) -> ET.Element:
        for cell in row.findall(f"{{{self.XML_NS}}}c"):
            if cell.attrib.get("r") == reference:
                return cell
        raise AccompanimentRegistryDocumentError(
            f"No se encontro la celda {reference} en la plantilla."
        )

    def _set_inline_text(self, cell: ET.Element, value: str) -> None:
        cell.attrib["t"] = "inlineStr"
        for child in list(cell):
            cell.remove(child)
        inline = ET.SubElement(cell, f"{{{self.XML_NS}}}is")
        text = ET.SubElement(inline, f"{{{self.XML_NS}}}t")
        text.text = value or ""
        if value and (value.startswith(" ") or value.endswith(" ") or "\n" in value):
            text.attrib["{http://www.w3.org/XML/1998/namespace}space"] = "preserve"

    def _set_number(self, cell: ET.Element, value: float) -> None:
        cell.attrib.pop("t", None)
        for child in list(cell):
            cell.remove(child)
        value_node = ET.SubElement(cell, f"{{{self.XML_NS}}}v")
        value_node.text = f"{value:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%d/%m/%Y")

    @staticmethod
    def _estimated_row_height(activity: dict[str, Any]) -> str:
        text_parts = [
            activity.get("description", ""),
            "\n".join(activity.get("equipment_lines", [])),
            "\n".join(activity.get("material_lines", [])),
        ]
        length = max(len(part) for part in text_parts)
        lines = max(2, min(10, (length // 70) + 2))
        return str(max(29.25, lines * 14.5))
