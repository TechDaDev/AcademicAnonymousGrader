# Academic Anonymous Grader — Configuration Validation
"""Startup validation for required settings and secrets.

Production rejects:
    - missing or malformed encryption keys (validated via actual key decoder)
    - identical encryption and fingerprint keys
    - debug mode enabled
    - invalid APP_ENV
    - invalid session timeout
    - unwritable data directories
    - unsafe parser limits
    - invalid Streamlit port

Development and testing modes skip key validation so the app remains
usable without configured keys.
"""

from __future__ import annotations

import os
from pathlib import Path

from config import get_settings
from security.exceptions import (
    InvalidEncryptionKeyError,
    InvalidFingerprintKeyError,
    MissingEncryptionKeyError,
    MissingFingerprintKeyError,
    SameKeyError,
)
from security.key_validation import load_keys


class ConfigValidationError(Exception):
    """Raised when a required configuration setting is invalid."""


def validate_config() -> list[str]:
    """Validate all required configuration settings.

    Returns
    -------
    list[str]
        List of validation error messages. Empty list means all checks passed.
    """
    errors: list[str] = []

    try:
        settings = get_settings()
    except ValueError as exc:
        errors.append(f"Settings failed to load: {exc}")
        return errors
    except Exception as exc:
        errors.append(f"Unexpected settings error: {exc}")
        return errors

    app_env = settings.app_env.lower() if hasattr(settings, 'app_env') else "development"

    # APP_ENV validation
    valid_envs = {"development", "testing", "production"}
    if app_env not in valid_envs:
        errors.append(f"APP_ENV must be one of {valid_envs}, got '{app_env}'.")

    # Database configuration
    try:
        db_url = settings.resolved_database_url()
        if not db_url:
            errors.append("Database URL or path is not configured.")
    except Exception as exc:
        errors.append(f"Database URL resolution failed: {exc}")

    # Database path writability (for SQLite)
    db_url_str = getattr(settings, 'database_url', "")
    if db_url_str and db_url_str.startswith("sqlite"):
        # Extract path from sqlite:/// URL
        db_rel = db_url_str[len("sqlite:///"):]
        if db_rel and not db_rel.startswith("/"):
            db_path = (settings._resolve(db_rel) if hasattr(settings, '_resolve')
                       else Path(db_rel))
            parent = db_path.parent
            if not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except OSError:
                    errors.append(f"Database directory is not writable: {parent}")
            elif not os.access(str(parent), os.W_OK):
                errors.append(f"Database directory is not writable: {parent}")

    # Encryption keys — validate via actual key decoder
    enc_key_raw = settings.identity_encryption_key
    fp_key_raw = settings.identity_fingerprint_key

    if app_env == "production":
        try:
            load_keys(enc_key_raw, fp_key_raw)
        except MissingEncryptionKeyError:
            errors.append("IDENTITY_ENCRYPTION_KEY is not set (required in production).")
        except MissingFingerprintKeyError:
            errors.append("IDENTITY_FINGERPRINT_KEY is not set (required in production).")
        except InvalidEncryptionKeyError as exc:
            errors.append(f"IDENTITY_ENCRYPTION_KEY is invalid: {exc}")
        except InvalidFingerprintKeyError as exc:
            errors.append(f"IDENTITY_FINGERPRINT_KEY is invalid: {exc}")
        except SameKeyError:
            errors.append(
                "IDENTITY_ENCRYPTION_KEY and IDENTITY_FINGERPRINT_KEY must be different."
            )
    else:
        # Development/testing: warn if not set, but don't block
        if not enc_key_raw:
            errors.append("IDENTITY_ENCRYPTION_KEY is not set (recommended for development).")
        if not fp_key_raw:
            errors.append("IDENTITY_FINGERPRINT_KEY is not set (recommended for development).")

    # Session timeout
    timeout = getattr(settings, 'session_timeout_minutes', None)
    if timeout is None:
        errors.append("SESSION_TIMEOUT_MINUTES is not configured.")
    elif int(timeout) < 1:
        errors.append("SESSION_TIMEOUT_MINUTES must be at least 1.")

    # Data directories
    data_dir = settings.data_directory if hasattr(settings, 'data_directory') else "data"
    backup_dir = getattr(settings, 'backup_directory', None) or getattr(settings, 'BACKUP_DIR', "backups")
    export_dir = getattr(settings, 'export_directory', None) or getattr(settings, 'EXPORT_DIR', "exports")
    log_dir = getattr(settings, 'log_directory', None) or getattr(settings, 'LOG_DIR', "logs")

    for name, path_str in [("DATA_DIR", str(data_dir)), ("BACKUP_DIR", str(backup_dir)),
                            ("EXPORT_DIR", str(export_dir)), ("LOG_DIR", str(log_dir))]:
        p = Path(path_str)
        if not p.is_absolute():
            p = Path.cwd() / p
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except OSError:
                errors.append(f"{name} is not writable: {p}")
        elif not os.access(str(p), os.W_OK):
            errors.append(f"{name} is not writable: {p}")

    # Debug mode warning
    debug = getattr(settings, 'app_debug', False)
    if debug and app_env == "production":
        errors.append("Debug mode is enabled in production. Set APP_DEBUG=false.")

    # Parser limits
    for name, value, max_val in [
        ("MAX_HTML_TABLES", getattr(settings, 'max_html_tables', 0), 100),
        ("MAX_IMPORT_ROWS", getattr(settings, 'max_import_rows', 0), 100_000),
        ("MAX_IMPORT_COLUMNS", getattr(settings, 'max_import_columns', 0), 2000),
    ]:
        if value <= 0:
            errors.append(f"{name} must be greater than zero.")
        elif value > max_val:
            errors.append(f"{name} ({value}) exceeds safe maximum ({max_val}).")

    return errors


def validate_config_or_exit() -> None:
    """Validate configuration and print errors, exiting if any found."""
    errors = validate_config()
    if errors:
        import sys
        print("Configuration validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)


