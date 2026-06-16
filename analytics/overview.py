# Academic Anonymous Grader — Overview Analytics
"""Overview dashboard metrics for Administrator and Instructor views.
All data is computed from existing models — no new storage required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from analytics.models import InstructorOverviewMetrics, OverviewMetrics, PrivacyState
from models.assessment import Assessment
from models.instructor_assignment import InstructorAssignment
from models.material import Material
from models.submission import Submission
from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_admin_overview(
    session: Session,
    ctx: AuthContext | None,
) -> OverviewMetrics:
    """Get administrator overview dashboard metrics.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.

    Returns
    -------
    OverviewMetrics
        Overview metrics.
    """
    if ctx is None or ctx.role != "administrator":
        return OverviewMetrics()

    total_materials = session.query(Material).count()
    total_assessments = session.query(Assessment).count()
    active_assessments = (
        session.query(Assessment)
        .filter(Assessment.status.in_(["draft", "ready", "grading"]))
        .count()
    )
    finalized_assessments = (
        session.query(Assessment).filter(Assessment.status == "finalized").count()
    )

    total_subs = session.query(Submission).count()
    graded_subs = session.query(Submission).filter(
        Submission.grading_status == "graded"
    ).count()
    pending = session.query(Submission).filter(
        Submission.grading_status == "pending"
    ).count()
    drafts = session.query(Submission).filter(
        Submission.grading_status == "in_progress"
    ).count()
    corrections = session.query(Submission).filter(
        Submission.review_status == "needs_correction"
    ).count()
    approved = session.query(Submission).filter(
        Submission.review_status == "approved"
    ).count()

    now = datetime.now(UTC)
    active_claims = session.query(Submission).filter(
        Submission.grading_status == "pending",
        Submission.assigned_grader_user_id.isnot(None),
        Submission.grading_lock_expires_at > now,
    ).count()

    active_assignments = session.query(InstructorAssignment).filter(
        InstructorAssignment.is_active == True  # noqa: E712
    ).count()

    # Average turnaround
    graded_subs_data = (
        session.query(Submission)
        .filter(
            Submission.grading_status == "graded",
            Submission.grading_claimed_at.isnot(None),
            Submission.completed_at.isnot(None),
        )
        .all()
    )
    durations = []
    for s in graded_subs_data:
        if s.grading_claimed_at and s.completed_at:
            delta = s.completed_at - s.grading_claimed_at
            hours = delta.total_seconds() / 3600.0
            if hours >= 0:
                durations.append(hours)
    avg_turnaround = (sum(durations) / len(durations)) if durations else None

    # Finalization readiness
    from services.finalization_service import get_finalization_readiness

    ready_count = 0
    blocked_count = 0
    for a in session.query(Assessment.id).filter(Assessment.status != "finalized").all():
        try:
            ready = get_finalization_readiness(session, a[0])
            if ready.is_ready:
                ready_count += 1
            else:
                blocked_count += 1
        except Exception:
            blocked_count += 1

    completion_pct = (graded_subs / total_subs * 100.0) if total_subs > 0 else 0.0

    return OverviewMetrics(
        total_materials=total_materials,
        total_assessments=total_assessments,
        active_assessments=active_assessments,
        finalized_assessments=finalized_assessments,
        total_submissions=total_subs,
        grading_completion_percentage=round(completion_pct, 1),
        pending_grading=pending,
        drafts=drafts,
        returned_corrections=corrections,
        approved_submissions=approved,
        active_grading_claims=active_claims,
        active_instructor_assignments=active_assignments,
        avg_grading_turnaround_hours=round(avg_turnaround, 1) if avg_turnaround is not None else None,
        ready_for_finalization=ready_count,
        blocked_from_finalization=blocked_count,
    )


def get_instructor_overview(
    session: Session,
    ctx: AuthContext | None,
) -> InstructorOverviewMetrics:
    """Get instructor's own overview dashboard metrics.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.

    Returns
    -------
    InstructorOverviewMetrics
        Instructor overview metrics.
    """
    if ctx is None or not ctx.user_id:
        return InstructorOverviewMetrics(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    # Get assigned assessment IDs
    assignment_ids = [
        r[0]
        for r in session.query(InstructorAssignment.assessment_id)
        .filter(
            InstructorAssignment.instructor_user_id == ctx.user_id,
            InstructorAssignment.is_active == True,  # noqa: E712
        )
        .all()
    ]

    if not assignment_ids:
        return InstructorOverviewMetrics(
            assigned_assessments=0,
            privacy=PrivacyState(suppressed=False),
        )

    sub_query = session.query(Submission).filter(
        Submission.assessment_id.in_(assignment_ids)
    )
    total_subs = sub_query.count()

    pending = sub_query.filter(
        Submission.grading_status == "pending"
    ).count()
    drafts = sub_query.filter(
        Submission.grading_status == "in_progress"
    ).count()
    completed = sub_query.filter(
        Submission.grading_status == "graded"
    ).count()
    corrections = sub_query.filter(
        Submission.review_status == "needs_correction"
    ).count()

    now = datetime.now(UTC)
    own_claims = sub_query.filter(
        Submission.assigned_grader_user_id == ctx.user_id,
        Submission.grading_status == "pending",
        Submission.grading_lock_expires_at > now,
    ).count()

    comp_pct = (completed / total_subs * 100.0) if total_subs > 0 else 0.0

    # Turnaround
    own_graded = (
        session.query(Submission)
        .filter(
            Submission.assessment_id.in_(assignment_ids),
            Submission.assigned_grader_user_id == ctx.user_id,
            Submission.grading_status == "graded",
            Submission.grading_claimed_at.isnot(None),
            Submission.completed_at.isnot(None),
        )
        .all()
    )
    durations = []
    for s in own_graded:
        if s.grading_claimed_at and s.completed_at:
            delta = s.completed_at - s.grading_claimed_at
            hours = delta.total_seconds() / 3600.0
            if hours >= 0:
                durations.append(hours)
    avg_turnaround = (sum(durations) / len(durations)) if durations else None

    return InstructorOverviewMetrics(
        assigned_assessments=len(assignment_ids),
        pending_submissions=pending,
        drafts=drafts,
        completed_grading=completed,
        returned_corrections=corrections,
        active_claims=own_claims,
        completion_percentage=round(comp_pct, 1),
        avg_turnaround_hours=round(avg_turnaround, 1) if avg_turnaround is not None else None,
        privacy=PrivacyState(suppressed=False),
    )
