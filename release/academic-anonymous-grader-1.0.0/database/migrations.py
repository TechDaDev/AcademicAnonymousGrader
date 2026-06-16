# Academic Anonymous Grader — Versioned Database Migrations
"""Internal versioned migration runner.

This module provides a lightweight, versioned migration system that is
applied at application startup.  It is designed for a single-process,
single-writer application (Streamlit + SQLite).

Schema versions are tracked in a ``_schema_version`` table with columns:
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT

Migration workflow:
    1. ``run_migrations(engine)`` inspects the current schema version.
    2. Applies each pending migration in order.
    3. Records each applied version.

This system is NOT a replacement for Alembic in multi-developer,
multi-environment projects.  It is intentionally simple for this
application's deployment model.

Downgrade is not supported — the goal is forward-only, additive
changes that never delete or alter existing columns.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, Text, inspect
from sqlalchemy import text as sa_text

logger = logging.getLogger("academic_grader.migrations")

# ── Current schema revision ───────────────────────────────────────
# Increment this when adding a new migration.
SCHEMA_VERSION: int = 3

# Initial version from Phase 1-9 (tables created by Base.metadata.create_all)
SCHEMA_VERSION_INITIAL: int = 1


# ── Migration definitions ─────────────────────────────────────────


def _get_applied_versions(engine: Engine) -> set[int]:
    """Return the set of schema versions already applied."""
    inspector = inspect(engine)
    if "_schema_version" not in inspector.get_table_names():
        return set()

    with engine.connect() as conn:
        result = conn.execute(sa_text("SELECT version FROM _schema_version"))
        return {row[0] for row in result}


def _record_migration(engine: Engine, version: int, description: str) -> None:
    """Record a completed migration."""
    with engine.begin() as conn:
        conn.execute(
            sa_text(
                "INSERT INTO _schema_version (version, applied_at, description) "
                "VALUES (:v, :t, :d)"
            ),
            {"v": version, "t": datetime.now(UTC).isoformat(), "d": description},
        )


def _ensure_schema_version_table(engine: Engine) -> None:
    """Create the schema version tracking table if it does not exist."""
    metadata = MetaData()
    Table(
        "_schema_version",
        metadata,
        Column("version", Integer, primary_key=True),
        Column("applied_at", String(30), nullable=False),
        Column("description", Text, nullable=True),
    )
    metadata.create_all(engine, checkfirst=True)


# ── Individual migrations ─────────────────────────────────────────


def _migrate_v1_to_v2(engine: Engine) -> None:
    """Phase 10 — Add instructor assignments and grading claim columns.

    Changes:
        1. Create instructor_assignments table (if not exists).
        2. Create active-only partial unique index.
        3. Add grading claim columns to submissions table.
        4. Create index on assigned_grader_user_id.
    """
    # Step 1: Create instructor_assignments table via model metadata
    # This is already handled by Base.metadata.create_all, but we ensure
    # it here explicitly for migration clarity.
    import models.instructor_assignment  # noqa: F401 — register model
    from database.base import Base

    Base.metadata.create_all(engine, checkfirst=True)

    # Step 2: Ensure the partial unique index exists
    # SQLAlchemy creates this via the Index definition in the model.
    # We verify it exists and create it manually if needed.
    inspector = inspect(engine)
    indexes = inspector.get_indexes("instructor_assignments")
    index_names = {idx["name"] for idx in indexes if idx.get("name")}

    if "uq_active_instructor_assignment" not in index_names:
        with engine.connect() as conn:
            conn.execute(
                sa_text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_instructor_assignment "
                    "ON instructor_assignments (instructor_user_id, assessment_id) "
                    "WHERE is_active = 1"
                )
            )
            conn.commit()

    # Step 3: Add grading claim columns to submissions
    inspector = inspect(engine)
    sub_columns = {col["name"] for col in inspector.get_columns("submissions")}

    with engine.begin() as conn:
        if "assigned_grader_user_id" not in sub_columns:
            conn.execute(
                sa_text(
                    "ALTER TABLE submissions ADD COLUMN assigned_grader_user_id "
                    "VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL"
                )
            )
        if "grading_claimed_at" not in sub_columns:
            conn.execute(
                sa_text(
                    "ALTER TABLE submissions ADD COLUMN grading_claimed_at "
                    "DATETIME"
                )
            )
        if "grading_lock_expires_at" not in sub_columns:
            conn.execute(
                sa_text(
                    "ALTER TABLE submissions ADD COLUMN grading_lock_expires_at "
                    "DATETIME"
                )
            )

    # Step 4: Create index on assigned_grader_user_id
    if "assigned_grader_user_id" not in sub_columns:
        with engine.begin() as conn:
            conn.execute(
                sa_text(
                    "CREATE INDEX IF NOT EXISTS ix_submissions_assigned_grader "
                    "ON submissions (assigned_grader_user_id)"
                )
            )

    logger.info("Migration v1→v2 complete: instructor assignments and claim columns added.")


def _migrate_v2_to_v3(engine: Engine) -> None:
    """Phase 12.1 — Add academic structure reference tables.

    Creates Department, AcademicStage, AcademicTerm, AcademicYear tables
    and adds foreign-key columns to materials.
    """
    import models.academic_stage  # noqa: F401
    import models.academic_term  # noqa: F401
    import models.academic_year  # noqa: F401
    import models.department  # noqa: F401
    from database.base import Base

    # Create reference tables via model metadata
    Base.metadata.create_all(engine, checkfirst=True)

    # Add foreign-key columns to materials (if not already present)
    inspector = inspect(engine)
    existing_columns = {c["name"] for c in inspector.get_columns("materials")}

    if "department_id" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(
                sa_text(
                    "ALTER TABLE materials ADD COLUMN department_id VARCHAR(36) "
                    "REFERENCES departments(id) ON DELETE RESTRICT"
                )
            )
            conn.execute(
                sa_text(
                    "ALTER TABLE materials ADD COLUMN academic_stage_id VARCHAR(36) "
                    "REFERENCES academic_stages(id) ON DELETE RESTRICT"
                )
            )
            conn.execute(
                sa_text(
                    "ALTER TABLE materials ADD COLUMN academic_term_id VARCHAR(36) "
                    "REFERENCES academic_terms(id) ON DELETE RESTRICT"
                )
            )
            conn.execute(
                sa_text(
                    "ALTER TABLE materials ADD COLUMN academic_year_id VARCHAR(36) "
                    "REFERENCES academic_years(id) ON DELETE RESTRICT"
                )
            )
            conn.execute(
                sa_text(
                    "ALTER TABLE materials ADD COLUMN classification_needs_review "
                    "BOOLEAN NOT NULL DEFAULT 0"
                )
            )

    # Create indexes
    for col in ("department_id", "academic_stage_id", "academic_term_id", "academic_year_id"):
        idx_name = f"ix_materials_{col}"
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("materials")}
        if idx_name not in existing_indexes:
            with engine.begin() as conn:
                conn.execute(
                    sa_text(f"CREATE INDEX {idx_name} ON materials ({col})")
                )

    # ── Legacy value mapping ─────────────────────────────────────────
    # Try to map existing free-text fields to reference IDs.
    # Unmapped or partially mapped records get classification_needs_review = 1.
    # Always run on materials that have no classification refs set, even
    # if the FK columns already exist (idempotent re-run safe).
    _map_legacy_classification_values(engine)

    logger.info("Migration v2→v3 complete: academic structure reference tables added.")


# ── Legacy classification value mapping ────────────────────────────


def _normalize(text: str | None) -> str:
    """Normalize text for matching: lowercase, strip, collapse whitespace."""
    if not text:
        return ""
    import re
    return re.sub(r"\s+", " ", text.strip().lower())


# Department mapping: free-text → code lookup
_LEGACY_DEPT_MAP: dict[str, str] = {
    "big data": "big_data",
    "bigdata": "big_data",
    "medical application": "medical_applications",
    "medical applications": "medical_applications",
    "medicalapplication": "medical_applications",
    "engineering application": "engineering_applications",
    "engineering applications": "engineering_applications",
    "engineeringapplication": "engineering_applications",
}

# Stage mapping: free-text → stage_number (1-based)
_LEGACY_STAGE_MAP: dict[str, int] = {
    "stage 1": 1, "first stage": 1, "first": 1,
    "stage 2": 2, "second stage": 2, "second": 2,
    "stage 3": 3, "third stage": 3, "third": 3,
    "stage 4": 4, "fourth stage": 4, "fourth": 4,
}

# Term mapping: free-text → term_number (1-based)
_LEGACY_TERM_MAP: dict[str, int] = {
    "term 1": 1, "semester 1": 1, "first term": 1, "first semester": 1,
    "term 2": 2, "semester 2": 2, "second term": 2, "second semester": 2,
}

# Academic year mapping: range pattern like "2026-2027" or "2026–2027"
def _parse_legacy_academic_year(text: str | None) -> tuple[int, int] | None:
    """Parse academic year range from free-text. Returns (start, end) or None."""
    if not text:
        return None
    normalized = _normalize(text)
    # Match patterns like "2026-2027", "2026–2027", "2026/2027", "2026 2027"
    m = re.match(r"(\d{4})\s*[-–/]\s*(\d{4})$", normalized)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
        if end == start + 1:
            return (start, end)
    return None


def _map_legacy_classification_values(engine: Engine) -> None:
    """Map legacy free-text classification fields to reference IDs.

    This runs after the reference tables are created and the FK columns
    are added. It:
    1. Queries all material records.
    2. Tries to match free-text fields to reference records.
    3. Updates matched records with the reference IDs.
    4. Sets classification_needs_review = 1 for all existing records
       where any of the four classification refs is missing.
    """
    with engine.begin() as conn:
        # Fetch all existing materials
        rows = conn.execute(
            sa_text(
                "SELECT id, department, stage, academic_year FROM materials"
            )
        ).fetchall()

        # Pre-fetch reference lookups
        dept_rows = conn.execute(
            sa_text("SELECT id, code FROM departments")
        ).fetchall()
        dept_by_code: dict[str, str] = {r[1]: r[0] for r in dept_rows}

        stage_rows = conn.execute(
            sa_text("SELECT id, stage_number FROM academic_stages")
        ).fetchall()
        stage_by_num: dict[int, str] = {r[1]: r[0] for r in stage_rows}

        term_rows = conn.execute(
            sa_text("SELECT id, term_number FROM academic_terms")
        ).fetchall()
        term_by_num: dict[int, str] = {r[1]: r[0] for r in term_rows}

        year_rows = conn.execute(
            sa_text("SELECT id, start_year, end_year FROM academic_years")
        ).fetchall()
        year_by_range: dict[tuple[int, int], str] = {}
        for r in year_rows:
            year_by_range[(r[1], r[2])] = r[0]

        mapped_count = 0
        partial_count = 0
        for row in rows:
            mat_id = row[0]
            dept_text = row[1]
            stage_text = row[2]
            year_text = row[3]

            dept_id: str | None = None
            stage_id: str | None = None
            term_id: str | None = None
            year_id: str | None = None

            # Map department
            if dept_text:
                norm_dept = _normalize(dept_text)
                dept_code = _LEGACY_DEPT_MAP.get(norm_dept)
                if dept_code and dept_code in dept_by_code:
                    dept_id = dept_code  # Use code as key
                    dept_id = dept_by_code.get(dept_code)

            # Map stage (try numeric first, then text patterns)
            if stage_text:
                norm_stage = _normalize(stage_text)
                # Try direct numeric
                try:
                    sn = int(norm_stage)
                    if 1 <= sn <= 4:
                        stage_id = stage_by_num.get(sn)
                except ValueError:
                    pass
                if not stage_id:
                    sn_val = _LEGACY_STAGE_MAP.get(norm_stage)
                    if sn_val is not None:
                        stage_id = stage_by_num.get(sn_val)

            # Map term (check stage text for term hints)
            if stage_text:
                norm_stage_check = _normalize(stage_text)
                for term_key, term_num in _LEGACY_TERM_MAP.items():
                    if term_key in norm_stage_check:
                        term_id = term_by_num.get(term_num)
                        break

            # Map academic year
            parsed_year = _parse_legacy_academic_year(year_text)
            if parsed_year and parsed_year in year_by_range:
                year_id = year_by_range[parsed_year]

            # Determine which refs are set
            refs_set = sum(1 for r in [dept_id, stage_id, term_id, year_id] if r)
            needs_review = 1 if refs_set < 4 else 0

            updates: list[str] = []
            params: dict[str, object] = {"id": mat_id}

            if dept_id:
                updates.append("department_id = :dept_id")
                params["dept_id"] = dept_id
            if stage_id:
                updates.append("academic_stage_id = :stage_id")
                params["stage_id"] = stage_id
            if term_id:
                updates.append("academic_term_id = :term_id")
                params["term_id"] = term_id
            if year_id:
                updates.append("academic_year_id = :year_id")
                params["year_id"] = year_id

            updates.append("classification_needs_review = :needs_review")
            params["needs_review"] = needs_review

            if updates:
                set_clause = ", ".join(updates)
                conn.execute(
                    sa_text(f"UPDATE materials SET {set_clause} WHERE id = :id"),  # noqa: S608 — column names are hardcoded constants
                    params,
                )

            if refs_set >= 4:
                mapped_count += 1
            elif refs_set > 0:
                partial_count += 1

        logger.info(
            "Legacy mapping: %d fully mapped, %d partially mapped, %d total records",
            mapped_count, partial_count, len(rows),
        )


# ── Migration registry ────────────────────────────────────────────

_MIGRATIONS: dict[int, tuple[str, Any]] = {
    2: ("Add instructor assignments, claim columns, and indexes", _migrate_v1_to_v2),
    3: ("Add academic structure reference tables", _migrate_v2_to_v3),
}


def get_pending_migrations(engine: Engine) -> list[int]:
    """Return the list of pending migration version numbers in order."""
    _ensure_schema_version_table(engine)
    applied = _get_applied_versions(engine)
    current_max = max(applied) if applied else SCHEMA_VERSION_INITIAL

    # If no migrations recorded but tables exist, treat as at version 1
    if not applied:
        inspector = inspect(engine)
        if "users" in inspector.get_table_names():
            # Record version 1 as already applied
            _record_migration(engine, SCHEMA_VERSION_INITIAL, "Initial schema (Phases 1-9)")
            applied = {SCHEMA_VERSION_INITIAL}
            current_max = SCHEMA_VERSION_INITIAL

    pending = [v for v in range(current_max + 1, SCHEMA_VERSION + 1) if v in _MIGRATIONS]
    return sorted(pending)


def run_migrations(engine: Engine) -> list[str]:
    """Run all pending migrations and return a list of applied descriptions.

    Returns
    -------
    list[str]
        Descriptions of applied migrations.  Empty list means schema is up to date.
    """
    pending = get_pending_migrations(engine)
    applied_descriptions: list[str] = []

    for version in pending:
        description, migrate_fn = _MIGRATIONS[version]
        logger.info("Applying migration v%s: %s", version, description)
        try:
            migrate_fn(engine)
            _record_migration(engine, version, description)
            applied_descriptions.append(f"v{version}: {description}")
            logger.info("Migration v%s applied successfully.", version)
        except Exception:
            logger.exception("Migration v%s failed. Database may be in an inconsistent state.", version)
            raise

    return applied_descriptions


def get_current_schema_version(engine: Engine) -> int:
    """Return the current schema version of the connected database.

    Returns 0 if the schema version table does not exist.
    """
    try:
        _ensure_schema_version_table(engine)
        applied = _get_applied_versions(engine)
        if applied:
            return max(applied)
        # If no migrations recorded but tables exist, it's the initial version
        inspector = inspect(engine)
        if "users" in inspector.get_table_names():
            return SCHEMA_VERSION_INITIAL
        return 0
    except Exception:
        return 0


def get_expected_schema_version() -> int:
    """Return the schema version this application expects."""
    return SCHEMA_VERSION


def verify_schema_version(engine: Engine) -> tuple[bool, str]:
    """Verify that the database schema matches the expected version.

    Returns
    -------
    tuple[bool, str]
        (is_healthy, message)
    """
    current = get_current_schema_version(engine)
    expected = SCHEMA_VERSION

    if current == 0:
        return False, "Schema version could not be determined. Database may be empty."

    if current < expected:
        return False, (
            f"Schema version {current} is behind expected {expected}. "
            f"Run migrations to upgrade."
        )

    if current > expected:
        return False, (
            f"Schema version {current} is ahead of expected {expected}. "
            f"The application binary may be outdated."
        )

    return True, f"Schema version {current} is current."
