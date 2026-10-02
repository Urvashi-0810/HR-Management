"""
excel_writer.py — Writes extracted CV data to a styled Excel file.

Creates a professional Excel output with:
  - Formatted header row
  - Auto-sized columns
  - Filename column to trace back to source CV
  - Status column for processing results
"""

import logging
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.config import EXTRACTION_FIELDS, OUTPUT_EXCEL

logger = logging.getLogger(__name__)

# Column definitions: (internal_key, display_header)
COLUMNS: list[tuple[str, str]] = [
    ("_filename", "File Name"),
    ("full_name", "Full Name"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("location", "Location"),
    ("date_of_birth", "Date of Birth"),
    ("age", "Age"),
    ("summary", "Summary"),
    ("current_job_title", "Current/Last Job Title"),
    ("experience_years", "Experience (Years)"),
    ("education", "Education"),
    ("skills", "Skills"),
    ("certifications", "Certifications"),
    ("languages", "Languages"),
    ("_status", "Status"),
]

# Styling constants
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="2B579A", end_color="2B579A", fill_type="solid")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
CELL_FONT = Font(name="Calibri", size=10)
CELL_ALIGNMENT = Alignment(vertical="top", wrap_text=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)
ALT_ROW_FILL = PatternFill(start_color="F2F6FC", end_color="F2F6FC", fill_type="solid")
SUCCESS_FONT = Font(name="Calibri", size=10, color="217346")
ERROR_FONT = Font(name="Calibri", size=10, color="C00000")


def _create_workbook() -> Workbook:
    """Create a new workbook with styled headers."""
    wb = Workbook()
    ws = wb.active
    ws.title = "CV Data"

    # Write header row
    for col_idx, (_, header) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER

    # Freeze the header row
    ws.freeze_panes = "A2"

    # Set initial column widths
    default_widths = {
        "_filename": 25,
        "full_name": 22,
        "email": 28,
        "phone": 18,
        "location": 20,
        "date_of_birth": 14,
        "age": 8,
        "summary": 45,
        "current_job_title": 25,
        "experience_years": 14,
        "education": 35,
        "skills": 40,
        "certifications": 30,
        "languages": 18,
        "_status": 15,
    }
    for col_idx, (key, _) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = default_widths.get(key, 20)

    return wb


def _style_data_row(ws, row_idx: int, status: str) -> None:
    """Apply styling to a data row."""
    for col_idx in range(1, len(COLUMNS) + 1):
        cell = ws.cell(row=row_idx, column=col_idx)
        cell.font = CELL_FONT
        cell.alignment = CELL_ALIGNMENT
        cell.border = THIN_BORDER

        # Alternating row colors
        if row_idx % 2 == 0:
            cell.fill = ALT_ROW_FILL

    # Style the status column
    status_col = len(COLUMNS)
    status_cell = ws.cell(row=row_idx, column=status_col)
    if status.lower() == "success":
        status_cell.font = SUCCESS_FONT
    else:
        status_cell.font = ERROR_FONT


def write_to_excel(
    records: list[dict[str, Any]],
    output_path: Path | None = None,
    append: bool = False,
) -> Path:
    """
    Write extracted CV data records to an Excel file.

    Args:
        records: List of dicts, each containing extraction fields + "_filename" and "_status".
        output_path: Override the default output path.
        append: If True and the file exists, append rows instead of overwriting.

    Returns:
        Path to the written Excel file.
    """
    out = output_path or OUTPUT_EXCEL

    # Ensure output directory exists
    out.parent.mkdir(parents=True, exist_ok=True)

    # Load existing or create new workbook
    if append and out.exists():
        logger.info("Appending to existing Excel file: %s", out)
        wb = load_workbook(str(out))
        ws = wb.active
        start_row = ws.max_row + 1
    else:
        wb = _create_workbook()
        ws = wb.active
        start_row = 2  # Row 1 is the header

    # Write data rows
    for i, record in enumerate(records):
        row_idx = start_row + i
        status = record.get("_status", "unknown")

        for col_idx, (key, _) in enumerate(COLUMNS, start=1):
            value = record.get(key)
            # Convert None to empty string for cleaner Excel output
            if value is None:
                value = ""
            # Convert lists to comma-separated strings
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            ws.cell(row=row_idx, column=col_idx, value=str(value))

        _style_data_row(ws, row_idx, status)

    # Auto-filter on all columns
    ws.auto_filter.ref = ws.dimensions

    # Save
    wb.save(str(out))
    logger.info("Excel file saved: %s (%d records written)", out, len(records))

    return out


def read_from_excel(input_path: Path | None = None) -> list[dict[str, Any]]:
    """
    Read CV data records back from an Excel file.

    Args:
        input_path: Path to the Excel file. Defaults to OUTPUT_EXCEL.

    Returns:
        List of dicts, one per row, keyed by internal field names.
    """
    path = input_path or OUTPUT_EXCEL
    if not path.exists():
        logger.warning("Excel file not found: %s", path)
        return []

    wb = load_workbook(str(path), read_only=True)
    ws = wb.active

    # Build column key mapping from header row
    headers = []
    for cell in ws[1]:
        # Find the internal key for this header
        found_key = None
        for key, display in COLUMNS:
            if cell.value == display:
                found_key = key
                break
        headers.append(found_key or cell.value)

    records = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):  # Skip fully empty rows
            continue
        record = {}
        for i, value in enumerate(row):
            if i < len(headers):
                key = headers[i]
                record[key] = value if value is not None else ""
        records.append(record)

    wb.close()
    logger.info("Read %d records from: %s", len(records), path)
    return records
