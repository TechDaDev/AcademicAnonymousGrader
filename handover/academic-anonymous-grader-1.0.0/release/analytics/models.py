# Academic Anonymous Grader — Analytics Result Models
"""Privacy-safe typed result data transfer objects for analytics.

These DTOs are returned by analytics service functions and consumed by
the Streamlit UI and export generators. They contain no ORM objects,
no student identity fields, no raw responses, and no feedback text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

# ── Privacy state ────────────────────────────────────────────────


@dataclass(frozen=True)
class PrivacyState:
    """Privacy suppression state for a report or metric."""

    suppressed: bool = False
    reason: str = ""
    minimum_group_size: int = 5
    actual_group_size: int = 0


# ── Overview ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class OverviewMetrics:
    """Administrator overview dashboard metrics."""

    total_materials: int = 0
    total_assessments: int = 0
    active_assessments: int = 0
    finalized_assessments: int = 0
    total_submissions: int = 0
    grading_completion_percentage: float = 0.0
    pending_grading: int = 0
    drafts: int = 0
    returned_corrections: int = 0
    approved_submissions: int = 0
    active_grading_claims: int = 0
    active_instructor_assignments: int = 0
    avg_grading_turnaround_hours: float | None = None
    ready_for_finalization: int = 0
    blocked_from_finalization: int = 0


@dataclass(frozen=True)
class InstructorOverviewMetrics:
    """Instructor's own overview dashboard metrics."""

    assigned_assessments: int = 0
    pending_submissions: int = 0
    drafts: int = 0
    completed_grading: int = 0
    returned_corrections: int = 0
    active_claims: int = 0
    completion_percentage: float = 0.0
    avg_turnaround_hours: float | None = None
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Grading Progress ─────────────────────────────────────────────


@dataclass(frozen=True)
class GradingProgressSummary:
    """Grading progress for a material, assessment, or instructor."""

    total_submissions: int = 0
    not_started: int = 0
    claimed: int = 0
    draft: int = 0
    completed: int = 0
    needs_correction: int = 0
    corrected: int = 0
    approved: int = 0
    finalized: int = 0
    percentage_complete: float = 0.0
    percentage_approved: float = 0.0
    unresolved_blockers: int = 0
    active_claims: int = 0
    stale_claims: int = 0
    avg_claim_to_completion_hours: float | None = None
    avg_return_to_correction_hours: float | None = None
    last_activity: datetime | None = None
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Workload ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class InstructorWorkloadMetrics:
    """Workload summary for one instructor."""

    instructor_user_id: str = ""
    instructor_display_name: str | None = None
    active_assignments: int = 0
    assigned_assessments: int = 0
    assigned_submissions: int = 0
    pending_submissions: int = 0
    completed_submissions: int = 0
    corrections_pending: int = 0
    completion_percentage: float = 0.0
    avg_grading_duration_hours: float | None = None
    last_activity: datetime | None = None
    active_claims: int = 0
    stale_claims: int = 0
    workload_status: str = "unknown"  # light, balanced, high, overloaded
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Assessment Performance ────────────────────────────────────────


@dataclass(frozen=True)
class AssessmentPerformanceMetrics:
    """Performance statistics for a single assessment."""

    assessment_id: str = ""
    assessment_title: str = ""
    material_title: str = ""
    maximum_grade: Decimal = Decimal("0")
    submission_count: int = 0
    graded_count: int = 0
    approved_count: int = 0
    mean_grade: float | None = None
    median_grade: float | None = None
    minimum_grade: float | None = None
    max_grade_val: float | None = None
    standard_deviation: float | None = None
    lower_quartile: float | None = None
    upper_quartile: float | None = None
    interquartile_range: float | None = None
    pass_count: int = 0
    fail_count: int = 0
    pass_percentage: float = 0.0
    completion_percentage: float = 0.0
    ready_for_finalization: bool = False
    blocker_count: int = 0
    population_mode: str = "approved"  # snapshot, approved, finalized
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Grade Distribution ────────────────────────────────────────────


@dataclass(frozen=True)
class GradeBand:
    """A single grade band with count and percentage."""

    label: str = ""
    min_pct: float = 0.0
    max_pct: float = 100.0
    count: int = 0
    percentage: float = 0.0


