# Academic Anonymous Grader — Submission Model
"""Submission model — a single student's submitted work for one assessment."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.anonymous_student import AnonymousStudent
    from models.assessment import Assessment
    from models.grade_record import GradeRecord
    from models.import_batch import ImportBatch
    from models.response import Response


class Submission(TimestampMixin, Base):
    """Represents a single student's submitted work for one assessment."""

    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    anonymous_student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("anonymous_students.id"), nullable=False
    )
    import_batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_batches.id"), nullable=False
    )
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_duration_text: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_grade: Mapped[Decimal | None] = mapped_column(Numeric(8, 2, asdecimal=True), nullable=True)
    source_grade_maximum: Mapped[Decimal | None] = mapped_column(Numeric(8, 2, asdecimal=True), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045
    grading_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_ready")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    assessment: Mapped[Assessment] = relationship("Assessment", back_populates="submissions")
    anonymous_student: Mapped[AnonymousStudent] = relationship(
        "AnonymousStudent", back_populates="submissions"
    )
    import_batch: Mapped[ImportBatch] = relationship("ImportBatch", back_populates="submissions")
    responses: Mapped[list[Response]] = relationship(
        "Response", back_populates="submission", cascade="all, delete-orphan"
    )
    grade_records: Mapped[list[GradeRecord]] = relationship(
        "GradeRecord", back_populates="submission", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "assessment_id", "anonymous_student_id", "import_batch_id",
            name="uq_submission_per_assessment_student_batch",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Submission id={self.id} assessment_id={self.assessment_id} "
            f"status='{self.grading_status}'>"
        )
