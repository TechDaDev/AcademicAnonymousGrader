"""Phase 5 UI helper tests."""

from __future__ import annotations

from decimal import Decimal

from services.grading_service import (
    GradingProgress,
    QuestionGradingItem,
    SubmissionGradingView,
)


class TestGradingProgressProperties:
    def test_completion_percentage_zero(self) -> None:
        p = GradingProgress(
            total_submissions=0,
            ungraded_submissions=0,
            in_progress_submissions=0,
            completed_submissions=0,
        )
        assert p.completion_percentage == 0.0

    def test_completion_percentage_half(self) -> None:
        p = GradingProgress(
            total_submissions=4,
            ungraded_submissions=1,
            in_progress_submissions=1,
            completed_submissions=2,
        )
        assert p.completion_percentage == 50.0

    def test_completion_percentage_full(self) -> None:
        p = GradingProgress(
            total_submissions=3,
            ungraded_submissions=0,
            in_progress_submissions=0,
            completed_submissions=3,
        )
        assert p.completion_percentage == 100.0


class TestQuestionGradingItemRepr:
    def test_repr_safe(self) -> None:
        q = QuestionGradingItem(
            question_id="id1",
            question_number=1,
            question_title="Test Q",
            maximum_grade=Decimal("10"),
            response_text="Secret response content",
            is_blank=False,
            grade=Decimal("7.5"),
            feedback="Good",
            grading_status="graded",
        )
        rep = repr(q)
        assert "q=1" in rep
        assert "Secret" not in rep


class TestSubmissionGradingViewRepr:
    def test_repr_safe(self) -> None:
        v = SubmissionGradingView(
            submission_id="sub123",
            anonymous_code="STU-TEST01",
            assessment_title="Test",
            questions=[],
            current_total=Decimal("0"),
            maximum_total=Decimal("100"),
            is_complete=False,
        )
        rep = repr(v)
        assert "STU-TEST01" in rep
        assert "encrypted" not in rep
