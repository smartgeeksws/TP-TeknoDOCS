"""Conversion de libros XLSX a PDF en Windows y Linux."""

from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


class SpreadsheetPdfError(RuntimeError):
    """Error controlado al convertir una hoja de calculo a PDF."""


_SPREADSHEET_LOCK = threading.Lock()


def convert_xlsx_to_pdf(
    xlsx_path: Path,
    pdf_path: Path,
    sheet_name: str = "GCDTP-F-019",
) -> None:
    with _SPREADSHEET_LOCK:
        if platform.system() == "Windows":
            _convert_with_excel(xlsx_path, pdf_path, sheet_name)
        else:
            _convert_with_libreoffice(xlsx_path, pdf_path)
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise SpreadsheetPdfError("No se produjo el archivo PDF esperado.")


def _convert_with_excel(xlsx_path: Path, pdf_path: Path, sheet_name: str) -> None:
    try:
        import pythoncom
        import win32com.client
    except ImportError as error:
        raise SpreadsheetPdfError(
            "La conversion local requiere Microsoft Excel y pywin32."
        ) from error

    excel = None
    workbook = None
    pythoncom.CoInitialize()
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(str(xlsx_path.resolve()), ReadOnly=True)
        worksheet = workbook.Worksheets(sheet_name)
        worksheet.PageSetup.PaperSize = 1
        worksheet.PageSetup.Orientation = 2
        worksheet.PageSetup.Zoom = False
        worksheet.PageSetup.FitToPagesTall = False
        worksheet.PageSetup.FitToPagesWide = 1
        worksheet.PageSetup.LeftMargin = excel.InchesToPoints(0.15)
        worksheet.PageSetup.RightMargin = excel.InchesToPoints(0.15)
        worksheet.PageSetup.TopMargin = excel.InchesToPoints(0.3)
        worksheet.PageSetup.BottomMargin = excel.InchesToPoints(0.3)
        worksheet.PageSetup.CenterHorizontally = True
        worksheet.PageSetup.PrintArea = worksheet.UsedRange.Address
        worksheet.ResetAllPageBreaks()
        worksheet.ExportAsFixedFormat(
            0,
            str(pdf_path.resolve()),
            IgnorePrintAreas=False,
        )
    except Exception as error:
        raise SpreadsheetPdfError(
            f"No fue posible convertir el documento con Microsoft Excel: {error}"
        ) from error
    finally:
        if workbook is not None:
            try:
                workbook.Close(False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _convert_with_libreoffice(xlsx_path: Path, pdf_path: Path) -> None:
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable is None:
        raise SpreadsheetPdfError("LibreOffice no esta instalado en el servidor.")
    with tempfile.TemporaryDirectory(prefix="tp_lo_profile_") as profile:
        result = subprocess.run(
            [
                executable,
                "--headless",
                f"-env:UserInstallation=file:///{Path(profile).as_posix()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf_path.parent.resolve()),
                str(xlsx_path.resolve()),
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    converted = pdf_path.parent / f"{xlsx_path.stem}.pdf"
    if result.returncode != 0 or not converted.is_file():
        detail = result.stderr.strip() or result.stdout.strip()
        raise SpreadsheetPdfError(
            f"No fue posible convertir el documento con LibreOffice: {detail}"
        )
    if converted.resolve() != pdf_path.resolve():
        converted.replace(pdf_path)
