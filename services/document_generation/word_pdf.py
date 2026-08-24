"""Conversión de documentos Word a PDF en Windows y Linux."""

from __future__ import annotations

import platform
import shutil
import subprocess
import threading
from pathlib import Path


class PdfConversionError(RuntimeError):
    """Error controlado al convertir un DOCX a PDF."""


_WORD_LOCK = threading.Lock()


def convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> None:
    """Usa Microsoft Word en Windows y LibreOffice en servidores Linux."""

    with _WORD_LOCK:
        if platform.system() == "Windows":
            _convert_with_microsoft_word(docx_path, pdf_path)
        else:
            _convert_with_libreoffice(docx_path, pdf_path)

    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise PdfConversionError("No se produjo el archivo PDF esperado.")


def _convert_with_microsoft_word(docx_path: Path, pdf_path: Path) -> None:
    try:
        import pythoncom
        import win32com.client
    except ImportError as error:
        raise PdfConversionError(
            "La conversión local requiere Microsoft Word y pywin32."
        ) from error

    word = None
    document = None
    pythoncom.CoInitialize()
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(
            str(docx_path.resolve()),
            ReadOnly=True,
            AddToRecentFiles=False,
        )
        document.ExportAsFixedFormat(
            OutputFileName=str(pdf_path.resolve()),
            ExportFormat=17,
            OpenAfterExport=False,
        )
    except Exception as error:
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise PdfConversionError(
                f"No fue posible convertir el documento con Microsoft Word: {error}"
            ) from error
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _convert_with_libreoffice(docx_path: Path, pdf_path: Path) -> None:
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable is None:
        raise PdfConversionError(
            "LibreOffice no está instalado en el servidor."
        )

    result = subprocess.run(
        [
            executable,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_path.parent.resolve()),
            str(docx_path.resolve()),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    converted_path = pdf_path.parent / f"{docx_path.stem}.pdf"
    if result.returncode != 0 or not converted_path.is_file():
        detail = result.stderr.strip() or result.stdout.strip()
        raise PdfConversionError(
            f"No fue posible convertir el documento con LibreOffice: {detail}"
        )
    if converted_path.resolve() != pdf_path.resolve():
        converted_path.replace(pdf_path)
