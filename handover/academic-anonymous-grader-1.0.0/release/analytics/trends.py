# Academic Anonymous Grader — Trend Analytics
"""Time-series trend analytics — grading completion, corrections,
approvals, and workload trends over time.

Uses daily, weekly, or monthly grouping based on date range.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func

from analytics.filters import AnalyticsFilter, authorized_assessment_ids
from analytics.models import PrivacyState, TrendDataPoint, TrendReport
from models.submission import Submission
from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _grouping_label(
    dt: datetime,
    date_from: datetime | None,
    date_to: datetime | None,
) -> str:
    """Determine the label grouping based on date range span."""
    if date_from and date_to:
        span_days = (date_to - date_from).days
        if span_days > 90:
            return dt.strftime("%Y-%m")  # Monthly
        if span_days > 30:
            return dt.strftime("%Y-W%W")  # Weekly
    return dt.strftime("%Y-%m-%d")  # Daily


def get_grading_completion_trend(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter | None = None,
    assessment_id: str | None = None,
) -> TrendReport:
    """Get grading completion over time.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    filter_obj : AnalyticsFilter | None
        Optional filter.
    assessment_id : str | None
        Specific assessment.

    Returns
    -------
    TrendReport
        Trend data points.
    """
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if assessment_id:
        if assessment_id not in auth_ids:
            return TrendReport(
                privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
            )
        auth_ids = [assessment_id]

    if not auth_ids:
        return TrendReport(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    query = session.query(
        func.date(Submission.completed_at).label("day"),
        func.count(Submission.id).label("count"),
    ).filter(
        Submission.assessment_id.in_(auth_ids),
        Submission.grading_status == "graded",
        Submission.completed_at.isnot(None),
    )

    if filter_obj and filter_obj.date_from:
        query = query.filter(Submission.completed_at >= filter_obj.date_from)
    if filter_obj and filter_obj.date_to:
        query = query.filter(Submission.completed_at <= filter_obj.date_to)

    query = query.group_by("day").order_by("day")
    results = query.all()

    points = [
        TrendDataPoint(date_label=str(r.day), value=float(r.count), count=int(r.count))
        for r in results
    ]
    total = sum(p.count for p in points)

    return TrendReport(
        series_name="Grading Completion",
        data_points=points,
        total=total,
        privacy=PrivacyState(suppressed=False),
    )


def get_correction_trend(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter | None = None,
) -> TrendReport:
    """Get correction return trend over time."""
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if not auth_ids:
        return TrendReport(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    query = session.query(
        func.date(Submission.reviewed_at).label("day"),
        func.count(Submission.id).label("count"),
    ).filter(
        Submission.assessment_id.in_(auth_ids),
        Submission.review_status == "needs_correction",
        Submission.reviewed_at.isnot(None),
    )

    if filter_obj and filter_obj.date_from:
        query = query.filter(Submission.reviewed_at >= filter_obj.date_from)
    if filter_obj and filter_obj.date_to:
        query = query.filter(Submission.reviewed_at <= filter_obj.date_to)

    query = query.group_by("day").order_by("day")
    results = query.all()

    points = [
        TrendDataPoint(date_label=str(r.day), value=float(r.count), count=int(r.count))
        for r in results
    ]
    total = sum(p.count for p in points)

    return TrendReport(
        series_name="Corrections Returned",
        data_points=points,
        total=total,
        privacy=PrivacyState(suppressed=False),
    )
