"""Review service tests."""

from __future__ import annotations

from decimal import Decimal
from typing import Any as _Any

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
    ReviewApprovalBlockedError,
    ReviewNoteRequiredError,
    ReviewSubmissionNotFoundError,
)
from services.review_service import (
    approve_submission_review,
    calculate_review_progress,
    get_review_submission,
    list_review_submissions,
    mark_submission_needs_correction,
    return_submission_to_grading,
    validate_assessment_review,
    validate_submission_for_review,
)


def _setup(session: Session) -> dict[str, _Any]:
    material = Material(name="Review Test")
    session.add(material)
    session.flush()
    assessment = Assessment(material_id=material.id, title="Review Assessment", maximum_grade=Decimal("100"))
    session.add(assessment)
    session.flush()
    q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=Decimal("40"))
    q2 = Question(assessment_id=assessment.id, question_number=2, maximum_grade=Decimal("60"))
    session.add_all([q1, q2])
    session.flush()
    batch = ImportBatch(assessment_id=assessment.id, source_filename="test.html")
    session.add(batch)
    session.flush()
    identity = StudentIdentity(encrypted_first_name="enc:R")
    session.add(identity)
    session.flush()
    anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-REV001")
    session.add(anon)
    session.flush()
    sub = Submission(assessment_id=assessment.id, anonymous_student_id=anon.id, import_batch_id=batch.id)
    session.add(sub)
    session.flush()
    # Create graded GradeRecords
    g1 = GradeRecord(submission_id=sub.id, question_id=q1.id, grade=Decimal("35"), grading_status="graded")
    g2 = GradeRecord(submission_id=sub.id, question_id=q2.id, grade=Decimal("55"), grading_status="graded")
    session.add_all([g1, g2])
    session.flush()
    return {"assessment": assessment, "q1": q1, "q2": q2, "anon": anon, "submission": sub, "batch": batch}


class TestListReviewSubmissions:
    def test_list_submissions(self, session: Session) -> None:
        data = _setup(session)
        results = list_review_submissions(session, data["assessment"].id)
        assert len(results) == 1
        assert results[0].anonymous_code == "STU-REV001"
        assert results[0].review_status == "not_ready"

    def test_list_no_names(self, session: Session) -> None:
        data = _setup(session)
        results = list_review_submissions(session, data["assessment"].id)
        for r in results:
            assert not hasattr(r, "first_name")
            assert not hasattr(r, "email")


class TestGetReviewSubmission:
    def test_get_submission(self, session: Session) -> None:
        data = _setup(session)
        view = get_review_submission(session, data["submission"].id, data["assessment"].id)
        assert view is not None
        assert view.anonymous_code == "STU-REV001"
        assert len(view.questions) == 2
        assert view.total_grade == Decimal("90")
        assert view.maximum_grade == Decimal("100")

    def test_validation_no_errors_for_valid(self, session: Session) -> None:
        data = _setup(session)
        # Set review status to ready_for_review (grade records exist and are graded)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.review_status = "ready_for_review"
        session.flush()
        errors = validate_submission_for_review(session, data["submission"].id, data["assessment"].id)
        assert len(errors) == 0

    def test_missing_grade_record_error(self, session: Session) -> None:
        data = _setup(session)
        # Delete one grade record
        session.query(GradeRecord).filter(GradeRecord.submission_id == data["submission"].id).delete()
        session.flush()
        errors = validate_submission_for_review(session, data["submission"].id, data["assessment"].id)
        assert len(errors) > 0

    def test_navigation_by_code(self, session: Session) -> None:
        data = _setup(session)
        # Create second submission with higher code
        id2 = StudentIdentity(encrypted_first_name="enc:N2")
        session.add(id2)
        session.flush()
        anon2 = AnonymousStudent(student_identity_id=id2.id, anonymous_code="STU-REV002")
        session.add(anon2)
        session.flush()
        sub2 = Submission(
            assessment_id=data["assessment"].id, anonymous_student_id=anon2.id,
            import_batch_id=data["batch"].id,
        )
        session.add(sub2)
        session.flush()

        view1 = get_review_submission(session, data["submission"].id, data["assessment"].id)
        assert view1 is not None
        assert view1.previous_submission_id is None
        assert view1.next_submission_id == sub2.id

        view2 = get_review_submission(session, sub2.id, data["assessment"].id)
        assert view2 is not None
        assert view2.previous_submission_id == data["submission"].id
        assert view2.next_submission_id is None

    def test_safe_repr(self, session: Session) -> None:
        data = _setup(session)
        view = get_review_submission(session, data["submission"].id, data["assessment"].id)
        assert view is not None
        rep = repr(view)
        assert "STU-REV001" in rep
        assert "enc:R" not in rep


