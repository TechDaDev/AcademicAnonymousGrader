# Academic Anonymous Grader — Finalization Service
"""Service layer for assessment finalization.

SAFETY: This service must never query or expose StudentIdentity.
All finalization uses anonymous codes only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.orm import joinedload

from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.question import Question
from models.submission import Submission
from services.authorization_service import PERM_FINALIZE_ASSESSMENT, AuthContext, authorize_context
from services.exceptions import (
    AssessmentAlreadyFinalizedError,
    AssessmentNotReadyForFinalizationError,
)
from services.logging_service import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger("finalization")


# ── Typed result objects ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ValidationMessage:
    type: str  # "error" or "warning"
    message: str
    code: str


@dataclass(frozen=True, slots=True)
class FinalizationReadiness:
    assessment_id: str
    total_submissions: int
    approved_submissions: int
    blocking_errors: list[ValidationMessage] = field(default_factory=list)
    warnings: list[ValidationMessage] = field(default_factory=list)
    is_ready: bool = False


@dataclass(frozen=True, slots=True)
class FinalizedSubmissionSummary:
    submission_id: str
    anonymous_code: str
    final_grade: Decimal
    maximum_grade: Decimal
    review_status: str


@dataclass(frozen=True, slots=True)
class FinalizationResult:
    assessment_id: str
    finalized_at: datetime
    submission_count: int
    final_grade_total: Decimal
    status: str
    warning_count: int


@dataclass(frozen=True, slots=True)
class FinalizedAssessmentSummary:
    assessment_id: str
    title: str
    status: str
    finalized_at: datetime | None
    total_submissions: int
    approved_submissions: int
    average_grade: Decimal
    minimum_grade: Decimal
    maximum_grade: Decimal
    final_grade_total: Decimal
    maximum_total: Decimal


# ── Internal helpers ──────────────────────────────────────────────


def _get_assessment(session: Session, assessment_id: str) -> Assessment:
    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        msg = f"Assessment {assessment_id} not found"
        raise AssessmentNotReadyForFinalizationError(msg)
    return assessment


def _get_questions(session: Session, assessment_id: str) -> list[Question]:
    return (
        session.query(Question)
        .filter(Question.assessment_id == assessment_id)
        .order_by(Question.question_number)
        .all()
    )


def _get_submissions(session: Session, assessment_id: str) -> list[Submission]:
    return (
        session.query(Submission)
        .filter(Submission.assessment_id == assessment_id)
        .options(joinedload(Submission.anonymous_student))
        .order_by(Submission.id)
        .all()
    )


def _get_grade_map(session: Session, submission_id: str) -> dict[str, GradeRecord]:
    records = (
        session.query(GradeRecord)
        .filter(GradeRecord.submission_id == submission_id)
        .all()
    )
    return {r.question_id: r for r in records}


# ── Public API ────────────────────────────────────────────────────


def get_finalization_readiness(
    session: Session,
    assessment_id: str,
) -> FinalizationReadiness:
    """Check whether an assessment is ready for finalization."""
    assessment = _get_assessment(session, assessment_id)
    questions = _get_questions(session, assessment_id)
    submissions = _get_submissions(session, assessment_id)

    errors: list[ValidationMessage] = []
    warnings_list: list[ValidationMessage] = []

    # FA001: No questions
    if not questions:
        errors.append(ValidationMessage(
            type="error", message="Assessment has no questions defined.", code="FA001",
        ))

    # FA002: Question total mismatch
    if questions:
        question_total = sum((q.maximum_grade for q in questions), Decimal("0"))
        if question_total != assessment.maximum_grade:
            errors.append(ValidationMessage(
                type="error",
                message=(
                    f"Question total ({question_total}) does not match "
                    f"assessment maximum ({assessment.maximum_grade})."
                ),
                code="FA002",
            ))

    # FA003: No submissions
    if not submissions:
        errors.append(ValidationMessage(
            type="error", message="Assessment has no submissions.", code="FA003",
        ))

    approved_count = 0

    # Phase 10 — Check for active grading claims (FA012)
    active_claims = (
        session.query(Submission)
        .filter(
            Submission.assessment_id == assessment_id,
            Submission.assigned_grader_user_id.isnot(None),
            Submission.grading_lock_expires_at > datetime.now(UTC),
        )
        .count()
    )
    if active_claims > 0:
        errors.append(ValidationMessage(
            type="error",
            message=f"{active_claims} active grading claim(s) must be released before finalization.",
            code="FA012",
        ))

    # Phase 10 — Check for ungraded submissions (not draft, not graded, not approved)
    ungraded = sum(
        1 for s in submissions
        if s.grading_status == "pending" and s.review_status not in ("approved", "needs_correction")
    )
    if ungraded > 0:
        errors.append(ValidationMessage(
            type="error",
            message=f"{ungraded} submission(s) remain ungraded.",
            code="FA013",
        ))

    for sub in submissions:
        sid_prefix = sub.id[:8]

        # FA004: No anonymous student
        if sub.anonymous_student is None:
            errors.append(ValidationMessage(
                type="error",
                message=f"Submission {sid_prefix} has no anonymous student.",
                code="FA004",
            ))
            continue

        # FA005: Not approved
        if sub.review_status != "approved":
            errors.append(ValidationMessage(
                type="error",
                message=(
                    f"Submission {sub.anonymous_student.anonymous_code} "
                    f"is not approved (status={sub.review_status})."
                ),
                code="FA005",
            ))
            continue

        grade_map = _get_grade_map(session, sub.id)

        for q in questions:
            gr = grade_map.get(q.id)

            # FA006: Missing GradeRecord
            if gr is None:
                errors.append(ValidationMessage(
                    type="error",
                    message=(
                        f"Submission {sub.anonymous_student.anonymous_code} "
                        f"Q{q.question_number}: missing GradeRecord."
                    ),
                    code="FA006",
                ))
                continue

            # FA007: Null grade
            if gr.grade is None:
                errors.append(ValidationMessage(
                    type="error",
                    message=f"Submission {sub.anonymous_student.anonymous_code} Q{q.question_number}: grade is null.",
                    code="FA007",
                ))

            # FA008: Grade below zero
            if gr.grade is not None and gr.grade < Decimal("0"):
                errors.append(ValidationMessage(
                    type="error",
                    message=f"Submission {sub.anonymous_student.anonymous_code} Q{q.question_number}: "
                            f"grade {gr.grade} is negative.",
                    code="FA008",
                ))

            # FA009: Grade above max
            if gr.grade is not None and gr.grade > q.maximum_grade:
                errors.append(ValidationMessage(
                    type="error",
                    message=f"Submission {sub.anonymous_student.anonymous_code} Q{q.question_number}: "
                            f"grade {gr.grade} exceeds max {q.maximum_grade}.",
                    code="FA009",
                ))

            # FA010: Not graded
            if gr.grading_status != "graded":
                errors.append(ValidationMessage(
                    type="error",
                    message=f"Submission {sub.anonymous_student.anonymous_code} Q{q.question_number}: "
                            f"status is '{gr.grading_status}', not 'graded'.",
                    code="FA010",
                ))

        # FA011: Total exceeds max
        total_grade = Decimal("0")
        for q in questions:
            gr = grade_map.get(q.id)
            if gr is not None and gr.grade is not None:
                total_grade += gr.grade
        if total_grade > assessment.maximum_grade:
            errors.append(ValidationMessage(
                type="error",
                message=(
                    f"Submission {sub.anonymous_student.anonymous_code} total {total_grade} "
                    f"exceeds assessment max {assessment.maximum_grade}."
                ),
                code="FA011",
            ))

        approved_count += 1

    is_ready = len(errors) == 0

    return FinalizationReadiness(
        assessment_id=assessment_id,
        total_submissions=len(submissions),
        approved_submissions=approved_count,
        blocking_errors=errors,
        warnings=warnings_list,
        is_ready=is_ready,
    )


def validate_assessment_for_finalization(
    session: Session,
    assessment_id: str,
) -> FinalizationReadiness:
    """Alias for get_finalization_readiness."""
    return get_finalization_readiness(session, assessment_id)


def finalize_assessment(
    session: Session,
    assessment_id: str,
    finalization_note: str | None = None,
    *,
    auth_ctx: AuthContext,
) -> FinalizationResult:
    """Finalize an assessment if it passes readiness checks.

    Parameters
    ----------
    session : Session
        Database session.
    assessment_id : str
        Assessment ID to finalize.
    finalization_note : str | None
        Optional note.
    auth_ctx : AuthContext
        Authorization context. Enforces finalize_assessment permission.

    Raises
    ------
    InsufficientPermissionsError
        If auth_ctx role lacks PERM_FINALIZE_ASSESSMENT.
    AssessmentNotReadyForFinalizationError
        If readiness checks fail.
    AssessmentAlreadyFinalizedError
        If already finalized.
    """
    authorize_context(auth_ctx, PERM_FINALIZE_ASSESSMENT)
    assessment = _get_assessment(session, assessment_id)

    if assessment.finalization_status == "finalized":
        raise AssessmentAlreadyFinalizedError(
            f"Assessment {assessment_id[:8]} is already finalized."
        )

    readiness = get_finalization_readiness(session, assessment_id)
    if not readiness.is_ready:
        error_msgs = "; ".join(e.message for e in readiness.blocking_errors)
        raise AssessmentNotReadyForFinalizationError(
            f"Assessment {assessment_id[:8]} is not ready for finalization: {error_msgs}"
        )

    now = datetime.now(UTC)

    # Calculate final grade total
    submissions = _get_submissions(session, assessment_id)
    questions = _get_questions(session, assessment_id)
    final_total = Decimal("0")

    for sub in submissions:
        grade_map = _get_grade_map(session, sub.id)
        sub_total = Decimal("0")
        for q in questions:
            gr = grade_map.get(q.id)
            if gr is not None and gr.grade is not None:
                sub_total += gr.grade
        final_total += sub_total

    assessment.finalization_status = "finalized"
    assessment.finalized_at = now
    assessment.status = "finalized"
    assessment.finalization_note = finalization_note
    session.flush()

    logger.info(
        "Assessment %s finalized at %s with %d submissions, total grade %s",
        assessment_id[:8], now, len(submissions), final_total,
    )

    return FinalizationResult(
        assessment_id=assessment_id,
        finalized_at=now,
        submission_count=len(submissions),
        final_grade_total=final_total,
        status="finalized",
        warning_count=len(readiness.warnings),
    )


def get_finalized_assessment_summary(
    session: Session,
    assessment_id: str,
) -> FinalizedAssessmentSummary | None:
    """Get a summary of a finalized assessment, or None if not finalized."""
    assessment = _get_assessment(session, assessment_id)
    if assessment.finalization_status != "finalized":
        return None

    questions = _get_questions(session, assessment_id)
    submissions = _get_submissions(session, assessment_id)

    approved_count = 0
    grades_list: list[Decimal] = []

    for sub in submissions:
        if sub.review_status == "approved":
            approved_count += 1
        grade_map = _get_grade_map(session, sub.id)
        total_g = Decimal("0")
        for q in questions:
            gr = grade_map.get(q.id)
            if gr is not None and gr.grade is not None:
                total_g += gr.grade
        grades_list.append(total_g)

    avg = sum(grades_list, Decimal("0")) / max(len(grades_list), 1) if grades_list else Decimal("0")
    min_g = min(grades_list) if grades_list else Decimal("0")
    max_g = max(grades_list) if grades_list else Decimal("0")
    total_all = sum(grades_list, Decimal("0"))

    return FinalizedAssessmentSummary(
        assessment_id=assessment_id,
        title=assessment.title,
        status=assessment.status,
        finalized_at=assessment.finalized_at,
        total_submissions=len(submissions),
        approved_submissions=approved_count,
        average_grade=avg,
        minimum_grade=min_g,
        maximum_grade=max_g,
        final_grade_total=total_all,
        maximum_total=assessment.maximum_grade,
    )


def calculate_final_grade(
    session: Session,
    submission_id: str,
    assessment_id: str,
) -> Decimal:
    """Calculate the final grade for a submission from its GradeRecords."""
    questions = _get_questions(session, assessment_id)
    grade_map = _get_grade_map(session, submission_id)
    total = Decimal("0")
    for q in questions:
        gr = grade_map.get(q.id)
        if gr is not None and gr.grade is not None:
            total += gr.grade
    return total


def verify_finalized_integrity(
    session: Session,
    assessment_id: str,
) -> bool:
    """Verify that a finalized assessment's grades are reproducible."""
    assessment = _get_assessment(session, assessment_id)
    if assessment.finalization_status != "finalized":
        return False

    questions = _get_questions(session, assessment_id)
    submissions = _get_submissions(session, assessment_id)

    for sub in submissions:
        grade_map = _get_grade_map(session, sub.id)
        for q in questions:
            gr = grade_map.get(q.id)
            if gr is None:
                return False
            if gr.grade is None:
                return False
            if gr.grade > q.maximum_grade:
                return False
            if gr.grading_status != "graded":
                return False

    return True
