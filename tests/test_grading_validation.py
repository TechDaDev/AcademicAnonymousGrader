"""Grading validation tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.student_identity import StudentIdentity
from models.submission import Submission
from services.exceptions import InvalidGradeError
from services.grading_service import save_submission_grades


def _setup(session: Session) -> dict:  # type: ignore[type-arg]
    material = Material(name="Validation Test")
    session.add(material)
    session.flush()
    assessment = Assessment(
        material_id=material.id, title="Validation Assessment",
        maximum_grade=Decimal("100"),
    )
    session.add(assessment)
    session.flush()
    q1 = Question(
        assessment_id=assessment.id, question_number=1,
        maximum_grade=Decimal("50"), title="Q1",
    )
    q2 = Question(
        assessment_id=assessment.id, question_number=2,
        maximum_grade=Decimal("50"), title="Q2",
    )
    session.add_all([q1, q2])
    session.flush()
    batch = ImportBatch(assessment_id=assessment.id, source_filename="test.html")
    session.add(batch)
    session.flush()
    identity = StudentIdentity(encrypted_first_name="enc:X")
    session.add(identity)
    session.flush()
    anon = AnonymousStudent(
        student_identity_id=identity.id, anonymous_code="STU-VAL01",
    )
    session.add(anon)
    session.flush()
    sub = Submission(
        assessment_id=assessment.id, anonymous_student_id=anon.id,
        import_batch_id=batch.id,
    )
    session.add(sub)
    session.flush()
    return {"assessment": assessment, "q1": q1, "q2": q2, "submission": sub}


class TestGradeValidation:
    def test_reject_negative(self, session: Session) -> None:
        data = _setup(session)
        with pytest.raises(InvalidGradeError, match="below zero"):
            save_submission_grades(
                session=session,
                submission_id=data["submission"].id,
                assessment_id=data["assessment"].id,
                grades={data["q1"].id: "-10"},
                feedbacks={},
            )

    def test_reject_above_question_max(self, session: Session) -> None:
        data = _setup(session)
        with pytest.raises(InvalidGradeError, match="exceeds maximum"):
            save_submission_grades(
                session=session,
                submission_id=data["submission"].id,
                assessment_id=data["assessment"].id,
                grades={data["q1"].id: "60"},
                feedbacks={},
            )

    def test_reject_invalid_decimal(self, session: Session) -> None:
        data = _setup(session)
        with pytest.raises(InvalidGradeError, match="not a valid number"):
            save_submission_grades(
                session=session,
                submission_id=data["submission"].id,
                assessment_id=data["assessment"].id,
                grades={data["q1"].id: "abc"},
                feedbacks={},
            )

    def test_draft_allows_missing_grade(self, session: Session) -> None:
        data = _setup(session)
        result = save_submission_grades(
            session=session,
            submission_id=data["submission"].id,
            assessment_id=data["assessment"].id,
            grades={data["q1"].id: ""},
            feedbacks={},
        )
        assert result.current_total == Decimal("0")
        assert not result.is_complete

    def test_mark_graded_rejects_missing_grade(self, session: Session) -> None:
        data = _setup(session)
        from services.exceptions import IncompleteGradingError
        with pytest.raises(IncompleteGradingError):
            save_submission_grades(
                session=session,
                submission_id=data["submission"].id,
                assessment_id=data["assessment"].id,
                grades={data["q1"].id: "30"},
                feedbacks={},
                marking_graded=True,
            )
