# Academic Anonymous Grader — Analytics Grading Progress
"""Grading progress analytics — completion status, claim tracking, and
turnaround time calculations.

All functions require an AuthContext and enforce authorization scope.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func

from analytics.filters import AnalyticsFilter, authorized_assessment_ids
from analytics.models import GradingProgressSummary, PrivacyState
from analytics.privacy import check_group_size
from models.submission import Submission
from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


STALE_CLAIM_HOURS_DEFAULT = 4


def get_grading_progress(
    session: Session,
    ctx: AuthContext | None,
    assessment_id: str | None = None,
    filter_obj: AnalyticsFilter | None = None,
) -> GradingProgressSummary:
    """Get grading progress for authorized assessments.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    assessment_id : str | None
        Specific assessment to scope to.
    filter_obj : AnalyticsFilter | None
        Additional filter parameters.

    Returns
    -------
    GradingProgressSummary
        Grading progress metrics.
    """
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if assessment_id:
        if assessment_id not in auth_ids:
            return GradingProgressSummary(
                privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
            )
        auth_ids = [assessment_id]

    if not auth_ids:
        return GradingProgressSummary(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    query = session.query(Submission).filter(Submission.assessment_id.in_(auth_ids))

    total = query.count()

    if total == 0:
        return GradingProgressSummary(privacy=PrivacyState(suppressed=False))

    # Check privacy threshold
    privacy = check_group_size(total, filter_obj.minimum_group_size if filter_obj else None)
    if privacy.suppressed:
        return GradingProgressSummary(privacy=privacy)

    # Status counts
    not_started = query.filter(
        Submission.grading_status == "pending",
        Submission.assigned_grader_user_id.is_(None),
    ).count()

    claimed = query.filter(
        Submission.assigned_grader_user_id.isnot(None),
        Submission.grading_status == "pending",
    ).count()

    draft = query.filter(Submission.grading_status == "in_progress").count()
    completed = query.filter(Submission.grading_status == "graded").count()

    needs_correction = query.filter(Submission.review_status == "needs_correction").count()
    approved = query.filter(Submission.review_status == "approved").count()

    # Corrected: submissions that were returned and re-graded
    corrected = query.filter(
        Submission.review_status == "approved",
        Submission.reviewed_at.isnot(None),
    ).count()

    finalized_ids = (
        session.query(Submission.id)
        .filter(
            Submission.assessment_id.in_(auth_ids),
            Submission.assessment.has(status="finalized"),
        )
        .count()
    )

    pct_complete = (completed / total * 100.0) if total > 0 else 0.0
    pct_approved = (approved / total * 100.0) if total > 0 else 0.0

    # Active claims
    now = datetime.now(UTC)
    now - timedelta(hours=STALE_CLAIM_HOURS_DEFAULT)
    active_claims = query.filter(
        Submission.grading_status == "pending",
        Submission.assigned_grader_user_id.isnot(None),
        Submission.grading_lock_expires_at > now,
    ).count()

    stale_claims = query.filter(
        Submission.grading_status == "pending",
        Submission.assigned_grader_user_id.isnot(None),
        Submission.grading_lock_expires_at <= now,
    ).count()

    # Turnaround: claim to completion
    graded_subs = (
        session.query(Submission)
        .filter(
            Submission.assessment_id.in_(auth_ids),
            Submission.grading_status == "graded",
            Submission.grading_claimed_at.isnot(None),
            Submission.completed_at.isnot(None),
        )
        .all()
    )
    durations = []
    for s in graded_subs:
        if s.grading_claimed_at and s.completed_at:
            delta = s.completed_at - s.grading_claimed_at
            hours = delta.total_seconds() / 3600.0
            if hours >= 0:
                durations.append(hours)
    avg_claim = (sum(durations) / len(durations)) if durations else None

    # Return to correction turnaround
    corrected_subs = (
        session.query(Submission)
        .filter(
            Submission.assessment_id.in_(auth_ids),
            Submission.reviewed_at.isnot(None),
            Submission.status.isnot(None),
        )
        .all()
    )
    corr_durations = []
    for s in corrected_subs:
        if hasattr(s, "reviewed_at") and s.reviewed_at and s.completed_at:
            delta = s.reviewed_at - s.completed_at
            hours = delta.total_seconds() / 3600.0
            if hours >= 0:
                corr_durations.append(hours)

    avg_corr = (sum(corr_durations) / len(corr_durations)) if corr_durations else None

    # Last activity
    last_activity = (
        session.query(func.max(Submission.imported_at))
        .filter(Submission.assessment_id.in_(auth_ids))
        .scalar()
    )

    return GradingProgressSummary(
        total_submissions=total,
        not_started=not_started,
        claimed=claimed,
        draft=draft,
        completed=completed,
        needs_correction=needs_correction,
        corrected=corrected,
        approved=approved,
        finalized=finalized_ids,
        percentage_complete=round(pct_complete, 1),
        percentage_approved=round(pct_approved, 1),
        active_claims=active_claims,
        stale_claims=stale_claims,
        avg_claim_to_completion_hours=round(avg_claim, 1) if avg_claim is not None else None,
        avg_return_to_correction_hours=round(avg_corr, 1) if avg_corr is not None else None,
        last_activity=last_activity,
        privacy=privacy,
    )