class TestApproveSubmission:
    def test_approve_valid(self, session: Session) -> None:
        data = _setup(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.review_status = "ready_for_review"
        session.flush()
        view = approve_submission_review(session, data["submission"].id, data["assessment"].id)
        assert view.review_status == "approved"

    def test_approve_with_note(self, session: Session) -> None:
        data = _setup(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.review_status = "ready_for_review"
        session.flush()
        view = approve_submission_review(
            session, data["submission"].id, data["assessment"].id, reviewer_note="All good",
        )
        assert view.review_status == "approved"

    def test_approve_blocked_with_errors(self, session: Session) -> None:
        data = _setup(session)
        # Delete grade record to create error
        session.query(GradeRecord).filter(GradeRecord.submission_id == data["submission"].id).delete()
        session.flush()
        with pytest.raises(ReviewApprovalBlockedError):
            approve_submission_review(session, data["submission"].id, data["assessment"].id)

    def test_approve_nonexistent_raises(self, session: Session) -> None:
        data = _setup(session)
        with pytest.raises(ReviewSubmissionNotFoundError):
            approve_submission_review(session, "nonexistent", data["assessment"].id)


class TestNeedsCorrection:
    def test_mark_needs_correction(self, session: Session) -> None:
        data = _setup(session)
        view = mark_submission_needs_correction(
            session, data["submission"].id, data["assessment"].id, reviewer_note="Fix Q1",
        )
        assert view.review_status == "needs_correction"
        assert view.review_note == "Fix Q1"

    def test_note_required(self, session: Session) -> None:
        data = _setup(session)
        with pytest.raises(ReviewNoteRequiredError):
            mark_submission_needs_correction(
                session, data["submission"].id, data["assessment"].id, reviewer_note="",
            )

    def test_preserves_grades(self, session: Session) -> None:
        data = _setup(session)
        view = mark_submission_needs_correction(
            session, data["submission"].id, data["assessment"].id, reviewer_note="Review needed",
        )
        assert view.total_grade == Decimal("90")


class TestReturnToGrading:
    def test_return_to_grading(self, session: Session) -> None:
        data = _setup(session)
        # First mark needs correction
        mark_submission_needs_correction(session, data["submission"].id, data["assessment"].id, reviewer_note="Fix")
        # Then return to grading
        view = return_submission_to_grading(session, data["submission"].id, data["assessment"].id)
        assert view.review_status == "not_ready"
        assert view.review_note is None


class TestReviewProgress:
    def test_all_not_ready(self, session: Session) -> None:
        data = _setup(session)
        progress = calculate_review_progress(session, data["assessment"].id)
        assert progress.total_submissions == 1
        assert progress.not_ready == 1

    def test_approved(self, session: Session) -> None:
        data = _setup(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.review_status = "approved"
        session.flush()
        progress = calculate_review_progress(session, data["assessment"].id)
        assert progress.approved == 1
        assert progress.completion_percentage == 100.0

    def test_mixed_statuses(self, session: Session) -> None:
        data = _setup(session)
        # Add more submissions
        for code in ["STU-REV003", "STU-REV004"]:
            ident = StudentIdentity(encrypted_first_name="enc:X")
            session.add(ident)
            session.flush()
            anon = AnonymousStudent(student_identity_id=ident.id, anonymous_code=code)
            session.add(anon)
            session.flush()
            sub = Submission(
                assessment_id=data["assessment"].id, anonymous_student_id=anon.id,
                import_batch_id=data["batch"].id,
            )
            session.add(sub)
            session.flush()

        subs = (
            session.query(Submission)
            .filter(Submission.assessment_id == data["assessment"].id)
            .order_by(Submission.id).all()
        )
        if len(subs) >= 2:
            subs[1].review_status = "ready_for_review"
        if len(subs) >= 3:
            subs[2].review_status = "approved"
        session.flush()

        progress = calculate_review_progress(session, data["assessment"].id)
        assert progress.total_submissions == 3
        assert progress.not_ready == 1
        assert progress.ready_for_review == 1
        assert progress.approved == 1

    def test_zero_submissions(self, session: Session) -> None:
        data = _setup(session)
        a2 = Assessment(material_id=data["assessment"].material_id, title="Empty", maximum_grade=Decimal("100"))
        session.add(a2)
        session.flush()
        progress = calculate_review_progress(session, a2.id)
        assert progress.total_submissions == 0
        assert progress.completion_percentage == 0.0


class TestAssessmentValidation:
    def test_ready_assessment(self, session: Session) -> None:
        data = _setup(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        assert sub is not None
        sub.review_status = "approved"
        session.flush()
        result = validate_assessment_review(session, data["assessment"].id)
        assert result.is_ready is True
        assert len(result.blocking_errors) == 0

    def test_no_questions_error(self, session: Session) -> None:
        data = _setup(session)
        a2 = Assessment(material_id=data["assessment"].material_id, title="No Q", maximum_grade=Decimal("100"))
        session.add(a2)
        session.flush()
        result = validate_assessment_review(session, a2.id)
        assert result.is_ready is False

    def test_needs_correction_blocks_ready(self, session: Session) -> None:
        data = _setup(session)
        sub = session.query(Submission).filter(Submission.id == data["submission"].id).first()
        assert sub is not None
        sub.review_status = "needs_correction"
        session.flush()
        result = validate_assessment_review(session, data["assessment"].id)
        assert result.is_ready is False
