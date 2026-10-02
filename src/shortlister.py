"""
shortlister.py — Filter and shortlist candidates from extracted CV data.

Reads the extraction Excel, applies configurable criteria, and outputs
a filtered list of candidates that meet the requirements.

Supports filtering by:
  - Experience (min/max years)
  - Age (min/max)
  - Required skills (any match)
  - Required education keywords
  - Required job title keywords
  - Required location keywords
"""

import logging
from pathlib import Path
from typing import Any

from src.config import OUTPUT_EXCEL, SHORTLIST_EXCEL
from src.excel_writer import read_from_excel, write_to_excel

logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int."""
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _contains_any(text: str, keywords: list[str]) -> bool:
    """Check if text contains any of the given keywords (case-insensitive)."""
    if not text or not keywords:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def shortlist_candidates(
    criteria: dict[str, Any],
    input_path: Path | None = None,
    output_path: Path | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Filter candidates based on the given criteria.

    Args:
        criteria: Dict with filter keys:
            - min_experience (float): Minimum years of experience
            - max_experience (float): Maximum years of experience
            - min_age (int): Minimum age
            - max_age (int): Maximum age
            - required_skills (list[str]): At least one skill must match
            - required_education (list[str]): Education must contain one keyword
            - required_job_title (list[str]): Job title must contain one keyword
            - required_location (list[str]): Location must contain one keyword
        input_path: Path to the source Excel file (default: OUTPUT_EXCEL).
        output_path: Path to save the shortlisted Excel (default: SHORTLIST_EXCEL).
        candidates: Optional pre-loaded candidate list (skips Excel read).

    Returns:
        Summary dict with shortlisted records and counts.
    """
    # Load candidates
    if candidates is None:
        records = read_from_excel(input_path or OUTPUT_EXCEL)
    else:
        records = candidates

    if not records:
        logger.warning("No candidate records found.")
        return {"total": 0, "shortlisted": 0, "rejected": 0, "candidates": []}

    # Only consider successfully extracted records
    records = [r for r in records if r.get("_status", "success") == "success"]

    logger.info("Applying shortlist criteria to %d candidates...", len(records))
    logger.info("Criteria: %s", criteria)

    shortlisted = []
    rejected = []

    for record in records:
        reasons = []
        passed = True

        # ── Experience filter ──
        min_exp = criteria.get("min_experience")
        max_exp = criteria.get("max_experience")
        exp_years = _safe_float(record.get("experience_years"))

        if min_exp is not None and exp_years < float(min_exp):
            passed = False
            reasons.append(f"experience {exp_years}y < min {min_exp}y")
        if max_exp is not None and exp_years > float(max_exp):
            passed = False
            reasons.append(f"experience {exp_years}y > max {max_exp}y")

        # ── Age filter ──
        min_age = criteria.get("min_age")
        max_age = criteria.get("max_age")
        age = _safe_int(record.get("age"))

        if min_age is not None and age > 0 and age < int(min_age):
            passed = False
            reasons.append(f"age {age} < min {min_age}")
        if max_age is not None and age > 0 and age > int(max_age):
            passed = False
            reasons.append(f"age {age} > max {max_age}")

        # ── Skills filter ──
        required_skills = criteria.get("required_skills")
        if required_skills and isinstance(required_skills, list) and len(required_skills) > 0:
            candidate_skills = str(record.get("skills", ""))
            if not _contains_any(candidate_skills, required_skills):
                passed = False
                reasons.append(f"missing required skills: {required_skills}")

        # ── Education filter ──
        required_education = criteria.get("required_education")
        if required_education and isinstance(required_education, list) and len(required_education) > 0:
            candidate_edu = str(record.get("education", ""))
            if not _contains_any(candidate_edu, required_education):
                passed = False
                reasons.append(f"education mismatch: {required_education}")

        # ── Job title filter ──
        required_job_title = criteria.get("required_job_title")
        if required_job_title and isinstance(required_job_title, list) and len(required_job_title) > 0:
            candidate_title = str(record.get("current_job_title", ""))
            if not _contains_any(candidate_title, required_job_title):
                passed = False
                reasons.append(f"job title mismatch: {required_job_title}")

        # ── Location filter ──
        required_location = criteria.get("required_location")
        if required_location and isinstance(required_location, list) and len(required_location) > 0:
            candidate_loc = str(record.get("location", ""))
            if not _contains_any(candidate_loc, required_location):
                passed = False
                reasons.append(f"location mismatch: {required_location}")

        if passed:
            record["_shortlist_status"] = "shortlisted"
            shortlisted.append(record)
            logger.debug("  ✓ %s — PASS", record.get("full_name", "Unknown"))
        else:
            record["_shortlist_status"] = f"rejected: {'; '.join(reasons)}"
            rejected.append(record)
            logger.debug("  ✗ %s — FAIL: %s", record.get("full_name", "Unknown"), "; ".join(reasons))

    # Save shortlisted to Excel
    out = output_path or SHORTLIST_EXCEL
    if shortlisted:
        write_to_excel(shortlisted, output_path=out)
        logger.info("Shortlisted %d / %d candidates → %s", len(shortlisted), len(records), out)
    else:
        logger.warning("No candidates matched the criteria.")

    return {
        "total": len(records),
        "shortlisted": len(shortlisted),
        "rejected": len(rejected),
        "criteria_used": criteria,
        "candidates": shortlisted,
        "output_file": str(out) if shortlisted else None,
    }
