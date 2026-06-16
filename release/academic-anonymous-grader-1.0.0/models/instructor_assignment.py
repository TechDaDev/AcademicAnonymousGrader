# Academic Anonymous Grader — Instructor Assignment Model
"""Tracks which instructors are assigned to grade specific assessments.

An Instructor may grade only anonymous submissions belonging to assessments
explicitly assigned to that Instructor via this model.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin


class InstructorAssignment(Base, TimestampMixin):
    """Assignment of an instructor (grader) to an assessment.

    One assessment may have multiple instructors.
    One instructor may be assigned to multiple assessments.

    Active-only uniqueness:
        Only one active assignment may exist per (instructor_user_id, assessment_id)
        pair.  Inactive (historical) rows are unlimited.  This is enforced at the
        database level via a SQLite partial unique index equivalent to:
            CREATE UNIQUE INDEX ... ON instructor_assignments
                (instructor_user_id, assessment_id) WHERE is_active = 1

    Foreign-key deletion behaviour (all documented):
        - instructor_user_id → users.id ON DELETE CASCADE:
            Deleting a user cascades to their assignments (historical included).
            This is intentional: orphaned assignments have no meaning.
        - assessment_id → assessments.id ON DELETE CASCADE:
            Deleting an assessment cascades to all its assignments.
            This is safe because assessment deletion is already destructive
            (submissions, grades, responses are all cascade-deleted).
        - assigned_by_user_id → users.id ON DELETE SET NULL:
            If the administrator who created the assignment is deleted, the
            reference is set to NULL rather than destroying the assignment record.
            The assigned_by display may show "Deleted user" in the UI.
    """

    __tablename__ = "instructor_assignments"

    __table_args__ = (
        # Partial unique index: only one active assignment per (instructor, assessment)
        Index(
            "uq_active_instructor_assignment",
            "instructor_user_id",
            "assessment_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    instructor_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    unassigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships (for type hints and queries)
    instructor = relationship(
        "User",
        foreign_keys=[instructor_user_id],
        lazy="joined",
        innerjoin=True,
    )
    assigner = relationship(
        "User",
        foreign_keys=[assigned_by_user_id],
        lazy="joined",
    )
    assessment = relationship("Assessment", lazy="joined", innerjoin=True)

    def deactivate(self) -> None:
        """Mark this assignment as inactive."""
        self.is_active = False
        self.unassigned_at = datetime.now(UTC)
