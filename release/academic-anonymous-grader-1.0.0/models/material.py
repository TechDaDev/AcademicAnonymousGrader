# Academic Anonymous Grader — Material Model
"""Material (academic course/subject) model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from models.academic_stage import AcademicStage
    from models.academic_term import AcademicTerm
    from models.academic_year import AcademicYear
    from models.assessment import Assessment
    from models.department import Department


class Material(TimestampMixin, Base):
    """Represents an academic course or subject."""

    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    academic_year: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Phase 12.1 — Controlled classification foreign keys
    department_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    academic_stage_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_stages.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    academic_term_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    academic_year_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_years.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    classification_needs_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    __table_args__ = (
        Index("ix_material_name_year", "name", "academic_year"),
    )

    # Relationships
    assessments: Mapped[list[Assessment]] = relationship(
        "Assessment", back_populates="material", cascade="all, delete-orphan"
    )
    ref_department: Mapped[Department | None] = relationship("Department", foreign_keys=[department_id])
    ref_stage: Mapped[AcademicStage | None] = relationship("AcademicStage", foreign_keys=[academic_stage_id])
    ref_term: Mapped[AcademicTerm | None] = relationship("AcademicTerm", foreign_keys=[academic_term_id])
    ref_academic_year: Mapped[AcademicYear | None] = relationship("AcademicYear", foreign_keys=[academic_year_id])

    def __repr__(self) -> str:
        return f"<Material id={self.id} name='{self.name}'>"
