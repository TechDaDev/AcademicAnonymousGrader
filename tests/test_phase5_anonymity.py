"""Phase 5 anonymity tests — grading must never expose identities."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.student_identity import StudentIdentity
from models.submission import Submission
from services.grading_service import (
    get_grading_submission,
    list_anonymous_submissions,
)


def _setup(session: Session) -> dict:  # type: ignore[type-arg]
    material = Material(name="Anonymity Test")
    session.add(material)
    session.flush()
    assessment = Assessment(
        material_id=material.id, title="Anonymity Assessment",
        maximum_grade=Decimal("100"),
    )
    session.add(assessment)
    session.flush()
    q1 = Question(
        assessment_id=assessment.id, question_number=1,
        maximum_grade=Decimal("50"),
    )
    session.add(q1)
    session.flush()
    batch = ImportBatch(
        assessment_id=assessment.id, source_filename="test.html",
    )
    session.add(batch)
    session.flush()
    identity = StudentIdentity(
        encrypted_first_name="enc:Alice",
        encrypted_last_name="enc:Smith",
        encrypted_email="enc:alice@example.com",
        encrypted_institutional_student_id="enc:S12345",
    )
    session.add(identity)
    session.flush()
    anon = AnonymousStudent(
        student_identity_id=identity.id,
        anonymous_code="STU-ANON01",
    )
    session.add(anon)
    session.flush()
    sub = Submission(
        assessment_id=assessment.id,
        anonymous_student_id=anon.id,
        import_batch_id=batch.id,
    )
    session.add(sub)
    session.flush()
    return {"assessment": assessment, "submission": sub, "identity": identity, "anon": anon}


class TestGradingAnonymity:
    def test_list_does_not_return_names(self, session: Session) -> None:
        data = _setup(session)
        results = list_anonymous_submissions(session, data["assessment"].id)
        for r in results:
            assert r.anonymous_code == "STU-ANON01"
            assert not hasattr(r, "first_name")
            assert not hasattr(r, "last_name")
            assert not hasattr(r, "email")

    def test_list_does_not_expose_identity_id(self, session: Session) -> None:
        data = _setup(session)
        results = list_anonymous_submissions(session, data["assessment"].id)
        for r in results:
            assert not hasattr(r, "student_identity_id")
            assert not hasattr(r, "encrypted_first_name")

    def test_view_does_not_return_names(self, session: Session) -> None:
        data = _setup(session)
        view = get_grading_submission(
            session, data["submission"].id, data["assessment"].id,
        )
        assert view is not None
        assert view.anonymous_code == "STU-ANON01"
        assert not hasattr(view, "first_name")
        assert not hasattr(view, "last_name")
        assert not hasattr(view, "email")

    def test_view_does_not_include_student_identity(self, session: Session) -> None:
        data = _setup(session)
        view = get_grading_submission(
            session, data["submission"].id, data["assessment"].id,
        )
        assert view is not None
        # Should reference anonymous student, not StudentIdentity
        anon = (
            session.query(AnonymousStudent)
            .filter(AnonymousStudent.anonymous_code == "STU-ANON01")
            .first()
        )
        assert anon is not None
        assert anon.student_identity_id is not None  # FK exists
        # But the view should not expose it
        view_str = str(view)
        assert "Alice" not in view_str
        assert "alice@example.com" not in view_str

    def test_repr_safe(self, session: Session) -> None:
        data = _setup(session)
        view = get_grading_submission(
            session, data["submission"].id, data["assessment"].id,
        )
        assert view is not None
        rep = repr(view)
        assert "STU-ANON01" in rep
        assert "Alice" not in rep
