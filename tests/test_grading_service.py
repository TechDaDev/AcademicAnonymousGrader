"""Grading service tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.response import Response
from models.student_identity import StudentIdentity
from models.submission import Submission
from services.exceptions import (
    GradingQuestionNotFoundError,
    IncompleteGradingError,
    InvalidGradeError,
    SubmissionNotFoundError,
)
from services.grading_service import (
    calculate_grading_progress,
    get_grading_submission,
    list_anonymous_submissions,
    save_question_grade,
    save_submission_grades,
    validate_question_grade,
)

# ── Fixtures ──────────────────────────────────────────────────────


def _setup_grading_data(session: Session) -> dict:  # type: ignore[type-arg]
    """Create test data for grading tests."""
    material = Material(name="Grading Test Material")
    session.add(material)
    session.flush()

    assessment = Assessment(
        material_id=material.id,
        title="Grading Test Assessment",
        maximum_grade=Decimal("100"),
    )
    session.add(assessment)
    session.flush()

    q1 = Question(
        assessment_id=assessment.id, question_number=1,
        maximum_grade=Decimal("40"), title="Question 1",
    )
    q2 = Question(
        assessment_id=assessment.id, question_number=2,
        maximum_grade=Decimal("60"), title="Question 2",
    )
    session.add_all([q1, q2])
    session.flush()

    batch = ImportBatch(assessment_id=assessment.id, source_filename="test.html")
    session.add(batch)
    session.flush()

    identity = StudentIdentity(encrypted_first_name="enc:A")
    session.add(identity)
    session.flush()

    anon = AnonymousStudent(
        student_identity_id=identity.id,
        anonymous_code="STU-GRADE01",
    )
    session.add(anon)
    session.flush()

    submission = Submission(
        assessment_id=assessment.id,
        anonymous_student_id=anon.id,
        import_batch_id=batch.id,
    )
    session.add(submission)
    session.flush()

    resp1 = Response(
        submission_id=submission.id,
        question_id=q1.id,
        response_text="Answer to Q1",
    )
    resp2 = Response(
        submission_id=submission.id,
        question_id=q2.id,
        response_text="Answer to Q2",
    )
    session.add_all([resp1, resp2])
    session.flush()

    return {
        "material": material,
        "assessment": assessment,
        "q1": q1,
        "q2": q2,
        "identity": identity,
        "anon": anon,
        "submission": submission,
        "resp1": resp1,
        "resp2": resp2,
        "batch": batch,
    }


# ── Tests ─────────────────────────────────────────────────────────


class TestValidateQuestionGrade:
    def test_valid_grade(self) -> None:
        result = validate_question_grade("35.50", Decimal("40"))
        assert result == Decimal("35.50")

    def test_empty_returns_none(self) -> None:
        result = validate_question_grade("", Decimal("40"))
        assert result is None

    def test_none_returns_none(self) -> None:
        result = validate_question_grade(None, Decimal("40"))
        assert result is None

    def test_reject_negative(self) -> None:
        with pytest.raises(InvalidGradeError, match="below zero"):
            validate_question_grade("-5", Decimal("40"))

    def test_reject_above_max(self) -> None:
        with pytest.raises(InvalidGradeError, match="exceeds maximum"):
            validate_question_grade("50", Decimal("40"))

    def test_reject_invalid_decimal(self) -> None:
        with pytest.raises(InvalidGradeError, match="not a valid number"):
            validate_question_grade("abc", Decimal("40"))


class TestSaveQuestionGrade:
    def test_create_grade_record(self, session: Session) -> None:
        data = _setup_grading_data(session)
        result = save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("35.00"),
            feedback="Good work",
            grading_status="draft",
        )
        assert result.grade == Decimal("35.00")
        assert result.feedback == "Good work"
        assert result.grading_status == "draft"

    def test_update_existing_grade(self, session: Session) -> None:
        data = _setup_grading_data(session)
        save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("35.00"),
        )
        result = save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("38.00"),
        )
        assert result.grade == Decimal("38.00")

    def test_save_feedback(self, session: Session) -> None:
        data = _setup_grading_data(session)
        result = save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("35.00"),
            feedback="Great answer!",
        )
        assert result.feedback == "Great answer!"

    def test_mark_as_graded(self, session: Session) -> None:
        data = _setup_grading_data(session)
        result = save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("35.00"),
            grading_status="graded",
        )
        assert result.grading_status == "graded"
        assert result.graded_at is not None

    def test_preserve_decimal(self, session: Session) -> None:
        data = _setup_grading_data(session)
        result = save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("7.25"),
        )
        assert result.grade == Decimal("7.25")

    def test_grade_blank_response(self, session: Session) -> None:
        data = _setup_grading_data(session)
        # The existing response for q1 already has is_blank=False
        # Grade it - blank responses can still be graded
        result = save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("0.00"),
            feedback="No attempt",
        )
        assert result.grade == Decimal("0.00")

        result = save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("0.00"),
            feedback="No attempt",
        )
        assert result.grade == Decimal("0.00")

    def test_wrong_submission_raises(self, session: Session) -> None:
        data = _setup_grading_data(session)
        with pytest.raises(SubmissionNotFoundError):
            save_question_grade(
                session=session,
                submission_id="nonexistent",
                question_id=data["q1"].id,
                assessment_id=data["assessment"].id,
                grade=Decimal("10"),
            )

    def test_wrong_question_raises(self, session: Session) -> None:
        data = _setup_grading_data(session)
        with pytest.raises(GradingQuestionNotFoundError):
            save_question_grade(
                session=session,
                submission_id=data["submission"].id,
                question_id="nonexistent",
                assessment_id=data["assessment"].id,
                grade=Decimal("10"),
            )


class TestSaveSubmissionGrades:
    def test_save_draft(self, session: Session) -> None:
        data = _setup_grading_data(session)
        grades = {data["q1"].id: "35.00"}
        feedbacks: dict[str, str | None] = {data["q1"].id: "Good"}
        result = save_submission_grades(
            session=session,
            submission_id=data["submission"].id,
            assessment_id=data["assessment"].id,
            grades=grades,
            feedbacks=feedbacks,
            marking_graded=False,
        )
        assert result.current_total == Decimal("35.00")
        assert not result.is_complete

    def test_mark_fully_graded(self, session: Session) -> None:
        data = _setup_grading_data(session)
        grades = {
            data["q1"].id: "35.00",
            data["q2"].id: "55.00",
        }
        feedbacks: dict[str, str | None] = {}
        result = save_submission_grades(
            session=session,
            submission_id=data["submission"].id,
            assessment_id=data["assessment"].id,
            grades=grades,
            feedbacks=feedbacks,
            marking_graded=True,
        )
        assert result.current_total == Decimal("90.00")
        assert result.is_complete

    def test_mark_graded_rejects_missing(self, session: Session) -> None:
        data = _setup_grading_data(session)
        grades = {data["q1"].id: "35.00"}
        feedbacks: dict[str, str | None] = {}
        with pytest.raises(IncompleteGradingError):
            save_submission_grades(
                session=session,
                submission_id=data["submission"].id,
                assessment_id=data["assessment"].id,
                grades=grades,
                feedbacks=feedbacks,
                marking_graded=True,
            )

    def test_calculate_submission_total(self, session: Session) -> None:
        data = _setup_grading_data(session)
        grades = {
            data["q1"].id: "25.00",
            data["q2"].id: "45.00",
        }
        result = save_submission_grades(
            session=session,
            submission_id=data["submission"].id,
            assessment_id=data["assessment"].id,
            grades=grades,
            feedbacks={},
            marking_graded=True,
        )
        assert result.current_total == Decimal("70.00")
        assert result.is_complete

    def test_total_never_exceeds_max(self, session: Session) -> None:
        data = _setup_grading_data(session)
        grades = {
            data["q1"].id: "40.00",
            data["q2"].id: "65.00",  # 65 > 60 question max (caught before assessment check)
        }
        with pytest.raises(InvalidGradeError, match="exceeds maximum"):
            save_submission_grades(
                session=session,
                submission_id=data["submission"].id,
                assessment_id=data["assessment"].id,
                grades=grades,
                feedbacks={},
                marking_graded=True,
            )


class TestListAnonymousSubmissions:
    def test_list_submissions(self, session: Session) -> None:
        data = _setup_grading_data(session)
        result = list_anonymous_submissions(session, data["assessment"].id)
        assert len(result) == 1
        assert result[0].anonymous_code == "STU-GRADE01"
        assert result[0].submission_status == "ungraded"
        assert result[0].total_question_count == 2

    def test_list_shows_graded_status(self, session: Session) -> None:
        data = _setup_grading_data(session)
        save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("35.00"),
            grading_status="graded",
        )
        save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q2"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("55.00"),
            grading_status="graded",
        )
        result = list_anonymous_submissions(session, data["assessment"].id)
        assert len(result) == 1
        assert result[0].submission_status == "graded"

    def test_multiple_submissions_independent(self, session: Session) -> None:
        data = _setup_grading_data(session)
        new_identity = StudentIdentity(encrypted_first_name="enc:B")
        session.add(new_identity)
        session.flush()
        anon2 = AnonymousStudent(
            student_identity_id=new_identity.id,
            anonymous_code="STU-GRADE02",
        )
        session.add(anon2)
        session.flush()

        sub2 = Submission(
            assessment_id=data["assessment"].id,
            anonymous_student_id=anon2.id,
            import_batch_id=data["batch"].id,
        )
        session.add(sub2)
        session.flush()

        result = list_anonymous_submissions(session, data["assessment"].id)
        assert len(result) == 2
        assert result[0].anonymous_code != result[1].anonymous_code

    def test_no_names_returned(self, session: Session) -> None:
        """Verify grading queries never return identity data."""
        data = _setup_grading_data(session)
        result = list_anonymous_submissions(session, data["assessment"].id)
        for r in result:
            # Should only have anonymous code
            assert r.anonymous_code.startswith("STU-")
            # Should not expose identity fields
            assert not hasattr(r, "first_name")
            assert not hasattr(r, "email")


class TestGetGradingSubmission:
    def test_get_submission(self, session: Session) -> None:
        data = _setup_grading_data(session)
        view = get_grading_submission(
            session, data["submission"].id, data["assessment"].id
        )
        assert view is not None
        assert view.anonymous_code == "STU-GRADE01"
        assert view.assessment_title == "Grading Test Assessment"
        assert len(view.questions) == 2
        assert view.current_total == Decimal("0")
        assert view.maximum_total == Decimal("100")
        assert not view.is_complete

    def test_question_items(self, session: Session) -> None:
        data = _setup_grading_data(session)
        view = get_grading_submission(
            session, data["submission"].id, data["assessment"].id
        )
        assert view is not None
        q1_item = view.questions[0]
        assert q1_item.question_number == 1
        assert q1_item.maximum_grade == Decimal("40")
        assert q1_item.response_text == "Answer to Q1"
        assert q1_item.grading_status == "ungraded"
        assert q1_item.grade is None

    def test_safe_repr(self, session: Session) -> None:
        data = _setup_grading_data(session)
        view = get_grading_submission(
            session, data["submission"].id, data["assessment"].id
        )
        assert view is not None
        # __repr__ should not contain response text
        for q in view.questions:
            rep = repr(q)
            assert "Answer" not in rep

    def test_navigation_ids(self, session: Session) -> None:
        """Navigation uses anonymous_code ascending order."""
        data = _setup_grading_data(session)
        first_sub = data["submission"]
        # first_sub has anonymous_code STU-GRADE01

        # Create second submission with higher code
        id2 = StudentIdentity(encrypted_first_name="enc:Nav2")
        session.add(id2)
        session.flush()
        anon2 = AnonymousStudent(
            student_identity_id=id2.id, anonymous_code="STU-MID5555",
        )
        session.add(anon2)
        session.flush()
        sub2 = Submission(
            assessment_id=data["assessment"].id,
            anonymous_student_id=anon2.id,
            import_batch_id=data["batch"].id,
        )
        session.add(sub2)
        session.flush()

        # Create third submission with highest code
        id3 = StudentIdentity(encrypted_first_name="enc:Nav3")
        session.add(id3)
        session.flush()
        anon3 = AnonymousStudent(
            student_identity_id=id3.id, anonymous_code="STU-ZZZ9999",
        )
        session.add(anon3)
        session.flush()
        sub3 = Submission(
            assessment_id=data["assessment"].id,
            anonymous_student_id=anon3.id,
            import_batch_id=data["batch"].id,
        )
        session.add(sub3)
        session.flush()

        # First submission — previous is None, next is sub2
        view1 = get_grading_submission(
            session, first_sub.id, data["assessment"].id
        )
        assert view1 is not None
        assert view1.previous_submission_id is None
        assert view1.next_submission_id == sub2.id

        # Middle submission — previous is first_sub, next is sub3
        view2 = get_grading_submission(
            session, sub2.id, data["assessment"].id
        )
        assert view2 is not None
        assert view2.previous_submission_id == first_sub.id
        assert view2.next_submission_id == sub3.id

        # Last submission — previous is sub2, next is None
        view3 = get_grading_submission(
            session, sub3.id, data["assessment"].id
        )
        assert view3 is not None
        assert view3.previous_submission_id == sub2.id
        assert view3.next_submission_id is None

    def test_no_identity_exposure(self, session: Session) -> None:
        """Verify grading view never exposes StudentIdentity fields."""
        data = _setup_grading_data(session)
        view = get_grading_submission(
            session, data["submission"].id, data["assessment"].id
        )
        assert view is not None
        assert not hasattr(view, "first_name")
        assert not hasattr(view, "email")
        assert not hasattr(view, "student_identity_id")
        assert view.anonymous_code == "STU-GRADE01"


class TestGradingProgress:
    def test_all_ungraded(self, session: Session) -> None:
        data = _setup_grading_data(session)
        progress = calculate_grading_progress(session, data["assessment"].id)
        assert progress.total_submissions == 1
        assert progress.ungraded_submissions == 1
        assert progress.in_progress_submissions == 0
        assert progress.completed_submissions == 0

    def test_partially_graded(self, session: Session) -> None:
        data = _setup_grading_data(session)
        save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("35.00"),
            grading_status="graded",
        )
        progress = calculate_grading_progress(session, data["assessment"].id)
        assert progress.total_submissions == 1
        assert progress.ungraded_submissions == 0
        assert progress.in_progress_submissions == 1
        assert progress.completed_submissions == 0

    def test_fully_graded(self, session: Session) -> None:
        data = _setup_grading_data(session)
        save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("40"),
            grading_status="graded",
        )
        save_question_grade(
            session=session,
            submission_id=data["submission"].id,
            question_id=data["q2"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("60"),
            grading_status="graded",
        )
        progress = calculate_grading_progress(session, data["assessment"].id)
        assert progress.total_submissions == 1
        assert progress.ungraded_submissions == 0
        assert progress.in_progress_submissions == 0
        assert progress.completed_submissions == 1

    def test_mixed_submissions(self, session: Session) -> None:
        data = _setup_grading_data(session)
        # Create 2 more identities and submissions
        for code in ["STU-MIX02", "STU-MIX03"]:
            new_identity = StudentIdentity(encrypted_first_name="enc:MIX")
            session.add(new_identity)
            session.flush()
            anon = AnonymousStudent(
                student_identity_id=new_identity.id,
                anonymous_code=code,
            )
            session.add(anon)
            session.flush()
            sub = Submission(
                assessment_id=data["assessment"].id,
                anonymous_student_id=anon.id,
                import_batch_id=data["batch"].id,
            )
            session.add(sub)
            session.flush()

        # Grade submission 1 fully
        subs = (
            session.query(Submission)
            .filter(Submission.assessment_id == data["assessment"].id)
            .order_by(Submission.id)
            .all()
        )
        save_question_grade(
            session=session,
            submission_id=subs[0].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("40"),
            grading_status="graded",
        )
        save_question_grade(
            session=session,
            submission_id=subs[0].id,
            question_id=data["q2"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("60"),
            grading_status="graded",
        )

        # Grade submission 2 partially
        save_question_grade(
            session=session,
            submission_id=subs[1].id,
            question_id=data["q1"].id,
            assessment_id=data["assessment"].id,
            grade=Decimal("20"),
            grading_status="draft",
        )

        progress = calculate_grading_progress(session, data["assessment"].id)
        assert progress.total_submissions == 3
        assert progress.ungraded_submissions == 1
        assert progress.in_progress_submissions == 1
        assert progress.completed_submissions == 1

    def test_completion_percentage(self, session: Session) -> None:
        data = _setup_grading_data(session)
        progress = calculate_grading_progress(session, data["assessment"].id)
        assert progress.completion_percentage == 0.0

    def test_zero_submissions(self, session: Session) -> None:
        data = _setup_grading_data(session)
        # Create assessment with no submissions
        a2 = Assessment(
            material_id=data["material"].id,
            title="Empty Assessment",
            maximum_grade=Decimal("100"),
        )
        session.add(a2)
        session.flush()
        progress = calculate_grading_progress(session, a2.id)
        assert progress.total_submissions == 0
        assert progress.completion_percentage == 0.0
