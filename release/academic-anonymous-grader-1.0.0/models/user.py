# Academic Anonymous Grader — User Model
"""Local user model for authentication and authorization.

SECURITY: Never store passwords, decrypted identity data, or encryption
keys in this model. Passwords are stored as bcrypt hashes only.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin

# Maximum number of failed login attempts before account lockout
MAX_FAILED_ATTEMPTS: int = 5
# Duration (minutes) an account remains locked after exceeding failed attempts
LOCKOUT_DURATION_MINUTES: int = 15


class User(Base, TimestampMixin):
    """Local authenticated user.

    Roles:
        - administrator
        - grader
        - reviewer
        - exporter
        - viewer
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_locked(self) -> bool:
        """Check whether the account is currently locked."""
        if self.locked_until is None:
            return False
        lockout = self.locked_until
        if lockout.tzinfo is None:
            lockout = lockout.replace(tzinfo=UTC)
        return datetime.now(UTC) < lockout

    @property
    def is_administrator(self) -> bool:
        return self.role == "administrator"

    @property
    def lockout_remaining_minutes(self) -> int:
        """Return remaining lockout minutes (rounded up)."""
        if self.locked_until is None:
            return 0
        until = self.locked_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        remaining = (until - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return 0
        return int(remaining // 60) + 1

    def increment_failed_attempts(self) -> None:
        """Increment failed login counter; lock account if threshold exceeded."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            self.locked_until = datetime.now(UTC) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)

    def reset_failed_attempts(self) -> None:
        """Reset failed login counter and unlock account."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def record_login(self) -> None:
        """Update last_login_at and reset failed attempts."""
        self.last_login_at = datetime.now(UTC)
        self.reset_failed_attempts()

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' role='{self.role}'>"
