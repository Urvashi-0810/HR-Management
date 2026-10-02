"""
pipeline.py — Main orchestrator for the HR CV processing pipeline.

Supports running individual steps or the full pipeline:
  Step 1: Download CV attachments from email
  Step 2: Extract data from CVs via LLM → Excel
  Step 3: Shortlist candidates by criteria
  Step 4: Score shortlisted candidates against a job description

Usage:
  python -m src.pipeline download               # Step 1: Download from email
  python -m src.pipeline extract                 # Step 2: Extract CV data
  python -m src.pipeline shortlist               # Step 3: Shortlist candidates
  python -m src.pipeline match                   # Step 4: Job fit scoring
  python -m src.pipeline full                    # Run steps 1→2→3→4
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from tqdm import tqdm

from src.config import (
    CV_FOLDER,
    OUTPUT_EXCEL,
    SHORTLIST_EXCEL,
    JOB_MATCH_EXCEL,
    LLM_PROVIDER,
    LOG_LEVEL,
    SUPPORTED_EXTENSIONS,
)


def _setup_logging(level: str = LOG_LEVEL) -> None:
    """Configure logging for the pipeline."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S",
    )


# ══════════════════════════════════════════════
# Step 1: Download attachments from email
# ══════════════════════════════════════════════

def run_download() -> dict[str, Any]:
    """Download CV attachments from email."""
    from src.email_downloader import download_attachments

    logger = logging.getLogger("pipeline.download")
    logger.info("=" * 60)
    logger.info("Step 1: Downloading CV attachments from email")
    logger.info("=" * 60)

    result = download_attachments()
    return result


# ══════════════════════════════════════════════
# Step 2: Extract data from CVs
# ══════════════════════════════════════════════

def scan_cv_folder(folder: Path) -> list[Path]:
    """Find all supported CV files in the given folder."""
    if not folder.exists():
        raise FileNotFoundError(f"CV folder does not exist: {folder}")

    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def run_extract(
    cv_folder: Path | None = None,
    output_path: Path | None = None,
    provider: str | None = None,
    append: bool = False,
) -> Path:
    """Extract structured data from CVs in the folder using LLM."""
    from src.file_reader import read_file
    from src.llm_extractor import extract_cv_data
    from src.excel_writer import write_to_excel

    logger = logging.getLogger("pipeline.extract")

    folder = cv_folder or CV_FOLDER
    output = output_path or OUTPUT_EXCEL
    active_provider = provider or LLM_PROVIDER

    logger.info("=" * 60)
    logger.info("Step 2: CV Data Extraction")
    logger.info("=" * 60)
    logger.info("CV Folder  : %s", folder)
    logger.info("Output     : %s", output)
    logger.info("LLM        : %s", active_provider)
    logger.info("-" * 60)

    files = scan_cv_folder(folder)
    if not files:
        logger.warning("No supported CV files found in '%s'", folder)
        logger.info("Supported formats: %s", ", ".join(sorted(SUPPORTED_EXTENSIONS)))
        return output

    logger.info("Found %d CV file(s) to process.", len(files))

    records: list[dict[str, Any]] = []
    success_count = 0
    error_count = 0
    start_time = time.time()

    for file_path in tqdm(files, desc="Processing CVs", unit="file"):
        logger.info("Processing: %s", file_path.name)
        result: dict[str, Any] = {"_filename": file_path.name}

        # Step 2a: Extract text
        try:
            raw_text = read_file(file_path)
            if not raw_text.strip():
                logger.warning("  ⚠ No text extracted from '%s'", file_path.name)
                result["_status"] = "no_text"
                records.append(result)
                error_count += 1
                continue
            logger.info("  📄 Extracted %d chars of text", len(raw_text))
        except Exception as e:
            logger.error("  ✗ Failed to read '%s': %s", file_path.name, e)
            result["_status"] = f"read_error: {e}"
            records.append(result)
            error_count += 1
            continue

        # Step 2b: LLM extraction
        try:
            extracted = extract_cv_data(raw_text, provider=active_provider)
            result.update(extracted)
            result["_status"] = "success"
            logger.info("  ✓ Extracted → %s", extracted.get("full_name", "N/A"))
            success_count += 1
        except Exception as e:
            logger.error("  ✗ LLM extraction failed: %s", e)
            result["_status"] = f"llm_error: {e}"
            error_count += 1

        records.append(result)

    elapsed = time.time() - start_time

    # Write to Excel
    logger.info("-" * 60)
    output_file = write_to_excel(records, output_path=output, append=append)

    logger.info("=" * 60)
    logger.info("Extraction Complete!")
    logger.info("  Total files : %d", len(files))
    logger.info("  Successful  : %d", success_count)
    logger.info("  Errors      : %d", error_count)
    logger.info("  Time        : %.1f seconds", elapsed)
    logger.info("  Output      : %s", output_file)
    logger.info("=" * 60)

    return output_file


# ══════════════════════════════════════════════
# Step 3: Shortlist candidates
# ══════════════════════════════════════════════

