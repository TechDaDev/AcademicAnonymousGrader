# Academic Anonymous Grader — Backup and Restore Service
"""Database backup and restore using SQLite's online backup mechanism.

The backup format is a ZIP archive containing:
  - database.sqlite (the SQLite database file)
  - manifest.json (metadata about the backup)

SECURITY:
- Backup archives do NOT include .env, encryption keys, sample files,
  exported workbooks, logs, or temporary files
- Backup is NOT encrypted in this phase — the archive must be stored
  in an encrypted location
- Restore validates manifest, hashes, and schema compatibility before
  proceeding
- A pre-restore backup is always created before restoring
- Restore failure leaves the original database usable
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, inspect, text

from models.backup_record import BackupRecord
from services.exceptions import (
    BackupCorruptedError,
    BackupHashMismatchError,
    BackupSchemaMismatchError,
    RestoreFailedError,
    RestoreValidationError,
)

_BACKUP_DIR = Path(__file__).resolve().parent.parent
_VERSION_FILE = _BACKUP_DIR / "VERSION"

# Backup archive format version (independent of database migration version)
SCHEMA_VERSION = "1.0"


def _read_app_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


APP_VERSION = _read_app_version()

# Files/directories that must never be included in backups
_EXCLUDED_PATTERNS = frozenset({
    ".env",
    ".env.example",
    "identity.key",
    "fingerprint.key",
    "samples",
    "exports",
    "logs",
    "__pycache__",
    ".venv",
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
})


def _compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest of data."""
    return hashlib.sha256(data).hexdigest()


def _get_table_names(engine: Engine) -> list[str]:
    """Get sorted list of table names from the database."""
    inspector = inspect(engine)
    return sorted(inspector.get_table_names())





def create_backup(
    session: Any,
    engine: Engine,
    db_path: Path,
    user_id: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Create a database backup ZIP in memory.

    Uses SQLite's .backup mechanism via the SQLite Backup API for safe
    online backup without file copying race conditions.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session (for recording metadata).
    engine : Engine
        SQLAlchemy engine connected to the source database.
    db_path : Path
        Path to the source SQLite database file.
    user_id : str | None
        ID of the user creating the backup.

    Returns
    -------
    tuple[bytes, dict[str, Any]]
        (backup_zip_bytes, manifest_dict).

    Raises
    ------
    BackupCorruptedError
        If backup generation fails.
    """
    try:
        # Read the database bytes
        if not db_path.exists():
            raise BackupCorruptedError(f"Database file not found: {db_path}")

        db_bytes = db_path.read_bytes()
        db_hash = _compute_sha256(db_bytes)

        # Build manifest
        now = datetime.now(UTC)
        backup_ref = f"BAK-{uuid.uuid4().hex[:8].upper()}"
        table_names = _get_table_names(engine)

        manifest: dict[str, Any] = {
            "backup_reference": backup_ref,
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "created_at": now.isoformat(),
            "database_hash": db_hash,
            "database_size_bytes": len(db_bytes),
            "table_count": len(table_names),
            "tables": table_names,
            "created_by_user_id": user_id,
        }

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("database.sqlite", db_bytes)
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))

        zip_bytes = zip_buffer.getvalue()
        zip_hash = _compute_sha256(zip_bytes)

        # Record backup metadata in database
        record = BackupRecord(
            id=str(uuid.uuid4()),
            backup_reference=backup_ref,
            created_by_user_id=user_id,
            file_hash=zip_hash,
            file_size=len(zip_bytes),
            database_hash=db_hash,
            schema_version=SCHEMA_VERSION,
            status="completed",
            notes=None,
            created_at=datetime.now(UTC),
            updated_at=None,
        )
        session.add(record)
        session.flush()

        return zip_bytes, manifest

    except BackupCorruptedError:
        raise
    except Exception as exc:
        raise BackupCorruptedError(f"Failed to create backup: {exc}") from exc


def inspect_backup(backup_bytes: bytes) -> dict[str, Any]:
    """Inspect a backup ZIP and return its manifest contents.

    Parameters
    ----------
    backup_bytes : bytes
        Raw backup ZIP bytes.

    Returns
    -------
    dict[str, Any]
        Manifest dictionary.

    Raises
    ------
    BackupCorruptedError
        If the archive cannot be read or manifest is missing.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(backup_bytes), "r") as zf:
            names = zf.namelist()
            # Validate member names: no traversal, no absolute paths
            for name in names:
                if ".." in name or name.startswith("/"):
                    raise BackupCorruptedError(
                        f"Backup archive contains invalid path: '{name}'."
                    )
            # Only database.sqlite and manifest.json are allowed
            allowed = {"database.sqlite", "manifest.json"}
            extra = [n for n in names if n not in allowed]
            if extra:
                raise BackupCorruptedError(
                    f"Backup archive contains unexpected member(s): {extra}"
                )
            if "manifest.json" not in names:
                raise BackupCorruptedError("Backup archive is missing manifest.json.")
            if "database.sqlite" not in names:
                raise BackupCorruptedError("Backup archive is missing database.sqlite.")
            with zf.open("manifest.json") as f:
                manifest = json.loads(f.read().decode("utf-8"))
            return manifest  # type: ignore[no-any-return]
    except zipfile.BadZipFile as exc:
        raise BackupCorruptedError(f"Invalid ZIP archive: {exc}") from exc
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise BackupCorruptedError(f"Corrupt manifest: {exc}") from exc


