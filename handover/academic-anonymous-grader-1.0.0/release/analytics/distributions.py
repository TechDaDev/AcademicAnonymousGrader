# Academic Anonymous Grader — Grade Distribution Analytics
"""Grade distribution analysis — histograms, bands, quartiles, and
privacy-safe summary statistics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from analytics.filters import AnalyticsFilter, authorized_assessment_ids
from analytics.models import GradeBand, GradeDistribution, PrivacyState
from analytics.privacy import check_group_size, suppress_all_distribution, suppress_statistics
from analytics.statistics import (
    compute_grade_bands,
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


def get_grade_distribution(
    session: Session,
    ctx: AuthContext | None,
    assessment_id: str,
    filter_obj: AnalyticsFilter | None = None,
    bands: list[tuple[float, float, str]] | None = None,
) -> GradeDistribution:
    """Get grade distribution for an assessment.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    assessment_id : str
        Assessment ID.
    filter_obj : AnalyticsFilter | None
        Optional filter.
    bands : list[tuple[float, float, str]] | None
        Custom grade bands.

    Returns
    -------
    GradeDistribution
        Grade distribution.
    """
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if assessment_id not in auth_ids:
        return GradeDistribution(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    asmt = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not asmt:
        return GradeDistribution(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    # Get approved submission grade totals
    sub_ids = [
        r[0]
        for r in session.query(Submission.id)
        .filter(
            Submission.assessment_id == assessment_id,
            Submission.review_status == "approved",
        )
        .all()
    ]

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
        grade_totals.append(total_grade)

    max_f = float(asmt.maximum_grade)

    # Compute band distribution
    band_data = compute_grade_bands(grade_totals, max_f, bands)
    grade_bands = [
        GradeBand(
            label=str(b["label"]),
            min_pct=float(str(b["min_pct"])),
            max_pct=float(str(b["max_pct"])),
            count=int(str(b["count"])),
            percentage=float(str(b["percentage"])),
        )
        for b in band_data
    ]

    mean_val = safe_mean(grade_totals)
    median_val = safe_median(grade_totals)
    min_val = safe_min(grade_totals)
    max_val = safe_max(grade_totals)
    std_val = safe_stdev(grade_totals)
    q1, _, q3 = safe_quartiles(grade_totals)

    pass_count, fail_count, pass_pct = compute_pass_fail(grade_totals, maximum=max_f)

    # Convert to percentages
    mean_pct = ((mean_val / max_f) * 100.0) if mean_val is not None and max_f > 0 else None
    median_pct = ((median_val / max_f) * 100.0) if median_val is not None and max_f > 0 else None
    min_pct = ((min_val / max_f) * 100.0) if min_val is not None and max_f > 0 else None
    max_pct = ((max_val / max_f) * 100.0) if max_val is not None and max_f > 0 else None
    std_pct = ((std_val / max_f) * 100.0) if std_val is not None and max_f > 0 else None
    q1_pct = ((q1 / max_f) * 100.0) if q1 is not None and max_f > 0 else None
    q3_pct = ((q3 / max_f) * 100.0) if q3 is not None and max_f > 0 else None

    return GradeDistribution(
        assessment_id=assessment_id,
        assessment_title=asmt.title,
        submission_count=len(sub_ids),
        graded_count=len(grade_totals),
        bands=suppress_all_distribution(grade_bands, privacy),
        mean_grade_pct=suppress_statistics(round(mean_pct, 1) if mean_pct is not None else None, privacy),
        median_grade_pct=suppress_statistics(round(median_pct, 1) if median_pct is not None else None, privacy),
        minimum_grade_pct=suppress_statistics(round(min_pct, 1) if min_pct is not None else None, privacy),
        maximum_grade_pct=suppress_statistics(round(max_pct, 1) if max_pct is not None else None, privacy),
        std_dev_pct=suppress_statistics(round(std_pct, 1) if std_pct is not None else None, privacy),
        pass_count=pass_count,
        fail_count=fail_count,
        pass_percentage=round(pass_pct, 1),
        lower_quartile_pct=suppress_statistics(round(q1_pct, 1) if q1_pct is not None else None, privacy),
        upper_quartile_pct=suppress_statistics(round(q3_pct, 1) if q3_pct is not None else None, privacy),
        privacy=privacy,
    )
