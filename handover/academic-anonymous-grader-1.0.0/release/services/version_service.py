# Academic Anonymous Grader — Version Information
"""Application version and release metadata."""

from __future__ import annotations

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"

# Default fallback version if VERSION file is missing
_FALLBACK_VERSION = "1.0.0-rc1"


def _read_version() -> str:
    """Read version from the VERSION file."""
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return _FALLBACK_VERSION


#: Semantic version string, read once at import time
VERSION: str = _read_version()

#: Application name
APP_NAME: str = "Academic Anonymous Grader"

#: Application identifier
APP_ID: str = "academic-anonymous-grader"


def get_version() -> str:
    """Return the current application version."""
    return VERSION


def get_app_name() -> str:
    """Return the application display name."""
    return APP_NAME


def get_display_string() -> str:
    """Return a human-readable version string for UI display."""
    return f"{APP_NAME} v{VERSION}"
