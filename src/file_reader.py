"""
file_reader.py — Extracts raw text from PDF, DOCX, and image files.

Supports:
  - PDF  → PyPDF2
  - DOCX → python-docx
  - Images (PNG, JPG, TIFF, etc.) → Pillow + Tesseract OCR
"""

import logging
from pathlib import Path

import PyPDF2
import docx

from src.config import TESSERACT_PATH

logger = logging.getLogger(__name__)


def read_pdf(file_path: Path) -> str:
    """Extract text from a PDF file, page by page."""
    text_parts: list[str] = []
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                else:
                    logger.debug("Page %d of '%s' yielded no text (may be scanned image).", i + 1, file_path.name)
    except Exception as e:
        logger.error("Failed to read PDF '%s': %s", file_path.name, e)
        raise

    full_text = "\n".join(text_parts).strip()

    # If PDF has no extractable text, it's likely a scanned document — try OCR
    if not full_text:
        logger.info("PDF '%s' has no extractable text. Attempting OCR via image conversion...", file_path.name)
        full_text = _ocr_pdf(file_path)

    return full_text


def _ocr_pdf(file_path: Path) -> str:
    """Convert PDF pages to images and run OCR. Requires pdf2image + poppler."""
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(file_path))
        text_parts = []
        for img in images:
            text_parts.append(_ocr_image_object(img))
        return "\n".join(text_parts).strip()
    except ImportError:
        logger.warning(
            "pdf2image not installed. Cannot OCR scanned PDF '%s'. "
            "Install with: pip install pdf2image  (also requires poppler)",
            file_path.name,
        )
        return ""
    except Exception as e:
        logger.error("OCR on PDF '%s' failed: %s", file_path.name, e)
        return ""


def read_docx(file_path: Path) -> str:
    """Extract text from a DOCX file, paragraph by paragraph."""
    try:
        doc = docx.Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

        # Also extract text from tables (many CVs use tables for layout)
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)

        return "\n".join(paragraphs).strip()
    except Exception as e:
        logger.error("Failed to read DOCX '%s': %s", file_path.name, e)
        raise


def read_image(file_path: Path) -> str:
    """Extract text from an image file using Tesseract OCR."""
    try:
        from PIL import Image
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

        img = Image.open(file_path)
        return _ocr_image_object(img)
    except ImportError:
        logger.error("Pillow or pytesseract not installed. Cannot read image '%s'.", file_path.name)
        raise
    except Exception as e:
        logger.error("Failed to OCR image '%s': %s", file_path.name, e)
        raise


def _ocr_image_object(img) -> str:
    """Run OCR on a PIL Image object."""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    text = pytesseract.image_to_string(img)
    return text.strip()


def read_file(file_path: Path) -> str:
    """
    Route to the correct reader based on file extension.
    Returns the extracted raw text.
    """
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return read_pdf(file_path)
    elif ext in {".docx", ".doc"}:
        return read_docx(file_path)
    elif ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}:
        return read_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext} (file: {file_path.name})")
