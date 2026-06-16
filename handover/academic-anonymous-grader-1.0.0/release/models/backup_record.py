# Academic Anonymous Grader — BackupRecord Model
"""Backup record model for tracking database backup operations.

SECURITY: Never store backup bytes, full filesystem paths, encryption
keys, or decrypted identity data in this model.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin


class BackupRecord(Base, TimestampMixin):
    """Tracks each database backup created through the application.

    Backup archives are stored on the filesystem; this table records
    metadata such as the reference, hash, size, and schema version.
    """

    __tablename__ = "backup_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    backup_reference: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    database_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    restore_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<BackupRecord ref={self.backup_reference} status='{self.status}'>"
