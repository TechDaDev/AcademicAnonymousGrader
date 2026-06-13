# Academic Anonymous Grader — StudentIdentity Model
"""Student identity model — contains personally identifiable information.

SECURITY: All PII fields (first_name, last_name, email, institutional_student_id)
MUST be encrypted at rest in Phase 4. Do not log or expose these values.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.anonymous_student import AnonymousStudent


class StudentIdentity(TimestampMixin, Base):
    """Stores real student identifying information.

    This table contains PII. In Phase 4, first_name, last_name, email,
    and institutional_student_id must be encrypted at rest.

    Identity data is stored separately from grading data. Queries for
    grading must never join with this table.
    """

    __tablename__ = "student_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institutional_student_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # identity_fingerprint will use HMAC-SHA256 (Phase 4)
    identity_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Relationships
    anonymous_student: Mapped[AnonymousStudent] = relationship(
        "AnonymousStudent", back_populates="student_identity", uselist=False, cascade="all, delete-orphan"
    )
    # Submissions are accessed through anonymous_student.submissions
    # The ERD shows StudentIdentity 1:N Submission, but the physical path
    # goes through AnonymousStudent to avoid exposing PII in grading queries.

    def __repr__(self) -> str:
        # SAFETY: Never expose PII in __repr__
        return f"<StudentIdentity id={self.id}>"
