# Academic Anonymous Grader — Logging Service
"""Privacy-safe logging configuration with rotating file handler and redaction."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Privacy redaction patterns — defence-in-depth.
# Application code must still avoid passing sensitive data to logging.
# ---------------------------------------------------------------------------
REDACTION_PATTERNS: Final[list[tuple[str, str]]] = [
    # Email addresses
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]"),
    # Secret-like assignments: export KEY=value or KEY = value
    (r"(?i)((?:api[_-]?key|secret|token|password|passphrase|encryption[_-]?key"
     r"|fingerprint[_-]?key)\s*[=:]\s*['\"]?)[^\s'\"]+",
     r"\1[REDACTED]"),
    # Authorization header values
    (r"(?i)(Authorization:\s*\w+\s+)[^\s]+", r"\1[REDACTED]"),
    # Bearer tokens
    (r"(?i)(bearer\s+)[a-zA-Z0-9._-]+", r"\1[REDACTED]"),
    # API keys (alphanumeric strings of 32+ chars that look like keys)
    (r"(?<![a-zA-Z])([a-zA-Z0-9]{32,})(?![a-zA-Z])", "[KEY_REDACTED]"),
]


class PrivacyRedactionFilter(logging.Filter):
    """Logging filter that redacts sensitive patterns from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive patterns and return True (never drops messages)."""
        if hasattr(record, "msg") and isinstance(record.msg, str):
            for pattern, replacement in REDACTION_PATTERNS:
                record.msg = re.sub(pattern, replacement, record.msg)
        if hasattr(record, "args") and record.args:
            cleaned_args: list[object] = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in REDACTION_PATTERNS:
                        arg = re.sub(pattern, replacement, arg)
                cleaned_args.append(arg)
            record.args = tuple(cleaned_args)
        return True


def configure_logging(log_file: Path, log_level: str = "INFO") -> logging.Logger:
    """Configure application-wide logging with console and rotating file handlers.

    Parameters
    ----------
    log_file : Path
        Path to the log file. Parent directory must exist.
    log_level : str
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns
    -------
    logging.Logger
        The root application logger.
    """
    logger = logging.getLogger("academic_grader")
    logger.setLevel(log_level.upper())

    # Avoid duplicate handlers during Streamlit reruns
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(PrivacyRedactionFilter())
    logger.addHandler(console_handler)

    # Rotating file handler (10 MB per file, keep 5 backups)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_file), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(PrivacyRedactionFilter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger for the specified name.

    Parameters
    ----------
    name : str | None
        Logger name. If None, returns the root application logger.

    Returns
    -------
    logging.Logger
        Logger instance.
    """
    if name:
        return logging.getLogger(f"academic_grader.{name}")
    return logging.getLogger("academic_grader")
