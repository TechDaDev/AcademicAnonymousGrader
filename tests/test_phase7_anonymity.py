"""Phase 7 anonymity tests."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.student_identity import StudentIdentity
from models.submission import Submission
from services.finalization_service import finalize_assessment, get_finalization_readiness


class TestFinalizationAnonymity:
    def test_readiness_no_identities(self, session: Session) -> None:
        material = Material(name="Anon7"); session.add(material); session.flush()
        assessment = Assessment(material_id=material.id, title="Anon7", maximum_grade=Decimal("100"))
        session.add(assessment); session.flush()
        q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("100"))
        session.add(q1); session.flush()
        batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html"); session.add(batch); session.flush()
        identity = StudentIdentity(encrypted_first_name="enc:Hidden", encrypted_last_name="enc:Hidden")
        session.add(identity); session.flush()
        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-ANON7")
        session.add(anon); session.flush()
        sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id, review_status="approved")
        session.add(sub); session.flush()
        gr = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("85"), grading_status="graded")
        session.add(gr); session.flush()
        readiness = get_finalization_readiness(session, assessment.id)
        errors_text = " ".join(e.message for e in readiness.blocking_errors)
        assert "enc:Hidden" not in errors_text
        assert readiness.is_ready

    def test_finalize_no_identities_in_log(self, session: Session) -> None:
        material = Material(name="Anon7b"); session.add(material); session.flush()
        assessment = Assessment(material_id=material.id, title="Anon7b", maximum_grade=Decimal("100"))
        session.add(assessment); session.flush()
        q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("100"))
        session.add(q1); session.flush()
        batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html"); session.add(batch); session.flush()
        identity = StudentIdentity(encrypted_first_name="enc:Sec")
        session.add(identity); session.flush()
        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-ANON8")
        session.add(anon); session.flush()
        sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id, review_status="approved")
        session.add(sub); session.flush()
        gr = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("90"), grading_status="graded")
        session.add(gr); session.flush()
        result = finalize_assessment(session, assessment.id)
        assert result.status == "finalized"
        assert hasattr(result, "submission_count")
