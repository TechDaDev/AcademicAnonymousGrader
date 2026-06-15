"""Phase 6 database constraint tests for review columns."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.import_batch import ImportBatch
from models.material import Material
from models.student_identity import StudentIdentity
from models.submission import Submission


class TestReviewConstraints:
    def test_review_status_default(self, session: Session) -> None:
        material = Material(name="RC Test")
        session.add(material)
        session.flush()
        assessment = Assessment(material_id=material.id, title="RC", maximum_grade=Decimal("100"))
        session.add(assessment)
        session.flush()
        batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html")
        session.add(batch)
        session.flush()
        identity = StudentIdentity(encrypted_first_name="enc:RC")
        session.add(identity)
        session.flush()
        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-RC001")
        session.add(anon)
        session.flush()
        sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id)
        session.add(sub)
        session.flush()
        session.refresh(sub)
        assert sub.review_status == "not_ready"
        assert sub.reviewed_at is None
        assert sub.review_note is None

    def test_review_status_allowed_values(self, session: Session) -> None:
        material = Material(name="RC2")
        session.add(material)
        session.flush()
        assessment = Assessment(material_id=material.id, title="RC2", maximum_grade=Decimal("100"))
        session.add(assessment)
        session.flush()
        batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html")
        session.add(batch)
        session.flush()
        identity = StudentIdentity(encrypted_first_name="enc:RC2")
        session.add(identity)
        session.flush()
        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-RC002")
        session.add(anon)
        session.flush()
        sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id)
        session.add(sub)
        session.flush()

        for status in ("not_ready", "ready_for_review", "needs_correction", "approved"):
            sub.review_status = status
            session.flush()
            session.refresh(sub)
            assert sub.review_status == status

    def test_reviewed_at_updatable(self, session: Session) -> None:
        material = Material(name="RC3")
        session.add(material)
        session.flush()
        assessment = Assessment(material_id=material.id, title="RC3", maximum_grade=Decimal("100"))
        session.add(assessment)
        session.flush()
        batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html")
        session.add(batch)
        session.flush()
        identity = StudentIdentity(encrypted_first_name="enc:RC3")
        session.add(identity)
        session.flush()
        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-RC003")
        session.add(anon)
        session.flush()
        sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id)
        session.add(sub)
        session.flush()
        now = datetime.now(UTC)
        sub.reviewed_at = now
        sub.review_status = "approved"
        session.flush()
        session.refresh(sub)
        assert sub.reviewed_at is not None
        assert sub.review_note is None

    def test_review_note_stores_text(self, session: Session) -> None:
        material = Material(name="RC4")
        session.add(material)
        session.flush()
        assessment = Assessment(material_id=material.id, title="RC4", maximum_grade=Decimal("100"))
        session.add(assessment)
        session.flush()
        batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html")
        session.add(batch)
        session.flush()
        identity = StudentIdentity(encrypted_first_name="enc:RC4")
        session.add(identity)
        session.flush()
        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-RC004")
        session.add(anon)
        session.flush()
        sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id)
        session.add(sub)
        session.flush()
        note = "Needs correction: verify Q2 calculation"
        sub.review_note = note
        sub.review_status = "needs_correction"
        session.flush()
        session.refresh(sub)
        assert sub.review_note == note

    def test_review_status_column_exists(self, session: Session) -> None:
        from sqlalchemy import inspect
        inspector = inspect(session.bind)
        assert inspector is not None
        columns = [col["name"] for col in inspector.get_columns("submissions")]
        assert "review_status" in columns
        assert "reviewed_at" in columns
        assert "review_note" in columns
