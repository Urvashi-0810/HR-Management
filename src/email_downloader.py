"""
email_downloader.py — Download CV attachments from email via IMAP.

Features:
  - Connects to any IMAP server (Gmail, Outlook, Yahoo, etc.)
  - Downloads PDF, DOCX, and image attachments
  - Tracks progress via a JSON file so it never re-processes emails
  - Supports filtering by subject keyword and sender
  - Handles duplicate filenames with suffixes
"""

import email
import imaplib
import json
import logging
import os
import re
from datetime import datetime, timezone
from email.header import decode_header
from pathlib import Path
from typing import Any

from src.config import (
    EMAIL_IMAP_SERVER,
    EMAIL_IMAP_PORT,
    EMAIL_ADDRESS,
    EMAIL_PASSWORD,
    EMAIL_FOLDER,
    EMAIL_SUBJECT_FILTER,
    EMAIL_SENDER_FILTER,
    CV_FOLDER,
    EMAIL_TRACKER_FILE,
    SUPPORTED_EXTENSIONS,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Tracker — remember which emails we've processed
# ──────────────────────────────────────────────

def _load_tracker() -> dict[str, Any]:
    """Load the email tracker state from disk."""
    if EMAIL_TRACKER_FILE.exists():
        with open(EMAIL_TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "processed_uids": [],
        "last_run": None,
        "total_downloaded": 0,
        "download_history": [],
    }


def _save_tracker(tracker: dict[str, Any]) -> None:
    """Persist the email tracker state to disk."""
    EMAIL_TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EMAIL_TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tracker, f, indent=2, default=str)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _decode_header_value(value: str | None) -> str:
    """Decode an email header value that might be encoded."""
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result_parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result_parts.append(part)
    return " ".join(result_parts)


def _sanitize_filename(filename: str) -> str:
    """Remove or replace characters that are unsafe for filenames."""
    # Remove path separators and other problematic chars
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized).strip('_. ')
    return sanitized or "unnamed_attachment"


def _get_unique_filepath(folder: Path, filename: str) -> Path:
    """Generate a unique file path, adding a numeric suffix if file exists."""
    filepath = folder / filename
    if not filepath.exists():
        return filepath

    stem = filepath.stem
    suffix = filepath.suffix
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{suffix}"
        new_path = folder / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def _is_cv_attachment(filename: str) -> bool:
    """Check if a filename has a supported CV extension."""
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS


def _matches_sender_filter(from_addr: str) -> bool:
    """Check if the sender matches the configured filter."""
    if not EMAIL_SENDER_FILTER:
        return True  # No filter = accept all
    allowed = [s.strip().lower() for s in EMAIL_SENDER_FILTER.split(",") if s.strip()]
    from_lower = from_addr.lower()
    return any(sender in from_lower for sender in allowed)


def _matches_subject_filter(subject: str) -> bool:
    """Check if the subject matches the configured filter."""
    if not EMAIL_SUBJECT_FILTER:
        return True  # No filter = accept all
    return EMAIL_SUBJECT_FILTER.lower() in subject.lower()


# ──────────────────────────────────────────────
# Core download logic
# ──────────────────────────────────────────────

