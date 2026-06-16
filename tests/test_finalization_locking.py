"""Finalization locking tests."""

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
from security.encryption import encrypt_text
from security.key_validation import _decode_key
from security.models import EncryptionKey
from services.authorization_service import AuthContext
from services.exceptions import FinalizedAssessmentModificationError
from services.finalization_service import finalize_assessment
from services.grading_service import save_submission_grades
from services.question_service import create_question, delete_question
from services.review_service import (
    approve_submission_review,
    mark_submission_needs_correction,
    return_submission_to_grading,
)


def _get_key(settings) -> EncryptionKey:
    raw = settings.identity_encryption_key
    return EncryptionKey(_decode_key(raw, "IDENTITY_ENCRYPTION_KEY", 32))


def _setup_finalized(session: Session) -> dict:  # type: ignore[type-arg]
    material = Material(name="Lock Test"); session.add(material); session.flush()
    assessment = Assessment(material_id=material.id, title="Lock", maximum_grade=Decimal("100"))
    session.add(assessment); session.flush()
    q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("40"))
    q2 = Question(assessment_id=assessment.id, question_number=2, maximum_grade=Decimal("60"))
    session.add_all([q1, q2]); session.flush()
    batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html"); session.add(batch); session.flush()
    identity = StudentIdentity(encrypted_first_name="enc:L"); session.add(identity); session.flush()
    anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-LOCK01")
    session.add(anon); session.flush()
    sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id, review_status="approved")
    session.add(sub); session.flush()
    g1 = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("35"), grading_status="graded")
    g2 = GradeRecord(submission_id=sub.id, question_id=q2.id, grade=Decimal("55"), grading_status="graded")
    session.add_all([g1, g2]); session.flush()
    finalize_assessment(session, assessment.id, auth_ctx=_ADMIN_AUTH)
    return {"assessment": assessment, "q1": q1, "q2": q2, "submission": sub}


class TestGradingLocking:
    def test_edit_grade_after_finalization_blocked(self, session: Session) -> None:
        data = _setup_finalized(session)
        with pytest.raises(FinalizedAssessmentModificationError):
            save_submission_grades(
                session, data["submission"].id, data["assessment"].id,
                grades={data["q1"].id: "40"}, feedbacks={},
            )


class TestQuestionLocking:
    def test_add_question_after_finalization_blocked(self, session: Session) -> None:
        data = _setup_finalized(session)
        with pytest.raises(FinalizedAssessmentModificationError):
            create_question(
                session, data["assessment"].id,
                question_number=3, maximum_grade=Decimal("10"),
            )

    def test_delete_question_after_finalization_blocked(self, session: Session) -> None:
        data = _setup_finalized(session)
        with pytest.raises(FinalizedAssessmentModificationError):
            delete_question(session, data["q1"].id)


class TestReviewLocking:
    def test_approve_after_finalization_blocked(self, session: Session) -> None:
        data = _setup_finalized(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.review_status = "ready_for_review"; session.flush()
        with pytest.raises(FinalizedAssessmentModificationError):
            approve_submission_review(session, data["submission"].id, data["assessment"].id)

    def test_needs_correction_after_finalization_blocked(self, session: Session) -> None:
        data = _setup_finalized(session)
        with pytest.raises(FinalizedAssessmentModificationError):
            mark_submission_needs_correction(
                session, data["submission"].id, data["assessment"].id, reviewer_note="test",
            )

    def test_return_to_grading_after_finalization_blocked(self, session: Session) -> None:
        data = _setup_finalized(session)
        with pytest.raises(FinalizedAssessmentModificationError):
            return_submission_to_grading(session, data["submission"].id, data["assessment"].id)


class TestReExport:
    @staticmethod
    def _setup_full(session: Session, key) -> dict:  # type: ignore[type-arg]
        material = Material(name="ReExp"); session.add(material); session.flush()
        assessment = Assessment(material_id=material.id, title="ReExp", maximum_grade=Decimal("100"))
        session.add(assessment); session.flush()
        q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("100"))
        session.add(q1); session.flush()
        batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html"); session.add(batch); session.flush()
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(key, "ReExport"),
            encrypted_last_name=encrypt_text(key, "Test"),
            encrypted_email=encrypt_text(key, "re@example.com"),
        )
        session.add(identity); session.flush()
        anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-REEXP01")
        session.add(anon); session.flush()
        sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id, review_status="approved")
        session.add(sub); session.flush()
        gr = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("85"), grading_status="graded")
        session.add(gr); session.flush()
        finalize_assessment(session, assessment.id, auth_ctx=_ADMIN_AUTH)
        return {"assessment": assessment, "submission": sub}

    def test_reexport_allowed(self, session: Session, monkeypatch) -> None:
        from services.excel_export_service import generate_export_workbook
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", "8k7lYYckaMaqKDy31LgQhPCTvSup2elJtoEm0TEztXY=")
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", "yQH1YtA5kQtrilNmVo_qxLT0Yty4sl4k5vZMDnxgp-c=")
        from config import get_settings
        settings = get_settings()
        key = _get_key(settings)
        data = self._setup_full(session, key)
        # First export
        r1 = generate_export_workbook(session, data["assessment"].id, settings, auth_ctx=_ADMIN_AUTH)
        # Re-export — should work
        r2 = generate_export_workbook(session, data["assessment"].id, settings, auth_ctx=_ADMIN_AUTH)
        assert r2.export_reference != r1.export_reference
        # Grades unchanged (original 1 record)
        from models.grade_record import GradeRecord as GradeRec
        grades = session.query(GradeRec).all()
        assert len(grades) == 1
        # Finalization state unchanged
        a = session.query(Assessment).filter(Assessment.id == data["assessment"].id).first()
        assert a is not None
        assert a.finalization_status == "finalized"

_ADMIN_AUTH = AuthContext(user_id="test-admin", role="administrator")
