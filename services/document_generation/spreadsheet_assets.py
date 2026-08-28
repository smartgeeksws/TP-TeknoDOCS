"""Utilidades graficas compartidas para plantillas de hojas de calculo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl.drawing.image import Image as SpreadsheetImage
from openpyxl.drawing.spreadsheet_drawing import (
    AnchorMarker,
    OneCellAnchor,
    XDRPositiveSize2D,
)
from openpyxl.utils import range_boundaries
from openpyxl.utils.units import pixels_to_EMU, points_to_pixels


def add_centered_image(
    sheet: Any,
    image_path: Path,
    cell_range: str,
    height: float,
) -> None:
    """Inserta una imagen centrada en un rango de celdas."""

    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    image = SpreadsheetImage(image_path)
    aspect_ratio = image.width / image.height
    image.height = height
    image.width = height * aspect_ratio

    dimensions = tuple(sheet.column_dimensions.values())

    def column_width(column: int) -> int:
        dimension = next(
            (
                item
                for item in dimensions
                if (item.min or column) <= column <= (item.max or column)
            ),
            None,
        )
        width = (
            dimension.width
            if dimension is not None and dimension.width is not None
            else sheet.sheet_format.defaultColWidth
            or sheet.sheet_format.baseColWidth
            or 10
        )
        return max(1, round(width * 7))

    column_widths = [column_width(column) for column in range(min_col, max_col + 1)]
    row_heights = [
        points_to_pixels(
            sheet.row_dimensions[row].height
            or sheet.sheet_format.defaultRowHeight
            or 15
        )
        for row in range(min_row, max_row + 1)
    ]
    left = max(0, (sum(column_widths) - image.width) / 2)
    top = max(0, (sum(row_heights) - image.height) / 2)

    column_offset = 0
    while column_offset < len(column_widths) - 1 and left >= column_widths[column_offset]:
        left -= column_widths[column_offset]
        column_offset += 1
    row_offset = 0
    while row_offset < len(row_heights) - 1 and top >= row_heights[row_offset]:
        top -= row_heights[row_offset]
        row_offset += 1

    image.anchor = OneCellAnchor(
        _from=AnchorMarker(
            col=min_col - 1 + column_offset,
            colOff=pixels_to_EMU(left),
            row=min_row - 1 + row_offset,
            rowOff=pixels_to_EMU(top),
        ),
        ext=XDRPositiveSize2D(
            cx=pixels_to_EMU(image.width),
            cy=pixels_to_EMU(image.height),
        ),
    )
    sheet.add_image(image)
