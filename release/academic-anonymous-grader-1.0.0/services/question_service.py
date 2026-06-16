# Academic Anonymous Grader — Question Service
"""CRUD operations for assessment questions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.assessment import Assessment
from models.question import Question
from models.response import Response
from services.exceptions import (
    AssessmentNotFoundError,
    FinalizedAssessmentModificationError,
    InvalidAssessmentStateError,
    QuestionDeletionBlockedError,
    QuestionNotFoundError,
    QuestionValidationError,
)
from services.validation import (
    normalize_optional_text,
    validate_positive_decimal,
    validate_positive_int,
)


@dataclass
class QuestionResult:
    """Typed result for question operations."""
    id: str
    assessment_id: str
    question_number: int
    title: str | None
    maximum_grade: Decimal
    rubric: str | None
    has_responses: bool


def _question_to_result(q: Question) -> QuestionResult:
    return QuestionResult(
        id=q.id,
        assessment_id=q.assessment_id,
        question_number=q.question_number,
        title=q.title,
        maximum_grade=q.maximum_grade,
        rubric=q.rubric,
        has_responses=len(q.responses) > 0 if q.responses else False,
    )


def create_question(
    session: Session,
    assessment_id: str,
    question_number: int,
    maximum_grade: Decimal | str,
    title: str | None = None,
    rubric: str | None = None,
) -> QuestionResult:
    """Add a question to an assessment. Only allowed when assessment is draft.

    Raises QuestionValidationError or InvalidAssessmentStateError.
    """
    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")
    if assessment.finalization_status == "finalized":
        raise FinalizedAssessmentModificationError(
            f"Assessment {assessment_id[:8]} is finalized. Questions cannot be added."
        )
    if assessment.status not in ("draft", "ready"):
        raise InvalidAssessmentStateError(
            f"Cannot add questions to assessment in '{assessment.status}' status"
        )

    try:
        num = validate_positive_int(question_number, field_name="question_number")
        grade = validate_positive_decimal(maximum_grade, field_name="maximum_grade")
    except ValueError as exc:
        raise QuestionValidationError(str(exc)) from exc

    clean_title = normalize_optional_text(title, max_length=300)
    clean_rubric = normalize_optional_text(rubric)

    # Check duplicate number
    existing = session.query(Question).filter(
        Question.assessment_id == assessment_id,
        Question.question_number == num,
    ).first()
    if existing:
        raise QuestionValidationError(
            f"Question number {num} already exists in this assessment"
        )

    q = Question(
        assessment_id=assessment_id,
        question_number=num,
        title=clean_title,
        maximum_grade=grade,
        rubric=clean_rubric,
    )
    session.add(q)
    session.flush()
    return _question_to_result(q)


def update_question(
    session: Session,
    question_id: str,
    question_number: int | None = None,
    maximum_grade: Decimal | str | None = None,
    title: str | None = None,
    rubric: str | None = None,
) -> QuestionResult:
    """Update a question. Only allowed when assessment is draft."""
    q = session.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise QuestionNotFoundError(f"Question {question_id} not found")
    if q.assessment.status not in ("draft", "ready"):
        raise InvalidAssessmentStateError(
            f"Cannot edit questions in '{q.assessment.status}' status"
        )

    if question_number is not None:
        try:
            q.question_number = validate_positive_int(question_number, field_name="question_number")
        except ValueError as exc:
            raise QuestionValidationError(str(exc)) from exc
        # Check duplicate
        duplicate = session.query(Question).filter(
            Question.assessment_id == q.assessment_id,
            Question.question_number == q.question_number,
            Question.id != question_id,
        ).first()
        if duplicate:
            raise QuestionValidationError(
                f"Question number {q.question_number} already exists"
            )

    if maximum_grade is not None:
        try:
            q.maximum_grade = validate_positive_decimal(maximum_grade, field_name="maximum_grade")
        except ValueError as exc:
            raise QuestionValidationError(str(exc)) from exc

    if title is not None:
        q.title = normalize_optional_text(title, max_length=300)
    if rubric is not None:
        q.rubric = normalize_optional_text(rubric)

    session.flush()
    return _question_to_result(q)


def delete_question(session: Session, question_id: str) -> None:
    """Delete a question. Blocks if assessment is finalized or not draft."""
    q = session.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise QuestionNotFoundError(f"Question {question_id} not found")

    if q.assessment.finalization_status == "finalized":
        raise FinalizedAssessmentModificationError(
            f"Assessment {q.assessment_id[:8]} is finalized. Questions cannot be deleted."
        )

    if q.assessment.status != "draft":
        raise InvalidAssessmentStateError(
            "Questions can only be deleted from draft assessments"
        )

    # Check for existing responses
    response_count = session.query(func.count(Response.id)).filter(
        Response.question_id == question_id
    ).scalar() or 0
    if response_count > 0:
        raise QuestionDeletionBlockedError(
            f"Cannot delete question {q.question_number}: {response_count} response(s) exist"
        )

    session.delete(q)
    session.flush()


def reorder_questions(
    session: Session, assessment_id: str, question_ids_in_order: list[str]
) -> list[QuestionResult]:
    """Reorder questions by assigning sequential numbers based on provided order.

    Uses a two-step update (large temporary numbers) to avoid UNIQUE constraint
    violations during the swap while respecting positive-number constraints.
    """
    questions = session.query(Question).filter(
        Question.assessment_id == assessment_id
    ).all()
    q_map = {q.id: q for q in questions}

    # Step 1: assign large temporary numbers to avoid unique constraint conflicts
    temp_num = 1000000
    for qid in question_ids_in_order:
        if qid in q_map:
            q_map[qid].question_number = temp_num
            temp_num += 1
    session.flush()

    # Step 2: assign real sequential numbers
    for idx, qid in enumerate(question_ids_in_order, start=1):
        if qid in q_map:
            q_map[qid].question_number = idx
    session.flush()
    return list_questions(session, assessment_id)


def list_questions(session: Session, assessment_id: str) -> list[QuestionResult]:
    """List all questions for an assessment, ordered by question number."""
    questions = session.query(Question).filter(
        Question.assessment_id == assessment_id
    ).order_by(Question.question_number).all()
    return [_question_to_result(q) for q in questions]


def calculate_question_total(session: Session, assessment_id: str) -> Decimal:
    """Calculate the sum of all question maximum grades for an assessment."""
    result = session.query(func.sum(Question.maximum_grade)).filter(
        Question.assessment_id == assessment_id
    ).scalar()
    return result if result is not None else Decimal("0")
