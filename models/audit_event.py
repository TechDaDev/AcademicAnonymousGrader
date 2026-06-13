# Academic Anonymous Grader — AuditEvent Model
"""Audit event model for tracking significant actions.

SECURITY: Never store names, emails, student responses, feedback,
passwords, or secrets in audit events.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class AuditEvent(Base):
    """Logs significant actions for traceability and accountability.

    SAFETY: This table must never contain:
    - Student names, emails, or institutional IDs
    - Student response content
    - Grading feedback
    - Passwords or secrets
    - Encryption keys
    """

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id} type='{self.event_type}'>"
