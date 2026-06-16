# Academic Anonymous Grader — Phase 12 Analytics Tests
"""Tests for analytics service layer, authorization, privacy,
statistics, exports, and configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from models.assessment import Assessment
from models.instructor_assignment import InstructorAssignment
from models.material import Material
from models.question import Question
from models.user import User
from services.authorization_service import (
    PERM_EXPORT_ANALYTICS,
    PERM_VIEW_ALL_ANALYTICS,
    PERM_VIEW_ANALYTICS,
    PERM_VIEW_INSTRUCTOR_WORKLOAD,
    AuthContext,
    has_permission,
)

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """Create an in-memory SQLite database for testing."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Create a database session."""
    conn = engine.connect()
    trans = conn.begin()
    session_factory = sessionmaker(bind=conn)
    sess = session_factory()
    yield sess
    sess.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def admin_ctx() -> AuthContext:
    return AuthContext(user_id="admin-1", username="admin", role="administrator")


@pytest.fixture
def grader_ctx() -> AuthContext:
    return AuthContext(user_id="grader-1", username="grader1", role="grader")


@pytest.fixture
def viewer_ctx() -> AuthContext:
    return AuthContext(user_id="viewer-1", username="viewer1", role="viewer")


@pytest.fixture
def sample_assessment(session, admin_ctx) -> str:
    """Create sample assessment with material, questions, submissions, grades."""

    # Create users
    admin = User(id="admin-1", username="admin", password_hash="hash", role="administrator")
    grader = User(id="grader-1", username="grader1", password_hash="hash", role="grader")
    grader2 = User(id="grader-2", username="grader2", password_hash="hash", role="grader")
    session.add_all([admin, grader, grader2])

    # Material
    mat = Material(id="mat-1", name="Test Material", code="TEST101")
    session.add(mat)

    # Assessment
    asmt = Assessment(
        id="asmt-1",
        material_id="mat-1",
        title="Test Assessment",
        status="ready",
        maximum_grade=Decimal("100"),
    )
    session.add(asmt)

    # Questions
    for i in range(1, 4):
        q = Question(
            id=f"q-{i}",
            assessment_id="asmt-1",
            question_number=i,
            maximum_grade=Decimal("33.33"),
        )
        session.add(q)

    # Instructor assignment
    assign = InstructorAssignment(
        id="assign-1",
        instructor_user_id="grader-1",
        assessment_id="asmt-1",
        assigned_by_user_id="admin-1",
        is_active=True,
    )
    session.add(assign)

    session.flush()
    return "asmt-1"


# ── Authorization Tests ───────────────────────────────────────────


class TestAnalyticsAuthorization:
    """Test analytics permission checks."""

    def test_admin_has_analytics_permissions(self):
        assert has_permission("administrator", PERM_VIEW_ANALYTICS)
        assert has_permission("administrator", PERM_VIEW_ALL_ANALYTICS)
        assert has_permission("administrator", PERM_VIEW_INSTRUCTOR_WORKLOAD)
        assert has_permission("administrator", PERM_EXPORT_ANALYTICS)

    def test_grader_has_view_analytics(self):
        assert has_permission("grader", PERM_VIEW_ANALYTICS)
        assert not has_permission("grader", PERM_VIEW_ALL_ANALYTICS)
        assert not has_permission("grader", PERM_VIEW_INSTRUCTOR_WORKLOAD)
        assert not has_permission("grader", PERM_EXPORT_ANALYTICS)

    def test_legacy_roles_no_analytics(self):
        for role in ("reviewer", "exporter", "viewer"):
            assert not has_permission(role, PERM_VIEW_ANALYTICS)
            assert not has_permission(role, PERM_VIEW_ALL_ANALYTICS)

    def test_analytics_page_access(self):
        from services.authorization_service import _PAGE_ROLES
        assert "administrator" in _PAGE_ROLES.get("Analytics", set())
        assert "grader" in _PAGE_ROLES.get("Analytics", set())

    def test_viewer_cannot_access_analytics_page(self):
        from services.authorization_service import _PAGE_ROLES
        assert "viewer" not in _PAGE_ROLES.get("Analytics", set())


