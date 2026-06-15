# Academic Anonymous Grader — Assessment Service
"""CRUD operations for assessments."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from models.assessment import Assessment
from models.material import Material
from models.question import Question
from services.exceptions import (
    AssessmentNotFoundError,
    AssessmentValidationError,
    InvalidAssessmentStateError,
)
from services.validation import (
    normalize_optional_text,
    normalize_required_text,
    validate_positive_decimal,
    validate_status_transition,
)


@dataclass
class AssessmentResult:
    """Typed result for assessment operations."""
    id: str
    material_id: str
    material_name: str
    title: str
    assessment_type: str | None
    academic_year: str | None
    maximum_grade: Decimal
    status: str
    question_count: int
    question_total: Decimal
    is_valid: bool
    validation_message: str
    created_at: str
    updated_at: str | None


def _assessment_to_result(
    a: Assessment, question_total: Decimal | None = None
) -> AssessmentResult:
    q_count = len(a.questions)
    q_total = question_total if question_total is not None else (
        sum((q.maximum_grade for q in a.questions), Decimal("0"))
        if a.questions else Decimal("0")
    )
    is_valid = q_count > 0 and q_total == a.maximum_grade
    if q_count == 0:
        msg = "No questions configured"
    elif q_total != a.maximum_grade:
        diff = a.maximum_grade - q_total
        msg = f"Question total ({q_total}) {'below' if diff > 0 else 'exceeds'} maximum by {abs(diff)}"
    else:
        msg = "Configuration valid"

    return AssessmentResult(
        id=a.id,
        material_id=a.material_id,
        material_name=a.material.name if a.material else "",
        title=a.title,
        assessment_type=a.assessment_type,
        academic_year=a.academic_year,
        maximum_grade=a.maximum_grade,
        status=a.status,
        question_count=q_count,
        question_total=q_total,
        is_valid=is_valid,
        validation_message=msg,
        created_at=a.created_at.isoformat() if a.created_at else "",
        updated_at=a.updated_at.isoformat() if a.updated_at else None,
    )


def create_assessment(
    session: Session,
    material_id: str,
    title: str,
    assessment_type: str | None = None,
    academic_year: str | None = None,
    maximum_grade: Decimal | str | None = None,
) -> AssessmentResult:
    """Create a new assessment under a material.

    Raises AssessmentValidationError if the material is archived or validation fails.
    """
    material = session.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise AssessmentValidationError("Parent material not found")
    if material.is_archived:
        raise AssessmentValidationError("Cannot create assessment under an archived material")

    try:
        clean_title = normalize_required_text(title, max_length=200)
    except ValueError as exc:
        raise AssessmentValidationError(str(exc)) from exc

    try:
        grade = validate_positive_decimal(
            maximum_grade if maximum_grade is not None else "0",
            field_name="maximum_grade",
        )
    except ValueError as exc:
        raise AssessmentValidationError(str(exc)) from exc

    clean_type = normalize_optional_text(assessment_type, max_length=100)
    clean_year = normalize_optional_text(academic_year, max_length=30)

    assessment = Assessment(
        material_id=material_id,
        title=clean_title,
        assessment_type=clean_type,
        academic_year=clean_year,
        maximum_grade=grade,
        status="draft",
    )
    session.add(assessment)
    session.flush()
    return _assessment_to_result(assessment)


def get_assessment(session: Session, assessment_id: str) -> AssessmentResult:
    """Get an assessment by ID."""
    a = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")
    return _assessment_to_result(a)


def list_assessments(
    session: Session,
    material_id: str | None = None,
    status_filter: str | None = None,
    include_archived: bool = False,
    search_query: str | None = None,
) -> list[AssessmentResult]:
    """List assessments with optional filters."""
    query = session.query(Assessment)
    if material_id:
        query = query.filter(Assessment.material_id == material_id)
    if status_filter and status_filter != "all":
        query = query.filter(Assessment.status == status_filter)
    elif not include_archived:
        query = query.filter(Assessment.status != "archived")
    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(Assessment.title.ilike(pattern))
    query = query.order_by(Assessment.status, Assessment.title)
    assessments = query.all()
    return [_assessment_to_result(a) for a in assessments]


def update_assessment(
    session: Session,
    assessment_id: str,
    title: str | None = None,
    assessment_type: str | None = None,
    academic_year: str | None = None,
    maximum_grade: Decimal | str | None = None,
    status: str | None = None,
) -> AssessmentResult:
    """Update assessment fields. Archived and protected statuses block editing."""
    a = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")

    if a.status in ("grading", "finalized"):
        raise InvalidAssessmentStateError(
            f"Cannot edit assessment in '{a.status}' status"
        )
    if a.status == "archived" and status != "draft":
        raise InvalidAssessmentStateError(
            "Cannot edit an archived assessment without restoring it first"
        )

    if title is not None:
        try:
            a.title = normalize_required_text(title, max_length=200)
        except ValueError as exc:
            raise AssessmentValidationError(str(exc)) from exc

    if assessment_type is not None:
        a.assessment_type = normalize_optional_text(assessment_type, max_length=100)
    if academic_year is not None:
        a.academic_year = normalize_optional_text(academic_year, max_length=30)
    if maximum_grade is not None:
        try:
            a.maximum_grade = validate_positive_decimal(maximum_grade, field_name="maximum_grade")
        except ValueError as exc:
            raise AssessmentValidationError(str(exc)) from exc

    if status is not None and status != a.status:
        try:
            validate_status_transition(a.status, status)
        except ValueError as exc:
            raise InvalidAssessmentStateError(str(exc)) from exc
        a.status = status

    session.flush()
    return _assessment_to_result(a)


def archive_assessment(session: Session, assessment_id: str) -> AssessmentResult:
    """Archive an assessment."""
    a = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")
    try:
        validate_status_transition(a.status, "archived")
    except ValueError as exc:
        raise InvalidAssessmentStateError(str(exc)) from exc
    a.status = "archived"
    session.flush()
    return _assessment_to_result(a)


def restore_assessment(session: Session, assessment_id: str) -> AssessmentResult:
    """Restore an archived assessment to draft."""
    a = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")
    if a.status != "archived":
        raise InvalidAssessmentStateError("Assessment is not archived")
    a.status = "draft"
    session.flush()
    return _assessment_to_result(a)


def validate_assessment_configuration(session: Session, assessment_id: str) -> AssessmentResult:
    """Validate and return assessment configuration status."""
    a = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")
    return _assessment_to_result(a)


def mark_assessment_ready(session: Session, assessment_id: str) -> AssessmentResult:
    """Mark assessment as ready if configuration is valid."""
    a = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")
    result = _assessment_to_result(a)
    if not result.is_valid:
        raise AssessmentValidationError(
            f"Cannot mark ready: {result.validation_message}"
        )
    a.status = "ready"
    session.flush()
    return _assessment_to_result(a)


def return_assessment_to_draft(session: Session, assessment_id: str) -> AssessmentResult:
    """Return a ready assessment to draft."""
    a = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")
    if a.status != "ready":
        raise InvalidAssessmentStateError("Only 'ready' assessments can be returned to draft")
    a.status = "draft"
    session.flush()
    return _assessment_to_result(a)


def duplicate_assessment(session: Session, assessment_id: str) -> AssessmentResult:
    """Duplicate an assessment and its questions as a new draft."""
    original = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not original:
        raise AssessmentNotFoundError(f"Assessment {assessment_id} not found")

    # Eagerly load questions
    session.query(Question).filter(Question.assessment_id == assessment_id).all()

    new_assessment = Assessment(
        material_id=original.material_id,
        title=f"{original.title} (Copy)",
        assessment_type=original.assessment_type,
        academic_year=original.academic_year,
        maximum_grade=original.maximum_grade,
        status="draft",
    )
    session.add(new_assessment)
    session.flush()

    # Copy questions
    for q in original.questions:
        new_q = Question(
            assessment_id=new_assessment.id,
            question_number=q.question_number,
            title=q.title,
            maximum_grade=q.maximum_grade,
            rubric=q.rubric,
        )
        session.add(new_q)
    session.flush()
    return _assessment_to_result(new_assessment)


def search_assessments(
    session: Session, query_str: str, material_id: str | None = None
) -> list[AssessmentResult]:
    """Search assessments by title."""
    return list_assessments(session, material_id=material_id, search_query=query_str)
