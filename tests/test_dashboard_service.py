# Academic Anonymous Grader — Dashboard Service Tests
"""Tests for services/dashboard_service.py."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.material import Material
from services.dashboard_service import get_dashboard_stats


class TestDashboardService:
    """Verify dashboard statistics."""

    def test_empty_database_returns_zero_counts(self, session: Session) -> None:
        stats = get_dashboard_stats(session)
        assert stats.material_count == 0
        assert stats.assessment_count == 0
        assert stats.student_count == 0
        assert stats.submission_count == 0

    def test_inserted_records_return_correct_counts(self, session: Session) -> None:
        # Add one material
        material = Material(name="Course A")
        session.add(material)
        session.flush()

        stats = get_dashboard_stats(session)
        assert stats.material_count == 1
        # No assessments or students yet
        assert stats.assessment_count == 0
        assert stats.student_count == 0