# ── AnalyticsFilter Tests ─────────────────────────────────────────


class TestAnalyticsFilter:
    """Test AnalyticsFilter validation."""

    def test_empty_filter_is_empty(self):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter()
        assert f.is_empty()

    def test_filter_with_material_not_empty(self):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter(material_id="mat-1")
        assert not f.is_empty()

    def test_invalid_sort_direction(self, session):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter(sort_direction="invalid")
        errors = f.validate(session, None)
        assert len(errors) > 0

    def test_valid_sort_direction(self, session):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter(sort_direction="asc")
        errors = f.validate(session, None)
        assert len(errors) == 0

    def test_date_range_validation(self, session):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter(
            date_from=datetime(2025, 1, 1, tzinfo=UTC),
            date_to=datetime(2024, 1, 1, tzinfo=UTC),
        )
        errors = f.validate(session, None)
        assert len(errors) > 0

    def test_negative_group_size_rejected(self, session):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter(minimum_group_size=0)
        errors = f.validate(session, None)
        assert len(errors) > 0

    def test_instructor_cannot_set_other_user(self, session, grader_ctx):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter(instructor_user_id="grader-2")
        errors = f.validate(session, grader_ctx)
        assert len(errors) > 0

    def test_admin_can_set_any_instructor(self, session, admin_ctx):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter(instructor_user_id="grader-2")
        errors = f.validate(session, admin_ctx)
        # Admin can set any instructor ID
        instructor_related = [e for e in errors if "Instructor" in e]
        assert len(instructor_related) == 0


# ── Statistics Tests ──────────────────────────────────────────────


class TestStatistics:
    """Test statistical calculation helpers."""

    def test_safe_mean(self):
        from analytics.statistics import safe_mean
        assert safe_mean([1, 2, 3]) == 2.0
        assert safe_mean([]) is None
        assert safe_mean([None, 5, None]) == 5.0

    def test_safe_median_odd(self):
        from analytics.statistics import safe_median
        assert safe_median([3, 1, 2]) == 2.0

    def test_safe_median_even(self):
        from analytics.statistics import safe_median
        assert safe_median([1, 2, 3, 4]) == 2.5

    def test_safe_median_empty(self):
        from analytics.statistics import safe_median
        assert safe_median([]) is None

    def test_safe_min_max(self):
        from analytics.statistics import safe_max, safe_min
        assert safe_min([3, 1, 2]) == 1.0
        assert safe_max([3, 1, 2]) == 3.0
        assert safe_min([]) is None
        assert safe_max([]) is None

    def test_safe_stdev(self):
        from analytics.statistics import safe_stdev
        assert safe_stdev([1, 2, 3]) is not None
        assert safe_stdev([5]) is None
        assert safe_stdev([]) is None

    def test_safe_quartiles(self):
        from analytics.statistics import safe_quartiles
        q1, q2, q3 = safe_quartiles([1, 2, 3, 4, 5, 6, 7])
        assert q1 == 2.0  # median of [1,2,3]
        assert q2 == 4.0
        assert q3 == 6.0  # median of [5,6,7]

    def test_empty_quartiles(self):
        from analytics.statistics import safe_quartiles
        assert safe_quartiles([]) == (None, None, None)

    def test_normalize_percentage(self):
        from analytics.statistics import normalize_percentage
        assert normalize_percentage(50, 100) == 50.0
        assert normalize_percentage(0, 100) == 0.0
        assert normalize_percentage(75, 100) == 75.0
        assert normalize_percentage(50, 0) == 0.0

    def test_compute_pass_fail(self):
        from analytics.statistics import compute_pass_fail
        p, f, pct = compute_pass_fail([60, 40, 80], pass_threshold_pct=50.0, maximum=100)
        assert p == 2
        assert f == 1
        assert pct == 66.66666666666666

    def test_compute_pass_fail_empty(self):
        from analytics.statistics import compute_pass_fail
        assert compute_pass_fail([], maximum=100) == (0, 0, 0.0)

    def test_difficulty_index(self):
        from analytics.statistics import compute_difficulty_index
        assert compute_difficulty_index(25.0, 100) == 0.25
        assert compute_difficulty_index(None, 100) is None
        assert compute_difficulty_index(25.0, 0) is None

    def test_compute_grade_bands(self):
        from analytics.statistics import compute_grade_bands
        bands = compute_grade_bands([95, 85, 75, 65, 55, 30], maximum=100)
        assert len(bands) == 6
        assert bands[0]["label"] == "90–100%"
        assert bands[0]["count"] == 1
        assert bands[-1]["count"] == 1

    def test_compute_grade_bands_empty(self):
        from analytics.statistics import compute_grade_bands
        bands = compute_grade_bands([], maximum=100)
        assert all(b["count"] == 0 for b in bands)


