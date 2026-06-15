"""Phase 5 database constraint tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.student_identity import StudentIdentity
from models.submission import Submission


def _setup(session: Session) -> dict:  # type: ignore[type-arg]
    material = Material(name="Constraint Test")
    session.add(material)
    session.flush()
    assessment = Assessment(
        material_id=material.id, title="Constraint Assessment",
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
    batch = ImportBatch(assessment_id=assessment.id, source_filename="test.html")
    session.add(batch)
    session.flush()
    identity = StudentIdentity(encrypted_first_name="enc:X")
    session.add(identity)
    session.flush()
    anon = AnonymousStudent(
        student_identity_id=identity.id, anonymous_code="STU-CON01",
    )
    session.add(anon)
    session.flush()
    sub = Submission(
        assessment_id=assessment.id, anonymous_student_id=anon.id,
        import_batch_id=batch.id,
    )
    session.add(sub)
    session.flush()
    return {"assessment": assessment, "q1": q1, "submission": sub}


class TestGradeRecordConstraints:
    def test_duplicate_grade_blocked(self, session: Session) -> None:
        data = _setup(session)
        g1 = GradeRecord(
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            grade=Decimal("25"),
        )
        g2 = GradeRecord(
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            grade=Decimal("30"),
        )
        session.add_all([g1, g2])
        with pytest.raises(IntegrityError):
            session.flush()

    def test_grade_requires_valid_submission(self, session: Session) -> None:
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            gr = GradeRecord(
                submission_id="00000000-0000-0000-0000-000000000000",
                question_id="00000000-0000-0000-0000-000000000000",
            )
            session.add(gr)
            session.flush()
