"""
llm_extractor.py — Sends CV text to an LLM (Claude or Gemini) and gets back structured data.

The LLM is prompted to return a JSON object with the predefined extraction fields.
Supports switching between Claude and Gemini via config.
"""

import json
import logging
import re
from typing import Any

from src.config import (
    LLM_PROVIDER,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    EXTRACTION_FIELDS,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert HR data extraction assistant. Your job is to extract structured information from CV/resume text.

You MUST return a valid JSON object with exactly these fields:

{fields_spec}

Rules:
- If a field cannot be determined from the CV, set its value to null.
- "experience_years" should be a numeric value (integer or float). Calculate it from work history if not explicitly stated.
- "age" should be a numeric value (integer) if determinable. Calculate from date_of_birth if available.
- "skills" should be a comma-separated string of skills.
- "education" should include degree, field, and institution — comma-separated if multiple.
- "certifications" should be a comma-separated string.
- "languages" should be a comma-separated string.
- "date_of_birth" should be in YYYY-MM-DD format if available.
- "phone" should include country code if available.
- Return ONLY the JSON object. No markdown, no explanation, no code blocks."""


def _build_fields_spec() -> str:
    """Build a human-readable field specification for the prompt."""
    descriptions = {
        "full_name": "Full name of the candidate",
        "email": "Email address",
        "phone": "Phone number (with country code if available)",
        "location": "City, State/Province, Country",
        "date_of_birth": "Date of birth in YYYY-MM-DD format",
        "age": "Age in years (integer)",
        "summary": "Brief professional summary (2-3 sentences max)",
        "current_job_title": "Most recent or current job title",
        "experience_years": "Total years of professional experience (number)",
        "education": "Degrees, fields of study, institutions (comma-separated)",
        "skills": "Technical and soft skills (comma-separated)",
        "certifications": "Professional certifications (comma-separated)",
        "languages": "Languages spoken (comma-separated)",
    }
    lines = []
    for field in EXTRACTION_FIELDS:
        desc = descriptions.get(field, field)
        lines.append(f'  "{field}": "{desc}"')
    return "{\n" + ",\n".join(lines) + "\n}"


def _build_prompt(cv_text: str) -> str:
    """Build the full user prompt with the CV text."""
    return f"Extract structured data from the following CV/resume text:\n\n---\n{cv_text}\n---"


# ──────────────────────────────────────────────
# Claude (Anthropic) extractor
# ──────────────────────────────────────────────

def _extract_with_claude(cv_text: str) -> dict[str, Any]:
    """Extract CV data using the Anthropic Claude API."""
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed. Run: pip install anthropic")

    if not CLAUDE_API_KEY or CLAUDE_API_KEY == "your_claude_api_key_here":
        raise ValueError("CLAUDE_API_KEY is not set. Add it to your .env file.")

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    system_prompt = SYSTEM_PROMPT.format(fields_spec=_build_fields_spec())
    user_prompt = _build_prompt(cv_text)

    logger.debug("Sending CV text to Claude (%s)...", CLAUDE_MODEL)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ],
    )

    raw_response = response.content[0].text
    logger.debug("Claude raw response: %s", raw_response[:200])

    return _parse_llm_response(raw_response)


# ──────────────────────────────────────────────
# Gemini (Google) extractor
# ──────────────────────────────────────────────

def _extract_with_gemini(cv_text: str) -> dict[str, Any]:
    """Extract CV data using the Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY is not set. Add it to your .env file.")

    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT.format(fields_spec=_build_fields_spec()),
    )

    user_prompt = _build_prompt(cv_text)

    logger.debug("Sending CV text to Gemini (%s)...", GEMINI_MODEL)

    response = model.generate_content(user_prompt)

    raw_response = response.text
    logger.debug("Gemini raw response: %s", raw_response[:200])

    return _parse_llm_response(raw_response)


# ──────────────────────────────────────────────
# Response parsing
# ──────────────────────────────────────────────

def _parse_llm_response(raw: str) -> dict[str, Any]:
    """
    Parse the LLM response into a dict.
    Handles cases where the LLM wraps JSON in markdown code blocks.
    """
    cleaned = raw.strip()

    # Strip markdown code block wrappers if present
    if cleaned.startswith("```"):
        # Remove ```json or ``` at the start and ``` at the end
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s\nRaw response:\n%s", e, raw)
        # Return a dict with all fields set to None + attach the raw response for debugging
        data = {field: None for field in EXTRACTION_FIELDS}
        data["_raw_response"] = raw
        data["_parse_error"] = str(e)

    # Ensure all expected fields exist
    for field in EXTRACTION_FIELDS:
        if field not in data:
            data[field] = None

    return data


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def extract_cv_data(cv_text: str, provider: str | None = None) -> dict[str, Any]:
    """
    Extract structured data from CV text using the configured LLM provider.

    Args:
        cv_text: The raw text extracted from the CV.
        provider: Override the default LLM provider ("claude" or "gemini").

    Returns:
        A dict with the extraction fields populated.
    """
    active_provider = (provider or LLM_PROVIDER).lower()

    if not cv_text or not cv_text.strip():
        logger.warning("Empty CV text provided. Returning empty result.")
        return {field: None for field in EXTRACTION_FIELDS}

    # Truncate very long CVs to avoid token limits (keep first ~12k chars)
    if len(cv_text) > 12000:
        logger.info("CV text is very long (%d chars). Truncating to 12000 chars.", len(cv_text))
        cv_text = cv_text[:12000]

    if active_provider == "claude":
        return _extract_with_claude(cv_text)
    elif active_provider == "gemini":
        return _extract_with_gemini(cv_text)
    else:
        raise ValueError(f"Unknown LLM provider: '{active_provider}'. Use 'claude' or 'gemini'.")
