# Academic Anonymous Grader — Question Service Tests
"""Tests for services/question_service.py."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from models.assessment import Assessment
from models.material import Material
from services.assessment_service import create_assessment
from services.exceptions import (
    QuestionNotFoundError,
    QuestionValidationError,
)
from services.material_service import create_material
from services.question_service import (
    calculate_question_total,
    create_question,
    delete_question,
    list_questions,
    reorder_questions,
)


@pytest.fixture(scope="function")
def assessment(session: Session) -> Assessment:
    m = create_material(session, name="Test Material")
    session.flush()
    mat = session.query(Material).filter(Material.id == m.id).first()
    assert mat is not None
    a = create_assessment(session, material_id=mat.id, title="Test Assessment", maximum_grade=Decimal("100"))
    session.flush()
    result = session.query(Assessment).filter(Assessment.id == a.id).first()
    assert result is not None
    return result


class TestCreateQuestion:
    """Question creation tests."""

    def test_create_valid_question(self, session: Session, assessment: Assessment) -> None:
        q = create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("10.00"))
        session.flush()
        assert q.question_number == 1
        assert q.maximum_grade == Decimal("10.00")

    def test_reject_number_zero(self, session: Session, assessment: Assessment) -> None:
        with pytest.raises(QuestionValidationError, match="greater than zero"):
            create_question(session, assessment.id, question_number=0, maximum_grade=Decimal("10"))

    def test_reject_negative_number(self, session: Session, assessment: Assessment) -> None:
        with pytest.raises(QuestionValidationError, match="greater than zero"):
            create_question(session, assessment.id, question_number=-1, maximum_grade=Decimal("10"))

    def test_reject_duplicate_number(self, session: Session, assessment: Assessment) -> None:
        create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("10"))
        session.flush()
        with pytest.raises(QuestionValidationError, match="already exists"):
            create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("5"))

    def test_reject_zero_maximum_grade(self, session: Session, assessment: Assessment) -> None:
        with pytest.raises(QuestionValidationError, match="greater than zero"):
            create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("0"))

    def test_reject_negative_maximum_grade(self, session: Session, assessment: Assessment) -> None:
        with pytest.raises(QuestionValidationError, match="greater than zero"):
            create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("-5"))

    def test_preserve_decimal_exactly(self, session: Session, assessment: Assessment) -> None:
        q = create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("7.25"))
        session.flush()
        assert isinstance(q.maximum_grade, Decimal)
        assert q.maximum_grade == Decimal("7.25")

    def test_same_number_different_assessment_allowed(self, session: Session) -> None:
        m = create_material(session, name="M")
        session.flush()
        mat = session.query(Material).filter(Material.id == m.id).first()
        assert mat is not None
        a1 = create_assessment(session, material_id=mat.id, title="A1", maximum_grade=Decimal("50"))
        a2 = create_assessment(session, material_id=mat.id, title="A2", maximum_grade=Decimal("50"))
        session.flush()
        create_question(session, a1.id, question_number=1, maximum_grade=Decimal("10"))
        session.flush()
        q2 = create_question(session, a2.id, question_number=1, maximum_grade=Decimal("20"))
        session.flush()
        assert q2.question_number == 1


class TestQuestionTotals:
    """Question total calculation tests."""

    def test_multiple_questions_total(self, session: Session, assessment: Assessment) -> None:
        create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("25.00"))
        create_question(session, assessment.id, question_number=2, maximum_grade=Decimal("35.00"))
        create_question(session, assessment.id, question_number=3, maximum_grade=Decimal("40.00"))
        session.flush()
        total = calculate_question_total(session, assessment.id)
        assert total == Decimal("100.00")

    def test_reorder_questions(self, session: Session, assessment: Assessment) -> None:
        q1 = create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("10"))
        q2 = create_question(session, assessment.id, question_number=2, maximum_grade=Decimal("20"))
        session.flush()
        reorder_questions(session, assessment.id, [q2.id, q1.id])
        session.flush()
        questions = list_questions(session, assessment.id)
        assert questions[0].question_number == 1
        assert questions[0].id == q2.id


class TestDeleteQuestion:
    """Question deletion tests."""

    def test_delete_draft_question(self, session: Session, assessment: Assessment) -> None:
        q = create_question(session, assessment.id, question_number=1, maximum_grade=Decimal("10"))
        session.flush()
        delete_question(session, q.id)
        session.flush()
        questions = list_questions(session, assessment.id)
        assert len(questions) == 0

    def test_nonexistent_question_raises_error(self, session: Session) -> None:
        with pytest.raises(QuestionNotFoundError):
            delete_question(session, "bad-id")
