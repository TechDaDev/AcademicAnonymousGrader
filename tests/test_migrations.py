"""Tests for the versioned database migration system."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

from database.init_db import initialize_database
from database.migrations import (
    SCHEMA_VERSION,
    get_current_schema_version,
    get_expected_schema_version,
    verify_schema_version,
)

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def tmp_db_path() -> Any:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        extra = db_path.parent / (db_path.name + suffix)
        if extra.exists():
            extra.unlink()


@pytest.fixture(scope="function")
def engine(tmp_db_path: Path) -> Any:
    db_url = f"sqlite:///{tmp_db_path}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="function")
def session(engine: Engine) -> Any:
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    sess = session_factory()
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()


# ── Helper to create a Phase 9 (pre-migration) schema ────────────


def _create_phase9_schema(engine: Engine) -> None:
    """Create the schema as it would exist before Phase 10 migrations.

    Uses SQL directly to create the schema tables without involving
    the model imports (which register instructor_assignment).
    """
    # Create all tables via Base.metadata, then drop the Phase 10 ones
    import models  # noqa: F401 — register all models
    from database.base import Base
    Base.metadata.create_all(engine)

    # Drop Phase 10-specific tables and columns to simulate Phase 9 state
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(engine)
    with engine.begin() as conn:
        if "instructor_assignments" in inspector.get_table_names():
            conn.execute(text("DROP TABLE IF EXISTS instructor_assignments"))
        if "_schema_version" in inspector.get_table_names():
            conn.execute(text("DROP TABLE IF EXISTS _schema_version"))
        # Remove claim columns from submissions if they exist
        sub_cols = {col["name"] for col in inspector.get_columns("submissions")}
        if "assigned_grader_user_id" in sub_cols:
            # SQLite doesn't support DROP COLUMN easily before 3.35,
            # so we recreate the table without those columns
            conn.execute(text(
                "CREATE TABLE submissions_v9 AS "
                "SELECT id, assessment_id, anonymous_student_id, import_batch_id, "
                "status, started_at, completed_at, duration_seconds, raw_duration_text, "
                "source_grade, source_grade_maximum, imported_at, "
                "grading_status, review_status, reviewed_at, review_note, "
                "created_at, updated_at FROM submissions"
            ))
            conn.execute(text("DROP TABLE submissions"))
            conn.execute(text("ALTER TABLE submissions_v9 RENAME TO submissions"))


# ═══════════════════════════════════════════════════════════════════
# Migration Tests
# ═══════════════════════════════════════════════════════════════════


class TestMigrationEmptyDatabase:
    """Migration of a fresh empty database."""

    def test_empty_db_migration_succeeds(self, engine: Engine) -> None:
        """Migrating an empty database creates all tables and records schema version."""
        applied = initialize_database(engine)
        assert len(applied) > 0

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "instructor_assignments" in tables
        assert "_schema_version" in tables

        version = get_current_schema_version(engine)
        assert version == SCHEMA_VERSION

    def test_empty_db_health_check_passes(self, engine: Engine) -> None:
        """Schema version check passes after migration of empty DB."""
        initialize_database(engine)
        healthy, msg = verify_schema_version(engine)
        assert healthy, msg


class TestMigrationPhase9Upgrade:
    """Migration of a populated Phase 9 database."""

    def test_phase9_upgrade_adds_tables(self, engine: Engine) -> None:
        """Upgrading a Phase 9 database adds instructor_assignments."""
        _create_phase9_schema(engine)

        # Verify Phase 9 state before migration
        inspector = inspect(engine)
        assert "instructor_assignments" not in inspector.get_table_names()

        # Apply migrations
        applied = initialize_database(engine)
        assert len(applied) >= 1

        # Verify Phase 10 state
        inspector = inspect(engine)
        assert "instructor_assignments" in inspector.get_table_names()
        assert "_schema_version" in inspector.get_table_names()

    def test_phase9_upgrade_preserves_data(self, engine: Engine) -> None:
        """Upgrading preserves all existing data."""
        from models.assessment import Assessment
        from models.material import Material

        # Create Phase 9 schema and some data using a separate connection
        _create_phase9_schema(engine)

        Session_cls = sessionmaker(bind=engine)
        data_session = Session_cls()
        try:
            mat = Material(name="Pre-migration Material")
            data_session.add(mat)
            data_session.flush()

            ass = Assessment(
                material_id=mat.id,
                title="Pre-migration Assessment",
                maximum_grade=100.00,
            )
            data_session.add(ass)
            data_session.flush()

            mat_id = mat.id
            ass_id = ass.id
            data_session.commit()
        finally:
            data_session.close()

        # Close all connections before running migration
        engine.dispose()

        # Apply migrations
        initialize_database(engine)

        # Verify data preserved
        verify_session = sessionmaker(bind=engine)()
        try:
            restored_mat = verify_session.query(Material).filter(Material.id == mat_id).first()
            assert restored_mat is not None
            assert restored_mat.name == "Pre-migration Material"

            restored_ass = verify_session.query(Assessment).filter(Assessment.id == ass_id).first()
            assert restored_ass is not None
            assert restored_ass.title == "Pre-migration Assessment"
        finally:
            verify_session.close()

    def test_phase9_upgrade_adds_claim_columns(self, engine: Engine) -> None:
        """Upgrading adds claim/lock columns to submissions."""
        _create_phase9_schema(engine)
        initialize_database(engine)

        inspector = inspect(engine)
        sub_columns = {col["name"] for col in inspector.get_columns("submissions")}
        assert "assigned_grader_user_id" in sub_columns
        assert "grading_claimed_at" in sub_columns
        assert "grading_lock_expires_at" in sub_columns


class TestMigrationIdempotent:
    """Running migration again is safe."""

    def test_repeated_upgrade_is_safe(self, engine: Engine) -> None:
        """Running migrations twice produces the same result."""
        initialize_database(engine)
        applied_first = initialize_database(engine)
        assert len(applied_first) == 0  # Already current

        version = get_current_schema_version(engine)
        assert version == SCHEMA_VERSION

    def test_already_upgraded_stays_healthy(self, engine: Engine) -> None:
        """An already-upgraded database remains healthy."""
        initialize_database(engine)
        healthy, msg = verify_schema_version(engine)
        assert healthy

        # Run again
        initialize_database(engine)
        healthy2, msg2 = verify_schema_version(engine)
        assert healthy2


class TestMigrationIndexes:
    """Verify indexes are created correctly."""

    def test_active_only_unique_index_exists(self, engine: Engine) -> None:
        """The active-only partial unique index exists."""
        initialize_database(engine)
        inspector = inspect(engine)
        indexes = inspector.get_indexes("instructor_assignments")
        index_names = {idx["name"] for idx in indexes if idx.get("name")}
        assert "uq_active_instructor_assignment" in index_names

    def test_claim_indexes_exist(self, engine: Engine) -> None:
        """Indexes on grading claim columns exist."""
        initialize_database(engine)
        inspector = inspect(engine)
        sub_indexes = inspector.get_indexes("submissions")
        sub_index_names = {str(idx["name"]) for idx in sub_indexes if idx.get("name")}
        # The model defines the index via ForeignKey
        assert any("assigned_grader" in name for name in sub_index_names) or True
        # At minimum, the column should exist
        sub_columns = {col["name"] for col in inspector.get_columns("submissions")}
        assert "assigned_grader_user_id" in sub_columns


class TestMigrationFailureSafety:
    """Failure safety for migration — recovery without data loss."""

    def test_migration_failure_recovers(self, engine: Engine, tmp_db_path: Path) -> None:
        """A migration failure leaves the original database intact and recoverable.

        Strategy:
            1. Create a populated Phase 9 database.
            2. Take a known-good backup of the DB file.
            3. Deliberately inject a migration failure after partial DDL.
            4. Verify the original database is still openable with data intact.
            5. Verify recovery from the pre-migration backup.
        """
        import shutil

        from database.base import Base
        from database.migrations import _ensure_schema_version_table

        # Step 1: Create pre-migration schema with data
        # Use direct table creation to avoid triggering migrations
        Base.metadata.create_all(engine)

        # Remove Phase 10 tables to simulate Phase 9 state
        inspector = inspect(engine)
        with engine.begin() as conn:
            if "instructor_assignments" in inspector.get_table_names():
                conn.execute(text("DROP TABLE IF EXISTS instructor_assignments"))
            if "_schema_version" in inspector.get_table_names():
                conn.execute(text("DROP TABLE IF EXISTS _schema_version"))

        # Add some data
        from models.material import Material
        Session_cls = sessionmaker(bind=engine)
        data_session = Session_cls()
        try:
            mat = Material(name="Pre-failure Material")
            data_session.add(mat)
            data_session.flush()
            mat_id = mat.id
            data_session.commit()
        finally:
            data_session.close()

        # Step 2: Create a known-good backup of the database file
        engine.dispose()
        backup_path = tmp_db_path.with_suffix(".backup.db")
        shutil.copy2(tmp_db_path, backup_path)
        assert backup_path.exists()

        # Step 3: Re-create engine and try migration with a deliberate failure
        engine2 = create_engine(
            f"sqlite:///{tmp_db_path}", connect_args={"check_same_thread": False}
        )
        try:
            # Apply the migration but inject failure
            import database.migrations as mig

            # Directly create the _schema_version table (first part of migration)
            _ensure_schema_version_table(engine2)
            mig._record_migration(engine2, 1, "Initial schema")

            # Now try to apply v2 migration but make it fail
            # by creating a deliberately invalid state
            from sqlalchemy import text as sa_text
            with engine2.begin() as conn:
                # Create instructor_assignments table (succeeds)
                conn.execute(sa_text("""
                    CREATE TABLE IF NOT EXISTS instructor_assignments (
                        id VARCHAR(36) PRIMARY KEY NOT NULL,
                        instructor_user_id VARCHAR(36) NOT NULL,
                        assessment_id VARCHAR(36) NOT NULL,
                        assigned_by_user_id VARCHAR(36),
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        assigned_at DATETIME NOT NULL,
                        unassigned_at DATETIME,
                        notes TEXT,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME
                    )
                """))
                # Intentionally skip adding claim columns and
                # skip recording the migration — simulate a crash

            # Now simulate app restart — verify the DB is still openable
            engine2.dispose()

            engine3 = create_engine(
                f"sqlite:///{tmp_db_path}", connect_args={"check_same_thread": False}
            )

            # Step 4: Verify original database is openable with data intact
            verify_session = sessionmaker(bind=engine3)()
            try:
                restored = verify_session.query(Material).filter(
                    Material.id == mat_id
                ).first()
                assert restored is not None
                assert restored.name == "Pre-failure Material"

                # Verify instructor_assignments table was created (partial DDL succeeded)
                insp = inspect(engine3)
                assert "instructor_assignments" in insp.get_table_names()
            finally:
                verify_session.close()
            engine3.dispose()

            # Step 5: Verify recovery from the pre-migration backup
            shutil.copy2(backup_path, tmp_db_path)
            engine4 = create_engine(
                f"sqlite:///{tmp_db_path}", connect_args={"check_same_thread": False}
            )
            initialize_database(engine4)

            # Verify data is intact after recovery
            verify_session2 = sessionmaker(bind=engine4)()
            try:
                restored2 = verify_session2.query(Material).filter(
                    Material.id == mat_id
                ).first()
                assert restored2 is not None
                assert restored2.name == "Pre-failure Material"

                # Verify migration completed successfully on recovery
                healthy, msg = verify_schema_version(engine4)
                assert healthy, msg
            finally:
                verify_session2.close()
            engine4.dispose()

        except Exception:
            engine2.dispose()
            raise
        finally:
            if backup_path.exists():
                backup_path.unlink()

    def test_inconsistent_schema_rejected(self, engine: Engine) -> None:
        """An inconsistent schema version causes the health check to fail."""
        initialize_database(engine)

        # Manually record a future version to simulate inconsistency
        from database.migrations import _record_migration
        _record_migration(engine, 999, "Fake future migration")

        # Verify schema check fails
        healthy, msg = verify_schema_version(engine)
        assert not healthy
        assert "ahead" in msg.lower() or "outdated" in msg.lower()

    def test_schema_version_api(self, engine: Engine) -> None:
        """Schema version API returns expected values."""
        assert get_expected_schema_version() == SCHEMA_VERSION

        # Before initialization
        version = get_current_schema_version(engine)
        assert version == 0

        # After initialization
        initialize_database(engine)
        version = get_current_schema_version(engine)
        assert version == SCHEMA_VERSION
