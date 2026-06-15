"""Secure import service unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

import pytest
from sqlalchemy.orm import Session

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
from security.encryption import decrypt_text, encrypt_text
from security.fingerprint import (
    fingerprint_email,
    fingerprint_institutional_id,
)
from security.key_validation import (
    generate_encryption_key,
    generate_fingerprint_key,
    load_encryption_key,
    load_fingerprint_key,
)
from services.secure_import_service import (
    compute_dry_run,
    execute_secure_import,
)

# ── helpers ────────────────────────────────────────────────────────

def _make_parsed_import(rows: tuple[ParsedStudentRow, ...]) -> ParsedImport:
    return ParsedImport(
        source_filename="test.html",
        parser_name="html_test",
        table_index=0,
        columns=(
            ParsedColumn(
                original_name="First name",
                normalized_name="first_name",
                index=0,
                classification=ColumnClassification.IDENTITY,
                mapped_field="first_name",
                is_required=True,
                confidence=1.0,
            ),
            ParsedColumn(
                original_name="Email",
                normalized_name="email",
                index=1,
                classification=ColumnClassification.IDENTITY,
                mapped_field="email",
                is_required=True,
                confidence=1.0,
            ),
            ParsedColumn(
                original_name="Response 1",
                normalized_name="response_1",
                index=2,
                classification=ColumnClassification.RESPONSE,
                mapped_field="response_1",
                is_required=True,
                confidence=1.0,
                response_number=1,
            ),
            ParsedColumn(
                original_name="Response 2",
                normalized_name="response_2",
                index=3,
                classification=ColumnClassification.RESPONSE,
                mapped_field="response_2",
                is_required=True,
                confidence=1.0,
                response_number=2,
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
            response_column_count=2,
            duplicate_email_count=0,
        ),
        candidate_tables=(),
        parse_started_at=datetime.now(UTC),
        parse_completed_at=datetime.now(UTC),
    )


def _make_row(
    row_number: int,
    first_name: str = "Test",
    last_name: str = "User",
    email: str = "test@example.com",
    student_id: str | None = None,
    responses: tuple[str, ...] = ("Answer 1", "Answer 2"),
) -> ParsedStudentRow:
    return ParsedStudentRow(
        row_number=row_number,
        first_name=first_name,
        last_name=last_name,
        email=email,
        institutional_student_id=student_id,
        status="finished",
        started=datetime.now(UTC),
        completed=datetime.now(UTC),
        duration_seconds=300,
        source_grade=Decimal("15.5"),
        raw_source_grade="15.5 / 20",
        source_grade_maximum=Decimal("20"),
        responses=tuple(
            ParsedResponse(
                question_number=i + 1,
                column_name=f"Response {i+1}",
                text=resp,
                is_blank=not resp,
            )
            for i, resp in enumerate(responses)
        ),
        unknown_values={},
    )


def _setup_assessment(session: Session) -> tuple[Material, Assessment, Question, Question]:
    material = Material(name="Test Material")
    session.add(material)
    session.flush()

    assessment = Assessment(
        material_id=material.id,
        title="Test Assessment",
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
    q2 = Question(
        assessment_id=assessment.id,
        question_number=2,
        maximum_grade=Decimal("10"),
        title="Q2",
    )
    session.add_all([q1, q2])
    session.flush()

    return material, assessment, q1, q2


# ── Tests ──────────────────────────────────────────────────────────

class TestComputeDryRun:
    def test_dry_run_counts(self, session: Session, monkeypatch) -> None:
        """compute_dry_run handles missing keys gracefully."""
        monkeypatch.delenv("IDENTITY_ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("IDENTITY_FINGERPRINT_KEY", raising=False)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1)
        parsed = _make_parsed_import((row,))
        file_bytes = b"test content"
        file_hash = sha256(file_bytes).hexdigest()

        summary = compute_dry_run(parsed, session, assessment.id, file_hash)
        assert summary.keys_available is False
        assert summary.rows_ready > 0


class TestExecuteSecureImport:
    def test_import_one_new_student(self, session: Session, monkeypatch) -> None:
        """Import one new student successfully."""
        # Set up keys in environment
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Alice", "Smith", "alice@example.com", "ID001")
        parsed = _make_parsed_import((row,))
        file_bytes = b"test file content"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        assert result.imported_student_count == 1
        assert result.new_identity_count == 1
        assert result.matched_identity_count == 0
        assert result.submission_count == 1
        assert result.response_count == 2
        assert result.status == "completed"

    def test_import_multiple_students(self, session: Session, monkeypatch) -> None:
        """Import multiple students."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        rows = (
            _make_row(1, "Alice", "Smith", "alice@example.com", "ID001"),
            _make_row(2, "Bob", "Jones", "bob@example.com", "ID002"),
        )
        parsed = _make_parsed_import(rows)
        file_bytes = b"test multiple"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        assert result.imported_student_count == 2
        assert result.new_identity_count == 2
        assert result.submission_count == 2
        assert result.response_count == 4

    def test_arabic_identity_encryption(self, session: Session, monkeypatch) -> None:
        """Arabic identity fields encrypt/decrypt properly."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        enc_key = load_encryption_key(enc_key_str)
        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "أحمد", "محمد", "ahmed@example.com", "ID100")
        parsed = _make_parsed_import((row,))
        file_bytes = b"arabic test"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        assert result.imported_student_count == 1

        # Verify the encrypted data decrypts correctly
        identity = session.query(StudentIdentity).first()
        assert identity is not None
        first_name = decrypt_text(enc_key, identity.encrypted_first_name)
        assert first_name == "أحمد"

    def test_unicode_response_persistence(self, session: Session, monkeypatch) -> None:
        """Unicode responses are persisted correctly."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, responses=("مرحبا", "العالم"))
        parsed = _make_parsed_import((row,))
        file_bytes = b"unicode test"

        execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        responses = session.query(Response).all()
        texts = {r.response_text for r in responses}
        assert "مرحبا" in texts
        assert "العالم" in texts

    def test_blank_response_persistence(self, session: Session, monkeypatch) -> None:
        """Blank responses are persisted correctly."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, responses=("Answer 1", ""))
        parsed = _make_parsed_import((row,))
        file_bytes = b"blank test"

        execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        responses = session.query(Response).order_by(Response.question_id).all()
        blank_responses = [r for r in responses if r.is_blank]
        assert len(blank_responses) == 1

    def test_match_by_institutional_id(self, session: Session, monkeypatch) -> None:
        """Match by institutional ID on reimport."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        fp_key = load_fingerprint_key(fp_key_str)

        # Pre-create identity
        identity = StudentIdentity(
            encrypted_first_name="enc:Existing",
            encrypted_email="enc:existing@example.com",
            encrypted_institutional_student_id="enc:ID100",
            institutional_id_fingerprint=fingerprint_institutional_id("ID100", fp_key),
        )
        session.add(identity)
        session.flush()

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Existing", "User", "existing@example.com", "ID100")
        parsed = _make_parsed_import((row,))
        file_bytes = b"match id test"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        assert result.matched_identity_count == 1
        assert result.new_identity_count == 0
        assert result.imported_student_count == 1

    def test_duplicate_file_blocked(self, session: Session, monkeypatch) -> None:
        """Duplicate file import is blocked."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1)
        parsed = _make_parsed_import((row,))
        file_bytes = b"same content"

        result1 = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )
        assert result1.imported_student_count == 1

        with pytest.raises(ValueError, match="already been imported"):
            execute_secure_import(
                session=session,
                parsed=parsed,
                assessment_id=assessment.id,
                assessment_question_numbers=(1, 2),
                file_bytes=file_bytes,
                source_filename="test.html",
                table_index=0,
            )

    def test_missing_encryption_key_blocks_import(self, session: Session, monkeypatch) -> None:
        """Missing encryption key raises error."""
        monkeypatch.delenv("IDENTITY_ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("IDENTITY_FINGERPRINT_KEY", raising=False)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1)
        parsed = _make_parsed_import((row,))
        file_bytes = b"test"

        from security.exceptions import MissingEncryptionKeyError
        with pytest.raises((MissingEncryptionKeyError, ValueError)):
            execute_secure_import(
                session=session,
                parsed=parsed,
                assessment_id=assessment.id,
                assessment_question_numbers=(1, 2),
                file_bytes=file_bytes,
                source_filename="test.html",
                table_index=0,
            )

    def test_grade_record_remains_empty(self, session: Session, monkeypatch) -> None:
        """GradeRecord table remains empty after import."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1)
        parsed = _make_parsed_import((row,))
        file_bytes = b"grade test"

        execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        grade_count = session.query(GradeRecord).count()
        assert grade_count == 0

    def test_import_batch_counts_accurate(self, session: Session, monkeypatch) -> None:
        """ImportBatch counts are accurate."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        rows = (
            _make_row(1, "Alice", "Smith", "alice@example.com", "ID001"),
            _make_row(2, "Bob", "Jones", "bob@example.com", "ID002"),
        )
        parsed = _make_parsed_import(rows)
        file_bytes = b"batch counts"

        execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        batch = session.query(ImportBatch).first()
        assert batch is not None
        assert batch.imported_rows == 2
        assert batch.skipped_rows == 0
        assert batch.total_rows == 2
        assert batch.status == "completed"
        assert batch.completed_at is not None

    def test_fingerprints_and_anonymous_code_created(self, session: Session, monkeypatch) -> None:
        """Verify fingerprints and anonymous code are created."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        fp_key = load_fingerprint_key(fp_key_str)
        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Alice", "Smith", "alice@example.com", "ID001")
        parsed = _make_parsed_import((row,))
        file_bytes = b"fingerprint test"

        execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        # Verify StudentIdentity has fingerprints
        identity = session.query(StudentIdentity).first()
        assert identity is not None
        assert identity.email_fingerprint is not None
        assert identity.institutional_id_fingerprint is not None
        expected_email_fp = fingerprint_email("alice@example.com", fp_key)
        expected_id_fp = fingerprint_institutional_id("ID001", fp_key)
        assert identity.email_fingerprint == expected_email_fp
        assert identity.institutional_id_fingerprint == expected_id_fp

        # Verify AnonymousStudent created with STU-XXXXXXXX
        anon = session.query(AnonymousStudent).first()
        assert anon is not None
        assert anon.anonymous_code.startswith("STU-")
        assert len(anon.anonymous_code) == 12

        # Verify Submission exists
        sub = session.query(Submission).first()
        assert sub is not None
        assert sub.status == "imported" or sub.status == "finished"

    def test_match_by_normalized_email(self, session: Session, monkeypatch) -> None:
        """Match by normalized email on reimport."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        fp_key = load_fingerprint_key(fp_key_str)
        enc_key = load_encryption_key(enc_key_str)

        # Pre-create identity with normalized email fingerprint
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Alice"),
            encrypted_last_name=encrypt_text(enc_key, "Smith"),
            encrypted_email=encrypt_text(enc_key, "alice@example.com"),
            email_fingerprint=fingerprint_email("alice@example.com", fp_key),
        )
        session.add(identity)
        session.flush()

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        # Reimport with different case — should match via normalized fingerprint
        row = _make_row(1, "Alice", "Smith", "ALICE@EXAMPLE.COM", None)
        parsed = _make_parsed_import((row,))
        file_bytes = b"normalized email test"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        assert result.matched_identity_count == 1
        assert result.new_identity_count == 0

    def test_institutional_id_takes_precedence(self, session: Session, monkeypatch) -> None:
        """ID match returns MATCHED_BY_INSTITUTIONAL_ID even when email also matches."""
        from services.identity_matching_service import MatchResultType, find_matching_identity

        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        fp_key = load_fingerprint_key(fp_key_str)
        enc_key = load_encryption_key(enc_key_str)

        # Create one identity with both fingerprints
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Alice"),
            encrypted_institutional_student_id=encrypt_text(enc_key, "ID001"),
            encrypted_email=encrypt_text(enc_key, "alice@example.com"),
            institutional_id_fingerprint=fingerprint_institutional_id("ID001", fp_key),
            email_fingerprint=fingerprint_email("alice@example.com", fp_key),
        )
        session.add(identity)
        session.flush()

        # Directly test the matching function
        match = find_matching_identity(session, "ID001", "alice@example.com", fp_key)
        assert match.result_type == MatchResultType.MATCHED_BY_INSTITUTIONAL_ID
        assert match.existing_identity_id == identity.id

        # Also verify email-only match works
        match_email = find_matching_identity(session, None, "alice@example.com", fp_key)
        assert match_email.result_type == MatchResultType.MATCHED_BY_EMAIL
        assert match_email.existing_identity_id == identity.id

    def test_anonymous_student_reused(self, session: Session, monkeypatch) -> None:
        """AnonymousStudent reused when same identity imported again."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        fp_key = load_fingerprint_key(fp_key_str)
        enc_key = load_encryption_key(enc_key_str)

        # Pre-create identity and anonymous student
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Alice"),
            encrypted_email=encrypt_text(enc_key, "alice@example.com"),
            encrypted_institutional_student_id=encrypt_text(enc_key, "ID001"),
            email_fingerprint=fingerprint_email("alice@example.com", fp_key),
            institutional_id_fingerprint=fingerprint_institutional_id("ID001", fp_key),
        )
        session.add(identity)
        session.flush()

        anon1 = AnonymousStudent(
            student_identity_id=identity.id,
            anonymous_code="STU-EXISTING",
        )
        session.add(anon1)
        session.flush()

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Alice", "Smith", "alice@example.com", "ID001")
        parsed = _make_parsed_import((row,))
        file_bytes = b"reuse test"

        execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        # AnonymousStudent should be reused
        anon_count = session.query(AnonymousStudent).count()
        assert anon_count == 1
        anon_found = session.query(AnonymousStudent).first()
        assert anon_found is not None
        assert anon_found.anonymous_code == "STU-EXISTING"

    def test_duplicate_submission_blocked(self, session: Session, monkeypatch) -> None:
        """Duplicate submission per assessment/student blocked."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Alice", "Smith", "alice@example.com", "ID001")
        parsed = _make_parsed_import((row,))
        file_bytes = b"dup sub test"

        # First import succeeds
        result1 = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )
        assert result1.imported_student_count == 1
        assert result1.submission_count == 1

        # Second import with same data — submission should be skipped (duplicate)
        file_bytes2 = b"dup sub test 2"
        result2 = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes2,
            source_filename="test2.html",
            table_index=0,
        )
        # The student is the same, so submission is duplicate -> skipped
        assert result2.skipped_row_count == 1
        assert result2.submission_count == 0
        # But identity should be matched
        assert result2.matched_identity_count == 1

    def test_mapping_conflict_blocks_import(self, session: Session, monkeypatch) -> None:
        """Mapping conflict (no identity columns) blocks import."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        # Create parsed import with only response columns — no identity
        parsed = ParsedImport(
            source_filename="test.html",
            parser_name="html_test",
            table_index=0,
            columns=(
                ParsedColumn(
                    "Response 1", "response_1", 0,
                    ColumnClassification.RESPONSE, "response_1", True, 1.0,
                    response_number=1,
                ),
            ),
            rows=(_make_row(1),),
            response_columns=(),
            unknown_columns=(),
            warnings=(),
            errors=(),
            statistics=ImportStatistics(
                total_rows=1, valid_rows=1, warning_rows=0, error_rows=0,
                blank_response_count=0, response_column_count=1,
                duplicate_email_count=0,
            ),
            candidate_tables=(),
            parse_started_at=datetime.now(UTC),
            parse_completed_at=datetime.now(UTC),
        )

        with pytest.raises(ValueError, match="has errors"):
            execute_secure_import(
                session=session,
                parsed=parsed,
                assessment_id=assessment.id,
                assessment_question_numbers=(1, 2),
                file_bytes=b"test",
                source_filename="test.html",
                table_index=0,
            )

    def test_reconciliation_conflict_blocks_import(self, session: Session, monkeypatch) -> None:
        """Reconciliation conflict (mismatched questions) blocks import."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1)
        parsed = _make_parsed_import((row,))

        with pytest.raises(ValueError, match="unresolved"):
            execute_secure_import(
                session=session,
                parsed=parsed,
                assessment_id=assessment.id,
                assessment_question_numbers=(99,),  # wrong question numbers
                file_bytes=b"test",
                source_filename="test.html",
                table_index=0,
            )

    def test_ambiguous_identity_blocks_import(self, session: Session, monkeypatch) -> None:
        """Ambiguous identity (ID and email match different identities) blocks import."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        fp_key = load_fingerprint_key(fp_key_str)
        enc_key = load_encryption_key(enc_key_str)

        # Create two identities — one matches ID, another matches email
        identity_a = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Alice"),
            encrypted_institutional_student_id=encrypt_text(enc_key, "ID001"),
            institutional_id_fingerprint=fingerprint_institutional_id("ID001", fp_key),
        )
        identity_b = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Bob"),
            encrypted_email=encrypt_text(enc_key, "alice@example.com"),
            email_fingerprint=fingerprint_email("alice@example.com", fp_key),
        )
        session.add_all([identity_a, identity_b])
        session.flush()

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        # Row has both ID001 and alice@example.com — ambiguous since they belong to different identities
        row = _make_row(1, "Alice", "Smith", "alice@example.com", "ID001")
        parsed = _make_parsed_import((row,))
        file_bytes = b"ambiguous test"

        # Without manual decisions, ambiguous identity should block (skip row)
        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        # Row should be skipped since identity is ambiguous and no manual decision
        assert result.skipped_row_count == 1
        assert result.imported_student_count == 0

    def test_manual_match_decision_works(self, session: Session, monkeypatch) -> None:
        """Manual match decision resolves ambiguity."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        fp_key = load_fingerprint_key(fp_key_str)
        enc_key = load_encryption_key(enc_key_str)

        # Create two identities
        identity_a = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Alice"),
            encrypted_institutional_student_id=encrypt_text(enc_key, "ID001"),
            institutional_id_fingerprint=fingerprint_institutional_id("ID001", fp_key),
        )
        identity_b = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Bob"),
            encrypted_email=encrypt_text(enc_key, "alice@example.com"),
            email_fingerprint=fingerprint_email("alice@example.com", fp_key),
        )
        session.add_all([identity_a, identity_b])
        session.flush()

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Alice", "Smith", "alice@example.com", "ID001")
        parsed = _make_parsed_import((row,))
        file_bytes = b"manual match test"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
            manual_decisions={"row:1": f"match:{identity_a.id}"},
        )

        assert result.imported_student_count == 1
        assert result.matched_identity_count == 1

    def test_manual_create_new_decision_works(self, session: Session, monkeypatch) -> None:
        """Manual create-new decision creates a new identity."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        # No pre-existing identity — row has no ID or email
        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Charlie", "Brown")
        row = ParsedStudentRow(
            row_number=1,
            first_name="Charlie",
            last_name="Brown",
            email=None,
            institutional_student_id=None,
            status=None,
            started=None,
            completed=None,
            duration_seconds=None,
            source_grade=None,
            raw_source_grade=None,
            source_grade_maximum=None,
            responses=(),
            unknown_values={},
        )
        parsed = _make_parsed_import((row,))
        file_bytes = b"manual create test"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
            manual_decisions={"row:1": "create_new"},
        )

        assert result.imported_student_count == 1
        assert result.new_identity_count == 1

    def test_manual_skip_decision_works(self, session: Session, monkeypatch) -> None:
        """Manual skip decision skips the row."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Charlie", "Brown")
        row = ParsedStudentRow(
            row_number=1,
            first_name="Charlie",
            last_name="Brown",
            email=None,
            institutional_student_id=None,
            status=None,
            started=None,
            completed=None,
            duration_seconds=None,
            source_grade=None,
            raw_source_grade=None,
            source_grade_maximum=None,
            responses=(),
            unknown_values={},
        )
        parsed = _make_parsed_import((row,))
        file_bytes = b"manual skip test"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
            manual_decisions={"row:1": "skip"},
        )

        assert result.imported_student_count == 0
        assert result.skipped_row_count == 1

    def test_transaction_rollback_on_failure(self, session: Session, monkeypatch) -> None:
        """Failed import rolls back all created records."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1)
        parsed = _make_parsed_import((row,))
        file_bytes = b"rollback test"

        # Force a failure by providing wrong question numbers
        with pytest.raises(ValueError):
            execute_secure_import(
                session=session,
                parsed=parsed,
                assessment_id=assessment.id,
                assessment_question_numbers=(99,),
                file_bytes=file_bytes,
                source_filename="test.html",
                table_index=0,
            )

        # No records should exist
        assert session.query(StudentIdentity).count() == 0
        assert session.query(AnonymousStudent).count() == 0
        assert session.query(ImportBatch).count() == 0
        assert session.query(Submission).count() == 0
        assert session.query(Response).count() == 0

    def test_unfinished_submission_metadata(self, session: Session, monkeypatch) -> None:
        """Unfinished submission metadata persisted."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        from datetime import timedelta
        started = datetime.now(UTC) - timedelta(hours=1)

        row = ParsedStudentRow(
            row_number=1,
            first_name="Alice",
            last_name="Smith",
            email="alice@example.com",
            institutional_student_id="ID001",
            status="unfinished",
            started=started,
            completed=None,
            duration_seconds=None,
            source_grade=None,
            raw_source_grade=None,
            source_grade_maximum=None,
            responses=(),
            unknown_values={},
        )
        parsed = _make_parsed_import((row,))
        file_bytes = b"unfinished test"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        assert result.imported_student_count == 1

        sub = session.query(Submission).first()
        assert sub is not None
        assert sub.status == "unfinished"
        assert sub.started_at is not None
        assert sub.completed_at is None
        assert sub.duration_seconds is None

    def test_source_grade_informational(self, session: Session, monkeypatch) -> None:
        """Source grade stored but GradeRecord remains empty."""
        enc_key_str = generate_encryption_key()
        fp_key_str = generate_fingerprint_key()
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", enc_key_str)
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", fp_key_str)

        material, assessment, q1, q2 = _setup_assessment(session)
        session.flush()

        row = _make_row(1, "Alice", "Smith", "alice@example.com", "ID001",
                         responses=("Answer 1", "Answer 2"))
        parsed = _make_parsed_import((row,))
        file_bytes = b"source grade test"

        result = execute_secure_import(
            session=session,
            parsed=parsed,
            assessment_id=assessment.id,
            assessment_question_numbers=(1, 2),
            file_bytes=file_bytes,
            source_filename="test.html",
            table_index=0,
        )

        assert result.imported_student_count == 1

        # Source grade stored on submission
        sub = session.query(Submission).first()
        assert sub is not None
        assert sub.source_grade == Decimal("15.5")

        # GradeRecord remains empty
        assert session.query(GradeRecord).count() == 0
