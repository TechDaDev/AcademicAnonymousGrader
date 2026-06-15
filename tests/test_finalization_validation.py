"""Finalization validation tests — comprehensive validation matrix."""

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
from services.exceptions import (
    AssessmentAlreadyFinalizedError,
)
from services.finalization_service import (
    finalize_assessment,
    get_finalization_readiness,
)


def _setup_base(session: Session) -> dict:  # type: ignore[type-arg]
    material = Material(name="FVal"); session.add(material); session.flush()
    assessment = Assessment(material_id=material.id, title="FVal", maximum_grade=Decimal("100"))
    session.add(assessment); session.flush()
    q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("40"))
    q2 = Question(assessment_id=assessment.id, question_number=2, maximum_grade=Decimal("60"))
    session.add_all([q1, q2]); session.flush()
    batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html"); session.add(batch); session.flush()
    identity = StudentIdentity(encrypted_first_name="enc:FV"); session.add(identity); session.flush()
    anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-FVAL01")
    session.add(anon); session.flush()
    sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id, review_status="approved")
    session.add(sub); session.flush()
    g1 = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("35"), grading_status="graded")
    g2 = GradeRecord(submission_id=sub.id, question_id=q2.id, grade=Decimal("55"), grading_status="graded")
    session.add_all([g1, g2]); session.flush()
    return {"assessment": assessment, "q1": q1, "q2": q2, "sub": sub}


class TestFinalizationValidation:
    def test_no_questions_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        session.query(GradeRecord).delete(); session.flush()
        session.query(Question).delete(); session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_question_total_mismatch_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        q = session.query(Question).filter(Question.id == data["q1"].id).first()
        assert q is not None
        q.maximum_grade = Decimal("50"); session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_no_submissions_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        session.query(Submission).delete(); session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_unapproved_submission_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        sub = session.query(Submission).filter(Submission.id == data["sub"].id).first()
        assert sub is not None
        sub.review_status = "ready_for_review"; session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_needs_correction_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        sub = session.query(Submission).filter(Submission.id == data["sub"].id).first()
        assert sub is not None
        sub.review_status = "needs_correction"; session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_missing_grade_record_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        session.query(GradeRecord).delete(); session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_null_grade_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        gr = session.query(GradeRecord).first()
        assert gr is not None
        gr.grade = None; session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_grade_below_zero_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        gr = session.query(GradeRecord).first()
        assert gr is not None
        gr.grade = Decimal("-5"); session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_grade_above_question_max_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        gr = session.query(GradeRecord).filter(GradeRecord.question_id == data["q2"].id).first()
        assert gr is not None
        gr.grade = Decimal("999"); session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_non_graded_status_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        gr = session.query(GradeRecord).first()
        assert gr is not None
        gr.grading_status = "draft"; session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_submission_total_above_max_blocks(self, session: Session) -> None:
        data = _setup_base(session)
        gr1 = session.query(GradeRecord).filter(GradeRecord.question_id == data["q1"].id).first()
        gr2 = session.query(GradeRecord).filter(GradeRecord.question_id == data["q2"].id).first()
        assert gr1 is not None; assert gr2 is not None
        gr1.grade = Decimal("100"); gr2.grade = Decimal("100"); session.flush()
        r = get_finalization_readiness(session, data["assessment"].id)
        assert not r.is_ready

    def test_second_finalization_blocked(self, session: Session) -> None:
        data = _setup_base(session)
        finalize_assessment(session, data["assessment"].id)
        try:
            finalize_assessment(session, data["assessment"].id)
            assert False, "Should have raised"
        except AssessmentAlreadyFinalizedError:
            pass

    def test_timestamp_stored(self, session: Session) -> None:
        data = _setup_base(session)
        result = finalize_assessment(session, data["assessment"].id)
        assert result.finalized_at is not None
        assessment = session.query(Assessment).filter(Assessment.id == data["assessment"].id).first()
        assert assessment is not None
        assert assessment.finalization_status == "finalized"

    def test_source_grade_ignored(self, session: Session) -> None:
        data = _setup_base(session)
        sub = session.query(Submission).filter(Submission.id == data["sub"].id).first()
        assert sub is not None
        sub.source_grade = Decimal("999"); session.flush()
        result = finalize_assessment(session, data["assessment"].id)
        assert result.final_grade_total == Decimal("90")