def download_attachments(
    imap_server: str | None = None,
    imap_port: int | None = None,
    email_address: str | None = None,
    email_password: str | None = None,
    email_folder: str | None = None,
    output_folder: Path | None = None,
) -> dict[str, Any]:
    """
    Connect to IMAP, scan for emails with CV attachments, download them.

    Only processes emails not already tracked. Updates the tracker after each email.

    Args:
        imap_server: IMAP server address (default from .env)
        imap_port: IMAP port (default from .env)
        email_address: Email login (default from .env)
        email_password: Email password (default from .env)
        email_folder: Mailbox folder to scan (default from .env)
        output_folder: Where to save attachments (default from .env)

    Returns:
        Summary dict with counts and details of downloads.
    """
    server = imap_server or EMAIL_IMAP_SERVER
    port = imap_port or EMAIL_IMAP_PORT
    addr = email_address or EMAIL_ADDRESS
    pwd = email_password or EMAIL_PASSWORD
    folder = email_folder or EMAIL_FOLDER
    out_folder = output_folder or CV_FOLDER

    # Validate
    if not addr or addr == "your_email@gmail.com":
        raise ValueError("EMAIL_ADDRESS is not set. Add it to your .env file.")
    if not pwd or pwd == "your_app_password_here":
        raise ValueError("EMAIL_PASSWORD is not set. Add it to your .env file.")

    # Ensure output folder exists
    out_folder.mkdir(parents=True, exist_ok=True)

    # Load tracker
    tracker = _load_tracker()
    processed_uids = set(tracker.get("processed_uids", []))

    logger.info("Connecting to %s:%d as %s...", server, port, addr)

    result_summary = {
        "new_emails_scanned": 0,
        "attachments_downloaded": 0,
        "skipped_already_processed": 0,
        "skipped_no_match": 0,
        "errors": 0,
        "files": [],
    }

    mail = None
    try:
        # Connect
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(addr, pwd)
        logger.info("✓ Logged in successfully.")

        # Select mailbox
        status, data = mail.select(folder, readonly=True)
        if status != "OK":
            raise ConnectionError(f"Failed to select folder '{folder}': {data}")

        total_messages = int(data[0])
        logger.info("Mailbox '%s' has %d total messages.", folder, total_messages)

        # Search for all emails (we filter by tracker)
        status, data = mail.search(None, "ALL")
        if status != "OK":
            raise ConnectionError("Failed to search emails.")

        all_uids = data[0].split()
        logger.info("Found %d email UIDs to check.", len(all_uids))

        # Process each email
        for uid_bytes in all_uids:
            uid = uid_bytes.decode("utf-8")

            # Skip already processed
            if uid in processed_uids:
                result_summary["skipped_already_processed"] += 1
                continue

            result_summary["new_emails_scanned"] += 1

            try:
                # Fetch the email
                status, msg_data = mail.fetch(uid_bytes, "(RFC822)")
                if status != "OK":
                    logger.warning("Failed to fetch email UID %s", uid)
                    result_summary["errors"] += 1
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode headers
                subject = _decode_header_value(msg.get("Subject", ""))
                from_addr = _decode_header_value(msg.get("From", ""))
                date_str = msg.get("Date", "")

                # Apply filters
                if not _matches_subject_filter(subject):
                    result_summary["skipped_no_match"] += 1
                    processed_uids.add(uid)
                    continue

                if not _matches_sender_filter(from_addr):
                    result_summary["skipped_no_match"] += 1
                    processed_uids.add(uid)
                    continue

                # Walk through email parts looking for attachments
                found_attachment = False
                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition", ""))
                    if "attachment" not in content_disposition:
                        continue

                    raw_filename = part.get_filename()
                    if not raw_filename:
                        continue

                    filename = _decode_header_value(raw_filename)
                    filename = _sanitize_filename(filename)

                    if not _is_cv_attachment(filename):
                        logger.debug("Skipping non-CV attachment: %s", filename)
                        continue

                    # Download the attachment
                    file_data = part.get_payload(decode=True)
                    if not file_data:
                        logger.warning("Empty attachment data for '%s' in UID %s", filename, uid)
                        continue

                    filepath = _get_unique_filepath(out_folder, filename)
                    with open(filepath, "wb") as f:
                        f.write(file_data)

                    found_attachment = True
                    result_summary["attachments_downloaded"] += 1
                    result_summary["files"].append({
                        "filename": filepath.name,
                        "source_email": from_addr,
                        "subject": subject,
                        "date": date_str,
                        "size_bytes": len(file_data),
                    })

                    logger.info(
                        "  📥 Downloaded: %s (from: %s, subject: %s)",
                        filepath.name, from_addr[:40], subject[:50],
                    )

                # Mark as processed regardless of whether it had attachments
                processed_uids.add(uid)

                # Save tracker after each email (resume-safe)
                tracker["processed_uids"] = list(processed_uids)
                tracker["last_run"] = datetime.now(timezone.utc).isoformat()
                tracker["total_downloaded"] = tracker.get("total_downloaded", 0) + (
                    1 if found_attachment else 0
                )
                _save_tracker(tracker)

            except Exception as e:
                logger.error("Error processing email UID %s: %s", uid, e)
                result_summary["errors"] += 1
                # Still mark as processed to avoid infinite retries
                processed_uids.add(uid)

    except imaplib.IMAP4.error as e:
        logger.error("IMAP error: %s", e)
        raise
    except Exception as e:
        logger.error("Email download failed: %s", e)
        raise
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass

    # Final tracker save
    tracker["processed_uids"] = list(processed_uids)
    tracker["last_run"] = datetime.now(timezone.utc).isoformat()
    if result_summary["files"]:
        tracker.setdefault("download_history", []).append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": result_summary["attachments_downloaded"],
            "files": [f["filename"] for f in result_summary["files"]],
        })
    _save_tracker(tracker)

    # Log summary
    logger.info("=" * 50)
    logger.info("Email Download Summary:")
    logger.info("  New emails scanned    : %d", result_summary["new_emails_scanned"])
    logger.info("  Attachments downloaded : %d", result_summary["attachments_downloaded"])
    logger.info("  Skipped (processed)   : %d", result_summary["skipped_already_processed"])
    logger.info("  Skipped (no match)    : %d", result_summary["skipped_no_match"])
    logger.info("  Errors                : %d", result_summary["errors"])
    logger.info("=" * 50)

    return result_summary


def get_tracker_status() -> dict[str, Any]:
    """Return the current tracker state for status reporting."""
    tracker = _load_tracker()
    return {
        "total_emails_processed": len(tracker.get("processed_uids", [])),
        "total_downloaded": tracker.get("total_downloaded", 0),
        "last_run": tracker.get("last_run"),
        "recent_history": tracker.get("download_history", [])[-5:],  # Last 5 runs
    }


def reset_tracker() -> None:
    """Reset the tracker to re-process all emails. Use with caution."""
    _save_tracker({
        "processed_uids": [],
        "last_run": None,
        "total_downloaded": 0,
        "download_history": [],
    })
    logger.info("Email tracker has been reset.")
