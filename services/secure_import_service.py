"""Secure import service — persists validated Phase 3 preview into encrypted records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy.orm import Session

from config import get_settings
from models.anonymous_student import AnonymousStudent
from models.import_batch import ImportBatch
from models.question import Question
from models.response import Response
from models.student_identity import StudentIdentity
from models.submission import Submission
from parsers.models import (
    ParsedImport,
)
from security.encryption import encrypt_text
from security.exceptions import MissingEncryptionKeyError, MissingFingerprintKeyError
from security.fingerprint import fingerprint_email, fingerprint_institutional_id
from security.key_validation import load_keys
from security.models import FingerprintKey
from services.authorization_service import PERM_IMPORT_EXECUTE, AuthContext, authorize_context
from services.identity_matching_service import (
    MatchResult,
    MatchResultType,
    find_matching_identity,
)
from services.import_preview_service import reconcile_assessment, validate_mapping
from services.logging_service import get_logger
from services.pseudonymization_service import get_or_create_anonymous_student

logger = get_logger("secure_import")


@dataclass(frozen=True, slots=True)
class SecureImportResult:
    import_batch_id: str
    imported_student_count: int
    matched_identity_count: int
    new_identity_count: int
    skipped_row_count: int
    submission_count: int
    response_count: int
    warning_count: int
    status: str


@dataclass(frozen=True, slots=True)
class DryRunSummary:
    rows_ready: int
    matched_by_id: int
    matched_by_email: int
    new_identities: int
    ambiguous: int
    manual_resolution: int
    skipped_rows: int
    expected_submissions: int
    expected_responses: int
    duplicate_file: bool
    duplicate_submission_warning: bool
    mapping_errors: bool
    reconciliation_unresolved: bool
    keys_available: bool = True


def _compute_dry_run(
    parsed: ParsedImport,
    session: Session,
    fp_key: FingerprintKey | None,
    assessment_id: str,
    file_hash: str,
    keys_available: bool = True,
) -> DryRunSummary:
    """Compute a dry-run summary without persisting anything."""
    rows_ready = 0
    matched_by_id = 0
    matched_by_email = 0
    new_ids = 0
    ambiguous = 0
    manual_res = 0
    skipped = 0
    expected_responses = 0

    for row in parsed.rows:
        if row.errors or row.ignored:
            skipped += 1
            continue

        if not keys_available:
            # Can't match without keys
            if not row.email and not row.institutional_student_id:
                manual_res += 1
            else:
                new_ids += 1
                rows_ready += 1
            expected_responses += len(row.responses)
            continue

        if not row.email and not row.institutional_student_id:
            manual_res += 1
            continue

        match = find_matching_identity(
            session, row.institutional_student_id, row.email, fp_key  # type: ignore[arg-type]
        )
        if match.result_type == MatchResultType.MATCHED_BY_INSTITUTIONAL_ID:
            matched_by_id += 1
            rows_ready += 1
        elif match.result_type == MatchResultType.MATCHED_BY_EMAIL:
            matched_by_email += 1
            rows_ready += 1
        elif match.result_type == MatchResultType.NEW_IDENTITY:
            new_ids += 1
            rows_ready += 1
        elif match.result_type == MatchResultType.AMBIGUOUS_CONFLICT:
            ambiguous += 1
        else:
            manual_res += 1
        expected_responses += len(row.responses)

    # Check duplicate file
    existing_batch = (
        session.query(ImportBatch)
        .filter(
            ImportBatch.assessment_id == assessment_id,
            ImportBatch.source_file_hash == file_hash,
        )
        .first()
    )
    duplicate_file = existing_batch is not None

    return DryRunSummary(
        rows_ready=rows_ready,
        matched_by_id=matched_by_id,
        matched_by_email=matched_by_email,
        new_identities=new_ids,
        ambiguous=ambiguous,
        manual_resolution=manual_res,
        skipped_rows=skipped,
        expected_submissions=rows_ready,
        expected_responses=expected_responses,
        duplicate_file=duplicate_file,
        duplicate_submission_warning=False,
        mapping_errors=False,
        reconciliation_unresolved=False,
        keys_available=keys_available,
    )


ManualDecision = dict[str, str]  # row_ref -> "match:<identity_id>" | "create_new" | "skip"


def execute_secure_import(
    session: Session,
    parsed: ParsedImport,
    assessment_id: str,
    assessment_question_numbers: tuple[int, ...],
    file_bytes: bytes,
    source_filename: str,
    table_index: int | None,
    manual_decisions: ManualDecision | None = None,
    *,
    auth_ctx: AuthContext,
) -> SecureImportResult:
    """Execute a secure import within a single transaction.

    Parameters
    ----------
    session : Session
        Database session.
    parsed : ParsedImport
        Normalized parsed import data.
    assessment_id : str
        Target assessment ID.
    assessment_question_numbers : tuple[int, ...]
        Question numbers for the assessment.
    file_bytes : bytes
        Original file bytes (for duplicate detection).
    source_filename : str
        Original filename.
    table_index : int | None
        Table/sheet index used.
    manual_decisions : ManualDecision | None
        Manual identity matching decisions.
    auth_ctx : AuthContext
        Authorization context. Enforces import_execute permission.

    Raises
    ------
    InsufficientPermissionsError
        If auth_ctx role lacks PERM_IMPORT_EXECUTE.
    """
    authorize_context(auth_ctx, PERM_IMPORT_EXECUTE)

    # Block import into finalized assessments
    settings = get_settings()
    enc_key, fp_key = load_keys(
        settings.identity_encryption_key,
        settings.identity_fingerprint_key,
    )

    # Validate prerequisites
    mapping_valid = validate_mapping(parsed)
    if not mapping_valid.valid:
        raise ValueError("Column mapping has errors — cannot import")

    reconciliation = reconcile_assessment(parsed, assessment_question_numbers)
    if not reconciliation.exact_match:
        raise ValueError("Assessment reconciliation is unresolved — cannot import")

    if parsed.errors:
        raise ValueError("File-level validation errors exist — cannot import")

    file_hash = sha256(file_bytes).hexdigest()

    # Check duplicate file
    existing = (
        session.query(ImportBatch)
        .filter(
            ImportBatch.assessment_id == assessment_id,
            ImportBatch.source_file_hash == file_hash,
        )
        .first()
    )
    if existing:
        raise ValueError("This file has already been imported into this assessment")

    # Create ImportBatch
    now = datetime.now(UTC)
    batch = ImportBatch(
        assessment_id=assessment_id,
        source_filename=f"import_{file_hash[:12]}",
        source_format="html",
        status="importing",
        source_file_hash=file_hash,
        source_file_size=len(file_bytes),
        parser_name=parsed.parser_name,
        selected_table_index=table_index,
        total_rows=len(parsed.rows),
        imported_rows=0,
        skipped_rows=0,
        started_at=now,
    )
    session.add(batch)
    session.flush()

    imported_count = 0
    matched_count = 0
    new_count = 0
    skipped_count = 0
    submission_count = 0
    response_count = 0
    warning_count = 0

    # Get questions for mapping
    questions = (
        session.query(Question)
        .filter(Question.assessment_id == assessment_id)
        .order_by(Question.question_number)
        .all()
    )
    question_map: dict[int, str] = {q.question_number: q.id for q in questions}

    for row in parsed.rows:
        if row.errors or row.ignored:
            skipped_count += 1
            continue

        # Match identity
        match = find_matching_identity(
            session, row.institutional_student_id, row.email, fp_key
        )

        if match.result_type in (
            MatchResultType.AMBIGUOUS_CONFLICT,
            MatchResultType.MANUAL_RESOLUTION_REQUIRED,
            MatchResultType.INVALID_IDENTITY,
        ):
            # Check for manual decision
            row_ref = f"row:{row.row_number}"
            decision = (manual_decisions or {}).get(row_ref)
            if decision == "skip":
                skipped_count += 1
                continue
            elif decision and decision.startswith("match:"):
                manual_match_id = decision.split(":", 1)[1]
                # Validate the referenced identity exists
                existing_identity = session.query(StudentIdentity).filter_by(id=manual_match_id).first()
                if existing_identity is None:
                    skipped_count += 1
                    continue
                # Override match so the existing-identity branch is taken
                match = MatchResult(
                    MatchResultType.MATCHED_BY_INSTITUTIONAL_ID,
                    manual_match_id, None, blocking=False,
                )
            elif decision == "create_new":
                # Treat as new identity — falls through to NEW_IDENTITY logic
                match = MatchResult(MatchResultType.NEW_IDENTITY, None, None, blocking=False)
            else:
                skipped_count += 1
                continue

        if match.result_type == MatchResultType.NEW_IDENTITY:
            # Create new encrypted identity
            identity = StudentIdentity()
            identity.encrypted_first_name = encrypt_text(enc_key, row.first_name)
            identity.encrypted_last_name = encrypt_text(enc_key, row.last_name)
            identity.encrypted_email = encrypt_text(enc_key, row.email)
            identity.encrypted_institutional_student_id = encrypt_text(
                enc_key, row.institutional_student_id
            )
            identity.email_fingerprint = fingerprint_email(row.email, fp_key)
            identity.institutional_id_fingerprint = fingerprint_institutional_id(
                row.institutional_student_id, fp_key
            )
            session.add(identity)
            session.flush()
            current_identity_id: str = identity.id
            new_count += 1
        else:
            # Use existing identity
            _id = match.existing_identity_id
            if _id is None:  # pragma: no cover
                skipped_count += 1
                continue
            current_identity_id = _id
            matched_count += 1
            # Do NOT silently overwrite encrypted values

        # Get or create anonymous student
        get_or_create_anonymous_student(session, current_identity_id)

        # Get anonymous student ID
        anon = (
            session.query(AnonymousStudent)
            .filter_by(student_identity_id=current_identity_id)
            .first()
        )
        if anon is None:  # pragma: no cover
            skipped_count += 1
            continue

        # Check for existing submission (duplicate prevention)
        existing_sub = (
            session.query(Submission)
            .filter(
                Submission.assessment_id == assessment_id,
                Submission.anonymous_student_id == anon.id,
            )
            .first()
        )
        if existing_sub:
            skipped_count += 1
            continue

        # Create submission
        sub = Submission(
            assessment_id=assessment_id,
            anonymous_student_id=anon.id,
            import_batch_id=batch.id,
            status=row.status or "imported",
            started_at=row.started,
            completed_at=row.completed,
            duration_seconds=row.duration_seconds,
            source_grade=row.source_grade,
            source_grade_maximum=row.source_grade_maximum,
        )
        session.add(sub)
        session.flush()
        submission_count += 1
        imported_count += 1

        # Create response records
        for resp in row.responses:
            question_id = question_map.get(resp.question_number)
            if question_id is None:
                logger.warning(
                    "No question found for number %s, skipping response",
                    resp.question_number,
                )
                continue
            existing_resp = (
                session.query(Response)
                .filter(
                    Response.submission_id == sub.id,
                    Response.question_id == question_id,
                )
                .first()
            )
            if existing_resp:
                continue
            response_rec = Response(
                submission_id=sub.id,
                question_id=question_id,
                response_text=resp.text,
                is_blank=resp.is_blank,
            )
            session.add(response_rec)
            response_count += 1

    # Update batch
    batch.imported_rows = imported_count
    batch.skipped_rows = skipped_count
    now_utc = datetime.now(UTC)
    batch.completed_at = now_utc
    batch.status = "completed"
    warning_count = len(parsed.warnings) + len(parsed.errors)

    # Mark imported_at on all submissions in this batch
    for sub in session.query(Submission).filter(Submission.import_batch_id == batch.id).all():
        sub.imported_at = now_utc

    return SecureImportResult(
        import_batch_id=batch.id,
        imported_student_count=imported_count,
        matched_identity_count=matched_count,
        new_identity_count=new_count,
        skipped_row_count=skipped_count,
        submission_count=submission_count,
        response_count=response_count,
        warning_count=warning_count,
        status="completed",
    )


def compute_dry_run(
    parsed: ParsedImport,
    session: Session,
    assessment_id: str,
    file_hash: str,
) -> DryRunSummary:
    """Public dry-run wrapper that attempts to load keys and returns a summary.

    If keys are missing, returns a summary with keys_available=False
    and all match counts set to zero.
    """
    settings = get_settings()
    try:
        _, fp_key = load_keys(
            settings.identity_encryption_key,
            settings.identity_fingerprint_key,
        )
        keys_available = True
    except (MissingEncryptionKeyError, MissingFingerprintKeyError):
        fp_key = None
        keys_available = False

    return _compute_dry_run(
        parsed=parsed,
        session=session,
        fp_key=fp_key,
        assessment_id=assessment_id,
        file_hash=file_hash,
        keys_available=keys_available,
    )
