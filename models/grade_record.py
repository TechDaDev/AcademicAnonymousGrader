# Academic Anonymous Grader — GradeRecord Model
"""Grade record model — score and feedback for a single response.

SECURITY: feedback must never be logged.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.response import Response


class GradeRecord(TimestampMixin, Base):
    """Stores the score and feedback assigned to a single response."""

    __tablename__ = "grade_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    response_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("responses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2, asdecimal=True), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045

    # Relationships
    response: Mapped[Response] = relationship("Response", back_populates="grade_record")

    def __repr__(self) -> str:
        return (
            f"<GradeRecord id={self.id} response_id={self.response_id} "
            f"status='{self.status}'>"
        )
