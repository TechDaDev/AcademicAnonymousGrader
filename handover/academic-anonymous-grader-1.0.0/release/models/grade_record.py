# Academic Anonymous Grader — GradeRecord Model
"""Grade record model — score and feedback for a single question in a submission.

SECURITY: feedback must never be logged.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.question import Question
    from models.submission import Submission


class GradeRecord(TimestampMixin, Base):
    """Stores the grade and feedback assigned to a single question in a submission."""

    __tablename__ = "grade_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), nullable=False
    )
    grade: Mapped[Decimal | None] = mapped_column(Numeric(8, 2, asdecimal=True), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    grading_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ungraded")
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045

    # Relationships
    submission: Mapped[Submission] = relationship("Submission", back_populates="grade_records")
    question: Mapped[Question] = relationship("Question")

    __table_args__ = (
        UniqueConstraint(
            "submission_id", "question_id",
            name="uq_grade_per_submission_question",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<GradeRecord id={self.id} submission_id={self.submission_id} "
            f"grading_status='{self.grading_status}'>"
        )
