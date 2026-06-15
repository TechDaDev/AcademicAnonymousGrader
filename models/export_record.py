# Academic Anonymous Grader — ExportRecord Model
"""Export record model — tracks each authorised export of results.

SECURITY: Never store decrypted identity data, workbook bytes, or
export file paths that contain identity information.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.assessment import Assessment


class ExportRecord(TimestampMixin, Base):
    """Records each authorised export of identifiable results."""

    __tablename__ = "export_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    export_format: Mapped[str] = mapped_column(String(10), nullable=False, default="xlsx")
    export_reference: Mapped[str] = mapped_column(
        String(20), nullable=False, default=lambda: f"EXP-{uuid.uuid4().hex[:8].upper()}"
    )
    workbook_schema_version: Mapped[str] = mapped_column(String(10), nullable=False, default="1.0")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045

    # Relationships
    assessment: Mapped[Assessment] = relationship("Assessment", back_populates="export_records")

    def __repr__(self) -> str:
        return f"<ExportRecord id={self.id[:8]} ref={self.export_reference}>"
