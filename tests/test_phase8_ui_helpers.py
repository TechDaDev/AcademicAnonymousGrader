# Academic Anonymous Grader — Phase 8 UI Helpers Tests
"""Tests for session UI helper functions."""

from __future__ import annotations

from typing import Any

from services.authorization_service import get_session_user_role


class TestGetSessionUserRole:
    """Test get_session_user_role helper."""

    def test_authenticated_returns_role(self) -> None:
        """An authenticated session returns the stored role."""
        class FakeState:
            def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
                state = {
                    "authenticated": True,
                    "role": "grader",
                }
                return state.get(key, default)

        role = get_session_user_role(FakeState())
        assert role == "grader"

    def test_unauthenticated_returns_anonymous(self) -> None:
        """An unauthenticated session returns 'anonymous'."""
        class FakeState:
            def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
                state = {
                    "authenticated": False,
                }
                return state.get(key, default)

        role = get_session_user_role(FakeState())
        assert role == "anonymous"

    def test_no_auth_key_returns_anonymous(self) -> None:
        """Session without authenticated key returns 'anonymous'."""
        class FakeState:
            def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
                return default

        role = get_session_user_role(FakeState())
        assert role == "anonymous"


class TestUserModelProperties:
    """Test User model convenience properties."""

    def test_is_administrator_true(self) -> None:
        """is_administrator returns True for admin role."""
        user = _make_user(role="administrator")
        assert user.is_administrator is True

    def test_is_administrator_false(self) -> None:
        """is_administrator returns False for non-admin roles."""
        for role in ["grader", "reviewer", "exporter", "viewer"]:
            user = _make_user(role=role)
            assert user.is_administrator is False

    def test_is_locked_true(self) -> None:
        """is_locked returns True when locked_until is in the future."""
        from datetime import UTC, datetime, timedelta

        user = _make_user()
        user.locked_until = datetime.now(UTC) + timedelta(minutes=10)
        assert user.is_locked is True

    def test_is_locked_false_when_none(self) -> None:
        """is_locked returns False when locked_until is None."""
        user = _make_user()
        user.locked_until = None
        assert user.is_locked is False

    def test_is_locked_false_when_expired(self) -> None:
        """is_locked returns False when lockout has expired."""
        from datetime import UTC, datetime, timedelta

        user = _make_user()
        user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        assert user.is_locked is False

    def test_lockout_remaining_minutes(self) -> None:
        """lockout_remaining_minutes returns positive value when locked."""
        from datetime import UTC, datetime, timedelta

        user = _make_user()
        user.locked_until = datetime.now(UTC) + timedelta(minutes=5)
        remaining = user.lockout_remaining_minutes
        assert remaining > 0
        assert remaining <= 6  # 5 min + 1 rounding


def _make_user(role: str = "viewer") -> Any:
    """Create a User instance without a session."""
    from models.user import User

    return User(
        username="test_user",
        password_hash="$2b$12$" + "a" * 53,
        role=role,
    )
