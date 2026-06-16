# Academic Anonymous Grader — Academic Term Model
"""Controlled reference model for academic terms.

Initial terms (seeded):
    - Term 1, Term 2
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin


class AcademicTerm(TimestampMixin, Base):
    """Academic term reference."""

    __tablename__ = "academic_terms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    term_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    archived_at: Mapped[str | None] = mapped_column(String(30), nullable=True)

    def __repr__(self) -> str:
        return f"<AcademicTerm code='{self.code}' name='{self.display_name}'>"
