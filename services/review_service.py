# Academic Anonymous Grader — Review Service
"""Service layer for review and validation workflow.

SAFETY: This service must never query or expose StudentIdentity.
All review uses anonymous codes only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.orm import joinedload

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.question import Question
from models.response import Response
from models.submission import Submission
from services.exceptions import (
    FinalizedAssessmentModificationError,
    ReviewApprovalBlockedError,
    ReviewNoteRequiredError,
    ReviewSubmissionNotFoundError,
)
from services.logging_service import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger("review")

# ── Typed result objects ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReviewSubmissionSummary:
    submission_id: str
    anonymous_code: str
    grading_status: str
    review_status: str
    total_grade: Decimal
    maximum_grade: Decimal
    validation_error_count: int
    validation_warning_count: int


@dataclass(frozen=True, slots=True)
class ReviewValidationMessage:
    type: str  # "error" or "warning"
    message: str
    question_number: int | None = None
    code: str | None = None

    def __repr__(self) -> str:
        return f"<ReviewValidationMessage type={self.type} code={self.code}>"


@dataclass(frozen=True, slots=True)
class ReviewQuestionItem:
    question_number: int
    question_title: str | None
    maximum_grade: Decimal
    response_text: str | None
    is_blank: bool
    grade: Decimal | None
    feedback: str | None
    grading_status: str
    validation_messages: tuple[ReviewValidationMessage, ...] = ()

    def __repr__(self) -> str:
        return f"<ReviewQuestionItem q={self.question_number} status='{self.grading_status}'>"


@dataclass(frozen=True, slots=True)
class ReviewSubmissionView:
    submission_id: str
    anonymous_code: str
    assessment_title: str
    questions: tuple[ReviewQuestionItem, ...]
    total_grade: Decimal
    maximum_grade: Decimal
    review_status: str
    review_note: str | None
    validation_errors: tuple[ReviewValidationMessage, ...] = ()
    validation_warnings: tuple[ReviewValidationMessage, ...] = ()
    previous_submission_id: str | None = None
    next_submission_id: str | None = None

    def __repr__(self) -> str:
        return f"<ReviewSubmissionView sub={self.submission_id[:8]} code='{self.anonymous_code}'>"


@dataclass(frozen=True, slots=True)
class ReviewProgress:
    total_submissions: int
    not_ready: int
    ready_for_review: int
    needs_correction: int
    approved: int

    @property
    def completion_percentage(self) -> float:
        if self.total_submissions == 0:
            return 0.0
        return round(self.approved / self.total_submissions * 100, 1)


@dataclass(frozen=True, slots=True)
class AssessmentValidationResult:
    blocking_errors: tuple[ReviewValidationMessage, ...] = ()
    warnings: tuple[ReviewValidationMessage, ...] = ()
    total_submissions: int = 0
    graded_submissions: int = 0
    approved_submissions: int = 0
    is_ready: bool = False

    def __repr__(self) -> str:
        return f"<AssessmentValidationResult ready={self.is_ready}>"


# ── Helpers ───────────────────────────────────────────────────────


def _check_not_finalized(session: Session, assessment_id: str) -> None:
    """Raise if the assessment is finalized."""
    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment and assessment.finalization_status == "finalized":
        raise FinalizedAssessmentModificationError(
            f"Assessment {assessment_id[:8]} is finalized. Review changes are blocked."
        )


def _get_assessment_questions(session: Session, assessment_id: str) -> list[Question]:
    return (
        session.query(Question)
        .filter(Question.assessment_id == assessment_id)
        .order_by(Question.question_number)
        .all()
    )


def _get_existing_grade_records(
    session: Session,
    submission_id: str,
) -> dict[str, GradeRecord]:
    records = (
        session.query(GradeRecord)
        .filter(GradeRecord.submission_id == submission_id)
        .all()
    )
    return {r.question_id: r for r in records}


def _get_submission_responses(
    session: Session,
    submission_id: str,
) -> dict[str, Response]:
    responses = (
        session.query(Response)
        .filter(Response.submission_id == submission_id)
        .all()
    )
    return {r.question_id: r for r in responses}


# ── Public API ────────────────────────────────────────────────────


def list_reviewable_assessments(
    session: Session,
    material_id: str,
) -> list[Assessment]:
    """List assessments with submissions ready for review."""
    return (
        session.query(Assessment)
        .filter(
            Assessment.material_id == material_id,
            Assessment.status.in_(["ready", "grading", "finalized"]),
        )
        .order_by(Assessment.title)
        .all()
    )


def list_review_submissions(
    session: Session,
    assessment_id: str,
    status_filter: str | None = None,
) -> list[ReviewSubmissionSummary]:
    """List all submissions for review with validation summaries."""
    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        return []

    questions = _get_assessment_questions(session, assessment_id)
    max_total: Decimal = sum((q.maximum_grade for q in questions), Decimal("0"))

    submissions = (
        session.query(Submission)
        .filter(Submission.assessment_id == assessment_id)
        .join(Submission.anonymous_student)
        .options(joinedload(Submission.anonymous_student))
        .order_by(AnonymousStudent.anonymous_code)
        .all()
    )

    results: list[ReviewSubmissionSummary] = []
    for sub in submissions:
        grade_recs = _get_existing_grade_records(session, sub.id)
        responses = _get_submission_responses(session, sub.id)
        total_grade: Decimal = sum(
            (g.grade for g in grade_recs.values() if g.grade is not None),
            Decimal("0"),
        )

        # Count validation issues
        err_count = 0
        warn_count = 0
        for q in questions:
            gr = grade_recs.get(q.id)
            if gr is None:
                err_count += 1
            elif gr.grade is None:
                err_count += 1
            elif gr.grade < Decimal("0") or gr.grade > q.maximum_grade:
                err_count += 1
            elif gr.grading_status != "graded":
                err_count += 1

            resp = responses.get(q.id)
            grade = gr.grade if gr else None
            if resp and resp.is_blank and grade is not None and grade > Decimal("0"):
                warn_count += 1
            if resp and resp.is_blank and not (gr.feedback if gr else None):
                warn_count += 1
            if resp and not resp.is_blank and grade is not None and grade == Decimal("0"):
                warn_count += 1

        if status_filter and status_filter != "all" and sub.review_status != status_filter:
            continue

        results.append(
            ReviewSubmissionSummary(
                submission_id=sub.id,
                anonymous_code=sub.anonymous_student.anonymous_code,
                grading_status=sub.grading_status,
                review_status=sub.review_status,
                total_grade=total_grade,
                maximum_grade=max_total,
                validation_error_count=err_count,
                validation_warning_count=warn_count,
            )
        )

    return sorted(results, key=lambda r: r.anonymous_code)


def get_review_submission(
    session: Session,
    submission_id: str,
    assessment_id: str,
) -> ReviewSubmissionView | None:
    """Load a full review view for one submission."""
    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id, Submission.assessment_id == assessment_id)
        .options(
            joinedload(Submission.anonymous_student),
            joinedload(Submission.assessment),
        )
        .first()
    )
    if submission is None:
        return None

    assessment = submission.assessment
    questions = _get_assessment_questions(session, assessment_id)
    responses = _get_submission_responses(session, submission_id)
    grade_recs = _get_existing_grade_records(session, submission_id)

    # Navigation by anonymous_code
    sub_rows = (
        session.query(Submission.id)
        .join(AnonymousStudent, Submission.anonymous_student_id == AnonymousStudent.id)
        .filter(Submission.assessment_id == assessment_id)
        .order_by(AnonymousStudent.anonymous_code)
        .all()
    )
    sub_ids = [row[0] for row in sub_rows]
    current_idx = sub_ids.index(submission_id) if submission_id in sub_ids else -1
    prev_id = sub_ids[current_idx - 1] if current_idx > 0 else None
    next_id = sub_ids[current_idx + 1] if current_idx < len(sub_ids) - 1 else None

    max_total: Decimal = sum((q.maximum_grade for q in questions), Decimal("0"))
    total_grade: Decimal = Decimal("0")
    errors: list[ReviewValidationMessage] = []
    warnings: list[ReviewValidationMessage] = []
    items: list[ReviewQuestionItem] = []

    for q in questions:
        gr = grade_recs.get(q.id)
        resp = responses.get(q.id)
        q_errors: list[ReviewValidationMessage] = []
        q_warnings: list[ReviewValidationMessage] = []

        grade = gr.grade if gr else None
        feedback = gr.feedback if gr else None
        gs = gr.grading_status if gr else "ungraded"

        if gr is None:
            q_errors.append(ReviewValidationMessage(
                type="error", message="Missing grade record", question_number=q.question_number, code="RV001",
            ))
        elif grade is None:
            q_errors.append(ReviewValidationMessage(
                type="error", message="Grade is missing", question_number=q.question_number, code="RV002",
            ))
        elif grade < Decimal("0"):
            q_errors.append(ReviewValidationMessage(
                type="error", message=f"Grade {grade} is negative", question_number=q.question_number, code="RV003",
            ))
        elif grade > q.maximum_grade:
            q_errors.append(ReviewValidationMessage(
                type="error", message=f"Grade {grade} exceeds maximum {q.maximum_grade}",
                question_number=q.question_number, code="RV004",
            ))
        elif gs != "graded":
            q_errors.append(ReviewValidationMessage(
                type="error", message=f"Grade status is '{gs}' not 'graded'",
                question_number=q.question_number, code="RV005",
            ))

        if grade is not None:
            total_grade += grade

        # Warnings
        if resp and resp.is_blank and grade is not None and grade > Decimal("0"):
            q_warnings.append(ReviewValidationMessage(
                type="warning", message="Blank response received non-zero grade",
                question_number=q.question_number, code="RVW001",
            ))
        if resp and resp.is_blank and not feedback:
            q_warnings.append(ReviewValidationMessage(
                type="warning", message="Blank response has no feedback",
                question_number=q.question_number, code="RVW002",
            ))
        if resp and not resp.is_blank and grade is not None and grade == Decimal("0"):
            q_warnings.append(ReviewValidationMessage(
                type="warning", message="Non-blank response received zero grade",
                question_number=q.question_number, code="RVW003",
            ))

        errors.extend(q_errors)
        warnings.extend(q_warnings)

        items.append(ReviewQuestionItem(
            question_number=q.question_number,
            question_title=q.title,
            maximum_grade=q.maximum_grade,
            response_text=resp.response_text if resp else None,
            is_blank=resp.is_blank if resp else False,
            grade=grade,
            feedback=feedback,
            grading_status=gs,
            validation_messages=tuple(q_errors + q_warnings),
        ))

    return ReviewSubmissionView(
        submission_id=submission.id,
        anonymous_code=submission.anonymous_student.anonymous_code,
        assessment_title=assessment.title,
        questions=tuple(items),
        total_grade=total_grade,
        maximum_grade=max_total,
        review_status=submission.review_status,
        review_note=submission.review_note,
        validation_errors=tuple(errors),
        validation_warnings=tuple(warnings),
        previous_submission_id=prev_id,
        next_submission_id=next_id,
    )


def validate_submission_for_review(
    session: Session,
    submission_id: str,
    assessment_id: str,
) -> list[ReviewValidationMessage]:
    """Validate a single submission for review readiness."""
    view = get_review_submission(session, submission_id, assessment_id)
    if view is None:
        raise ReviewSubmissionNotFoundError(f"Submission {submission_id} not found")
    errs = list(view.validation_errors)
    # Total validation
    if view.total_grade > view.maximum_grade:
        errs.append(ReviewValidationMessage(
            type="error", message=f"Total grade {view.total_grade} exceeds maximum {view.maximum_grade}",
            code="RV006",
        ))
    return errs


def approve_submission_review(
    session: Session,
    submission_id: str,
    assessment_id: str,
    reviewer_note: str | None = None,
) -> ReviewSubmissionView:
    """Approve a submission after review validation."""
    _check_not_finalized(session, assessment_id)
    errors = validate_submission_for_review(session, submission_id, assessment_id)
    if errors:
        raise ReviewApprovalBlockedError(
            f"Cannot approve: {errors[0].message} (code: {errors[0].code})"
        )

    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id, Submission.assessment_id == assessment_id)
        .first()
    )
    if submission is None:
        raise ReviewSubmissionNotFoundError(f"Submission {submission_id} not found")

    submission.review_status = "approved"
    submission.reviewed_at = datetime.now(UTC)
    if reviewer_note:
        submission.review_note = reviewer_note
    session.flush()

    view = get_review_submission(session, submission_id, assessment_id)
    if view is None:  # pragma: no cover
        raise ReviewSubmissionNotFoundError(f"Submission {submission_id} not found after approve")
    logger.info(
        "Submission %s approved for assessment %s",
        submission_id[:8], assessment_id[:8],
    )
    return view


def mark_submission_needs_correction(
    session: Session,
    submission_id: str,
    assessment_id: str,
    reviewer_note: str,
) -> ReviewSubmissionView:
    """Mark a submission as needing correction."""
    _check_not_finalized(session, assessment_id)
    if not reviewer_note or not reviewer_note.strip():
        raise ReviewNoteRequiredError("Reviewer note is required when marking needs correction")

    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id, Submission.assessment_id == assessment_id)
        .first()
    )
    if submission is None:
        raise ReviewSubmissionNotFoundError(f"Submission {submission_id} not found")

    submission.review_status = "needs_correction"
    submission.review_note = reviewer_note.strip()
    session.flush()

    view = get_review_submission(session, submission_id, assessment_id)
    if view is None:  # pragma: no cover
        raise ReviewSubmissionNotFoundError(f"Submission {submission_id} not found after needs_correction")
    logger.info(
        "Submission %s marked needs_correction for assessment %s",
        submission_id[:8], assessment_id[:8],
    )
    return view


def return_submission_to_grading(
    session: Session,
    submission_id: str,
    assessment_id: str,
) -> ReviewSubmissionView:
    """Return a submission to grading (reset review status)."""
    _check_not_finalized(session, assessment_id)
    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id, Submission.assessment_id == assessment_id)
        .first()
    )
    if submission is None:
        raise ReviewSubmissionNotFoundError(f"Submission {submission_id} not found")

    submission.review_status = "not_ready"
    submission.review_note = None
    session.flush()

    view = get_review_submission(session, submission_id, assessment_id)
    if view is None:  # pragma: no cover
        raise ReviewSubmissionNotFoundError(f"Submission {submission_id} not found after return")
    return view


def calculate_review_progress(
    session: Session,
    assessment_id: str,
) -> ReviewProgress:
    """Calculate review progress for an assessment."""
    submissions = (
        session.query(Submission)
        .filter(Submission.assessment_id == assessment_id)
        .all()
    )

    total = len(submissions)
    not_ready = sum(1 for s in submissions if s.review_status == "not_ready")
    ready = sum(1 for s in submissions if s.review_status == "ready_for_review")
    needs_corr = sum(1 for s in submissions if s.review_status == "needs_correction")
    approved = sum(1 for s in submissions if s.review_status == "approved")

    return ReviewProgress(
        total_submissions=total,
        not_ready=not_ready,
        ready_for_review=ready,
        needs_correction=needs_corr,
        approved=approved,
    )


def validate_assessment_review(
    session: Session,
    assessment_id: str,
) -> AssessmentValidationResult:
    """Validate an entire assessment for review completeness."""
    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    errors: list[ReviewValidationMessage] = []
    warnings: list[ReviewValidationMessage] = []

    if assessment is None:
        errors.append(ReviewValidationMessage(type="error", message="Assessment not found", code="RA001"))
        return AssessmentValidationResult(blocking_errors=tuple(errors), is_ready=False)

    questions = _get_assessment_questions(session, assessment_id)
    if not questions:
        errors.append(ReviewValidationMessage(type="error", message="Assessment has no questions", code="RA002"))

    q_total: Decimal = sum((q.maximum_grade for q in questions), Decimal("0"))
    if q_total != assessment.maximum_grade:
        errors.append(ReviewValidationMessage(
            type="error",
            message=f"Question total {q_total} does not match assessment maximum {assessment.maximum_grade}",
            code="RA003",
        ))

    submissions = (
        session.query(Submission)
        .filter(Submission.assessment_id == assessment_id)
        .options(joinedload(Submission.anonymous_student))
        .all()
    )

    if not submissions:
        errors.append(ReviewValidationMessage(type="error", message="No submissions to review", code="RA004"))

    total_subs = len(submissions)
    graded_count = 0
    approved_count = 0
    needs_correction_count = 0

    for sub in submissions:
        if sub.anonymous_student is None:
            errors.append(ReviewValidationMessage(
                type="error", message=f"Submission {sub.id[:8]} has no anonymous student", code="RA005",
            ))
            continue

        grade_recs = _get_existing_grade_records(session, sub.id)
        expected_q = len(questions)
        actual_grades = sum(1 for q in questions if q.id in grade_recs and grade_recs[q.id].grade is not None)

        if actual_grades == expected_q:
            graded_count += 1
        else:
            missing_count = expected_q - actual_grades
            errors.append(ReviewValidationMessage(
                type="error",
                message=(
                    f"Submission {sub.anonymous_student.anonymous_code} has "
                    f"{missing_count} missing or incomplete grade record(s)"
                ),
                code="RA008",
            ))

        if sub.review_status == "needs_correction":
            needs_correction_count += 1

        if sub.review_status == "approved":
            approved_count += 1

        # Validate grade totals
        graded_vals: list[Decimal] = [g.grade for g in grade_recs.values() if g.grade is not None]
        total_g: Decimal = sum(graded_vals, Decimal("0"))
        if total_g > assessment.maximum_grade:
            msg = (
                f"Submission {sub.anonymous_student.anonymous_code} total {total_g} "
                f"exceeds max {assessment.maximum_grade}"
            )
            errors.append(ReviewValidationMessage(type="error", message=msg, code="RA006"))

    if needs_correction_count > 0:
        errors.append(ReviewValidationMessage(
            type="error",
            message=f"{needs_correction_count} submission(s) still marked as needs correction",
            code="RA007",
        ))

    is_ready = len(errors) == 0 and total_subs > 0

    return AssessmentValidationResult(
        blocking_errors=tuple(errors),
        warnings=tuple(warnings),
        total_submissions=total_subs,
        graded_submissions=graded_count,
        approved_submissions=approved_count,
        is_ready=is_ready,
    )
