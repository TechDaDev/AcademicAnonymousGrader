# Academic Anonymous Grader — Question Model
"""Question model representing a single question within an assessment."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.assessment import Assessment
    from models.response import Response


class Question(TimestampMixin, Base):
    """Represents a single question within an assessment."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    maximum_grade: Mapped[Decimal] = mapped_column(Numeric(8, 2, asdecimal=True), nullable=False)
    rubric: Mapped[str | None] = mapped_column(String(10000), nullable=True)

    __table_args__ = (
        UniqueConstraint("assessment_id", "question_number", name="uq_question_number_per_assessment"),
        CheckConstraint("question_number > 0", name="ck_question_number_positive"),
        CheckConstraint("maximum_grade > 0", name="ck_question_max_grade_positive"),
    )

    # Relationships
    assessment: Mapped[Assessment] = relationship("Assessment", back_populates="questions")
    responses: Mapped[list[Response]] = relationship(
        "Response", back_populates="question", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} assessment_id={self.assessment_id} number={self.question_number}>"
