# Academic Anonymous Grader — ImportBatch Model
"""Import batch model — records metadata about a file import operation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.assessment import Assessment
    from models.submission import Submission


class ImportBatch(TimestampMixin, Base):
    """Records metadata about a file import operation.

    Every import creates an ImportBatch record. Reimports are tracked,
    and deduplication logic prevents silent duplication.
    """

    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_format: Mapped[str] = mapped_column(String(10), nullable=False, default="html")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    imported_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045

    # Relationships
    assessment: Mapped[Assessment] = relationship("Assessment", back_populates="import_batches")
    submissions: Mapped[list[Submission]] = relationship(
        "Submission", back_populates="import_batch", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<ImportBatch id={self.id} assessment_id={self.assessment_id} "
            f"file='{self.source_filename}' status='{self.status}'>"
        )
