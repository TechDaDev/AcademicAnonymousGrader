# Academic Anonymous Grader — Session Security Tests
"""Tests for session management — login/logout, timeout, state safety."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from ui.session import (
    SESSION_ACTIVITY_KEY,
    SESSION_AUTH_KEY,
    SESSION_DISPLAY_NAME_KEY,
    SESSION_LOGIN_TIME_KEY,
    SESSION_ROLE_KEY,
    SESSION_USER_ID_KEY,
    SESSION_USERNAME_KEY,
    check_session_timeout,
    get_current_role,
    get_current_user_id,
    get_current_username,
    init_session_state,
    is_authenticated,
    login_user,
    logout_user,
    update_activity,
)


class TestSessionState:
    """Test session state management functions."""

    def test_init_session_state_sets_defaults(self) -> None:
        """init_session_state sets default values."""
        # We can't easily test with st.session_state in unit tests,
        # but we can test the logic by simulating a namespace
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            assert state[SESSION_AUTH_KEY] is False
            assert state[SESSION_USER_ID_KEY] is None

    def test_login_sets_state(self) -> None:
        """login_user sets all expected state fields."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-1", "testuser", "grader", "Test User")
            assert state[SESSION_AUTH_KEY] is True
            assert state[SESSION_USER_ID_KEY] == "user-1"
            assert state[SESSION_USERNAME_KEY] == "testuser"
            assert state[SESSION_ROLE_KEY] == "grader"
            assert state[SESSION_DISPLAY_NAME_KEY] == "Test User"
            assert state[SESSION_LOGIN_TIME_KEY] is not None
            assert state[SESSION_ACTIVITY_KEY] is not None

    def test_login_without_display_name(self) -> None:
        """login_user works without display_name."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-2", "nondisplay", "viewer")
            assert state[SESSION_DISPLAY_NAME_KEY] is None

    def test_logout_clears_state(self) -> None:
        """logout_user clears all auth state."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-3", "logoutuser", "administrator")
            logout_user()
            assert state[SESSION_AUTH_KEY] is False
            assert state[SESSION_USER_ID_KEY] is None
            assert state[SESSION_USERNAME_KEY] is None
            assert state[SESSION_ROLE_KEY] is None

    def test_is_authenticated_true(self) -> None:
        """is_authenticated returns True after login."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-4", "authuser", "grader")
            assert is_authenticated() is True

    def test_is_authenticated_false(self) -> None:
        """is_authenticated returns False before login."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            assert is_authenticated() is False

    def test_get_current_role_authenticated(self) -> None:
        """get_current_role returns the correct role."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-5", "roleuser", "reviewer")
            assert get_current_role() == "reviewer"

    def test_get_current_role_anonymous(self) -> None:
        """get_current_role returns 'anonymous' when not authenticated."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            assert get_current_role() == "anonymous"

    def test_get_current_user_id(self) -> None:
        """get_current_user_id returns the user ID."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-6", "iduser", "exporter")
            assert get_current_user_id() == "user-6"

    def test_get_current_user_id_none(self) -> None:
        """get_current_user_id returns None when not authenticated."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            assert get_current_user_id() is None

    def test_get_current_username(self) -> None:
        """get_current_username returns the username."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-7", "nameuser", "viewer")
            assert get_current_username() == "nameuser"

    def test_update_activity(self) -> None:
        """update_activity refreshes the activity timestamp."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-8", "activeuser", "grader")
            old_activity = state[SESSION_ACTIVITY_KEY]
            update_activity()
            new_activity = state[SESSION_ACTIVITY_KEY]
            assert new_activity is not None
            assert old_activity is not None
            assert new_activity >= old_activity

    def test_session_has_no_password(self) -> None:
        """Session state must never contain password fields."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-9", "safeuser", "grader")
            state["some_other_key"] = "test"
            # Ensure no password-related keys exist
            for key in state:
                assert "password" not in key.lower()

    def test_session_has_no_orm_object(self) -> None:
        """Session state must not contain ORM objects."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            # Simulate that only scalar values are stored
            login_user("user-10", "ormuser", "grader")
            for val in state.values():
                # ORM objects are not simple types
                if hasattr(val, "__class__") and hasattr(val, "__table__"):
                    pytest.fail("ORM object found in session state")


class TestSessionTimeout:
    """Test session timeout logic."""

    def test_timeout_not_expired(self) -> None:
        """check_session_timeout returns True when within timeout."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-11", "timeuser", "grader")
            # Activity just set to now, so should be valid
            assert check_session_timeout() is True

    def test_timeout_expired(self) -> None:
        """check_session_timeout returns False when past timeout."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-12", "expireduser", "grader")
            # Set activity to 31 minutes ago
            state[SESSION_ACTIVITY_KEY] = datetime.now(UTC) - timedelta(minutes=31)
            assert check_session_timeout() is False
            # Session should be cleared
            assert state.get(SESSION_AUTH_KEY) is False

    def test_timeout_exact_boundary(self) -> None:
        """check_session_timeout returns True at exactly 29 minutes."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            login_user("user-13", "boundaryuser", "viewer")
            # Set activity to 29 minutes ago (within 30 min timeout)
            state[SESSION_ACTIVITY_KEY] = datetime.now(UTC) - timedelta(minutes=29)
            assert check_session_timeout() is True

    def test_not_authenticated_returns_false(self) -> None:
        """check_session_timeout returns False when not authenticated."""
        state: dict[str, Any] = {}
        with patch("streamlit.session_state", state):
            init_session_state()
            result = check_session_timeout()
            assert result is False
