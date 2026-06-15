# Academic Anonymous Grader — StudentIdentity Model
"""Student identity model — contains personally identifiable information.

SECURITY: All PII fields (first_name, last_name, email, institutional_student_id)
MUST be encrypted at rest in Phase 4. Do not log or expose these values.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.anonymous_student import AnonymousStudent


class StudentIdentity(TimestampMixin, Base):
    """Stores encrypted student identity information.

    Identity fields are AES-256-GCM encrypted at rest.
    Matching is done via HMAC-SHA256 fingerprints.
    """

    __tablename__ = "student_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Encrypted identity fields
    encrypted_first_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    encrypted_last_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    encrypted_email: Mapped[str | None] = mapped_column(String(512), nullable=True)
    encrypted_institutional_student_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    encryption_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Fingerprint fields for identity matching
    email_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    institutional_id_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Relationships
    anonymous_student: Mapped[AnonymousStudent] = relationship(
        "AnonymousStudent", back_populates="student_identity", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_student_identities_email_fingerprint", "email_fingerprint"),
        Index("ix_student_identities_institutional_id_fingerprint", "institutional_id_fingerprint"),
    )

    def __repr__(self) -> str:
        return f"<StudentIdentity id={self.id}>"
