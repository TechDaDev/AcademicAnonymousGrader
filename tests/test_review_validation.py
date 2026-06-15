"""Review validation tests."""

from __future__ import annotations

from decimal import Decimal
from typing import Any as _Any

from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.student_identity import StudentIdentity
from models.submission import Submission
from services.review_service import validate_submission_for_review


def _setup(session: Session, grade: Decimal | None = Decimal("35"), status: str = "graded") -> dict[str, _Any]:
    material = Material(name="Val Test")
    session.add(material)
    session.flush()
    assessment = Assessment(material_id=material.id, title="Val Assessment", maximum_grade=Decimal("100"))
    session.add(assessment)
    session.flush()
    q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("40"))
    q2 = Question(assessment_id=assessment.id, question_number=2, maximum_grade=Decimal("60"))
    session.add_all([q1, q2])
    session.flush()
    batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html")
    session.add(batch)
    session.flush()
    identity = StudentIdentity(encrypted_first_name="enc:V")
    session.add(identity)
    session.flush()
    anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-VAL001")
    session.add(anon)
    session.flush()
    sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id)
    session.add(sub)
    session.flush()
    g1 = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("30"), grading_status="graded")
    g2 = GradeRecord(submission_id=sub.id, question_id=q2.id, grade=grade, grading_status=status)
    session.add_all([g1, g2])
    session.flush()
    sub.review_status = "ready_for_review"
    session.flush()
    return {"assessment": assessment, "submission": sub}


class TestReviewValidation:
    def test_valid_has_no_errors(self, session: Session) -> None:
        data = _setup(session)
        errors = validate_submission_for_review(session, data["submission"].id, data["assessment"].id)
        assert len(errors) == 0

    def test_missing_grade_record(self, session: Session) -> None:
        data = _setup(session)
        session.query(GradeRecord).delete()
        session.flush()
        errors = validate_submission_for_review(session, data["submission"].id, data["assessment"].id)
        assert len(errors) > 0

    def test_null_grade(self, session: Session) -> None:
        data = _setup(session, grade=None)
        errors = validate_submission_for_review(session, data["submission"].id, data["assessment"].id)
        assert len(errors) > 0

    def test_grade_above_max(self, session: Session) -> None:
        data = _setup(session, grade=Decimal("70"))  # 70 > 60 for q2
        errors = validate_submission_for_review(session, data["submission"].id, data["assessment"].id)
        assert len(errors) > 0

    def test_not_graded_status(self, session: Session) -> None:
        data = _setup(session, grade=Decimal("30"), status="draft")
        errors = validate_submission_for_review(session, data["submission"].id, data["assessment"].id)
        assert len(errors) > 0
