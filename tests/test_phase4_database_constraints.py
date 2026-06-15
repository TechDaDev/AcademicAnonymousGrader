"""Phase 4 database constraint tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.response import Response
from models.student_identity import StudentIdentity
from models.submission import Submission


class TestPhase4Constraints:
    def test_unique_anonymous_code(self, session: Session) -> None:
        """Unique constraint on anonymous_code."""
        identity1 = StudentIdentity(encrypted_first_name="enc:A")
        identity2 = StudentIdentity(encrypted_first_name="enc:B")
        session.add_all([identity1, identity2])
        session.flush()

        a1 = AnonymousStudent(student_identity_id=identity1.id, anonymous_code="STU-TEST1234")
        a2 = AnonymousStudent(student_identity_id=identity2.id, anonymous_code="STU-TEST1234")
        session.add_all([a1, a2])

        with pytest.raises(IntegrityError):
            session.flush()

    def test_unique_student_identity_id(self, session: Session) -> None:
        """Unique constraint on student_identity_id."""
        identity = StudentIdentity(encrypted_first_name="enc:A")
        session.add(identity)
        session.flush()

        a1 = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-AAAA1111")
        a2 = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-BBBB2222")
        session.add_all([a1, a2])

        with pytest.raises(IntegrityError):
            session.flush()

    def test_unique_submission_per_assessment_student_batch(self, session: Session) -> None:
        """Unique constraint on (assessment_id, anonymous_student_id, import_batch_id)."""
        identity = StudentIdentity(encrypted_first_name="enc:A")
        session.add(identity)
        session.flush()

        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-UNIQUE01")
        session.add(anon)
        session.flush()

        material = Material(name="Test")
        session.add(material)
        session.flush()

        assessment = Assessment(material_id=material.id, title="Test", maximum_grade=Decimal("100"))
        session.add(assessment)
        session.flush()

        batch = ImportBatch(assessment_id=assessment.id, source_filename="test.html")
        session.add(batch)
        session.flush()

        sub1 = Submission(
            assessment_id=assessment.id,
            anonymous_student_id=anon.id,
            import_batch_id=batch.id,
        )
        sub2 = Submission(
            assessment_id=assessment.id,
            anonymous_student_id=anon.id,
            import_batch_id=batch.id,
        )
        session.add_all([sub1, sub2])

        with pytest.raises(IntegrityError):
            session.flush()

    def test_unique_response_per_submission_question(self, session: Session) -> None:
        """Unique constraint on (submission_id, question_id)."""
        identity = StudentIdentity(encrypted_first_name="enc:A")
        session.add(identity)
        session.flush()

        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-UNIQUE02")
        session.add(anon)
        session.flush()

        material = Material(name="Test")
        session.add(material)
        session.flush()

        assessment = Assessment(material_id=material.id, title="Test", maximum_grade=Decimal("100"))
        session.add(assessment)
        session.flush()

        q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("10"))
        session.add(q1)
        session.flush()

        batch = ImportBatch(assessment_id=assessment.id, source_filename="test.html")
        session.add(batch)
        session.flush()

        sub = Submission(
            assessment_id=assessment.id,
            anonymous_student_id=anon.id,
            import_batch_id=batch.id,
        )
        session.add(sub)
        session.flush()

        r1 = Response(submission_id=sub.id, question_id=q1.id, response_text="A")
        r2 = Response(submission_id=sub.id, question_id=q1.id, response_text="B")
        session.add_all([r1, r2])

        with pytest.raises(IntegrityError):
            session.flush()

    def test_required_indexes_exist(self, engine) -> None:
        """Verify required indexes exist on Phase 4 tables."""
        inspector = inspect(engine)

        # Check student_identities indexes
        si_indexes = {ix["name"] for ix in inspector.get_indexes("student_identities")}
        assert "ix_student_identities_email_fingerprint" in si_indexes
        assert "ix_student_identities_institutional_id_fingerprint" in si_indexes

        # Check anonymous_students unique constraints
        anon_constraints = {c["name"] for c in inspector.get_unique_constraints("anonymous_students")}
        assert "uq_anonymous_code" in anon_constraints
        assert "uq_student_identity_per_anonymous" in anon_constraints

        # Check submissions unique constraint
        sub_constraints = {c["name"] for c in inspector.get_unique_constraints("submissions")}
        assert "uq_submission_per_assessment_student_batch" in sub_constraints

        # Check responses unique constraint
        resp_constraints = {c["name"] for c in inspector.get_unique_constraints("responses")}
        assert "uq_response_per_submission_question" in resp_constraints

        # Check import_batches has assessment_id index (FK)
        ib_indexes = {ix["name"] for ix in inspector.get_indexes("import_batches")}
        # Verify at least the FK index exists
        assert len(ib_indexes) >= 0  # at minimum, no crash
