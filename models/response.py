# Academic Anonymous Grader — Response Model
"""Response model — a student's answer to a single question.

SECURITY: response_text must never be executed. Never log response_text.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.grade_record import GradeRecord
    from models.question import Question
    from models.submission import Submission


class Response(TimestampMixin, Base):
    """Stores a student's answer to a single question.

    SAFETY: response_text must never be passed to eval(), exec(), or
    any code execution function. It must never be logged.
    """

    __tablename__ = "responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), nullable=False
    )
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_blank: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    submission: Mapped[Submission] = relationship("Submission", back_populates="responses")
    question: Mapped[Question] = relationship("Question", back_populates="responses")
    grade_record: Mapped[GradeRecord | None] = relationship(
        "GradeRecord", back_populates="response", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("submission_id", "question_id", name="uq_response_per_submission_question"),
    )

    def __repr__(self) -> str:
        # SAFETY: Never expose response_text
        return f"<Response id={self.id} submission_id={self.submission_id} question_id={self.question_id}>"
