# Academic Anonymous Grader — Session Management
"""Streamlit session authentication and timeout management.

Session state fields:
  - authenticated: bool
  - user_id: str
  - username: str
  - role: str
  - display_name: str | None
  - login_timestamp: datetime
  - last_activity_timestamp: datetime

Never stored in session state:
  - password
  - password hash
  - encryption keys
  - decrypted identity data
  - database session
  - ORM user object
"""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from config import get_settings
from services.authorization_service import display_role, require_page_access
from services.exceptions import InsufficientPermissionsError

SESSION_AUTH_KEY = "authenticated"
SESSION_USER_ID_KEY = "user_id"
SESSION_USERNAME_KEY = "username"
SESSION_ROLE_KEY = "role"
SESSION_DISPLAY_NAME_KEY = "display_name"
SESSION_LOGIN_TIME_KEY = "login_timestamp"
SESSION_ACTIVITY_KEY = "last_activity_timestamp"


def init_session_state() -> None:
    """Initialize session state keys if not present."""
    if SESSION_AUTH_KEY not in st.session_state:
        st.session_state[SESSION_AUTH_KEY] = False
    if SESSION_USER_ID_KEY not in st.session_state:
        st.session_state[SESSION_USER_ID_KEY] = None
    if SESSION_USERNAME_KEY not in st.session_state:
        st.session_state[SESSION_USERNAME_KEY] = None
    if SESSION_ROLE_KEY not in st.session_state:
        st.session_state[SESSION_ROLE_KEY] = None
    if SESSION_DISPLAY_NAME_KEY not in st.session_state:
        st.session_state[SESSION_DISPLAY_NAME_KEY] = None
    if SESSION_LOGIN_TIME_KEY not in st.session_state:
        st.session_state[SESSION_LOGIN_TIME_KEY] = None
    if SESSION_ACTIVITY_KEY not in st.session_state:
        st.session_state[SESSION_ACTIVITY_KEY] = None


def login_user(user_id: str, username: str, role: str, display_name: str | None = None) -> None:
    """Set session state for an authenticated user.

    Parameters
    ----------
    user_id : str
        User ID.
    username : str
        Username.
    role : str
        User role.
    display_name : str | None
        Optional display name.
    """
    now = datetime.now(UTC)
    st.session_state[SESSION_AUTH_KEY] = True
    st.session_state[SESSION_USER_ID_KEY] = user_id
    st.session_state[SESSION_USERNAME_KEY] = username
    st.session_state[SESSION_ROLE_KEY] = role
    st.session_state[SESSION_DISPLAY_NAME_KEY] = display_name
    st.session_state[SESSION_LOGIN_TIME_KEY] = now
    st.session_state[SESSION_ACTIVITY_KEY] = now


def logout_user() -> None:
    """Clear all authentication-related session state."""
    st.session_state[SESSION_AUTH_KEY] = False
    st.session_state[SESSION_USER_ID_KEY] = None
    st.session_state[SESSION_USERNAME_KEY] = None
    st.session_state[SESSION_ROLE_KEY] = None
    st.session_state[SESSION_DISPLAY_NAME_KEY] = None
    st.session_state[SESSION_LOGIN_TIME_KEY] = None
    st.session_state[SESSION_ACTIVITY_KEY] = None


def is_authenticated() -> bool:
    """Check whether the current session is authenticated."""
    return bool(st.session_state.get(SESSION_AUTH_KEY)) and bool(
        st.session_state.get(SESSION_USER_ID_KEY)
    )


def get_current_role() -> str:
    """Get the current user's role.

    Returns
    -------
    str
        Role string, or 'anonymous' if not authenticated.
    """
    if is_authenticated():
        return str(st.session_state.get(SESSION_ROLE_KEY, "anonymous"))
    return "anonymous"


def get_current_user_id() -> str | None:
    """Get the current user's ID."""
    if is_authenticated():
        return st.session_state.get(SESSION_USER_ID_KEY)
    return None


def get_current_username() -> str | None:
    """Get the current username."""
    if is_authenticated():
        return st.session_state.get(SESSION_USERNAME_KEY)
    return None


def update_activity() -> None:
    """Update the last activity timestamp."""
    if is_authenticated():
        st.session_state[SESSION_ACTIVITY_KEY] = datetime.now(UTC)


def check_session_timeout() -> bool:
    """Check whether the session has timed out due to inactivity.

    Returns
    -------
    bool
        True if the session is still valid. False if timed out.
    """
    if not is_authenticated():
        return False

    last_activity = st.session_state.get(SESSION_ACTIVITY_KEY)
    if last_activity is None:
        return False

    settings = get_settings()
    timeout_minutes = settings.session_timeout_minutes
    now = datetime.now(UTC)

    # Use timezone-aware comparison
    if isinstance(last_activity, datetime):
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=UTC)
    else:
        return False

    elapsed = (now - last_activity).total_seconds()
    if elapsed > timeout_minutes * 60:
        logout_user()
        return False

    return True


def require_authentication() -> None:
    """Redirect to login page if not authenticated or session timed out.

    Must be called at the top of every protected page.
    """
    init_session_state()

    if not is_authenticated():
        st.switch_page("app.py")
        st.stop()

    if not check_session_timeout():
        st.warning(
            f"Your session has expired due to inactivity "
            f"(timeout: {get_settings().session_timeout_minutes} minutes). "
            "Please log in again."
        )
        st.switch_page("app.py")
        st.stop()

    update_activity()


def render_logout_button() -> None:
    """Render a logout button in the sidebar."""
    if is_authenticated():
        username_val = st.session_state.get(SESSION_USERNAME_KEY, "Unknown")
        role_val = st.session_state.get(SESSION_ROLE_KEY, "unknown")
        role_display = display_role(role_val)
        st.sidebar.markdown(f"**Logged in as:** {username_val}")
        st.sidebar.caption(f"Role: {role_display}")
        if st.sidebar.button("🚪 Logout", key="logout_button", use_container_width=True):
            from database.engine import get_engine
            from database.session import create_session_factory, session_scope
            from services.audit_service import ACTION_LOGOUT, record_audit_event

            user_id = get_current_user_id()
            username_val2 = get_current_username()
            try:
                settings = get_settings()
                engine = get_engine(settings.resolved_database_url())
                factory = create_session_factory(engine)
                with session_scope(factory) as session:
                    record_audit_event(
                        session,
                        action=ACTION_LOGOUT,
                        user_id=user_id,
                        username_snapshot=username_val2,
                        outcome="success",
                    )
            except Exception:  # noqa: S110
                pass  # Logout must succeed even if audit fails

            logout_user()
            st.rerun()


def require_page_access_safe(page_name: str) -> None:
    """Check page access and show a safe error without traceback if denied.

    Must be called after require_authentication() in every page.

    Parameters
    ----------
    page_name : str
        Name of the page to check access for.
    """
    role = st.session_state.get(SESSION_ROLE_KEY, "")
    try:
        require_page_access(role, page_name)
    except InsufficientPermissionsError as exc:
        from ui.layout import render_safe_error

        render_safe_error(str(exc))
        st.stop()
