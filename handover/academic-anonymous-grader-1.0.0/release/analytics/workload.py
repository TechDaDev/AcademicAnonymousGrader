# Academic Anonymous Grader — Instructor Workload Analytics
"""Instructor workload analytics — assignment counts, completion rates,
and workload status labels.

Administrator-only comparison view and instructor self-view.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func

from analytics.models import InstructorWorkloadMetrics, PrivacyState
from models.instructor_assignment import InstructorAssignment
from models.submission import Submission
from models.user import User
from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Workload threshold defaults
WORKLOAD_LIGHT_MAX = 5
WORKLOAD_BALANCED_MAX = 15
WORKLOAD_HIGH_MAX = 30


def _classify_workload(assigned_count: int, pending_count: int) -> str:
    """Classify workload status based on assignments and pending work.

    Parameters
    ----------
    assigned_count : int
        Number of assigned submissions.
    pending_count : int
        Number of pending (ungraded) submissions.

    Returns
    -------
    str
        One of 'light', 'balanced', 'high', 'overloaded'.
    """
    if assigned_count == 0:
        return "light"
    pending_ratio = pending_count / assigned_count if assigned_count > 0 else 0
    if assigned_count <= WORKLOAD_LIGHT_MAX and pending_ratio <= 0.3:
        return "light"
    if assigned_count <= WORKLOAD_BALANCED_MAX and pending_ratio <= 0.5:
        return "balanced"
    if assigned_count <= WORKLOAD_HIGH_MAX and pending_ratio <= 0.7:
        return "high"
    return "overloaded"


def get_instructor_workload(
    session: Session,
    ctx: AuthContext | None,
    instructor_user_id: str | None = None,
) -> InstructorWorkloadMetrics:
    """Get workload metrics for a single instructor.

    Administrator may request any instructor. Instructor may only
    request their own workload.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    instructor_user_id : str | None
        Instructor to query. Defaults to current user.

    Returns
    -------
    InstructorWorkloadMetrics
        Workload metrics.
    """
    if ctx is None:
        return InstructorWorkloadMetrics(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    target_id = instructor_user_id or ctx.user_id

    # Authorization check
    if ctx.role != "administrator" and target_id != ctx.user_id:
        return InstructorWorkloadMetrics(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    # Get instructor user info
    user = session.query(User).filter(User.id == target_id).first()
    if not user or user.role not in ("grader", "administrator"):
        return InstructorWorkloadMetrics(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    # Active assignments
    assignments = (
        session.query(InstructorAssignment)
        .filter(
            InstructorAssignment.instructor_user_id == target_id,
            InstructorAssignment.is_active == True,  # noqa: E712
        )
        .all()
    )
    active_assignments = len(assignments)
    assessment_ids = [a.assessment_id for a in assignments]

    if not assessment_ids:
        return InstructorWorkloadMetrics(
            instructor_user_id=target_id,
            instructor_display_name=user.display_name,
            active_assignments=0,
            workload_status="light",
        )

    # Submission counts for assigned assessments
    sub_query = session.query(Submission).filter(
        Submission.assessment_id.in_(assessment_ids)
    )
    total_submissions = sub_query.count()
    pending = sub_query.filter(
        Submission.grading_status.in_(["pending", "in_progress"])
    ).count()
    completed = sub_query.filter(Submission.grading_status == "graded").count()
    corrections = sub_query.filter(
        Submission.review_status == "needs_correction"
    ).count()

    # Own claims
    now = datetime.now(UTC)
    own_active_claims = sub_query.filter(
        Submission.assigned_grader_user_id == target_id,
        Submission.grading_status == "pending",
        Submission.grading_lock_expires_at > now,
    ).count()

    stale_claims = sub_query.filter(
        Submission.assigned_grader_user_id == target_id,
        Submission.grading_status == "pending",
        Submission.grading_lock_expires_at <= now,
    ).count()

    # Completion percentage
    comp_pct = (completed / total_submissions * 100.0) if total_submissions > 0 else 0.0

    # Average grading duration
    graded_subs = (
        session.query(Submission)
        .filter(
            Submission.assessment_id.in_(assessment_ids),
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
    avg_dur = (sum(durations) / len(durations)) if durations else None

    # Last activity
    last_act = (
        session.query(func.max(Submission.completed_at))
        .filter(
            Submission.assessment_id.in_(assessment_ids),
            Submission.assigned_grader_user_id == target_id,
        )
        .scalar()
    )

    workload = _classify_workload(total_submissions, pending)

    return InstructorWorkloadMetrics(
        instructor_user_id=target_id,
        instructor_display_name=user.display_name,
        active_assignments=active_assignments,
        assigned_assessments=len(assessment_ids),
        assigned_submissions=total_submissions,
        pending_submissions=pending,
        completed_submissions=completed,
        corrections_pending=corrections,
        completion_percentage=round(comp_pct, 1),
        avg_grading_duration_hours=round(avg_dur, 1) if avg_dur is not None else None,
        last_activity=last_act,
        active_claims=own_active_claims,
        stale_claims=stale_claims,
        workload_status=workload,
        privacy=PrivacyState(suppressed=False),
    )


def list_all_instructor_workloads(
    session: Session,
    ctx: AuthContext | None,
) -> list[InstructorWorkloadMetrics]:
    """List workload for all active graders (administrator only).

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.

    Returns
    -------
    list[InstructorWorkloadMetrics]
        List of workload metrics, one per instructor.
    """
    if ctx is None or ctx.role != "administrator":
        return []

    graders = (
        session.query(User)
        .filter(User.role == "grader", User.is_active == True)  # noqa: E712
        .all()
    )

    results = []
    for g in graders:
        wl = get_instructor_workload(session, ctx, g.id)
        if not wl.privacy.suppressed:
            results.append(wl)
    return results
