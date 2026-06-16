# Academic Anonymous Grader — Dashboard Service
"""Dashboard statistics service."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.material import Material
from models.submission import Submission


@dataclass(frozen=True)
class DashboardStats:
    """Immutable dashboard statistics snapshot."""

    material_count: int = 0
    assessment_count: int = 0
    student_count: int = 0
    submission_count: int = 0
    active_materials: int = 0
    archived_materials: int = 0
    draft_assessments: int = 0
    ready_assessments: int = 0
    archived_assessments: int = 0


def get_dashboard_stats(session: Session) -> DashboardStats:
    """Query database for dashboard summary counts.

    Parameters
    ----------
    session : Session
        Active database session.

    Returns
    -------
    DashboardStats
        Snapshot of current counts.
    """
    try:
        material_count = session.query(func.count(Material.id)).scalar() or 0
        assessment_count = session.query(func.count(Assessment.id)).scalar() or 0
        student_count = session.query(func.count(AnonymousStudent.id)).scalar() or 0
        submission_count = session.query(func.count(Submission.id)).scalar() or 0
        active_materials = session.query(func.count(Material.id)).filter(
            Material.is_archived == False  # noqa: E712
        ).scalar() or 0
        archived_materials = session.query(func.count(Material.id)).filter(
            Material.is_archived == True  # noqa: E712
        ).scalar() or 0
        draft_assessments = session.query(func.count(Assessment.id)).filter(
            Assessment.status == "draft"
        ).scalar() or 0
        ready_assessments = session.query(func.count(Assessment.id)).filter(
            Assessment.status == "ready"
        ).scalar() or 0
        archived_assessments = session.query(func.count(Assessment.id)).filter(
            Assessment.status == "archived"
        ).scalar() or 0
    except Exception:
        return DashboardStats()

    return DashboardStats(
        material_count=material_count,
        assessment_count=assessment_count,
        student_count=student_count,
        submission_count=submission_count,
        active_materials=active_materials,
        archived_materials=archived_materials,
        draft_assessments=draft_assessments,
        ready_assessments=ready_assessments,
        archived_assessments=archived_assessments,
    )
