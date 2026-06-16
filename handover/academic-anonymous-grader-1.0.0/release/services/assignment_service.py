# Academic Anonymous Grader — Instructor Assignment Service
"""Service layer for managing instructor-to-assessment assignments.

All public service entry points that modify or view sensitive assignment
data require an ``AuthContext``.  Operations that are administrator-only
enforce this via ``require_role_is(ctx, "administrator")``.

SAFETY: This service must never query or expose StudentIdentity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from models.instructor_assignment import InstructorAssignment
from models.submission import GRADING_CLAIM_DURATION_MINUTES, Submission
from services.authorization_service import (
    PERM_MANAGE_ASSIGNMENTS,
    PERM_VIEW_ASSIGNMENTS,
    AuthContext,
    authorize_context,
    require_role_is,
)
from services.exceptions import (
    AssignmentBlockedByFinalizationError,
    AssignmentNotFoundError,
    DuplicateAssignmentError,
    GradingClaimConflictError,
    GradingClaimNotFoundError,
    InstructorAssignmentError,
    InsufficientPermissionsError,
)
from services.logging_service import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger("assignment")


# ── Data classes ──────────────────────────────────────────────────


@dataclass(frozen=True)
class InstructorWorkload:
    """Privacy-safe workload summary for one instructor."""

    instructor_user_id: str
    instructor_display_name: str | None
    active_assignment_count: int
    total_submissions: int = 0
    claimed_submissions: int = 0
    draft_submissions: int = 0
    completed_submissions: int = 0
    needs_correction_submissions: int = 0
    completion_percentage: float = 0.0


@dataclass(frozen=True)
class AssignmentSummary:
    """Privacy-safe summary of a single assignment with progress."""

    assignment_id: str
    instructor_user_id: str
    instructor_display_name: str | None
    assessment_id: str
    assessment_title: str
    material_title: str | None
    is_active: bool
    assigned_at: datetime
    unassigned_at: datetime | None
    total_submissions: int = 0
    not_started: int = 0
    draft: int = 0
    completed: int = 0
    needs_correction: int = 0
    approved: int = 0
    completion_percentage: float = 0.0


# ── Internal helpers ──────────────────────────────────────────────


def _require_admin(ctx: AuthContext | None) -> None:
    """Require that the auth context exists and is an administrator."""
    if ctx is None or not ctx.user_id:
        raise InsufficientPermissionsError(
            "Authentication context is required for this operation."
        )
    require_role_is(ctx, "administrator")


def _require_grader_or_admin(ctx: AuthContext | None) -> str:
    """Require auth context and return user_id.  Allows grader or admin."""
    if ctx is None or not ctx.user_id:
        raise InsufficientPermissionsError(
            "Authentication context is required for this operation."
        )
    return ctx.user_id


def _validate_instructor(session: Session, instructor_user_id: str) -> Any:
    """Validate user exists, is active, and has role='grader'.  Returns User."""
    from models.user import User

    instructor = session.query(User).filter(User.id == instructor_user_id).first()
    if instructor is None:
        raise InstructorAssignmentError("Instructor not found.")
    if not instructor.is_active:
        raise InstructorAssignmentError("Instructor account is not active.")
    if instructor.role != "grader":
        raise InstructorAssignmentError(
            f"User is not an instructor (role={instructor.role})."
        )
    return instructor


def _validate_assessment_not_finalized(session: Session, assessment_id: str) -> Any:
    """Validate assessment exists and is not finalized.  Returns Assessment."""
    from models.assessment import Assessment

    assessment = session.query(Assessment).filter(Assessment.id == assessment_id).first()
    if assessment is None:
        raise AssignmentBlockedByFinalizationError("Assessment not found.")
    if assessment.finalization_status == "finalized":
        raise AssignmentBlockedByFinalizationError(
            "Cannot assign instructors to a finalized assessment."
        )
    return assessment


def _compute_submission_counts(
    session: Session, assessment_id: str, instructor_user_id: str | None = None
) -> dict[str, int]:
    """Compute submission status counts for an assessment.

    If instructor_user_id is provided, filters by claimed/assigned grader.
    Returns counts for: total, claimed, draft, completed, needs_correction, approved.
    """
    query = session.query(Submission).filter(Submission.assessment_id == assessment_id)

    if instructor_user_id:
        query = query.filter(Submission.assigned_grader_user_id == instructor_user_id)

    submissions = query.all()
    total = len(submissions)

    claimed = sum(1 for s in submissions if s.assigned_grader_user_id is not None)
    draft = sum(
        1
        for s in submissions
        if s.grading_status == "draft" or s.grading_status == "in_progress"
    )
    completed = sum(1 for s in submissions if s.grading_status == "graded")
    needs_correction = sum(1 for s in submissions if s.review_status == "needs_correction")
    approved = sum(1 for s in submissions if s.review_status == "approved")
    not_started = total - claimed

    return {
        "total": total,
        "claimed": claimed,
        "not_started": not_started,
        "draft": draft,
        "completed": completed,
        "needs_correction": needs_correction,
        "approved": approved,
    }


# ── Administrator-only operations ─────────────────────────────────


def create_assignment(
    session: Session,
    instructor_user_id: str,
    assessment_id: str,
    *,
    auth_ctx: AuthContext,
    notes: str | None = None,
) -> InstructorAssignment:
    """Create an active assignment for an instructor to grade an assessment.

    Parameters
    ----------
    session : Session
        Database session.
    instructor_user_id : str
        ID of the instructor (user with role='grader').
    assessment_id : str
        ID of the assessment to assign.
    auth_ctx : AuthContext
        Authorization context.  Must be administrator.
    notes : str | None
        Optional privacy-safe notes.

    Returns
    -------
    InstructorAssignment
        The created assignment.

    Raises
    ------
    InsufficientPermissionsError
        If the auth context is missing or not administrator.
    InstructorAssignmentError
        If the target user is not a valid active instructor.
    AssignmentBlockedByFinalizationError
        If the assessment is finalized.
    DuplicateAssignmentError
        If an active assignment already exists.
    """
    authorize_context(auth_ctx, PERM_MANAGE_ASSIGNMENTS)
    _require_admin(auth_ctx)

    _validate_instructor(session, instructor_user_id)
    _validate_assessment_not_finalized(session, assessment_id)

    # Check for duplicate active assignment
    existing = (
        session.query(InstructorAssignment)
        .filter(
            InstructorAssignment.instructor_user_id == instructor_user_id,
            InstructorAssignment.assessment_id == assessment_id,
            InstructorAssignment.is_active == True,  # noqa: E712
        )
        .first()
    )
    if existing is not None:
        raise DuplicateAssignmentError(
            "Instructor already has an active assignment to this assessment."
        )

    assignment = InstructorAssignment(
        instructor_user_id=instructor_user_id,
        assessment_id=assessment_id,
        assigned_by_user_id=auth_ctx.user_id,
        notes=notes,
        is_active=True,
        assigned_at=datetime.now(UTC),
    )
    session.add(assignment)
    session.flush()

    logger.info(
        "Assignment created: instructor=%s assessment=%s by=%s",
        instructor_user_id[:8], assessment_id[:8], auth_ctx.user_id[:8],
    )
    return assignment


def deactivate_assignment(
    session: Session,
    assignment_id: str,
    *,
    auth_ctx: AuthContext,
) -> InstructorAssignment:
    """Deactivate an assignment.

    Does not delete grades or history.  Active grading claims on the
    assessment are handled safely — the deactivated instructor retains
    access to any submissions they already claimed until those claims
    expire or are released.

    Parameters
    ----------
    session : Session
        Database session.
    assignment_id : str
        ID of the assignment to deactivate.
    auth_ctx : AuthContext
        Authorization context.  Must be administrator.

    Returns
    -------
    InstructorAssignment
        The deactivated assignment.

    Raises
    ------
    InsufficientPermissionsError
        If the auth context is missing or not administrator.
    AssignmentNotFoundError
        If the assignment is not found.
    """
    authorize_context(auth_ctx, PERM_MANAGE_ASSIGNMENTS)
    _require_admin(auth_ctx)

    assignment = (
        session.query(InstructorAssignment)
        .filter(InstructorAssignment.id == assignment_id)
        .first()
    )
    if assignment is None:
        raise AssignmentNotFoundError("Assignment not found.")

    assignment.deactivate()
    session.flush()

    logger.info(
        "Assignment deactivated: id=%s instructor=%s assessment=%s by=%s",
        assignment_id[:8], assignment.instructor_user_id[:8],
        assignment.assessment_id[:8], auth_ctx.user_id[:8],
    )
    return assignment


def reassign_assessment(
    session: Session,
    assessment_id: str,
    current_instructor_user_id: str,
    new_instructor_user_id: str,
    *,
    auth_ctx: AuthContext,
) -> InstructorAssignment:
    """Reassign an assessment from one instructor to another.

    Deactivates the current instructor's active assignment and creates
    a new active assignment for the new instructor.

    Parameters
    ----------
    session : Session
        Database session.
    assessment_id : str
        Assessment ID to reassign.
    current_instructor_user_id : str
        Current instructor's user ID.
    new_instructor_user_id : str
        New instructor's user ID.
    auth_ctx : AuthContext
        Authorization context.  Must be administrator.

    Returns
    -------
    InstructorAssignment
        The new assignment for the new instructor.

    Raises
    ------
    InsufficientPermissionsError
        If not administrator.
    AssignmentNotFoundError
        If no active assignment exists for the current instructor.
    """
    authorize_context(auth_ctx, PERM_MANAGE_ASSIGNMENTS)
    _require_admin(auth_ctx)

    _validate_instructor(session, new_instructor_user_id)
    _validate_assessment_not_finalized(session, assessment_id)

    # Deactivate current assignment
    current = (
        session.query(InstructorAssignment)
        .filter(
            InstructorAssignment.instructor_user_id == current_instructor_user_id,
            InstructorAssignment.assessment_id == assessment_id,
            InstructorAssignment.is_active == True,  # noqa: E712
        )
        .first()
    )
    if current is None:
        raise AssignmentNotFoundError(
            "No active assignment found for the current instructor."
        )

    current.deactivate()

    # Check for duplicate
    existing_new = (
        session.query(InstructorAssignment)
        .filter(
            InstructorAssignment.instructor_user_id == new_instructor_user_id,
            InstructorAssignment.assessment_id == assessment_id,
            InstructorAssignment.is_active == True,  # noqa: E712
        )
        .first()
    )
    if existing_new is not None:
        # New instructor already has an active assignment — just return it
        logger.info(
            "Reassign skipped: new instructor %s already assigned to %s",
            new_instructor_user_id[:8], assessment_id[:8],
        )
        return existing_new

    # Create new assignment
    new_assignment = InstructorAssignment(
        instructor_user_id=new_instructor_user_id,
        assessment_id=assessment_id,
        assigned_by_user_id=auth_ctx.user_id,
        is_active=True,
        assigned_at=datetime.now(UTC),
        notes=f"Reassigned from {current_instructor_user_id[:8]}",
    )
    session.add(new_assignment)
    session.flush()

    logger.info(
        "Assessment %s reassigned from %s to %s by %s",
        assessment_id[:8], current_instructor_user_id[:8],
        new_instructor_user_id[:8], auth_ctx.user_id[:8],
    )
    return new_assignment


def get_active_assignments(
    session: Session,
    *,
    auth_ctx: AuthContext,
    instructor_user_id: str | None = None,
    assessment_id: str | None = None,
) -> list[InstructorAssignment]:
    """List active assignments with optional filters.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.  Must have view_assignments permission.
    instructor_user_id : str | None
        Filter by instructor.
    assessment_id : str | None
        Filter by assessment.

    Returns
    -------
    list[InstructorAssignment]
        List of active assignments.
    """
    authorize_context(auth_ctx, PERM_VIEW_ASSIGNMENTS)

    query = session.query(InstructorAssignment).filter(
        InstructorAssignment.is_active == True,  # noqa: E712
    )
    if instructor_user_id:
        query = query.filter(
            InstructorAssignment.instructor_user_id == instructor_user_id
        )
    if assessment_id:
        query = query.filter(
            InstructorAssignment.assessment_id == assessment_id
        )
    return list(query.order_by(InstructorAssignment.assigned_at.desc()).all())


def get_assignment_history(
    session: Session,
    *,
    auth_ctx: AuthContext,
    instructor_user_id: str | None = None,
    assessment_id: str | None = None,
    include_active: bool = True,
) -> list[InstructorAssignment]:
    """List assignment history (active and inactive).

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.  Must have view_assignments permission.
    instructor_user_id : str | None
        Filter by instructor.
    assessment_id : str | None
        Filter by assessment.
    include_active : bool
        If True, include active assignments in results.

    Returns
    -------
    list[InstructorAssignment]
        List of all matching assignments.
    """
    authorize_context(auth_ctx, PERM_VIEW_ASSIGNMENTS)

    query = session.query(InstructorAssignment)
    if not include_active:
        query = query.filter(
            InstructorAssignment.is_active == False,  # noqa: E712
        )
    if instructor_user_id:
        query = query.filter(
            InstructorAssignment.instructor_user_id == instructor_user_id
        )
    if assessment_id:
        query = query.filter(
            InstructorAssignment.assessment_id == assessment_id
        )
    return list(query.order_by(InstructorAssignment.assigned_at.desc()).all())


def get_workload_summaries(
    session: Session,
    *,
    auth_ctx: AuthContext,
) -> list[InstructorWorkload]:
    """Get workload summaries for all instructors with active assignments.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.  Must be administrator.

    Returns
    -------
    list[InstructorWorkload]
        Privacy-safe workload summaries.
    """
    authorize_context(auth_ctx, PERM_VIEW_ASSIGNMENTS)
    _require_admin(auth_ctx)

    from models.user import User

    active_assignments = (
        session.query(InstructorAssignment)
        .filter(InstructorAssignment.is_active == True)  # noqa: E712
        .all()
    )

    # Group by instructor
    instructor_map: dict[str, list[InstructorAssignment]] = {}
    for assn in active_assignments:
        instructor_map.setdefault(assn.instructor_user_id, []).append(assn)

    workloads: list[InstructorWorkload] = []
    for instructor_id, assignments in instructor_map.items():
        user = session.query(User).filter(User.id == instructor_id).first()
        display_name = user.display_name if user else None

        total = 0
        claimed = 0
        draft = 0
        completed = 0
        needs_correction = 0

        for assn in assignments:
            counts = _compute_submission_counts(
                session, assn.assessment_id, instructor_id
            )
            total += counts["total"]
            claimed += counts["claimed"]
            draft += counts["draft"]
            completed += counts["completed"]
            needs_correction += counts["needs_correction"]

        pct = round(completed / max(total, 1) * 100, 1)

        workloads.append(
            InstructorWorkload(
                instructor_user_id=instructor_id,
                instructor_display_name=display_name,
                active_assignment_count=len(assignments),
                total_submissions=total,
                claimed_submissions=claimed,
                draft_submissions=draft,
                completed_submissions=completed,
                needs_correction_submissions=needs_correction,
                completion_percentage=pct,
            )
        )

    return sorted(workloads, key=lambda w: w.instructor_display_name or "")


# ── Instructor-facing operations ──────────────────────────────────


def get_own_assignments(
    session: Session,
    *,
    auth_ctx: AuthContext,
    active_only: bool = True,
) -> list[InstructorAssignment]:
    """Get assignments for the authenticated instructor.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.  Must be a valid authenticated user.
    active_only : bool
        If True, return only active assignments.

    Returns
    -------
    list[InstructorAssignment]
        List of assignments for this instructor.
    """
    user_id = _require_grader_or_admin(auth_ctx)

    query = session.query(InstructorAssignment).filter(
        InstructorAssignment.instructor_user_id == user_id,
    )
    if active_only:
        query = query.filter(InstructorAssignment.is_active == True)  # noqa: E712
    return list(query.order_by(InstructorAssignment.assigned_at.desc()).all())


def is_instructor_assigned(
    session: Session,
    instructor_user_id: str,
    assessment_id: str,
) -> bool:
    """Check whether an instructor is actively assigned to an assessment.

    Parameters
    ----------
    session : Session
        Database session.
    instructor_user_id : str
        Instructor's user ID.
    assessment_id : str
        Assessment ID.

    Returns
    -------
    bool
        True if the instructor has an active assignment.
    """
    count = (
        session.query(InstructorAssignment)
        .filter(
            InstructorAssignment.instructor_user_id == instructor_user_id,
            InstructorAssignment.assessment_id == assessment_id,
            InstructorAssignment.is_active == True,  # noqa: E712
        )
        .count()
    )
    return count > 0


def get_own_assigned_assessments(
    session: Session,
    *,
    auth_ctx: AuthContext,
    active_only: bool = True,
) -> list[Any]:
    """Get distinct assessments assigned to the authenticated instructor.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.
    active_only : bool
        If True, return only active assignments.

    Returns
    -------
    list[Assessment]
        List of assessment objects.
    """
    from models.assessment import Assessment

    user_id = _require_grader_or_admin(auth_ctx)

    query = (
        session.query(Assessment)
        .join(InstructorAssignment, InstructorAssignment.assessment_id == Assessment.id)
        .filter(InstructorAssignment.instructor_user_id == user_id)
    )
    if active_only:
        query = query.filter(InstructorAssignment.is_active == True)  # noqa: E712
    return list(query.order_by(Assessment.title).all())


def check_instructor_assignment_access(
    session: Session,
    assessment_id: str,
    *,
    auth_ctx: AuthContext,
) -> bool:
    """Check whether the authenticated instructor has access to an assessment.

    Administrators always have access.  Instructors must have an active
    assignment.

    Parameters
    ----------
    session : Session
        Database session.
    assessment_id : str
        Assessment ID to check.
    auth_ctx : AuthContext
        Authorization context.

    Returns
    -------
    bool
        True if the instructor (or admin) has access.
    """
    if auth_ctx.role == "administrator":
        return True
    if auth_ctx.role == "grader":
        return is_instructor_assigned(session, auth_ctx.user_id, assessment_id)
    return False


def require_assignment_access(
    session: Session,
    assessment_id: str,
    *,
    auth_ctx: AuthContext,
) -> None:
    """Require the authenticated instructor has access to an assessment.

    Uses a generic message to avoid leaking existence information.

    Raises
    ------
    InsufficientPermissionsError
        If the user does not have access.
    """
    if not check_instructor_assignment_access(session, assessment_id, auth_ctx=auth_ctx):
        raise InsufficientPermissionsError(
            "The requested grading work is unavailable."
        )


# ── Grading claim operations ──────────────────────────────────────


def claim_submission(
    session: Session,
    submission_id: str,
    *,
    auth_ctx: AuthContext,
) -> Submission:
    """Atomically claim a submission for grading.

    Parameters
    ----------
    session : Session
        Database session.
    submission_id : str
        Submission ID to claim.
    auth_ctx : AuthContext
        Authorization context.  Must be grader or administrator.

    Returns
    -------
    Submission
        The claimed submission.

    Raises
    ------
    GradingClaimConflictError
        If the submission is already claimed by another instructor.
    InsufficientPermissionsError
        If the user lacks grading permission.
    """
    user_id = _require_grader_or_admin(auth_ctx)

    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None:
        raise GradingClaimNotFoundError("Submission not found.")

    now = datetime.now(UTC)

    # Check current claim status
    if (
        submission.assigned_grader_user_id is not None
        and submission.assigned_grader_user_id != user_id
    ):
        # Check if claim has expired
        if (
            submission.grading_lock_expires_at is not None
            and submission.grading_lock_expires_at > now
        ):
            raise GradingClaimConflictError(
                "This submission is currently being graded by another instructor."
            )

    # Atomically claim: update only if not claimed by another active owner
    expires_at = now + timedelta(minutes=GRADING_CLAIM_DURATION_MINUTES)

    result = (
        session.query(Submission)
        .filter(
            Submission.id == submission_id,
            (
                (Submission.assigned_grader_user_id.is_(None))
                | (Submission.assigned_grader_user_id == user_id)
                | (
                    (Submission.grading_lock_expires_at < now)
                    & (Submission.grading_lock_expires_at.isnot(None))
                )
            ),
        )
        .update(
            {
                "assigned_grader_user_id": user_id,
                "grading_claimed_at": now,
                "grading_lock_expires_at": expires_at,
            },
            synchronize_session="fetch",
        )
    )

    if result == 0:
        # Race condition: someone else claimed it between our check and update
        raise GradingClaimConflictError(
            "This submission is currently being graded by another instructor."
        )

    session.flush()
    # Re-fetch to get updated state
    submission = (
        session.query(Submission).filter(Submission.id == submission_id).first()
    )
    if submission is None:
        raise GradingClaimNotFoundError("Submission not found after claim.")

    logger.info(
        "Submission %s claimed by %s, expires at %s",
        submission_id[:8], user_id[:8], expires_at.isoformat(),
    )
    return submission


def renew_claim(
    session: Session,
    submission_id: str,
    *,
    auth_ctx: AuthContext,
) -> Submission:
    """Renew a grading claim (extend the expiration).

    Parameters
    ----------
    session : Session
        Database session.
    submission_id : str
        Submission ID to renew.
    auth_ctx : AuthContext
        Authorization context.

    Returns
    -------
    Submission
        The submission with renewed claim.

    Raises
    ------
    GradingClaimNotFoundError
        If the submission is not claimed by this instructor.
    """
    user_id = _require_grader_or_admin(auth_ctx)

    submission = (
        session.query(Submission)
        .filter(
            Submission.id == submission_id,
            Submission.assigned_grader_user_id == user_id,
        )
        .first()
    )
    if submission is None:
        raise GradingClaimNotFoundError(
            "No active claim found for this submission."
        )

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=GRADING_CLAIM_DURATION_MINUTES)
    submission.grading_lock_expires_at = expires_at
    submission.grading_claimed_at = now
    session.flush()

    logger.info(
        "Claim renewed for submission %s by %s",
        submission_id[:8], user_id[:8],
    )
    return submission


def release_claim(
    session: Session,
    submission_id: str,
    *,
    auth_ctx: AuthContext,
) -> Submission:
    """Release a grading claim.

    Administrator may release any claim.  The owning instructor may
    also release their own claim.

    Parameters
    ----------
    session : Session
        Database session.
    submission_id : str
        Submission ID.
    auth_ctx : AuthContext
        Authorization context.

    Returns
    -------
    Submission
        The submission with claim released.
    """
    user_id = _require_grader_or_admin(auth_ctx)

    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None:
        raise GradingClaimNotFoundError("Submission not found.")

    # Allow admin or owner to release
    if auth_ctx.role != "administrator" and submission.assigned_grader_user_id != user_id:
        raise InsufficientPermissionsError(
            "You do not have permission to release this claim."
        )

    submission.assigned_grader_user_id = None
    submission.grading_claimed_at = None
    submission.grading_lock_expires_at = None
    session.flush()

    logger.info(
        "Claim released for submission %s by %s",
        submission_id[:8], user_id[:8],
    )
    return submission


def release_all_claims_for_assignment(
    session: Session,
    assignment_id: str,
    *,
    auth_ctx: AuthContext,
) -> int:
    """Release all active grading claims for an assignment's assessment.

    Used when deactivating an assignment with active claims.

    Parameters
    ----------
    session : Session
        Database session.
    assignment_id : str
        Assignment ID.
    auth_ctx : AuthContext
        Authorization context.  Must be administrator.

    Returns
    -------
    int
        Number of claims released.
    """
    authorize_context(auth_ctx, PERM_MANAGE_ASSIGNMENTS)
    _require_admin(auth_ctx)

    assignment = (
        session.query(InstructorAssignment)
        .filter(InstructorAssignment.id == assignment_id)
        .first()
    )
    if assignment is None:
        raise AssignmentNotFoundError("Assignment not found.")

    result = (
        session.query(Submission)
        .filter(
            Submission.assessment_id == assignment.assessment_id,
            Submission.assigned_grader_user_id == assignment.instructor_user_id,
            Submission.grading_lock_expires_at.isnot(None),
        )
        .update(
            {
                "assigned_grader_user_id": None,
                "grading_claimed_at": None,
                "grading_lock_expires_at": None,
            },
            synchronize_session="fetch",
        )
    )
    session.flush()

    logger.info(
        "Released %d claims for assignment %s by %s",
        result, assignment_id[:8], auth_ctx.user_id[:8],
    )
    return result


def is_submission_claimed_by(
    session: Session,
    submission_id: str,
    user_id: str,
) -> bool:
    """Check whether a submission is claimed by a specific user.

    Returns True if the user owns the claim or if the claim has expired.
    """
    submission = (
        session.query(Submission)
        .filter(Submission.id == submission_id)
        .first()
    )
    if submission is None:
        return False
    if submission.assigned_grader_user_id is None:
        return False
    if submission.assigned_grader_user_id == user_id:
        return True
    # Check expiry
    now = datetime.now(UTC)
    if (
        submission.grading_lock_expires_at is not None
        and submission.grading_lock_expires_at <= now
    ):
        # Claim has expired — treat as not claimed
        return False
    return False


def get_assignment_summaries(
    session: Session,
    *,
    auth_ctx: AuthContext,
    active_only: bool = True,
    instructor_user_id: str | None = None,
    assessment_id: str | None = None,
) -> list[AssignmentSummary]:
    """Get assignments with progress counts.

    Parameters
    ----------
    session : Session
        Database session.
    auth_ctx : AuthContext
        Authorization context.
    active_only : bool
        If True, return only active assignments.
    instructor_user_id : str | None
        Filter by instructor.
    assessment_id : str | None
        Filter by assessment.

    Returns
    -------
    list[AssignmentSummary]
        List of assignment summaries.
    """
    authorize_context(auth_ctx, PERM_VIEW_ASSIGNMENTS)
    _require_admin(auth_ctx)

    from models.assessment import Assessment
    from models.material import Material

    query = (
        session.query(InstructorAssignment)
        .join(Assessment, InstructorAssignment.assessment_id == Assessment.id)
        .outerjoin(Material, Assessment.material_id == Material.id)
    )
    if active_only:
        query = query.filter(InstructorAssignment.is_active == True)  # noqa: E712
    if instructor_user_id:
        query = query.filter(
            InstructorAssignment.instructor_user_id == instructor_user_id
        )
    if assessment_id:
        query = query.filter(
            InstructorAssignment.assessment_id == assessment_id
        )

    assignments = query.all()

    summaries: list[AssignmentSummary] = []
    for assn in assignments:
        counts = _compute_submission_counts(session, assn.assessment_id)
        pct = round(counts["completed"] / max(counts["total"], 1) * 100, 1)

        summaries.append(
            AssignmentSummary(
                assignment_id=assn.id,
                instructor_user_id=assn.instructor_user_id,
                instructor_display_name=(
                    assn.instructor.display_name if assn.instructor else None
                ),
                assessment_id=assn.assessment_id,
                assessment_title=assn.assessment.title,
                material_title=(
                    assn.assessment.material.name if assn.assessment.material else None
                ),
                is_active=assn.is_active,
                assigned_at=assn.assigned_at,
                unassigned_at=assn.unassigned_at,
                total_submissions=counts["total"],
                not_started=counts["not_started"],
                draft=counts["draft"],
                completed=counts["completed"],
                needs_correction=counts["needs_correction"],
                approved=counts["approved"],
                completion_percentage=pct,
            )
        )

    return summaries
