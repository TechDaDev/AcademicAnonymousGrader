# Academic Anonymous Grader — Grading Service
"""Service layer for manual anonymous grading.

SAFETY: This service must never query or expose StudentIdentity.
All grading uses anonymous codes only.
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
    GradingError,
    GradingQuestionNotFoundError,
    IncompleteGradingError,
    InvalidGradeError,
    SubmissionNotFoundError,
)
from services.logging_service import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger("grading")


# ── Typed result objects ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AnonymousSubmissionSummary:
    submission_id: str
    anonymous_code: str
    submission_status: str
    graded_question_count: int
    total_question_count: int
    current_total: Decimal
    maximum_total: Decimal
    is_complete: bool


@dataclass(frozen=True, slots=True)
class QuestionGradingItem:
    question_id: str
    question_number: int
    question_title: str | None
    maximum_grade: Decimal
    response_text: str | None
    is_blank: bool
    grade: Decimal | None
    feedback: str | None
    grading_status: str

    def __repr__(self) -> str:
        return (
            f"<QuestionGradingItem q={self.question_number} "
            f"status='{self.grading_status}'>"
        )


@dataclass(frozen=True, slots=True)
class SubmissionGradingView:
    submission_id: str
    anonymous_code: str
    assessment_title: str
    questions: list[QuestionGradingItem]
    current_total: Decimal
    maximum_total: Decimal
    is_complete: bool
    review_status: str = "not_ready"
    review_note: str | None = None
    previous_submission_id: str | None = None
    next_submission_id: str | None = None

    def __repr__(self) -> str:
        return f"<SubmissionGradingView sub={self.submission_id[:8]} code='{self.anonymous_code}'>"


@dataclass(frozen=True, slots=True)
class GradingProgress:
    total_submissions: int
    ungraded_submissions: int
    in_progress_submissions: int
    completed_submissions: int

    @property
    def completion_percentage(self) -> float:
        if self.total_submissions == 0:
            return 0.0
        return round(self.completed_submissions / self.total_submissions * 100, 1)


# ── Helpers ───────────────────────────────────────────────────────


def _get_assessment_questions(session: Session, assessment_id: str) -> list[Question]:
    return (
        session.query(Question)
        .filter(Question.assessment_id == assessment_id)
        .order_by(Question.question_number)
        .all()
    )


def _get_submission_responses(session: Session, submission_id: str) -> dict[str, Response]:
    """Return {question_id: Response} for a submission."""
    responses = (
        session.query(Response)
        .filter(Response.submission_id == submission_id)
        .all()
    )
    return {r.question_id: r for r in responses}


def _get_existing_grade_records(
    session: Session,
    submission_id: str,
) -> dict[str, GradeRecord]:
    """Return {question_id: GradeRecord} for a submission."""
    records = (
        session.query(GradeRecord)
        .filter(GradeRecord.submission_id == submission_id)
        .all()
    )
    return {r.question_id: r for r in records}


# ── Public API ────────────────────────────────────────────────────


def list_gradable_assessments(
    session: Session,
    material_id: str,
) -> list[Assessment]:
    """List assessments that have imported submissions ready for grading."""
    return (
        session.query(Assessment)
        .filter(
            Assessment.material_id == material_id,
            Assessment.status.in_(["ready", "grading", "finalized"]),
        )
        .order_by(Assessment.title)
        .all()
    )


def list_anonymous_submissions(
    session: Session,
    assessment_id: str,
    status_filter: str | None = None,
) -> list[AnonymousSubmissionSummary]:
    """List all submissions for an assessment with grading summaries.

    Never joins StudentIdentity.
    """
    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        return []

    questions = _get_assessment_questions(session, assessment_id)
    total_q = len(questions)
    max_total: Decimal = sum((q.maximum_grade for q in questions), Decimal("0"))

    submissions = (
        session.query(Submission)
        .filter(Submission.assessment_id == assessment_id)
        .options(joinedload(Submission.anonymous_student))
        .order_by(Submission.id)
        .all()
    )

    results: list[AnonymousSubmissionSummary] = []
    for sub in submissions:
        grade_recs = _get_existing_grade_records(session, sub.id)
        graded_qs = [g for g in grade_recs.values() if g.grade is not None and g.grading_status == "graded"]
        all_graded = (
            len(graded_qs) == total_q
            if total_q > 0
            else False
        )
        any_graded = len(graded_qs) > 0
        current_total: Decimal = sum(
            (g.grade for g in graded_qs if g.grade is not None),
            Decimal("0"),
        )

        if total_q == 0:
            status = "ungraded"
        elif all_graded:
            status = "graded"
        elif any_graded:
            status = "in_progress"
        else:
            status = "ungraded"

        if status_filter and status_filter != "all" and status != status_filter:
            continue

        results.append(
            AnonymousSubmissionSummary(
                submission_id=sub.id,
                anonymous_code=sub.anonymous_student.anonymous_code,
                submission_status=status,
                graded_question_count=len(graded_qs),
                total_question_count=total_q,
                current_total=current_total,
                maximum_total=max_total,
                is_complete=all_graded,
            )
        )

    return sorted(results, key=lambda r: r.anonymous_code)


def get_grading_submission(
    session: Session,
    submission_id: str,
    assessment_id: str,
) -> SubmissionGradingView | None:
    """Load a full grading view for one submission.

    Never decrypts StudentIdentity.
    """
    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id, Submission.assessment_id == assessment_id)
        .options(joinedload(Submission.anonymous_student), joinedload(Submission.assessment))
        .first()
    )
    if submission is None:
        return None

    assessment = submission.assessment
    questions = _get_assessment_questions(session, assessment_id)
    responses = _get_submission_responses(session, submission_id)
    grade_recs = _get_existing_grade_records(session, submission_id)

    # Get previous and next submission IDs for navigation
    # Use same ordering as list_anonymous_submissions: anonymous_code ascending
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
    current_total: Decimal = Decimal("0")
    items: list[QuestionGradingItem] = []

    for q in questions:
        resp = responses.get(q.id)
        gr = grade_recs.get(q.id)
        grade = gr.grade if gr else None
        feedback = gr.feedback if gr else None
        gs = gr.grading_status if gr else "ungraded"

        if grade is not None:
            current_total += grade

        items.append(
            QuestionGradingItem(
                question_id=q.id,
                question_number=q.question_number,
                question_title=q.title,
                maximum_grade=q.maximum_grade,
                response_text=resp.response_text if resp else None,
                is_blank=resp.is_blank if resp else False,
                grade=grade,
                feedback=feedback,
                grading_status=gs,
            )
        )

    all_graded = all(
        gr.grading_status == "graded" and gr.grade is not None
        for gr in grade_recs.values()
    ) if grade_recs else False
    fully_graded = all_graded and len(grade_recs) == len(questions)

    return SubmissionGradingView(
        submission_id=submission.id,
        anonymous_code=submission.anonymous_student.anonymous_code,
        assessment_title=assessment.title,
        questions=items,
        current_total=current_total,
        maximum_total=max_total,
        is_complete=fully_graded,
        previous_submission_id=prev_id,
        review_status=submission.review_status,
        review_note=submission.review_note,
        next_submission_id=next_id,
    )


def get_or_create_grade_record(
    session: Session,
    submission_id: str,
    question_id: str,
) -> GradeRecord:
    """Get existing or create a new GradeRecord for a submission/question pair."""
    existing = (
        session.query(GradeRecord)
        .filter(
            GradeRecord.submission_id == submission_id,
            GradeRecord.question_id == question_id,
        )
        .first()
    )
    if existing:
        return existing

    record = GradeRecord(
        submission_id=submission_id,
        question_id=question_id,
        grading_status="ungraded",
    )
    session.add(record)
    session.flush()
    return record


def validate_question_grade(
    grade: str | None,
    maximum_grade: Decimal,
) -> Decimal | None:
    """Validate and convert a grade string to Decimal.

    Returns the grade or None if empty.
    Raises InvalidGradeError on invalid values.
    """
    if grade is None or grade.strip() == "":
        return None

    try:
        value = Decimal(grade.strip())
    except Exception as exc:
        raise InvalidGradeError(f"Grade '{grade}' is not a valid number") from exc

    if value < Decimal("0"):
        raise InvalidGradeError(f"Grade {value} is below zero")

    if value > maximum_grade:
        raise InvalidGradeError(
            f"Grade {value} exceeds maximum {maximum_grade}"
        )

    return value


def save_question_grade(
    session: Session,
    submission_id: str,
    question_id: str,
    assessment_id: str,
    grade: Decimal | None,
    feedback: str | None = None,
    grading_status: str = "draft",
) -> GradeRecord:
    """Save or update a grade for a single question.

    Validates the submission and question belong to the same assessment.
    Validates grade bounds.
    """
    # Verify submission exists and belongs to this assessment
    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id, Submission.assessment_id == assessment_id)
        .first()
    )
    if submission is None:
        raise SubmissionNotFoundError(f"Submission {submission_id} not found")

    # Verify question exists and belongs to this assessment
    question = (
        session.query(Question)
        .filter(Question.id == question_id, Question.assessment_id == assessment_id)
        .first()
    )
    if question is None:
        raise GradingQuestionNotFoundError(f"Question {question_id} not found in assessment {assessment_id}")

    # Validate grade
    if grade is not None:
        if grade < Decimal("0"):
            raise InvalidGradeError(f"Grade {grade} is below zero")
        if grade > question.maximum_grade:
            raise InvalidGradeError(
                f"Grade {grade} exceeds question maximum {question.maximum_grade}"
            )

    record = get_or_create_grade_record(session, submission_id, question_id)
    record.grade = grade
    record.feedback = feedback
    record.grading_status = grading_status
    if grading_status == "graded":
        record.graded_at = datetime.now(UTC)
    else:
        record.graded_at = None
    session.flush()
    return record


def save_submission_grades(
    session: Session,
    submission_id: str,
    assessment_id: str,
    grades: dict[str, str],  # question_id -> grade string
    feedbacks: dict[str, str | None],  # question_id -> feedback
    marking_graded: bool = False,
) -> SubmissionGradingView:
    """Save grades for multiple questions in a submission.

    If marking_graded=True, validates all questions have grades.
    """
    # Block edits on finalized assessments
    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment and assessment.finalization_status == "finalized":
        raise FinalizedAssessmentModificationError(
            f"Assessment {assessment_id[:8]} is finalized. Grades cannot be modified."
        )

    questions = _get_assessment_questions(session, assessment_id)
    if not questions:
        raise GradingError("Assessment has no questions configured")

    for q in questions:
        grade_str = grades.get(q.id, "")
        fb = feedbacks.get(q.id)

        try:
            grade_val = validate_question_grade(grade_str, q.maximum_grade)
        except InvalidGradeError:
            raise  # Re-raise validation errors

        status = "graded" if (marking_graded and grade_val is not None) else "draft"

        save_question_grade(
            session=session,
            submission_id=submission_id,
            question_id=q.id,
            assessment_id=assessment_id,
            grade=grade_val,
            feedback=fb,
            grading_status=status,
        )

    if marking_graded:
        # Verify all questions have grades
        saved_records = _get_existing_grade_records(session, submission_id)
        missing = [
            q.question_number
            for q in questions
            if q.id not in saved_records or saved_records[q.id].grade is None
        ]
        if missing:
            raise IncompleteGradingError(
                f"Cannot mark as graded: Question(s) {missing} are missing grades"
            )

        # Total validation
        grade_values: list[Decimal] = []
        for q in questions:
            if q.id in saved_records:
                g = saved_records[q.id].grade
                if g is not None:
                    grade_values.append(g)
        total = sum(grade_values, Decimal("0"))
        assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
        if assessment and total > assessment.maximum_grade:
            raise InvalidGradeError(
                f"Total grade {total} exceeds assessment maximum {assessment.maximum_grade}"
            )

    # Update review status when marking graded
    if marking_graded:
        submission = session.query(Submission).filter(Submission.id == submission_id).first()
        if submission and submission.review_status in ("not_ready", "needs_correction"):
            submission.review_status = "ready_for_review"

    session.flush()
    view = get_grading_submission(session, submission_id, assessment_id)
    if view is None:
        raise SubmissionNotFoundError(f"Submission {submission_id} not found after save")
    return view


def calculate_grading_progress(
    session: Session,
    assessment_id: str,
) -> GradingProgress:
    """Calculate grading progress for an assessment."""
    questions = _get_assessment_questions(session, assessment_id)
    total_q = len(questions)

    submissions = (
        session.query(Submission)
        .filter(Submission.assessment_id == assessment_id)
        .all()
    )

    total_submissions = len(submissions)
    ungraded = 0
    in_progress = 0
    completed = 0

    for sub in submissions:
        grade_recs = _get_existing_grade_records(session, sub.id)
        graded_qs = [
            g for g in grade_recs.values()
            if g.grade is not None and g.grading_status == "graded"
        ]
        has_any_grade = any(g.grade is not None for g in grade_recs.values())

        if total_q == 0:
            ungraded += 1
        elif len(graded_qs) == total_q:
            completed += 1
        elif has_any_grade:
            in_progress += 1
        else:
            ungraded += 1

    return GradingProgress(
        total_submissions=total_submissions,
        ungraded_submissions=ungraded,
        in_progress_submissions=in_progress,
        completed_submissions=completed,
    )
