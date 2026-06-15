"""Phase 7 UI helper tests."""

from __future__ import annotations

from decimal import Decimal

from services.finalization_service import (
    FinalizationReadiness,
    FinalizationResult,
    FinalizedAssessmentSummary,
    FinalizedSubmissionSummary,
    ValidationMessage,
)


class TestFinalizationDataClasses:
    def test_validation_message(self) -> None:
        m = ValidationMessage(type="error", message="Test error", code="FA001")
        assert m.type == "error"
        assert m.code == "FA001"

    def test_readiness_default_not_ready(self) -> None:
        r = FinalizationReadiness(assessment_id="a1", total_submissions=0, approved_submissions=0)
        assert not r.is_ready

    def test_readiness_ready(self) -> None:
        r = FinalizationReadiness(
            assessment_id="a1", total_submissions=1, approved_submissions=1,
            is_ready=True,
        )
        assert r.is_ready

    def test_finalization_result(self) -> None:
        from datetime import UTC, datetime
        r = FinalizationResult(
            assessment_id="a1", finalized_at=datetime.now(UTC),
            submission_count=5, final_grade_total=Decimal("450"),
            status="finalized", warning_count=0,
        )
        assert r.status == "finalized"
        assert r.submission_count == 5

    def test_finalized_submission_summary(self) -> None:
        s = FinalizedSubmissionSummary(
            submission_id="s1", anonymous_code="STU-T01",
            final_grade=Decimal("85"), maximum_grade=Decimal("100"),
            review_status="approved",
        )
        assert s.anonymous_code == "STU-T01"

    def test_finalized_assessment_summary(self) -> None:
        from datetime import UTC, datetime
        s = FinalizedAssessmentSummary(
            assessment_id="a1", title="Test", status="finalized",
            finalized_at=datetime.now(UTC),
            total_submissions=3, approved_submissions=3,
            average_grade=Decimal("80"), minimum_grade=Decimal("70"),
            maximum_grade=Decimal("90"), final_grade_total=Decimal("240"),
            maximum_total=Decimal("300"),
        )
        assert s.approved_submissions == 3
        assert s.average_grade == Decimal("80")
