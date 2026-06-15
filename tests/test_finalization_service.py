"""Finalization service tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
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
    get_finalized_assessment_summary,
    verify_finalized_integrity,
)


def _setup_approved(session: Session) -> dict:  # type: ignore[type-arg]
    material = Material(name="Fin Test"); session.add(material); session.flush()
    assessment = Assessment(material_id=material.id, title="Fin Test", maximum_grade=Decimal("100"))
    session.add(assessment); session.flush()
    q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("40"))
    q2 = Question(assessment_id=assessment.id, question_number=2, maximum_grade=Decimal("60"))
    session.add_all([q1, q2]); session.flush()
    batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html"); session.add(batch); session.flush()
    identity = StudentIdentity(encrypted_first_name="enc:F"); session.add(identity); session.flush()
    anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-FIN001")
    session.add(anon); session.flush()
    sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id, review_status="approved")
    session.add(sub); session.flush()
    g1 = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("35"), grading_status="graded")
    g2 = GradeRecord(submission_id=sub.id, question_id=q2.id, grade=Decimal("55"), grading_status="graded")
    session.add_all([g1, g2]); session.flush()
    return {"assessment": assessment, "submission": sub}


class TestFinalizationReadiness:
    def test_ready_assessment_finalizes(self, session: Session) -> None:
        data = _setup_approved(session)
        result = finalize_assessment(session, data["assessment"].id)
        assert result.status == "finalized"
        assert result.submission_count == 1
        assert result.final_grade_total == Decimal("90")

    def test_unapproved_submission_blocks(self, session: Session) -> None:
        data = _setup_approved(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.review_status = "ready_for_review"; session.flush()
        readiness = get_finalization_readiness(session, data["assessment"].id)
        assert not readiness.is_ready

    def test_needs_correction_blocks(self, session: Session) -> None:
        data = _setup_approved(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.review_status = "needs_correction"; session.flush()
        readiness = get_finalization_readiness(session, data["assessment"].id)
        assert not readiness.is_ready

    def test_missing_grade_record_blocks(self, session: Session) -> None:
        data = _setup_approved(session)
        session.query(GradeRecord).delete(); session.flush()
        readiness = get_finalization_readiness(session, data["assessment"].id)
        assert not readiness.is_ready

    def test_null_grade_blocks(self, session: Session) -> None:
        data = _setup_approved(session)
        gr = session.query(GradeRecord).first()
        assert gr is not None
        gr.grade = None; session.flush()
        readiness = get_finalization_readiness(session, data["assessment"].id)
        assert not readiness.is_ready

    def test_grade_above_max_blocks(self, session: Session) -> None:
        data = _setup_approved(session)
        gr = session.query(GradeRecord).first()
        assert gr is not None
        gr.grade = Decimal("999"); session.flush()
        readiness = get_finalization_readiness(session, data["assessment"].id)
        assert not readiness.is_ready

    def test_no_submissions_blocks(self, session: Session) -> None:
        data = _setup_approved(session)
        session.query(Submission).delete(); session.flush()
        readiness = get_finalization_readiness(session, data["assessment"].id)
        assert not readiness.is_ready

    def test_second_finalization_blocked(self, session: Session) -> None:
        data = _setup_approved(session)
        finalize_assessment(session, data["assessment"].id)
        with pytest.raises(AssessmentAlreadyFinalizedError):
            finalize_assessment(session, data["assessment"].id)

    def test_finalization_timestamp_stored(self, session: Session) -> None:
        data = _setup_approved(session)
        result = finalize_assessment(session, data["assessment"].id)
        assert result.finalized_at is not None
        assessment = session.query(Assessment).filter(Assessment.id == data["assessment"].id).first()
        assert assessment is not None
        assert assessment.finalized_at is not None
        assert assessment.finalization_status == "finalized"

    def test_final_grade_uses_grade_record_only(self, session: Session) -> None:
        data = _setup_approved(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.source_grade = Decimal("999")  # Should be ignored
        session.flush()
        result = finalize_assessment(session, data["assessment"].id)
        assert result.final_grade_total == Decimal("90")

    def test_question_total_mismatch_blocks(self, session: Session) -> None:
        data = _setup_approved(session)
        q = session.query(Question).filter(Question.assessment_id == data["assessment"].id).first()
        assert q is not None
        q.maximum_grade = Decimal("50"); session.flush()
        readiness = get_finalization_readiness(session, data["assessment"].id)
        assert not readiness.is_ready


class TestFinalizedSummary:
    def test_summary_returns_data(self, session: Session) -> None:
        data = _setup_approved(session)
        finalize_assessment(session, data["assessment"].id)
        summary = get_finalized_assessment_summary(session, data["assessment"].id)
        assert summary is not None
        assert summary.total_submissions == 1
        assert summary.average_grade == Decimal("90")

    def test_summary_none_if_not_finalized(self, session: Session) -> None:
        data = _setup_approved(session)
        summary = get_finalized_assessment_summary(session, data["assessment"].id)
        assert summary is None


class TestFinalizedIntegrity:
    def test_integrity_passes(self, session: Session) -> None:
        data = _setup_approved(session)
        finalize_assessment(session, data["assessment"].id)
        assert verify_finalized_integrity(session, data["assessment"].id) is True

    def test_integrity_fails_if_not_finalized(self, session: Session) -> None:
        data = _setup_approved(session)
        assert verify_finalized_integrity(session, data["assessment"].id) is False
