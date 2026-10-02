"""
config.py — Centralized configuration loaded from .env

All settings are read from environment variables with sensible defaults.
Import individual values from this module wherever needed.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


# ──────────────── LLM Provider ────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()

# Claude
CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Gemini
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ──────────────── Email (IMAP) ────────────────
EMAIL_IMAP_SERVER: str = os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com")
EMAIL_IMAP_PORT: int = int(os.getenv("EMAIL_IMAP_PORT", "993"))
EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
EMAIL_FOLDER: str = os.getenv("EMAIL_FOLDER", "INBOX")
EMAIL_SUBJECT_FILTER: str = os.getenv("EMAIL_SUBJECT_FILTER", "")
EMAIL_SENDER_FILTER: str = os.getenv("EMAIL_SENDER_FILTER", "")

# ──────────────── Paths ────────────────
CV_FOLDER: Path = Path(os.getenv("CV_FOLDER", _PROJECT_ROOT / "cvs")).resolve()
OUTPUT_EXCEL: Path = Path(os.getenv("OUTPUT_EXCEL", _PROJECT_ROOT / "output" / "cv_data.xlsx")).resolve()
SHORTLIST_EXCEL: Path = Path(os.getenv("SHORTLIST_EXCEL", _PROJECT_ROOT / "output" / "shortlisted.xlsx")).resolve()
JOB_MATCH_EXCEL: Path = Path(os.getenv("JOB_MATCH_EXCEL", _PROJECT_ROOT / "output" / "job_match_results.xlsx")).resolve()
EMAIL_TRACKER_FILE: Path = Path(os.getenv("EMAIL_TRACKER_FILE", _PROJECT_ROOT / "data" / "email_tracker.json")).resolve()

# Tesseract OCR
TESSERACT_PATH: str = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

# ──────────────── Processing ────────────────
MAX_CONCURRENT: int = int(os.getenv("MAX_CONCURRENT", "3"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ──────────────── API Server ────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# ──────────────── Supported file types ────────────────
SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

# ──────────────── Extraction fields ────────────────
EXTRACTION_FIELDS: list[str] = [
    "full_name",
    "email",
    "phone",
    "location",
    "date_of_birth",
    "age",
    "summary",
    "current_job_title",
    "experience_years",
    "education",
    "skills",
    "certifications",
    "languages",
]