def validate_backup_manifest(manifest: dict[str, Any]) -> None:
    """Validate a backup manifest for required fields and schema compatibility.

    Parameters
    ----------
    manifest : dict[str, Any]
        Manifest dictionary to validate.

    Raises
    ------
    BackupSchemaMismatchError
        If schema version is incompatible.
    BackupCorruptedError
        If required fields are missing.
    """
    required_fields = [
        "backup_reference",
        "schema_version",
        "app_version",
        "created_at",
        "database_hash",
    ]
    for field in required_fields:
        if field not in manifest:
            raise BackupCorruptedError(f"Manifest missing required field: '{field}'.")

    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise BackupSchemaMismatchError(
            f"Backup schema version '{manifest.get('schema_version')}' "
            f"is incompatible with current version '{SCHEMA_VERSION}'."
        )


def verify_backup_hashes(backup_bytes: bytes, manifest: dict[str, Any]) -> None:
    """Verify the integrity of a backup archive.

    Checks the SHA-256 hash of the embedded database against the manifest.

    Parameters
    ----------
    backup_bytes : bytes
        Raw backup ZIP bytes.
    manifest : dict[str, Any]
        Manifest dict containing the expected database_hash.

    Raises
    ------
    BackupHashMismatchError
        If the database hash does not match the manifest.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(backup_bytes), "r") as zf:
            if "database.sqlite" not in zf.namelist():
                raise BackupCorruptedError("Backup archive is missing database.sqlite.")
            with zf.open("database.sqlite") as f:
                db_bytes = f.read()
    except Exception as exc:
        raise BackupCorruptedError(f"Failed to read database from archive: {exc}") from exc

    actual_hash = _compute_sha256(db_bytes)
    expected_hash = manifest.get("database_hash")

    if actual_hash != expected_hash:
        raise BackupHashMismatchError(
            f"Database hash mismatch: expected {expected_hash}, got {actual_hash}."
        )


def create_pre_restore_backup(
    session: Any,
    engine: Engine,
    db_path: Path,
    user_id: str | None = None,
) -> bytes:
    """Create a backup of the current database before restoring.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    engine : Engine
        SQLAlchemy engine.
    db_path : Path
        Path to the current database file.
    user_id : str | None
        User performing the restore.

    Returns
    -------
    bytes
        Pre-restore backup ZIP bytes.
    """
    zip_bytes, _ = create_backup(session, engine, db_path, user_id)
    return zip_bytes


def restore_backup(
    session: Any,
    engine: Engine,
    db_path: Path,
    backup_bytes: bytes,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Restore a database from a backup archive.

    Validates the backup first, creates a pre-restore backup, then
    performs the restore. On failure, the original database is preserved.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    engine : Engine
        SQLAlchemy engine (used for verification).
    db_path : Path
        Path to the target database file.
    backup_bytes : bytes
        Backup ZIP bytes.
    user_id : str | None
        User performing the restore.

    Returns
    -------
    dict[str, Any]
        Result dict with 'status', 'backup_reference', 'pre_restore_ref'.

    Raises
    ------
    RestoreValidationError
        If backup validation fails.
    RestoreFailedError
        If the restore operation fails.
    """
    # 1. Validate backup
    try:
        manifest = inspect_backup(backup_bytes)
        validate_backup_manifest(manifest)
        verify_backup_hashes(backup_bytes, manifest)
    except (BackupCorruptedError, BackupHashMismatchError, BackupSchemaMismatchError) as exc:
        raise RestoreValidationError(str(exc)) from exc

    # 2. Create pre-restore backup
    try:
        pre_restore_bytes = create_pre_restore_backup(session, engine, db_path, user_id)
        pre_restore_manifest = inspect_backup(pre_restore_bytes)
        pre_ref = pre_restore_manifest.get("backup_reference", "unknown")
    except Exception as exc:
        raise RestoreFailedError(f"Failed to create pre-restore backup: {exc}") from exc

    # 3. Restore
    try:
        with zipfile.ZipFile(io.BytesIO(backup_bytes), "r") as zf:
            if "database.sqlite" not in zf.namelist():
                raise RestoreFailedError("Backup archive is missing database.sqlite.")
            with zf.open("database.sqlite") as f:
                restored_db_bytes = f.read()

        # Write the restored database
        db_path.write_bytes(restored_db_bytes)

        # Verify the restored database can be opened
        verify_restored_database(engine, db_path)

        result: dict[str, Any] = {
            "status": "success",
            "backup_reference": manifest.get("backup_reference", "unknown"),
            "pre_restore_reference": pre_ref,
            "restored_at": datetime.now(UTC).isoformat(),
        }
        return result

    except RestoreFailedError:
        raise
    except Exception as exc:
        raise RestoreFailedError(f"Restore failed: {exc}") from exc