def run_shortlist(
    criteria: dict[str, Any] | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Shortlist candidates based on criteria."""
    from src.shortlister import shortlist_candidates

    logger = logging.getLogger("pipeline.shortlist")

    logger.info("=" * 60)
    logger.info("Step 3: Shortlisting Candidates")
    logger.info("=" * 60)

    if criteria is None:
        # Default criteria — can be overridden via API or CLI
        criteria = _prompt_shortlist_criteria()

    result = shortlist_candidates(
        criteria=criteria,
        input_path=input_path or OUTPUT_EXCEL,
        output_path=output_path or SHORTLIST_EXCEL,
    )

    return result


def _prompt_shortlist_criteria() -> dict[str, Any]:
    """Interactively prompt the user for shortlist criteria (CLI mode)."""
    print("\n📋 Enter shortlisting criteria (press Enter to skip):\n")

    criteria = {}

    val = input("  Min experience (years): ").strip()
    if val:
        criteria["min_experience"] = float(val)

    val = input("  Max experience (years): ").strip()
    if val:
        criteria["max_experience"] = float(val)

    val = input("  Min age: ").strip()
    if val:
        criteria["min_age"] = int(val)

    val = input("  Max age: ").strip()
    if val:
        criteria["max_age"] = int(val)

    val = input("  Required skills (comma-separated): ").strip()
    if val:
        criteria["required_skills"] = [s.strip() for s in val.split(",") if s.strip()]

    val = input("  Required education keywords (comma-separated): ").strip()
    if val:
        criteria["required_education"] = [s.strip() for s in val.split(",") if s.strip()]

    val = input("  Required job title keywords (comma-separated): ").strip()
    if val:
        criteria["required_job_title"] = [s.strip() for s in val.split(",") if s.strip()]

    val = input("  Required location keywords (comma-separated): ").strip()
    if val:
        criteria["required_location"] = [s.strip() for s in val.split(",") if s.strip()]

    print()
    return criteria


# ══════════════════════════════════════════════
# Step 4: Job fit matching
# ══════════════════════════════════════════════

def run_match(
    job_description: str | None = None,
    candidates: list[dict[str, Any]] | None = None,
    provider: str | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run LLM-based job fit scoring."""
    from src.job_matcher import match_candidates_to_job
    from src.excel_writer import read_from_excel

    logger = logging.getLogger("pipeline.match")

    logger.info("=" * 60)
    logger.info("Step 4: Job Fit Matching")
    logger.info("=" * 60)

    # Get job description
    if not job_description:
        job_description = _prompt_job_description()

    # Get candidates
    if candidates is None:
        source = input_path or SHORTLIST_EXCEL
        if not source.exists():
            # Fall back to main extraction output
            source = OUTPUT_EXCEL
        candidates = read_from_excel(source)

    if not candidates:
        logger.warning("No candidates to match.")
        return {"total": 0, "results": []}

    result = match_candidates_to_job(
        job_description=job_description,
        candidates=candidates,
        provider=provider,
        output_path=output_path or JOB_MATCH_EXCEL,
    )

    return result


def _prompt_job_description() -> str:
    """Interactively prompt for a job description (CLI mode)."""
    print("\n📝 Enter the Job Description (type 'END' on a new line when done):\n")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


# ══════════════════════════════════════════════
# CLI Entry Point
# ══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="HR Management System — CV Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  download     Download CV attachments from email
  extract      Extract data from CVs using LLM -> Excel
  shortlist    Shortlist candidates by criteria
  match        Score shortlisted candidates against a job description
  full         Run the complete pipeline (download -> extract -> shortlist -> match)

Examples:
  python -m src.pipeline extract
  python -m src.pipeline extract --provider claude
  python -m src.pipeline shortlist --criteria '{"min_experience": 3, "required_skills": ["Python"]}'
  python -m src.pipeline match --jd-file job_description.txt
  python -m src.pipeline full
        """,

    )
    parser.add_argument(
        "step",
        choices=["download", "extract", "shortlist", "match", "full"],
        help="Which pipeline step to run",
    )
    parser.add_argument("--folder", "-f", type=Path, default=None, help="CV folder path")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output Excel path")
    parser.add_argument("--provider", "-p", choices=["claude", "gemini"], default=None, help="LLM provider")
    parser.add_argument("--append", "-a", action="store_true", help="Append to existing Excel")
    parser.add_argument("--criteria", type=str, default=None, help="Shortlist criteria as JSON string")
    parser.add_argument("--jd-file", type=Path, default=None, help="Path to job description text file")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None)

    args = parser.parse_args()
    _setup_logging(args.log_level or LOG_LEVEL)

    step = args.step

    if step == "download":
        run_download()

    elif step == "extract":
        run_extract(
            cv_folder=args.folder,
            output_path=args.output,
            provider=args.provider,
            append=args.append,
        )

    elif step == "shortlist":
        criteria = None
        if args.criteria:
            criteria = json.loads(args.criteria)
        run_shortlist(criteria=criteria, output_path=args.output)

    elif step == "match":
        jd = None
        if args.jd_file and args.jd_file.exists():
            jd = args.jd_file.read_text(encoding="utf-8")
        run_match(job_description=jd, provider=args.provider, output_path=args.output)

    elif step == "full":
        logging.getLogger("pipeline").info("Running full pipeline...")

        # Step 1
        try:
            run_download()
        except Exception as e:
            logging.getLogger("pipeline").error("Download step failed: %s", e)
            logging.getLogger("pipeline").info("Continuing with existing CVs in folder...")

        # Step 2
        run_extract(
            cv_folder=args.folder,
            output_path=args.output,
            provider=args.provider,
        )

        # Step 3
        criteria = None
        if args.criteria:
            criteria = json.loads(args.criteria)
        shortlist_result = run_shortlist(criteria=criteria)

        # Step 4
        jd = None
        if args.jd_file and args.jd_file.exists():
            jd = args.jd_file.read_text(encoding="utf-8")
        if shortlist_result.get("shortlisted", 0) > 0:
            run_match(
                job_description=jd,
                candidates=shortlist_result.get("candidates"),
                provider=args.provider,
            )
        else:
            logging.getLogger("pipeline").warning("No candidates shortlisted. Skipping job matching.")


if __name__ == "__main__":
    main()
