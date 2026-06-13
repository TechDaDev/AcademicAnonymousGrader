# Academic Anonymous Grader — Assessment Model
"""Assessment (graded component within a material) model."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.export_record import ExportRecord
    from models.import_batch import ImportBatch
    from models.material import Material
    from models.question import Question
    from models.submission import Submission


class Assessment(TimestampMixin, Base):
    """Represents a graded component within a material."""

    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    assessment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    maximum_grade: Mapped[Decimal] = mapped_column(Numeric(8, 2, asdecimal=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: UP045

    # Relationships
    material: Mapped[Material] = relationship("Material", back_populates="assessments")
    questions: Mapped[list[Question]] = relationship(
        "Question", back_populates="assessment", cascade="all, delete-orphan"
    )
    import_batches: Mapped[list[ImportBatch]] = relationship(
        "ImportBatch", back_populates="assessment", cascade="all, delete-orphan"
    )
    submissions: Mapped[list[Submission]] = relationship(
        "Submission", back_populates="assessment", cascade="all, delete-orphan"
    )
    export_records: Mapped[list[ExportRecord]] = relationship(
        "ExportRecord", back_populates="assessment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Assessment id={self.id} title='{self.title}' status='{self.status}'>"
