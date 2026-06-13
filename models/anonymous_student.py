# Academic Anonymous Grader — AnonymousStudent Model
"""Anonymous student mapping model — links real identities to grading IDs."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.student_identity import StudentIdentity
    from models.submission import Submission


class AnonymousStudent(TimestampMixin, Base):
    """Stores the mapping between a student's real identity and their anonymous grading ID.

    Anonymous IDs will be generated in Phase 4 using cryptographically
    secure randomness. In Phase 1, only the model structure is defined.
    """

    __tablename__ = "anonymous_students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_identity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_identities.id", ondelete="CASCADE"), nullable=False
    )
    # anonymous_id will be generated in Phase 4 (format: STU-XXXXXXXX)
    anonymous_id: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    student_identity: Mapped[StudentIdentity] = relationship(
        "StudentIdentity", back_populates="anonymous_student"
    )
    submissions: Mapped[list[Submission]] = relationship(
        "Submission", back_populates="anonymous_student"
    )

    __table_args__ = (
        UniqueConstraint("anonymous_id", name="uq_anonymous_id"),
        UniqueConstraint("student_identity_id", name="uq_student_identity_per_anonymous"),
    )

    def __repr__(self) -> str:
        return f"<AnonymousStudent id={self.id} anonymous_id='{self.anonymous_id}'>"
