# Academic Anonymous Grader — Assessment Service Tests
"""Tests for services/assessment_service.py."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from models.assessment import Assessment
from models.material import Material
from services.assessment_service import (
    archive_assessment,
    create_assessment,
    duplicate_assessment,
    mark_assessment_ready,
    restore_assessment,
    return_assessment_to_draft,
    update_assessment,
)
from services.exceptions import (
    AssessmentValidationError,
    InvalidAssessmentStateError,
)
from services.material_service import archive_material, create_material


@pytest.fixture(scope="function")
def material(session: Session) -> Material:
    m = create_material(session, name="Test Material")
    session.flush()
    result = session.query(Material).filter(Material.id == m.id).first()
    assert result is not None
    return result


class TestCreateAssessment:
    """Assessment creation tests."""

    def test_create_valid_assessment(self, session: Session, material: Material) -> None:
        result = create_assessment(
            session, material_id=material.id, title="Midterm",
            maximum_grade=Decimal("100.00"),
        )
        session.flush()
        assert result.title == "Midterm"
        assert result.status == "draft"
        assert result.maximum_grade == Decimal("100.00")

    def test_reject_missing_material(self, session: Session) -> None:
        with pytest.raises(AssessmentValidationError, match="Parent material not found"):
            create_assessment(session, material_id="bad-id", title="Test", maximum_grade=Decimal("10"))

    def test_reject_archived_parent_material(self, session: Session, material: Material) -> None:
        archive_material(session, material.id)
        session.flush()
        with pytest.raises(AssessmentValidationError, match="archived material"):
            create_assessment(session, material_id=material.id, title="Test", maximum_grade=Decimal("10"))

    def test_reject_blank_title(self, session: Session, material: Material) -> None:
        with pytest.raises(AssessmentValidationError, match="must not be blank"):
            create_assessment(session, material_id=material.id, title="", maximum_grade=Decimal("10"))

    def test_reject_zero_maximum_grade(self, session: Session, material: Material) -> None:
        with pytest.raises(AssessmentValidationError, match="greater than zero"):
            create_assessment(session, material_id=material.id, title="Test", maximum_grade=Decimal("0"))

    def test_reject_negative_maximum_grade(self, session: Session, material: Material) -> None:
        with pytest.raises(AssessmentValidationError, match="greater than zero"):
            create_assessment(session, material_id=material.id, title="Test", maximum_grade=Decimal("-5"))

    def test_preserve_decimal_values(self, session: Session, material: Material) -> None:
        result = create_assessment(
            session, material_id=material.id, title="Precision",
            maximum_grade=Decimal("99.99"),
        )
        session.flush()
        assert isinstance(result.maximum_grade, Decimal)
        assert result.maximum_grade == Decimal("99.99")


class TestArchiveRestoreAssessment:
    """Assessment archive and restore."""

    def test_draft_assessment_can_be_archived(self, session: Session, material: Material) -> None:
        result = create_assessment(session, material_id=material.id, title="DraftArch", maximum_grade=Decimal("50"))
        session.flush()
        archived = archive_assessment(session, result.id)
        assert archived.status == "archived"

    def test_ready_assessment_can_be_archived(self, session: Session, material: Material) -> None:
        from services.question_service import create_question
        a = create_assessment(session, material_id=material.id, title="ReadyArch", maximum_grade=Decimal("50"))
        session.flush()
        create_question(session, a.id, question_number=1, maximum_grade=Decimal("50"))
        session.flush()
        mark_assessment_ready(session, a.id)
        session.flush()
        archived = archive_assessment(session, a.id)
        assert archived.status == "archived"

    def test_archived_assessment_restores_as_draft(self, session: Session, material: Material) -> None:
        result = create_assessment(session, material_id=material.id, title="RestoreMe", maximum_grade=Decimal("50"))
        session.flush()
        archive_assessment(session, result.id)
        session.flush()
        restored = restore_assessment(session, result.id)
        assert restored.status == "draft"

    def test_grading_assessment_cannot_be_archived(self, session: Session, material: Material) -> None:
        a = create_assessment(session, material_id=material.id, title="GradingNo", maximum_grade=Decimal("50"))
        session.flush()
        a_model = session.get(Assessment, a.id)
        assert a_model is not None
        a_model.status = "grading"
        session.flush()
        with pytest.raises(InvalidAssessmentStateError, match="Cannot transition"):
            archive_assessment(session, a.id)

    def test_finalized_assessment_cannot_be_archived(self, session: Session, material: Material) -> None:
        a = create_assessment(session, material_id=material.id, title="FinalNo", maximum_grade=Decimal("50"))
        session.flush()
        a_model = session.get(Assessment, a.id)
        assert a_model is not None
        a_model.status = "finalized"
        session.flush()
        with pytest.raises(InvalidAssessmentStateError, match="Cannot transition"):
            archive_assessment(session, a.id)

    def test_reopened_assessment_cannot_be_archived(self, session: Session, material: Material) -> None:
        a = create_assessment(session, material_id=material.id, title="ReopenNo", maximum_grade=Decimal("50"))
        session.flush()
        a_model = session.get(Assessment, a.id)
        assert a_model is not None
        a_model.status = "reopened"
        session.flush()
        with pytest.raises(InvalidAssessmentStateError, match="Cannot transition"):
            archive_assessment(session, a.id)

    def test_archived_assessment_cannot_be_edited(self, session: Session, material: Material) -> None:
        result = create_assessment(session, material_id=material.id, title="Locked", maximum_grade=Decimal("50"))
        session.flush()
        archive_assessment(session, result.id)
        session.flush()
        with pytest.raises(InvalidAssessmentStateError, match="archived"):
            update_assessment(session, result.id, title="Changed")
    """Assessment duplication."""

    def test_duplicate_copies_configuration(self, session: Session, material: Material) -> None:
        a1 = create_assessment(session, material_id=material.id, title="Original", maximum_grade=Decimal("100"))
        session.flush()
        from services.question_service import create_question
        create_question(session, a1.id, question_number=1, maximum_grade=Decimal("50"))
        create_question(session, a1.id, question_number=2, maximum_grade=Decimal("50"))
        session.flush()
        dup = duplicate_assessment(session, a1.id)
        session.flush()
        assert dup.title == "Original (Copy)"
        assert dup.status == "draft"
        assert dup.maximum_grade == Decimal("100")
        assert dup.question_count == 2

    def test_duplicate_remains_draft(self, session: Session, material: Material) -> None:
        from services.question_service import create_question
        a1 = create_assessment(session, material_id=material.id, title="Source", maximum_grade=Decimal("50"))
        session.flush()
        create_question(session, a1.id, question_number=1, maximum_grade=Decimal("50"))
        session.flush()
        mark_assessment_ready(session, a1.id)
        session.flush()
        dup = duplicate_assessment(session, a1.id)
        assert dup.status == "draft"


class TestAssessmentState:
    """Assessment state transition tests."""

    def test_mark_ready_blocked_with_zero_questions(self, session: Session, material: Material) -> None:
        a = create_assessment(session, material_id=material.id, title="Empty", maximum_grade=Decimal("100"))
        session.flush()
        with pytest.raises(AssessmentValidationError, match="No questions"):
            mark_assessment_ready(session, a.id)

    def test_mark_ready_blocked_when_totals_mismatch(self, session: Session, material: Material) -> None:
        from services.question_service import create_question
        a = create_assessment(session, material_id=material.id, title="Mismatch", maximum_grade=Decimal("100"))
        session.flush()
        create_question(session, a.id, question_number=1, maximum_grade=Decimal("30"))
        session.flush()
        with pytest.raises(AssessmentValidationError, match="below"):
            mark_assessment_ready(session, a.id)

    def test_mark_ready_when_totals_match(self, session: Session, material: Material) -> None:
        from services.question_service import create_question
        a = create_assessment(session, material_id=material.id, title="Match", maximum_grade=Decimal("100"))
        session.flush()
        create_question(session, a.id, question_number=1, maximum_grade=Decimal("50"))
        create_question(session, a.id, question_number=2, maximum_grade=Decimal("50"))
        session.flush()
        ready = mark_assessment_ready(session, a.id)
        assert ready.status == "ready"

    def test_return_ready_to_draft(self, session: Session, material: Material) -> None:
        from services.question_service import create_question
        a = create_assessment(session, material_id=material.id, title="Revert", maximum_grade=Decimal("50"))
        session.flush()
        create_question(session, a.id, question_number=1, maximum_grade=Decimal("50"))
        session.flush()
        mark_assessment_ready(session, a.id)
        session.flush()
        draft = return_assessment_to_draft(session, a.id)
        assert draft.status == "draft"

    def test_archived_assessment_cannot_be_edited(self, session: Session, material: Material) -> None:
        a = create_assessment(session, material_id=material.id, title="Locked", maximum_grade=Decimal("50"))
        session.flush()
        archive_assessment(session, a.id)
        session.flush()
        with pytest.raises(InvalidAssessmentStateError, match="archived"):
            update_assessment(session, a.id, title="Changed")


class TestDecimalSum:
    """Decimal arithmetic tests."""

    def test_decimal_sum_equality(self, session: Session, material: Material) -> None:
        from services.question_service import create_question
        a = create_assessment(session, material_id=material.id, title="Decimals", maximum_grade=Decimal("5.00"))
        session.flush()
        create_question(session, a.id, question_number=1, maximum_grade=Decimal("2.25"))
        create_question(session, a.id, question_number=2, maximum_grade=Decimal("2.75"))
        session.flush()
        ready = mark_assessment_ready(session, a.id)
        assert ready.status == "ready"
