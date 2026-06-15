"""Focused Phase 6 review progress and assessment validation tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any as _Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.init_db import initialize_database
from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.response import Response
from models.student_identity import StudentIdentity
from models.submission import Submission
from services.review_service import (
    calculate_review_progress,
    list_review_submissions,
    validate_assessment_review,
)


def _base(session: Session, *, maximum_grade: Decimal = Decimal("10")) -> dict[str, _Any]:
    material = Material(name="Review Progress Material")
    session.add(material)
    session.flush()

    assessment = Assessment(
        material_id=material.id,
        title="Review Progress Assessment",
        maximum_grade=maximum_grade,
    )
    session.add(assessment)
    session.flush()

    batch = ImportBatch(assessment_id=assessment.id, source_filename="review.html")
    session.add(batch)
    session.flush()

    return {"material": material, "assessment": assessment, "batch": batch}


def _add_question(
    session: Session,
    assessment: Assessment,
    number: int,
    maximum_grade: Decimal,
) -> Question:
    question = Question(
        assessment_id=assessment.id,
        question_number=number,
        maximum_grade=maximum_grade,
    )
    session.add(question)
    session.flush()
    return question


def _add_submission(
    session: Session,
    assessment: Assessment,
    batch: ImportBatch,
    code: str,
    *,
    review_status: str = "not_ready",
    grade: Decimal | None = Decimal("8"),
    grading_status: str = "graded",
    question: Question | None = None,
) -> Submission:
    identity = StudentIdentity(encrypted_first_name=f"enc:{code}")
    session.add(identity)
    session.flush()

    anonymous = AnonymousStudent(
        student_identity_id=identity.id,
        anonymous_code=code,
    )
    session.add(anonymous)
    session.flush()

    submission = Submission(
        assessment_id=assessment.id,
        anonymous_student_id=anonymous.id,
        import_batch_id=batch.id,
        review_status=review_status,
    )
    session.add(submission)
    session.flush()

    if question is not None:
        session.add(
            GradeRecord(
                submission_id=submission.id,
                question_id=question.id,
                grade=grade,
                grading_status=grading_status,
            )
        )
        session.flush()

    return submission


class TestReviewProgressMatrix:
    def test_zero_submissions(self, session: Session) -> None:
        data = _base(session)
        progress = calculate_review_progress(session, data["assessment"].id)
        assert progress.total_submissions == 0
        assert progress.not_ready == 0
        assert progress.ready_for_review == 0
        assert progress.needs_correction == 0
        assert progress.approved == 0
        assert progress.completion_percentage == 0.0

    def test_all_not_ready(self, session: Session) -> None:
        data = _base(session)
        question = _add_question(session, data["assessment"], 1, Decimal("10"))
        _add_submission(session, data["assessment"], data["batch"], "STU-RP0001", question=question)
        _add_submission(session, data["assessment"], data["batch"], "STU-RP0002", question=question)

        progress = calculate_review_progress(session, data["assessment"].id)

        assert progress.total_submissions == 2
        assert progress.not_ready == 2
        assert progress.ready_for_review == 0
        assert progress.needs_correction == 0
        assert progress.approved == 0

    def test_ready_for_review(self, session: Session) -> None:
        data = _base(session)
        question = _add_question(session, data["assessment"], 1, Decimal("10"))
        _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RP0001",
            review_status="ready_for_review",
            question=question,
        )

        progress = calculate_review_progress(session, data["assessment"].id)

        assert progress.ready_for_review == 1

    def test_needs_correction(self, session: Session) -> None:
        data = _base(session)
        question = _add_question(session, data["assessment"], 1, Decimal("10"))
        _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RP0001",
            review_status="needs_correction",
            question=question,
        )

        progress = calculate_review_progress(session, data["assessment"].id)

        assert progress.needs_correction == 1

    def test_approved(self, session: Session) -> None:
        data = _base(session)
        question = _add_question(session, data["assessment"], 1, Decimal("10"))
        _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RP0001",
            review_status="approved",
            question=question,
        )

        progress = calculate_review_progress(session, data["assessment"].id)

        assert progress.approved == 1
        assert progress.completion_percentage == 100.0

    def test_mixed_statuses_and_completion_percentage(self, session: Session) -> None:
        data = _base(session)
        question = _add_question(session, data["assessment"], 1, Decimal("10"))
        for idx, status in enumerate(
            ["not_ready", "ready_for_review", "needs_correction", "approved"],
            start=1,
        ):
            _add_submission(
                session,
                data["assessment"],
                data["batch"],
                f"STU-RP000{idx}",
                review_status=status,
                question=question,
            )

        progress = calculate_review_progress(session, data["assessment"].id)

        assert progress.total_submissions == 4
        assert progress.not_ready == 1
        assert progress.ready_for_review == 1
        assert progress.needs_correction == 1
        assert progress.approved == 1
        assert progress.completion_percentage == 25.0

    def test_warning_count_for_filtering(self, session: Session) -> None:
        data = _base(session)
        question = _add_question(session, data["assessment"], 1, Decimal("10"))
        submission = _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RP0001",
            review_status="ready_for_review",
            grade=Decimal("1"),
            question=question,
        )
        session.add(
            Response(
                submission_id=submission.id,
                question_id=question.id,
                response_text="",
                is_blank=True,
            )
        )
        session.flush()

        summaries = list_review_submissions(session, data["assessment"].id)

        assert summaries[0].validation_warning_count == 2


class TestAssessmentReviewValidationMatrix:
    def test_assessment_with_no_questions(self, session: Session) -> None:
        data = _base(session)
        result = validate_assessment_review(session, data["assessment"].id)
        assert any(err.code == "RA002" for err in result.blocking_errors)
        assert result.is_ready is False

    def test_question_maximum_total_mismatch(self, session: Session) -> None:
        data = _base(session, maximum_grade=Decimal("10"))
        question = _add_question(session, data["assessment"], 1, Decimal("8"))
        _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RV0001",
            review_status="approved",
            question=question,
        )

        result = validate_assessment_review(session, data["assessment"].id)

        assert any(err.code == "RA003" for err in result.blocking_errors)
        assert result.is_ready is False

    def test_assessment_with_no_submissions(self, session: Session) -> None:
        data = _base(session)
        _add_question(session, data["assessment"], 1, Decimal("10"))

        result = validate_assessment_review(session, data["assessment"].id)

        assert any(err.code == "RA004" for err in result.blocking_errors)
        assert result.is_ready is False

    def test_submission_without_anonymous_student(self, tmp_db_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_db_path}", connect_args={"check_same_thread": False})
        initialize_database(engine)
        factory = sessionmaker(bind=engine)
        session = factory()
        try:
            data = _base(session)
            _add_question(session, data["assessment"], 1, Decimal("10"))
            session.add(
                Submission(
                    assessment_id=data["assessment"].id,
                    anonymous_student_id="missing-anonymous-student",
                    import_batch_id=data["batch"].id,
                    review_status="approved",
                )
            )
            session.flush()

            result = validate_assessment_review(session, data["assessment"].id)

            assert any(err.code == "RA005" for err in result.blocking_errors)
            assert result.is_ready is False
        finally:
            session.close()
            engine.dispose()

    def test_missing_grade_record(self, session: Session) -> None:
        data = _base(session)
        _add_question(session, data["assessment"], 1, Decimal("10"))
        _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RV0001",
            review_status="approved",
        )

        result = validate_assessment_review(session, data["assessment"].id)

        assert any(err.code == "RA008" for err in result.blocking_errors)
        assert result.is_ready is False

    def test_needs_correction_submission_blocks_readiness(self, session: Session) -> None:
        data = _base(session)
        question = _add_question(session, data["assessment"], 1, Decimal("10"))
        _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RV0001",
            review_status="needs_correction",
            question=question,
        )

        result = validate_assessment_review(session, data["assessment"].id)

        assert any(err.code == "RA007" for err in result.blocking_errors)
        assert result.is_ready is False

    def test_all_submissions_approved_returns_ready(self, session: Session) -> None:
        data = _base(session)
        question = _add_question(session, data["assessment"], 1, Decimal("10"))
        _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RV0001",
            review_status="approved",
            question=question,
        )
        _add_submission(
            session,
            data["assessment"],
            data["batch"],
            "STU-RV0002",
            review_status="approved",
            question=question,
        )

        result = validate_assessment_review(session, data["assessment"].id)

        assert result.is_ready is True
        assert result.total_submissions == 2
        assert result.graded_submissions == 2
        assert result.approved_submissions == 2
        assert result.blocking_errors == ()