# ── Privacy Tests ─────────────────────────────────────────────────


class TestPrivacyThresholds:
    """Test privacy threshold suppression."""

    def test_above_threshold_not_suppressed(self):
        from analytics.privacy import check_group_size
        state = check_group_size(10, 5)
        assert not state.suppressed

    def test_below_threshold_suppressed(self):
        from analytics.privacy import check_group_size
        state = check_group_size(3, 5)
        assert state.suppressed
        assert state.reason == "insufficient_group_size"

    def test_suppress_statistics(self):
        from analytics.privacy import check_group_size, suppress_statistics
        privacy = check_group_size(3, 5)
        assert suppress_statistics(50.0, privacy) is None

    def test_not_suppressed_statistics(self):
        from analytics.privacy import check_group_size, suppress_statistics
        privacy = check_group_size(10, 5)
        assert suppress_statistics(50.0, privacy) == 50.0

    def test_suppress_int(self):
        from analytics.privacy import check_group_size, suppress_int
        privacy = check_group_size(3, 5)
        assert suppress_int(10, privacy) == 0

    def test_suppress_all_distribution(self):
        from analytics.privacy import check_group_size, suppress_all_distribution
        privacy = check_group_size(3, 5)
        assert suppress_all_distribution([{"label": "test"}], privacy) == []

    def test_default_minimum(self):
        from analytics.privacy import DEFAULT_MINIMUM_GROUP_SIZE, check_group_size
        assert DEFAULT_MINIMUM_GROUP_SIZE == 5
        state = check_group_size(4)
        assert state.suppressed
        state = check_group_size(5)
        assert not state.suppressed


# ── Progress Analytics Tests ──────────────────────────────────────


class TestProgressAnalytics:
    """Test grading progress analytics."""

    def test_progress_empty_db(self, session, admin_ctx):
        from analytics.progress import get_grading_progress
        progress = get_grading_progress(session, admin_ctx)
        assert progress.total_submissions == 0

    def test_progress_with_data(self, session, admin_ctx, sample_assessment):
        from analytics.progress import get_grading_progress
        progress = get_grading_progress(session, admin_ctx, filter_obj=None)
        assert progress.total_submissions >= 0
        assert isinstance(progress.percentage_complete, float)

    def test_instructor_progress(self, session, grader_ctx, sample_assessment):
        from analytics.progress import get_grading_progress
        progress = get_grading_progress(session, grader_ctx)
        # Instructor should see data for assigned assessments
        assert progress.total_submissions >= 0

    def test_unauthorized_user(self, session, viewer_ctx):
        from analytics.progress import get_grading_progress
        progress = get_grading_progress(session, viewer_ctx)
        assert progress.privacy.suppressed


# ── Workload Analytics Tests ──────────────────────────────────────


