# Academic Anonymous Grader — Database Initialization Tests
"""Tests for database/init_db.py."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, text

from database.init_db import initialize_database, verify_database_tables

EXPECTED_TABLES = {
    "materials",
    "assessments",
    "questions",
    "student_identities",
    "anonymous_students",
    "import_batches",
    "submissions",
    "responses",
    "grade_records",
    "audit_events",
    "export_records",
}


class TestDatabaseInitialization:
    """Verify database initialization behavior."""

    def test_all_expected_tables_are_created(self, engine: Engine) -> None:
        """All Phase 1 tables should exist after initialization."""
        tables = verify_database_tables(engine)
        for table in EXPECTED_TABLES:
            assert table in tables, f"Missing table: {table}"

    def test_initialize_database_is_idempotent(self, engine: Engine) -> None:
        """Calling initialize_database twice should not raise."""
        initialize_database(engine)  # Second call
        tables = verify_database_tables(engine)
        assert len(tables) >= len(EXPECTED_TABLES)

    def test_sqlite_foreign_keys_are_enabled(self, engine: Engine) -> None:
        """SQLite foreign key enforcement must be active."""
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys;"))
            row = result.fetchone()
            assert row is not None
            assert row[0] == 1, "Foreign keys are not enabled"

    def test_database_file_is_created(self, engine: Engine, tmp_db_path: Path) -> None:
        """The database file should exist on disk."""
        assert tmp_db_path.exists(), "Database file was not created"
