# Academic Anonymous Grader — Progress Service
"""Privacy-safe aggregate progress tracking for assignments and grading.

Administrator view:
    - Progress by instructor (workload summaries)
    - Progress by assessment
    - Total and status counts
    - Completion percentage

Instructor view:
    - Own assigned assessments
    - Own pending, draft, completed, returned-correction counts
    - Own completion percentage

SAFETY: Never queries or exposes StudentIdentity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from models.assessment import Assessment
from models.instructor_assignment import InstructorAssignment
from models.submission import Submission
from services.authorization_service import AuthContext, authorize_context, require_role_is
from services.logging_service import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger("progress")


# ── Data classes ──────────────────────────────────────────────────


@dataclass(frozen=True)
class InstructorProgress:
    """Privacy-safe progress for one instructor."""

    instructor_user_id: str
    instructor_display_name: str | None
    total_submissions: int = 0
    pending_submissions: int = 0
    draft_submissions: int = 0
    completed_submissions: int = 0
    returned_correction_submissions: int = 0
    completion_percentage: float = 0.0
    last_activity_at: datetime | None = None


@dataclass(frozen=True)
class AssessmentProgress:
    """Privacy-safe progress for one assessment."""

    assessment_id: str
    assessment_title: str
    material_title: str | None
    total_submissions: int = 0
    ungraded_submissions: int = 0
    draft_submissions: int = 0
    graded_submissions: int = 0
    approved_submissions: int = 0
    completion_percentage: float = 0.0
    assigned_instructors: int = 0


@dataclass(frozen=True)
class OwnProgress:
    """Privacy-safe own progress for an instructor."""

    total_assessments: int = 0
    total_submissions: int = 0
    pending: int = 0
    draft: int = 0
    completed: int = 0
    returned_correction: int = 0
    completion_percentage: float = 0.0


# ── Internal helpers ──────────────────────────────────────────────


def _get_submission_counts_for_grader(
    session: Session, grader_user_id: str
) -> dict[str, int]:
    """Get submission status counts for a specific grader across all their assignments."""
    submissions = (
        session.query(Submission)
        .join(
            InstructorAssignment,
            (InstructorAssignment.assessment_id == Submission.assessment_id)
            & (InstructorAssignment.instructor_user_id == grader_user_id)
            & (InstructorAssignment.is_active == True),  # noqa: E712
        )
        .all()
    )

    total = len(submissions)
    pending = sum(1 for s in submissions if s.grading_status == "pending")
    draft = sum(
        1
        for s in submissions
        if s.grading_status in ("draft", "in_progress")
    )
    completed = sum(1 for s in submissions if s.grading_status == "graded")
    returned = sum(1 for s in submissions if s.review_status == "needs_correction")

    return {
        "total": total,
        "pending": pending,
        "draft": draft,
        "completed": completed,
        "returned": returned,
    }


# ── Public API ────────────────────────────────────────────────────


def get_instructor_progress(
    session: Session,
    *,
    auth_ctx: AuthContext,
    instructor_user_id: str | None = None,
) -> InstructorProgress:
    """Get progress for a specific instructor.

    Administrator may query any instructor.  Instructors may only
    query their own progress.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.
    instructor_user_id : str | None
        Instructor to query.  Defaults to the authenticated user for
        non-admin roles.

    Returns
    -------
    InstructorProgress
        Privacy-safe progress.
    """
    from models.user import User

    target_id = instructor_user_id or auth_ctx.user_id

    if auth_ctx.role != "administrator":
        target_id = auth_ctx.user_id

    counts = _get_submission_counts_for_grader(session, target_id)
    user = session.query(User).filter(User.id == target_id).first()

    pct = round(counts["completed"] / max(counts["total"], 1) * 100, 1)

    return InstructorProgress(
        instructor_user_id=target_id,
        instructor_display_name=user.display_name if user else None,
        total_submissions=counts["total"],
        pending_submissions=counts["pending"],
        draft_submissions=counts["draft"],
        completed_submissions=counts["completed"],
        returned_correction_submissions=counts["returned"],
        completion_percentage=pct,
    )


def get_assessment_progress(
    session: Session,
    *,
    auth_ctx: AuthContext,
    assessment_id: str,
) -> AssessmentProgress:
    """Get progress for a specific assessment.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.
    assessment_id : str
        Assessment ID.

    Returns
    -------
    AssessmentProgress
        Privacy-safe progress.
    """
    authorize_context(auth_ctx, "view_grades")

    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        return AssessmentProgress(assessment_id=assessment_id, assessment_title="Unknown", material_title="")

    material_title = assessment.material.name if assessment.material else None

    submissions = (
        session.query(Submission)
        .filter(Submission.assessment_id == assessment_id)
        .all()
    )

    total = len(submissions)
    ungraded = sum(1 for s in submissions if s.grading_status == "pending")
    draft = sum(
        1 for s in submissions if s.grading_status in ("draft", "in_progress")
    )
    graded = sum(1 for s in submissions if s.grading_status == "graded")
    approved = sum(1 for s in submissions if s.review_status == "approved")

    instructor_count = (
        session.query(InstructorAssignment)
        .filter(
            InstructorAssignment.assessment_id == assessment_id,
            InstructorAssignment.is_active == True,  # noqa: E712
        )
        .count()
    )

    pct = round(graded / max(total, 1) * 100, 1)

    return AssessmentProgress(
        assessment_id=assessment_id,
        assessment_title=assessment.title if assessment else "Unknown",
        material_title=material_title or "",
        total_submissions=total,
        ungraded_submissions=ungraded,
        draft_submissions=draft,
        graded_submissions=graded,
        approved_submissions=approved,
        completion_percentage=pct,
        assigned_instructors=instructor_count,
    )


def get_own_progress(
    session: Session,
    *,
    auth_ctx: AuthContext,
) -> OwnProgress:
    """Get progress for the authenticated instructor.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.  Must be grader or administrator.

    Returns
    -------
    OwnProgress
        Privacy-safe own progress.
    """
    counts = _get_submission_counts_for_grader(session, auth_ctx.user_id)

    # Count assigned assessments
    assessment_count = (
        session.query(InstructorAssignment)
        .filter(
            InstructorAssignment.instructor_user_id == auth_ctx.user_id,
            InstructorAssignment.is_active == True,  # noqa: E712
        )
        .count()
    )

    pct = round(counts["completed"] / max(counts["total"], 1) * 100, 1)

    return OwnProgress(
        total_assessments=assessment_count,
        total_submissions=counts["total"],
        pending=counts["pending"],
        draft=counts["draft"],
        completed=counts["completed"],
        returned_correction=counts["returned"],
        completion_percentage=pct,
    )


def get_all_instructor_progress(
    session: Session,
    *,
    auth_ctx: AuthContext,
) -> list[InstructorProgress]:
    """Get progress for all instructors with active assignments.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.  Must be administrator.

    Returns
    -------
    list[InstructorProgress]
        Privacy-safe progress list.
    """
    require_role_is(auth_ctx, "administrator")

    from models.user import User

    active_assignments = (
        session.query(InstructorAssignment)
        .filter(InstructorAssignment.is_active == True)  # noqa: E712
        .all()
    )

    instructor_ids = {a.instructor_user_id for a in active_assignments}
    result: list[InstructorProgress] = []

    for iid in instructor_ids:
        user = session.query(User).filter(User.id == iid).first()
        counts = _get_submission_counts_for_grader(session, iid)
        pct = round(counts["completed"] / max(counts["total"], 1) * 100, 1)

        result.append(
            InstructorProgress(
                instructor_user_id=iid,
                instructor_display_name=user.display_name if user else None,
                total_submissions=counts["total"],
                pending_submissions=counts["pending"],
                draft_submissions=counts["draft"],
                completed_submissions=counts["completed"],
                returned_correction_submissions=counts["returned"],
                completion_percentage=pct,
            )
        )

    return sorted(result, key=lambda p: p.instructor_display_name or "")