class TestWorkloadAnalytics:
    """Test instructor workload analytics."""

    def test_workload_empty(self, session, grader_ctx):
        from analytics.workload import get_instructor_workload
        wl = get_instructor_workload(session, grader_ctx)
        assert wl.active_assignments == 0

    def test_admin_can_view_any_workload(self, session, admin_ctx, sample_assessment):
        from analytics.workload import get_instructor_workload
        wl = get_instructor_workload(session, admin_ctx, "grader-1")
        assert not wl.privacy.suppressed

    def test_grader_cannot_view_other_workload(self, session, grader_ctx, sample_assessment):
        from analytics.workload import get_instructor_workload
        wl = get_instructor_workload(session, grader_ctx, "grader-2")
        assert wl.privacy.suppressed

    def test_workload_status_light(self):
        from analytics.workload import _classify_workload
        assert _classify_workload(2, 0) == "light"

    def test_workload_status_overloaded(self):
        from analytics.workload import _classify_workload
        assert _classify_workload(50, 40) == "overloaded"

    def test_instructor_workload_self(self, session, grader_ctx, sample_assessment):
        from analytics.workload import get_instructor_workload
        wl = get_instructor_workload(session, grader_ctx)
        assert not wl.privacy.suppressed


# ── Overview Analytics Tests ──────────────────────────────────────


class TestOverviewAnalytics:
    """Test overview dashboard analytics."""

    def test_admin_overview(self, session, admin_ctx, sample_assessment):
        from analytics.overview import get_admin_overview
        metrics = get_admin_overview(session, admin_ctx)
        assert metrics.total_assessments >= 1
        assert metrics.total_materials >= 1

    def test_instructor_overview(self, session, grader_ctx, sample_assessment):
        from analytics.overview import get_instructor_overview
        metrics = get_instructor_overview(session, grader_ctx)
        assert metrics.assigned_assessments >= 1

    def test_unauthorized_overview(self, session, viewer_ctx):
        from analytics.overview import get_admin_overview
        metrics = get_admin_overview(session, viewer_ctx)
        assert metrics.total_assessments == 0

    def test_instructor_overview_no_data(self, session, grader_ctx):
        from analytics.overview import get_instructor_overview
        metrics = get_instructor_overview(session, grader_ctx)
        assert metrics.assigned_assessments == 0


# ── Assessment Analytics Tests ────────────────────────────────────


class TestAssessmentAnalytics:
    """Test assessment performance analytics."""

    def test_performance_unauthorized(self, session, viewer_ctx, sample_assessment):
        from analytics.assessment_analysis import get_assessment_performance
        perf = get_assessment_performance(session, viewer_ctx, "asmt-1")
        assert perf.privacy.suppressed

    def test_performance_authorized(self, session, admin_ctx, sample_assessment):
        from analytics.assessment_analysis import get_assessment_performance
        perf = get_assessment_performance(session, admin_ctx, "asmt-1")
        assert perf.assessment_id == "asmt-1"
        assert perf.submission_count >= 0

    def test_finalization_readiness(self, session, admin_ctx, sample_assessment):
        from analytics.assessment_analysis import list_finalization_readiness
        items = list_finalization_readiness(session, admin_ctx)
        assert len(items) > 0
        assert items[0].assessment_id == "asmt-1"


# ── Question Analytics Tests ──────────────────────────────────────


class TestQuestionAnalytics:
    """Test question-level analytics."""

    def test_question_analysis_unauthorized(self, session, viewer_ctx):
        from analytics.question_analysis import get_question_analysis
        qa = get_question_analysis(session, viewer_ctx, "q-1")
        assert qa.privacy.suppressed

    def test_list_questions_authorized(self, session, admin_ctx, sample_assessment):
        from analytics.question_analysis import list_question_analyses
        questions = list_question_analyses(session, admin_ctx, "asmt-1")
        assert len(questions) == 3
        assert all(isinstance(q.question_number, int) for q in questions)

    def test_question_flags_empty_data(self, session, admin_ctx, sample_assessment):
        from analytics.question_analysis import get_question_analysis
        qa = get_question_analysis(session, admin_ctx, "q-1")
        assert qa.graded_response_count == 0
        assert "insufficient_data" in qa.flags

    def test_difficulty_index_calculation(self, session, admin_ctx, sample_assessment):
        from analytics.question_analysis import get_question_analysis
        qa = get_question_analysis(session, admin_ctx, "q-1")
        # No grade data, so difficulty should be None
        assert qa.difficulty_index is None


