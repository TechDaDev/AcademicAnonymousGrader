# Academic Anonymous Grader — Phase 8 Database Constraint Tests
"""Tests for database constraints on User and BackupRecord models."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from models.backup_record import BackupRecord
from models.user import User


class TestUserConstraints:
    """Test database-level constraints on the User model."""

    def test_username_unique(self, session: Any) -> None:
        """Username must be unique at the database level."""
        user1 = User(username="unique_test", password_hash="hash1", role="grader")
        session.add(user1)
        session.flush()

        user2 = User(username="unique_test", password_hash="hash2", role="viewer")
        session.add(user2)
        with pytest.raises(IntegrityError):
            session.flush()

    def test_username_not_null(self, session: Any) -> None:
        """Username must not be null."""
        user = User(password_hash="hash1", role="grader")
        session.add(user)
        with pytest.raises(IntegrityError):
            session.flush()

    def test_password_hash_not_null(self, session: Any) -> None:
        """Password hash must not be null."""
        user = User(username="no_hash_user", role="grader")
        session.add(user)
        with pytest.raises(IntegrityError):
            session.flush()

    def test_role_default_is_viewer(self, session: Any) -> None:
        """Default role should be 'viewer'."""
        user = User(username="default_role_user", password_hash="hash1")
        session.add(user)
        session.flush()
        assert user.role == "viewer"

    def test_is_active_default_true(self, session: Any) -> None:
        """Default is_active should be True."""
        user = User(username="active_default", password_hash="hash1", role="grader")
        session.add(user)
        session.flush()
        assert user.is_active is True

    def test_failed_attempts_default_zero(self, session: Any) -> None:
        """Default failed_login_attempts should be 0."""
        user = User(username="attempts_default", password_hash="hash1", role="grader")
        session.add(user)
        session.flush()
        assert user.failed_login_attempts == 0


class TestBackupRecordConstraints:
    """Test database-level constraints on the BackupRecord model."""

    def test_backup_reference_unique(self, session: Any) -> None:
        """Backup reference must be unique."""
        r1 = BackupRecord(backup_reference="BAK-UNIQUE", file_hash="a" * 64, file_size=100, database_hash="b" * 64, schema_version="1.0")
        session.add(r1)
        session.flush()

        r2 = BackupRecord(backup_reference="BAK-UNIQUE", file_hash="c" * 64, file_size=200, database_hash="d" * 64, schema_version="1.0")
        session.add(r2)
        with pytest.raises(IntegrityError):
            session.flush()

    def test_backup_reference_not_null(self, session: Any) -> None:
        """Backup reference must not be null."""
        r = BackupRecord(file_hash="a" * 64, file_size=100, database_hash="b" * 64, schema_version="1.0")
        session.add(r)
        with pytest.raises(IntegrityError):
            session.flush()

    def test_file_hash_not_null(self, session: Any) -> None:
        """File hash must not be null."""
        r = BackupRecord(backup_reference="BAK-NOHASH", file_size=100, database_hash="b" * 64, schema_version="1.0")
        session.add(r)
        with pytest.raises(IntegrityError):
            session.flush()