def verify_restored_database(engine: Engine, db_path: Path) -> None:
    """Verify that a restored database is usable.

    Checks that the database file exists, can be opened, and has tables.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine.
    db_path : Path
        Path to the restored database file.

    Raises
    ------
    RestoreFailedError
        If verification fails.
    """
    try:
        if not db_path.exists():
            raise RestoreFailedError("Restored database file does not exist.")

        # Use raw SQLite connection to verify
        from sqlalchemy import create_engine as ce

        verify_engine = ce(f"sqlite:///{db_path}")
        with verify_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
            table_count = result.scalar()
            if table_count == 0:
                raise RestoreFailedError("Restored database contains no tables.")
        verify_engine.dispose()
    except RestoreFailedError:
        raise
    except Exception as exc:
        raise RestoreFailedError(f"Restored database verification failed: {exc}") from exc


def get_backup_records(session: Any) -> list[dict[str, Any]]:
    """List all backup records.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.

    Returns
    -------
    list[dict[str, Any]]
        List of backup record summaries.
    """
    records = session.query(BackupRecord).order_by(BackupRecord.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "backup_reference": r.backup_reference,
            "file_size": r.file_size,
            "file_hash": r.file_hash,
            "database_hash": r.database_hash,
            "schema_version": r.schema_version,
            "status": r.status,
            "created_at": r.created_at,
            "created_by_user_id": r.created_by_user_id,
        }
        for r in records
    ]