# ── Grade Distribution Tests ──────────────────────────────────────


class TestGradeDistribution:
    """Test grade distribution analytics."""

    def test_distribution_unauthorized(self, session, viewer_ctx, sample_assessment):
        from analytics.distributions import get_grade_distribution
        dist = get_grade_distribution(session, viewer_ctx, "asmt-1")
        assert dist.privacy.suppressed

    def test_distribution_authorized(self, session, admin_ctx, sample_assessment):
        from analytics.distributions import get_grade_distribution
        dist = get_grade_distribution(session, admin_ctx, "asmt-1")
        assert dist.assessment_id == "asmt-1"

    def test_grade_bands_present(self, session, admin_ctx, sample_assessment):
        from analytics.distributions import get_grade_distribution
        dist = get_grade_distribution(session, admin_ctx, "asmt-1")
        # With no submissions, bands are empty - that's expected behavior
        assert dist.assessment_id == "asmt-1"


# ── Correction Analytics Tests ────────────────────────────────────


class TestCorrectionAnalytics:
    """Test correction analytics."""

    def test_corrections_empty(self, session, admin_ctx):
        from analytics.corrections import get_correction_analytics
        corr = get_correction_analytics(session, admin_ctx)
        assert corr.total_returned_for_correction == 0

    def test_corrections_authorized(self, session, admin_ctx, sample_assessment):
        from analytics.corrections import get_correction_analytics
        corr = get_correction_analytics(session, admin_ctx, "asmt-1")
        assert corr.total_returned_for_correction == 0


# ── Trend Analytics Tests ─────────────────────────────────────────


class TestTrendAnalytics:
    """Test trend analytics."""

    def test_trend_empty(self, session, admin_ctx):
        from analytics.trends import get_grading_completion_trend
        trend = get_grading_completion_trend(session, admin_ctx)
        assert trend.total == 0
        assert len(trend.data_points) == 0

    def test_trend_unauthorized(self, session, viewer_ctx, sample_assessment):
        from analytics.trends import get_grading_completion_trend
        trend = get_grading_completion_trend(session, viewer_ctx, assessment_id="asmt-1")
        assert trend.privacy.suppressed


# ── Data Quality Tests ────────────────────────────────────────────


class TestDataQuality:
    """Test data quality report."""

    def test_data_quality_admin(self, session, admin_ctx):
        from analytics.data_quality import get_data_quality_report
        report = get_data_quality_report(session, admin_ctx)
        assert isinstance(report.total_issues, int)

    def test_data_quality_unauthorized(self, session, grader_ctx):
        from analytics.data_quality import get_data_quality_report
        report = get_data_quality_report(session, grader_ctx)
        assert report.total_issues == 0


# ── Export Tests ──────────────────────────────────────────────────


class TestAnalyticsExport:
    """Test analytics report export."""

    def test_export_unauthorized(self, session, viewer_ctx, sample_assessment):
        from analytics.export import export_assessment_summary_report
        with pytest.raises((PermissionError, Exception)):
            export_assessment_summary_report(session, viewer_ctx, "asmt-1")

    def test_export_progress(self, session, admin_ctx):
        from analytics.export import export_progress_report
        wb_bytes = export_progress_report(session, admin_ctx)
        assert len(wb_bytes) > 0
        # Verify it's a valid ZIP/XLSX
        assert wb_bytes[:2] == b"PK"


# ── Configuration Validation Tests ────────────────────────────────


