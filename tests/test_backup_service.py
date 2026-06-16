# Academic Anonymous Grader — Backup Service Tests
"""Tests for backup_service.py — backup creation, manifest, hashes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from services.backup_service import (
    create_backup,
    get_backup_records,
    inspect_backup,
    validate_backup_manifest,
    verify_backup_hashes,
)
from services.exceptions import BackupCorruptedError, BackupHashMismatchError, BackupSchemaMismatchError

pytestmark = pytest.mark.usefixtures("session")

try:
    import zipfile
except ImportError:
    zipfile = None  # type: ignore[assignment]


class TestCreateBackup:
    """Test backup creation."""

    def test_backup_generated(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """A backup ZIP is generated successfully."""
        db_path = tmp_path / "test.db"
        # Create a minimal SQLite database
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.commit()
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path, user_id="test-user")
        assert len(zip_bytes) > 0
        assert manifest is not None
        assert "backup_reference" in manifest
        assert manifest["backup_reference"].startswith("BAK-")

    def test_manifest_valid(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """The manifest contains required fields."""
        db_path = tmp_path / "test2.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path)
        assert "schema_version" in manifest
        assert "app_version" in manifest
        assert "created_at" in manifest
        assert "database_hash" in manifest
        assert "database_size_bytes" in manifest
        assert "table_count" in manifest
        assert manifest["schema_version"] == "1.0"

    def test_database_hash_generated(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """The manifest includes a database SHA-256 hash."""
        db_path = tmp_path / "test3.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path)
        db_hash = manifest.get("database_hash")
        assert db_hash is not None
        assert len(db_hash) == 64  # SHA-256 hex

    def test_zip_opens(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """The backup ZIP can be opened and contains expected files."""
        db_path = tmp_path / "test4.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path)
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            assert "database.sqlite" in names
            assert "manifest.json" in names

    def test_backup_hash_generated(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """The backup record includes a file hash (SHA-256 of ZIP)."""
        db_path = tmp_path / "test5.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path)
        from models.backup_record import BackupRecord

        # Check the database record
        record = session.query(BackupRecord).first()
        assert record is not None
        assert record.file_hash is not None
        assert len(record.file_hash) == 64

    def test_env_not_in_backup(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """.env must not be in the backup archive."""
        db_path = tmp_path / "test6.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path)
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            for name in names:
                assert ".env" not in name, f"Found excluded file in backup: {name}"


class TestInspectBackup:
    """Test inspecting backup archives."""

    def test_inspect_valid_backup(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """A valid backup can be inspected."""
        db_path = tmp_path / "inspect1.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path)
        inspected = inspect_backup(zip_bytes)
        assert inspected["backup_reference"] == manifest["backup_reference"]

    def test_inspect_corrupt_zip(self) -> None:
        """A corrupt ZIP is rejected."""
        with pytest.raises(BackupCorruptedError, match="Invalid ZIP"):
            inspect_backup(b"not a zip file")


class TestValidateBackupManifest:
    """Test manifest validation."""

    def test_valid_manifest_passes(self) -> None:
        """A valid manifest passes validation."""
        manifest = {
            "backup_reference": "BAK-TEST001",
            "schema_version": "1.0",
            "app_version": "0.1.0",
            "created_at": "2026-06-15T00:00:00",
            "database_hash": "a" * 64,
        }
        validate_backup_manifest(manifest)  # Should not raise

    def test_missing_field_fails(self) -> None:
        """A manifest missing a required field is rejected."""
        manifest = {"backup_reference": "BAK-TEST002"}
        with pytest.raises(BackupCorruptedError, match="missing required field"):
            validate_backup_manifest(manifest)

    def test_schema_mismatch_fails(self) -> None:
        """A manifest with incompatible schema version is rejected."""
        manifest = {
            "backup_reference": "BAK-TEST003",
            "schema_version": "0.5",
            "app_version": "0.1.0",
            "created_at": "2026-06-15T00:00:00",
            "database_hash": "a" * 64,
        }
        with pytest.raises(BackupSchemaMismatchError, match="incompatible"):
            validate_backup_manifest(manifest)


class TestVerifyBackupHashes:
    """Test hash verification."""

    def test_hash_verification_passes(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """Hash verification passes for a valid backup."""
        db_path = tmp_path / "hash1.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path)
        verify_backup_hashes(zip_bytes, manifest)  # Should not raise

    def test_wrong_hash_fails(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """Hash verification fails when hash doesn't match."""
        db_path = tmp_path / "hash2.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        zip_bytes, manifest = create_backup(session, engine, db_path)
        manifest["database_hash"] = "x" * 64  # Tamper with hash
        with pytest.raises(BackupHashMismatchError, match="Database hash mismatch"):
            verify_backup_hashes(zip_bytes, manifest)


class TestGetBackupRecords:
    """Test querying backup records."""

    def test_get_records(self, engine: Any, session: Any, tmp_path: Path) -> None:
        """Backup records can be retrieved."""
        db_path = tmp_path / "records1.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        create_backup(session, engine, db_path, user_id="u1")
        records = get_backup_records(session)
        assert len(records) >= 1
        assert records[0]["backup_reference"] is not None
        assert records[0]["file_size"] > 0
