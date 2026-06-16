# Academic Anonymous Grader — Correction Analytics
"""Correction and review analytics — cycles, completion rates, and
assessment/question-level correction statistics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from analytics.filters import AnalyticsFilter, authorized_assessment_ids
from analytics.models import CorrectionAnalytics, PrivacyState
from analytics.privacy import check_group_size
from models.submission import Submission
from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_correction_analytics(
    session: Session,
    ctx: AuthContext | None,
    assessment_id: str | None = None,
    filter_obj: AnalyticsFilter | None = None,
) -> CorrectionAnalytics:
    """Get correction and review analytics.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    assessment_id : str | None
        Specific assessment.
    filter_obj : AnalyticsFilter | None
        Optional filter.

    Returns
    -------
    CorrectionAnalytics
        Correction analytics.
    """
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if assessment_id:
        if assessment_id not in auth_ids:
            return CorrectionAnalytics(
                privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
            )
        auth_ids = [assessment_id]

    if not auth_ids:
        return CorrectionAnalytics(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    query = session.query(Submission).filter(Submission.assessment_id.in_(auth_ids))
    total = query.count()

    privacy = check_group_size(total, filter_obj.minimum_group_size if filter_obj else None)

    total_returned = query.filter(
        Submission.review_status == "needs_correction"
    ).count()

    resolved = query.filter(
        Submission.review_status == "approved"
    ).count()

    unresolved = total_returned - resolved if total_returned > resolved else 0
    comp_pct = (resolved / total_returned * 100.0) if total_returned > 0 else 100.0

    # Average correction cycles (approximated as number of review changes)
    cycle_count = 0
    correction_subs = query.filter(
        Submission.review_status.in_(["needs_correction", "approved"]),
        Submission.reviewed_at.isnot(None),
    ).all()
    # Each unique review status change counts as a cycle
    for _ in correction_subs:
        cycle_count += 1

    avg_cycles = (
        round(cycle_count / len(correction_subs), 1) if correction_subs else None
    )

    # Return-to-correction duration
    durations = []
    for s in correction_subs:
        if s.reviewed_at and s.completed_at:
            delta = s.reviewed_at - s.completed_at
            hours = delta.total_seconds() / 3600.0
            if hours >= 0:
                durations.append(hours)
    avg_dur = (sum(durations) / len(durations)) if durations else None

    # Assessment correction rate
    asmt_rate = total_returned / total if total > 0 else 0.0

    return CorrectionAnalytics(
        total_returned_for_correction=total_returned,
        resolved_corrections=resolved,
        unresolved_corrections=unresolved,
        avg_correction_cycles=avg_cycles,
        correction_completion_percentage=round(comp_pct, 1),
        avg_return_to_correction_hours=round(avg_dur, 1) if avg_dur is not None else None,
        assessment_correction_rate=round(asmt_rate, 3),
        privacy=privacy,
    )
