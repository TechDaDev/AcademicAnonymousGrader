"""Phase 6 anonymity tests."""

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
from services.review_service import (
    get_review_submission,
    list_review_submissions,
)


def _setup(session: Session) -> dict[str, _Any]:
    material = Material(name="Anon6 Test")
    session.add(material)
    session.flush()
    assessment = Assessment(material_id=material.id, title="Anon6", maximum_grade=Decimal("100"))
    session.add(assessment)
    session.flush()
    q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("100"))
    session.add(q1)
    session.flush()
    batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html")
    session.add(batch)
    session.flush()
    identity = StudentIdentity(
        encrypted_first_name="enc:Phase6", encrypted_last_name="enc:Test",
        encrypted_email="enc:test@example.com", encrypted_institutional_student_id="enc:S6",
    )
    session.add(identity)
    session.flush()
    anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-ANON6")
    session.add(anon)
    session.flush()
    sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id)
    session.add(sub)
    session.flush()
    gr = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("85"), grading_status="graded")
    session.add(gr)
    session.flush()
    sub.review_status = "ready_for_review"
    session.flush()
    return {"assessment": assessment, "submission": sub}


class TestReviewAnonymity:
    def test_list_no_identities(self, session: Session) -> None:
        data = _setup(session)
        results = list_review_submissions(session, data["assessment"].id)
        for r in results:
            assert r.anonymous_code == "STU-ANON6"
            assert not hasattr(r, "first_name")
            assert not hasattr(r, "email")
            assert not hasattr(r, "encrypted_first_name")

    def test_view_no_identities(self, session: Session) -> None:
        data = _setup(session)
        view = get_review_submission(session, data["submission"].id, data["assessment"].id)
        assert view is not None
        assert view.anonymous_code == "STU-ANON6"
        assert not hasattr(view, "first_name")
        assert not hasattr(view, "email")

    def test_safe_repr(self, session: Session) -> None:
        data = _setup(session)
        view = get_review_submission(session, data["submission"].id, data["assessment"].id)
        assert view is not None
        rep = repr(view)
        assert "STU-ANON6" in rep
        assert "enc:Phase6" not in rep
