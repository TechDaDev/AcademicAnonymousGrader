"""Phase 4 raw database plaintext audit.

This test uses unique identity markers, persists them through secure import,
then inspects the SQLite database directly to verify no plaintext identity
data is stored in any text-like column.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import inspect, text

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.response import Response
from models.student_identity import StudentIdentity
from models.submission import Submission
from parsers.models import (
    ColumnClassification,
    ImportStatistics,
    ParsedColumn,
    ParsedImport,
    ParsedResponse,
    ParsedStudentRow,
)
from security.key_validation import (
    generate_encryption_key,
    generate_fingerprint_key,
)
from services.authorization_service import AuthContext
from services.secure_import_service import execute_secure_import

_ADMIN_AUTH = AuthContext(user_id="test-admin", role="administrator")

# ── Unique identity markers for plaintext audit ────────────────────
UNIQUE_FIRSTNAME = "UNIQUE_FIRSTNAME_PHASE4_MARKER"
UNIQUE_LASTNAME = "UNIQUE_LASTNAME_PHASE4_MARKER"
UNIQUE_EMAIL = "unique.phase4.identity@example.com"
UNIQUE_STUDENT_ID = "PHASE4-STUDENT-ID-0007"


def _make_parsed_import(rows: tuple[ParsedStudentRow, ...]) -> ParsedImport:
    return ParsedImport(
        source_filename="plaintext_audit.html",
        parser_name="html_test",
        table_index=0,
        columns=(
            ParsedColumn("First name", "first_name", 0, ColumnClassification.IDENTITY, "first_name", True, 1.0),
            ParsedColumn("Last name", "last_name", 1, ColumnClassification.IDENTITY, "last_name", True, 1.0),
            ParsedColumn("Email", "email", 2, ColumnClassification.IDENTITY, "email", True, 1.0),
            ParsedColumn(
                "Student ID", "institutional_student_id", 3,
                ColumnClassification.IDENTITY, "institutional_student_id", True, 1.0,
            ),
            ParsedColumn(
                "Response 1", "response_1", 4,
                ColumnClassification.RESPONSE, "response_1", True, 1.0, response_number=1,
            ),
        ),
        rows=rows,
        response_columns=(),
        unknown_columns=(),
        warnings=(),
        errors=(),
        statistics=ImportStatistics(
            total_rows=len(rows),
            valid_rows=len(rows),
            warning_rows=0,
            error_rows=0,
            blank_response_count=0,
            response_column_count=1,
            duplicate_email_count=0,
        ),
        candidate_tables=(),
        parse_started_at=None,  # type: ignore[arg-type]
        parse_completed_at=None,  # type: ignore[arg-type]
    )


def _make_row(row_number: int) -> ParsedStudentRow:
    return ParsedStudentRow(
        row_number=row_number,
        first_name=UNIQUE_FIRSTNAME,
        last_name=UNIQUE_LASTNAME,
        email=UNIQUE_EMAIL,
        institutional_student_id=UNIQUE_STUDENT_ID,
        status="finished",
        started=None,
        completed=None,
        duration_seconds=None,
        source_grade=Decimal("18.5"),
        raw_source_grade="18.5 / 20",
        source_grade_maximum=Decimal("20"),
        responses=(
            ParsedResponse(1, "Response 1", "This is a student response", False),
        ),
        unknown_values={},
    )


class TestRawDatabasePlaintextAudit:
    """Inspect the SQLite database directly for plaintext identity markers."""

    def test_no_plaintext_identity_in_database(
        self, tmp_db_path: Path, monkeypatch
    ) -> None:
        """Persist identity through secure import, then inspect raw SQLite."""
        # Set up keys
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        # Create engine, initialize DB, create session
        from sqlalchemy import create_engine, event

        from database.init_db import initialize_database

        db_url = f"sqlite:///{tmp_db_path}"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        initialize_database(engine)

        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        try:
            # Create material, assessment, questions
            material = Material(name="Plaintext Audit Material")
            session.add(material)
            session.flush()

            assessment = Assessment(
                material_id=material.id,
                title="Plaintext Audit Assessment",
                maximum_grade=Decimal("100"),
            )
            session.add(assessment)
            session.flush()

            q1 = Question(
                assessment_id=assessment.id,
                question_number=1,
                maximum_grade=Decimal("10"),
                title="Q1",
            )
            session.add(q1)
            session.flush()

            # Execute secure import
            row = _make_row(1)
            parsed = _make_parsed_import((row,))
            file_bytes = b"plaintext audit file content"

            execute_secure_import(
                session=session,
                parsed=parsed,
                assessment_id=assessment.id,
                assessment_question_numbers=(1,),
                file_bytes=file_bytes,
                source_filename="plaintext_audit.html",
                table_index=0,
                auth_ctx=_ADMIN_AUTH,
            )

            session.commit()

            # ── Direct SQLite inspection ──
            # Check all text-like columns in relevant tables for identity markers
            # 1. student_identities
            identity = session.query(StudentIdentity).first()
            assert identity is not None
            assert identity.encrypted_first_name is not None
            assert identity.encrypted_last_name is not None
            assert identity.encrypted_email is not None
            assert identity.encrypted_institutional_student_id is not None
            assert identity.email_fingerprint is not None
            assert identity.institutional_id_fingerprint is not None

            # Verify ciphertext differs from plaintext
            assert UNIQUE_FIRSTNAME not in identity.encrypted_first_name
            assert UNIQUE_LASTNAME not in identity.encrypted_last_name
            assert UNIQUE_EMAIL not in identity.encrypted_email
            assert UNIQUE_STUDENT_ID not in identity.encrypted_institutional_student_id

            # 2. anonymous_students
            anon = session.query(AnonymousStudent).first()
            assert anon is not None
            assert anon.anonymous_code.startswith("STU-")
            assert UNIQUE_FIRSTNAME not in anon.anonymous_code
            assert UNIQUE_EMAIL not in anon.anonymous_code

            # 3. import_batches
            batch = session.query(ImportBatch).first()
            assert batch is not None
            assert batch.imported_rows == 1
            assert batch.status == "completed"

            # 4. submissions
            submission = session.query(Submission).first()
            assert submission is not None

            # 5. responses - response content IS allowed here
            response = session.query(Response).first()
            assert response is not None
            assert response.response_text == "This is a student response"

            # 6. GradeRecord count is zero
            grade_count = session.query(GradeRecord).count()
            assert grade_count == 0

            # ── Raw SQL table scans for identity markers ──
            tables_to_scan = [
                "student_identities",
                "anonymous_students",
                "import_batches",
                "submissions",
                "grade_records",
            ]

            for table_name in tables_to_scan:
                inspector = inspect(engine)
                columns = [c["name"] for c in inspector.get_columns(table_name)]

                for col in columns:
                    # Skip columns that are expected to potentially contain content
                    if table_name == "responses" and col == "response_text":
                        continue
                    if col in ("created_at", "updated_at", "started_at", "completed_at",
                               "imported_at", "graded_at", "exported_at", "parse_started_at",
                               "parse_completed_at"):
                        continue
                    if col in ("id", "assessment_id", "student_identity_id", "anonymous_student_id",
                               "import_batch_id", "submission_id", "question_id", "response_id",
                               "material_id"):
                        continue
                    if col in ("score", "source_grade", "source_grade_maximum", "maximum_grade",
                               "duration_seconds"):
                        continue
                    if col in ("encryption_version", "total_rows", "imported_rows", "skipped_rows",
                               "warning_count", "error_count", "source_file_size",
                               "selected_table_index", "is_blank", "marked_for_review"):
                        continue
                    if col in ("status", "grading_status"):
                        continue
                    if col.endswith("_fingerprint"):
                        continue

                    # Scan this column for identity markers
                    match_count = session.execute(  # noqa: S608 — table/col from SQLAlchemy inspector, not user input
                        text(f"SELECT COUNT(*) FROM {table_name} WHERE {col} LIKE '%UNIQUE_FIRSTNAME_PHASE4_MARKER%' "  # noqa: S608
                             f"OR {col} LIKE '%UNIQUE_LASTNAME_PHASE4_MARKER%' "  # noqa: S608
                             f"OR {col} LIKE '%unique.phase4.identity@example.com%' "  # noqa: S608
                             f"OR {col} LIKE '%PHASE4-STUDENT-ID-0007%'")  # noqa: S608
                    ).scalar()
                    assert match_count == 0, (
                        f"Plaintext identity marker found in {table_name}.{col}"
                    )

        finally:
            session.close()
            engine.dispose()
