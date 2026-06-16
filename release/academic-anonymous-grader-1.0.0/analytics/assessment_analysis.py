# Academic Anonymous Grader — Assessment Performance Analytics
"""Assessment-level performance statistics including mean, median,
quartiles, pass/fail, and finalization readiness.

All functions require an AuthContext and enforce authorization scope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func

from analytics.filters import AnalyticsFilter, authorized_assessment_ids
from analytics.models import (
    AssessmentPerformanceMetrics,
    FinalizationReadinessItem,
    PrivacyState,
)
from analytics.privacy import check_group_size, suppress_statistics
from analytics.statistics import (
    compute_pass_fail,
    safe_max,
    safe_mean,
    safe_median,
    safe_min,
    safe_quartiles,
    safe_stdev,
)
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.submission import Submission
from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_assessment_performance(
    session: Session,
    ctx: AuthContext | None,
    assessment_id: str,
    filter_obj: AnalyticsFilter | None = None,
    mode: str = "approved",
) -> AssessmentPerformanceMetrics:
    """Get performance statistics for a single assessment.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    assessment_id : str
        Assessment ID.
    filter_obj : AnalyticsFilter | None
        Additional filter parameters.
    mode : str
        Population mode: 'snapshot', 'approved', 'finalized'.

    Returns
    -------
    AssessmentPerformanceMetrics
        Assessment performance metrics.
    """
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if assessment_id not in auth_ids:
        return AssessmentPerformanceMetrics(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    asmt = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not asmt:
        return AssessmentPerformanceMetrics(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    # Base query for submissions
    sub_query = session.query(Submission).filter(
        Submission.assessment_id == assessment_id
    )
    total_subs = sub_query.count()

    # Submissions by review status (for approved/finalized modes)
    if mode == "approved":
        sub_query = sub_query.filter(Submission.review_status == "approved")
    elif mode == "finalized":
        sub_query = sub_query.filter(
            Submission.assessment.has(status="finalized"),
            Submission.review_status == "approved",
        )

    graded_count = sub_query.filter(Submission.grading_status == "graded").count()
    approved_count = sub_query.filter(Submission.review_status == "approved").count()

    # Collect grade totals per submission
    sub_ids = [s.id for s in sub_query.all()]
    privacy = check_group_size(
        len(sub_ids),
        filter_obj.minimum_group_size if filter_obj else None,
    )

    grade_totals: list[float] = []
    for sid in sub_ids:
        grades = (
            session.query(func.coalesce(GradeRecord.grade, 0))
            .filter(GradeRecord.submission_id == sid)
            .all()
        )
        total_grade = sum(float(g[0]) for g in grades)
        if total_grade > 0 or any(g[0] is not None for g in grades):
            grade_totals.append(total_grade)

    max_grade_f = float(asmt.maximum_grade)
    mean_val = safe_mean(grade_totals)
    median_val = safe_median(grade_totals)
    min_val = safe_min(grade_totals)
    max_val = safe_max(grade_totals)
    std_val = safe_stdev(grade_totals)
    q1, _, q3 = safe_quartiles(grade_totals)
    iqr = (q3 - q1) if (q3 is not None and q1 is not None) else None

    pass_count, fail_count, pass_pct = compute_pass_fail(
        grade_totals, maximum=max_grade_f
    )

    comp_pct = (graded_count / total_subs * 100.0) if total_subs > 0 else 0.0

    # Finalization readiness
    from services.finalization_service import get_finalization_readiness
    ready = get_finalization_readiness(session, assessment_id)
    blocker_count = len(ready.blocking_errors) if hasattr(ready, "blocking_errors") else 0

    return AssessmentPerformanceMetrics(
        assessment_id=assessment_id,
        assessment_title=asmt.title,
        material_title=asmt.material.name if asmt.material else "",
        maximum_grade=asmt.maximum_grade,
        submission_count=total_subs,
        graded_count=graded_count,
        approved_count=approved_count,
        mean_grade=suppress_statistics(round(mean_val, 2) if mean_val is not None else None, privacy),
        median_grade=suppress_statistics(round(median_val, 2) if median_val is not None else None, privacy),
        minimum_grade=suppress_statistics(round(min_val, 2) if min_val is not None else None, privacy),
        max_grade_val=suppress_statistics(round(max_val, 2) if max_val is not None else None, privacy),
        standard_deviation=suppress_statistics(round(std_val, 2) if std_val is not None else None, privacy),
        lower_quartile=suppress_statistics(round(q1, 2) if q1 is not None else None, privacy),
        upper_quartile=suppress_statistics(round(q3, 2) if q3 is not None else None, privacy),
        interquartile_range=suppress_statistics(round(iqr, 2) if iqr is not None else None, privacy),
        pass_count=pass_count,
        fail_count=fail_count,
        pass_percentage=round(pass_pct, 1),
        completion_percentage=round(comp_pct, 1),
        ready_for_finalization=ready.is_ready if hasattr(ready, "is_ready") else False,
        blocker_count=blocker_count,
        population_mode=mode,
        privacy=privacy,
    )


def list_finalization_readiness(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter | None = None,
) -> list[FinalizationReadinessItem]:
    """List finalization readiness for all authorized assessments.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    filter_obj : AnalyticsFilter | None
        Optional filter.

    Returns
    -------
    list[FinalizationReadinessItem]
        Readiness items.
    """
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if not auth_ids:
        return []

    from services.finalization_service import get_finalization_readiness as _check_readiness

    items: list[FinalizationReadinessItem] = []
    for aid in auth_ids:
        asmt = session.query(Assessment).filter(Assessment.id == aid).first()
        if not asmt:
            continue

        sub_query = session.query(Submission).filter(Submission.assessment_id == aid)
        total = sub_query.count()
        graded = sub_query.filter(Submission.grading_status == "graded").count()
        drafts = sub_query.filter(Submission.grading_status == "in_progress").count()

        now = datetime.now(UTC)
        active_claims = sub_query.filter(
            Submission.grading_status == "pending",
            Submission.assigned_grader_user_id.isnot(None),
            Submission.grading_lock_expires_at > now,
        ).count()
        stale_claims = sub_query.filter(
            Submission.grading_status == "pending",
            Submission.assigned_grader_user_id.isnot(None),
            Submission.grading_lock_expires_at <= now,
        ).count()
        unresolved = sub_query.filter(
            Submission.review_status == "needs_correction"
        ).count()
        pending_approval = sub_query.filter(
            Submission.review_status == "not_ready",
            Submission.grading_status == "graded",
        ).count()

        ready = _check_readiness(session, aid)
        blocker_codes = (
            [str(b) for b in ready.blocking_errors]
            if hasattr(ready, "blocking_errors") and ready.blocking_errors
            else []
        )

        status = "ready" if (hasattr(ready, "is_ready") and ready.is_ready) else "blocked"
        if total == 0:
            status = "not_applicable"

        items.append(
            FinalizationReadinessItem(
                assessment_id=aid,
                assessment_title=asmt.title,
                total_submissions=total,
                graded=graded,
                drafts=drafts,
                active_claims=active_claims,
                stale_claims=stale_claims,
                unresolved_corrections=unresolved,
                approvals_pending=pending_approval,
                readiness_status=status,
                blocker_reason_codes=blocker_codes,
            )
        )

    return items