@dataclass(frozen=True)
class GradeDistribution:
    """Grade distribution analytics for an assessment."""

    assessment_id: str = ""
    assessment_title: str = ""
    submission_count: int = 0
    graded_count: int = 0
    bands: list[GradeBand] = field(default_factory=list)
    mean_grade_pct: float | None = None
    median_grade_pct: float | None = None
    minimum_grade_pct: float | None = None
    maximum_grade_pct: float | None = None
    std_dev_pct: float | None = None
    pass_count: int = 0
    fail_count: int = 0
    pass_percentage: float = 0.0
    lower_quartile_pct: float | None = None
    upper_quartile_pct: float | None = None
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Question Analysis ─────────────────────────────────────────────


@dataclass(frozen=True)
class QuestionAnalysis:
    """Analytics for a single question."""

    question_id: str = ""
    question_number: int = 0
    maximum_grade: Decimal = Decimal("0")
    graded_response_count: int = 0
    mean_awarded: float | None = None
    median_awarded: float | None = None
    minimum_awarded: float | None = None
    maximum_awarded: float | None = None
    standard_deviation: float | None = None
    average_percentage: float | None = None
    full_score_count: int = 0
    zero_score_count: int = 0
    partial_credit_count: int = 0
    unanswered_count: int = 0
    ungraded_count: int = 0
    difficulty_index: float | None = None
    discrimination_available: bool = False
    correction_return_count: int = 0
    flags: list[str] = field(default_factory=list)
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Trend ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrendDataPoint:
    """A single data point in a trend series."""

    date_label: str = ""
    value: float = 0.0
    count: int = 0


@dataclass(frozen=True)
class TrendReport:
    """Time-series trend analytics."""

    series_name: str = ""
    data_points: list[TrendDataPoint] = field(default_factory=list)
    total: int = 0
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Correction Analytics ──────────────────────────────────────────


@dataclass(frozen=True)
class CorrectionAnalytics:
    """Correction and review analytics."""

    total_returned_for_correction: int = 0
    resolved_corrections: int = 0
    unresolved_corrections: int = 0
    avg_correction_cycles: float | None = None
    correction_completion_percentage: float = 0.0
    avg_return_to_correction_hours: float | None = None
    assessment_correction_rate: float = 0.0
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Finalization Readiness ────────────────────────────────────────


@dataclass(frozen=True)
class FinalizationReadinessItem:
    """Readiness status for one assessment."""

    assessment_id: str = ""
    assessment_title: str = ""
    total_submissions: int = 0
    graded: int = 0
    drafts: int = 0
    active_claims: int = 0
    stale_claims: int = 0
    unresolved_corrections: int = 0
    approvals_pending: int = 0
    invalid_grades: int = 0
    assignment_issues: int = 0
    readiness_status: str = "unknown"  # ready, blocked, not_applicable
    blocker_reason_codes: list[str] = field(default_factory=list)


# ── Data Quality ──────────────────────────────────────────────────


@dataclass(frozen=True)
class DataQualityIssue:
    """A single data quality issue."""

    issue_type: str = ""
    severity: str = "information"  # information, warning, critical
    count: int = 0
    description: str = ""


@dataclass(frozen=True)
class DataQualityReport:
    """Overall data quality report."""

    issues: list[DataQualityIssue] = field(default_factory=list)
    total_issues: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0


# ── Grading Consistency ───────────────────────────────────────────


@dataclass(frozen=True)
class GradingConsistencySummary:
    """Instructor grading consistency comparison (admin only)."""

    instructor_user_id: str = ""
    instructor_display_name: str | None = None
    avg_awarded_pct: float | None = None
    median_awarded_pct: float | None = None
    grading_volume: int = 0
    completion_time_hours: float | None = None
    correction_return_rate: float | None = None
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Turnaround Time ───────────────────────────────────────────────


@dataclass(frozen=True)
class TurnaroundMetrics:
    """Turnaround time metrics for a workflow stage."""

    metric_name: str = ""
    avg_hours: float | None = None
    median_hours: float | None = None
    minimum_hours: float | None = None
    maximum_hours: float | None = None
    sample_count: int = 0
    missing_timestamp_count: int = 0
    privacy: PrivacyState = field(default_factory=PrivacyState)


# ── Export Metadata ───────────────────────────────────────────────


@dataclass(frozen=True)
class ReportExportMetadata:
    """Metadata included in every analytics report export."""

    report_title: str = ""
    generated_at: str = ""
    filter_summary: str = ""
    population_definition: str = ""
    privacy_suppression_notes: str = ""
    application_version: str = ""
    schema_version: str = ""
