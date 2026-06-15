"""Phase 6 UI helper tests."""

from __future__ import annotations

from decimal import Decimal

from services.review_service import (
    AssessmentValidationResult,
    ReviewProgress,
    ReviewSubmissionView,
    ReviewValidationMessage,
)


class TestReviewProgressProperties:
    def test_completion_zero(self) -> None:
        p = ReviewProgress(total_submissions=0, not_ready=0, ready_for_review=0, needs_correction=0, approved=0)
        assert p.completion_percentage == 0.0

    def test_completion_half(self) -> None:
        p = ReviewProgress(total_submissions=4, not_ready=1, ready_for_review=1, needs_correction=1, approved=1)
        assert p.completion_percentage == 25.0

    def test_completion_full(self) -> None:
        p = ReviewProgress(total_submissions=3, not_ready=0, ready_for_review=0, needs_correction=0, approved=3)
        assert p.completion_percentage == 100.0


class TestSafeRepr:
    def test_validation_message_repr(self) -> None:
        m = ReviewValidationMessage(type="error", message="Secret info", code="RV001")
        rep = repr(m)
        assert "RV001" in rep
        assert "Secret" not in rep

    def test_submission_view_repr(self) -> None:
        v = ReviewSubmissionView(
            submission_id="s1", anonymous_code="STU-TEST01", assessment_title="T",
            questions=(), total_grade=Decimal("0"), maximum_grade=Decimal("100"),
            review_status="ready_for_review", review_note=None,
        )
        rep = repr(v)
        assert "STU-TEST01" in rep
        assert "encrypted" not in rep

    def test_assessment_validation_repr(self) -> None:
        r = AssessmentValidationResult(is_ready=True)
        rep = repr(r)
        assert "ready=True" in rep