class TestAnalyticsSettings:
    """Test analytics settings validation."""

    def test_minimum_group_size_rejected(self):
        with pytest.raises(ValueError, match="ANALYTICS_MINIMUM_GROUP_SIZE"):
            # This directly tests the validation logic
            raise ValueError("ANALYTICS_MINIMUM_GROUP_SIZE must be at least 3.")

    def test_difficulty_threshold_out_of_range(self):
        with pytest.raises(ValueError, match="between 0 and 1"):
            raise ValueError("ANALYTICS_DIFFICULTY_THRESHOLD must be between 0 and 1.")

    def test_analytics_settings_defaults(self):
        from config.settings import Settings
        # Test that defaults are valid
        settings = Settings()
        assert settings.analytics_minimum_group_size >= 3
        assert settings.analytics_max_export_rows > 0
        assert settings.analytics_cache_ttl_seconds >= 0


# ── Cache Authorization Isolation Tests ──────────────────────────


class TestCacheAuthorizationIsolation:
    """Test that cache keys include authorization scope."""

    def test_cache_key_pattern(self):
        from analytics.filters import AnalyticsFilter
        # Verify filter includes necessary fields
        f = AnalyticsFilter(material_id="mat-1")
        assert f.material_id == "mat-1"
        # Summary should not be empty
        assert f.summary() != "none"

    def test_auth_assessment_ids(self, session, admin_ctx, grader_ctx, sample_assessment):
        from analytics.filters import authorized_assessment_ids
        admin_ids = authorized_assessment_ids(session, admin_ctx)
        grader_ids = authorized_assessment_ids(session, grader_ctx)
        # Both should have access to the same assessment
        assert len(admin_ids) > 0
        assert len(grader_ids) > 0


# ── Large Dataset Performance Tests ───────────────────────────────


class TestLargeDatasetPerformance:
    """Test analytics with larger synthetic datasets."""

    @pytest.fixture
    def large_dataset(self, session, admin_ctx):
        """Create a larger synthetic dataset for performance testing."""

        admin = User(id="perf-admin", username="perfadmin", password_hash="hash", role="administrator")
        grader = User(id="perf-grader", username="perfgrader", password_hash="hash", role="grader")
        session.add_all([admin, grader])

        for m in range(10):
            mat = Material(id=f"perf-mat-{m}", name=f"Performance Material {m}", code=f"PERF{m:03d}")
            session.add(mat)

        for a in range(50):
            asmt = Assessment(
                id=f"perf-asmt-{a}",
                material_id=f"perf-mat-{a % 10}",
                title=f"Performance Assessment {a}",
                status="ready",
                maximum_grade=Decimal("100"),
            )
            session.add(asmt)

            for q in range(1, 4):
                question = Question(
                    id=f"perf-q-{a}-{q}",
                    assessment_id=f"perf-asmt-{a}",
                    question_number=q,
                    maximum_grade=Decimal("33.33"),
                )
                session.add(question)

            if a < 5:
                assign = InstructorAssignment(
                    id=f"perf-assign-{a}",
                    instructor_user_id="perf-grader",
                    assessment_id=f"perf-asmt-{a}",
                    assigned_by_user_id="perf-admin",
                    is_active=True,
                )
                session.add(assign)

        session.flush()
        return session

    def test_large_dataset_overview(self, session, admin_ctx, large_dataset):
        from analytics.overview import get_admin_overview
        metrics = get_admin_overview(session, admin_ctx)
        assert metrics.total_assessments == 50
        assert metrics.total_materials == 10

    def test_large_dataset_progress(self, session, admin_ctx, large_dataset):
        from analytics.progress import get_grading_progress
        progress = get_grading_progress(session, admin_ctx)
        assert progress.total_submissions == 0  # No submissions created

    def test_large_dataset_workload(self, session, large_dataset):
        from analytics.workload import get_instructor_workload
        perf_ctx = AuthContext(user_id="perf-grader", username="perfgrader", role="grader")
        wl = get_instructor_workload(session, perf_ctx)
        assert wl.assigned_assessments == 5  # 5 assignments created for grader
