# Academic Anonymous Grader — Main Application Entry Point
"""Phase 8 — Authentication, Authorization, Audit, and Backup.

Login page for unauthenticated users. Dashboard for authenticated users.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from sqlalchemy.engine import Engine

from config import Settings, get_settings
from database.engine import get_engine
from database.init_db import initialize_database
from database.session import create_session_factory, session_scope
from services.audit_service import ACTION_LOGIN_FAILURE, ACTION_LOGIN_SUCCESS, record_audit_event
from services.auth_service import authenticate_user
from services.dashboard_service import get_dashboard_stats
from services.exceptions import AccountDisabledError, AccountLockedError, InvalidCredentialsError
from services.logging_service import configure_logging, get_logger
from ui.components import render_foundation_warning, render_metric_card
from ui.layout import configure_page, render_app_header, render_safe_error
from ui.session import (
    check_session_timeout,
    get_current_role,
    init_session_state,
    is_authenticated,
    login_user,
    logout_user,
    update_activity,
)

logger = get_logger("app")


def _render_login(
    settings: Settings, engine: Engine, factory: Any
) -> None:
    """Render the login form."""
    st.subheader("🔐 Login")
    st.markdown("Please log in to access the Academic Anonymous Grader.")

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if not username or not password:
            render_safe_error("Please enter both username and password.")
            return

        try:
            with session_scope(factory) as session:
                user = authenticate_user(session, username, password)
                login_user(user.id, user.username, user.role, user.display_name)
                record_audit_event(
                    session,
                    action=ACTION_LOGIN_SUCCESS,
                    user_id=user.id,
                    username_snapshot=user.username,
                    outcome="success",
                )
            st.rerun()
        except InvalidCredentialsError as exc:
            # Record failure (generic — no username enumeration)
            with session_scope(factory) as session:
                record_audit_event(
                    session,
                    action=ACTION_LOGIN_FAILURE,
                    username_snapshot="unknown",
                    outcome="failure",
                    reason_code="INVALID_CREDENTIALS",
                )
            render_safe_error(str(exc))
        except AccountLockedError as exc:
            with session_scope(factory) as session:
                record_audit_event(
                    session,
                    action=ACTION_LOGIN_FAILURE,
                    username_snapshot="unknown",
                    outcome="failure",
                    reason_code="ACCOUNT_LOCKED",
                )
            render_safe_error(str(exc))
        except AccountDisabledError as exc:
            render_safe_error(str(exc))
        except Exception:
            logger.exception("Login error")
            render_safe_error("An unexpected error occurred. Please try again.")

    st.divider()
    st.info(
        "⚠️ **No account yet?** Run the bootstrap command to create the first administrator:\n\n"
        "```bash\npython -m scripts.create_admin\n```"
    )


def _render_dashboard(settings: Settings, engine: Engine, session_factory: Any) -> None:  # noqa: ANN401
    """Render the dashboard for authenticated users."""
    try:
        with session_scope(session_factory) as session:
            stats = get_dashboard_stats(session)
    except Exception as exc:
        logger.error("Failed to load dashboard statistics: %s", exc)
        render_safe_error("Could not load dashboard data.")
        st.stop()

    # Render metric columns
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("📦 Materials", stats.material_count, "Total academic materials")
    with col2:
        render_metric_card("📝 Assessments", stats.assessment_count, "Total assessments")
    with col3:
        render_metric_card("👤 Students", stats.student_count, "Total anonymous student records")
    with col4:
        render_metric_card("📋 Submissions", stats.submission_count, "Total submissions")

    st.divider()

    # Phase 2 detail metrics
    st.subheader("Material and Assessment Status")
    det1, det2, det3, det4, det5 = st.columns(5)
    with det1:
        render_metric_card("Active Materials", stats.active_materials)
    with det2:
        render_metric_card("Archived Materials", stats.archived_materials)
    with det3:
        render_metric_card("Draft Assessments", stats.draft_assessments)
    with det4:
        render_metric_card("Ready Assessments", stats.ready_assessments)
    with det5:
        render_metric_card("Archived Assessments", stats.archived_assessments)

    st.divider()

    # System information
    st.subheader("System Information")
    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
    with info_col1:
        st.markdown(f"**Environment:** `{settings.app_env}`")
    with info_col2:
        from services.version_service import get_display_string
        st.markdown(f"**Version:** `{get_display_string()}`")
    with info_col3:
        db_status = "✅ Connected" if engine else "❌ Not connected"
        st.markdown(f"**Database:** {db_status}")
    with info_col4:
        st.markdown(f"**User:** `{st.session_state.get('username', 'Unknown')}` ({st.session_state.get('role', '?')})")

    render_foundation_warning()


def main() -> None:
    """Application entry point."""
    configure_page()
    init_session_state()

    # ------------------------------------------------------------------
    # Startup: load settings, configure logging, create dirs, init DB
    # ------------------------------------------------------------------
    try:
        settings = get_settings()
    except ValueError as exc:
        render_safe_error(f"Configuration error: {exc}")
        st.stop()

    # Configure logging
    configure_logging(
        log_file=settings.resolved_log_file,
        log_level=settings.log_level,
    )
    logger.info("Starting Academic Anonymous Grader — Phase 8")

    try:
        settings.create_directories(settings)
    except OSError as exc:
        logger.error("Failed to create required directories: %s", exc)
        render_safe_error("Could not create required application directories.")
        st.stop()

    # Initialize database
    try:
        database_url = settings.resolved_database_url()
        engine = get_engine(database_url, echo=settings.app_debug)
        initialize_database(engine)
        logger.info("Database initialized successfully")
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
        render_safe_error("Database initialization failed. Check configuration and permissions.")
        st.stop()

    session_factory = create_session_factory(engine)

    # Render header
    render_app_header()

    # ------------------------------------------------------------------
    # Authentication gate
    # ------------------------------------------------------------------
    if not is_authenticated():
        _render_login(settings, engine, session_factory)
        return

    # Check session timeout
    if not check_session_timeout():
        st.warning(
            f"Your session has expired due to inactivity "
            f"(timeout: {settings.session_timeout_minutes} minutes). "
            "Please log in again."
        )
        logout_user()
        st.rerun()
        return

    # Update activity timestamp
    update_activity()

    # ------------------------------------------------------------------
    # Role-aware sidebar navigation
    # ------------------------------------------------------------------
    # Hide default auto-generated page navigation
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] nav { display: none !important; }
        section[data-testid="stSidebar"] ul[data-testid="stSidebarNav"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    from services.authorization_service import can_access_page, display_role

    role = get_current_role()
    role_display = display_role(role)

    st.sidebar.markdown(f"**Logged in as:** {st.session_state.get('username', '')}")
    st.sidebar.caption(f"Role: {role_display}")
    st.sidebar.divider()

    # Build role-aware sidebar with markdown links
    if can_access_page(role, "Users"):
        links = [
            ("🏠 Dashboard", "/"),
            ("📦 Materials", "/Materials"),
            ("📝 Assessments", "/Assessments"),
            ("📥 Import", "/Import"),
            ("✏️ Grading", "/Grading"),
            ("🔍 Review", "/Review"),
            ("📤 Export", "/Export"),
            ("👥 Users", "/Users"),
            ("📋 Audit", "/Audit"),
            ("💾 Backup", "/Backup"),
            ("⚙️ Settings", "/Settings"),
            ("📌 Instructor Assignments", "/InstructorAssignments"),
            ("📊 Analytics", "/Analytics"),
            ("🏛️ Academic Structure", "/AcademicStructure"),
        ]
    elif can_access_page(role, "Grading"):
        links = [
            ("🏠 Dashboard", "/"),
            ("✏️ Grading", "/Grading"),
            ("📊 My Analytics", "/Analytics"),
        ]
    else:
        links = [("🏠 Dashboard", "/")]

    for label, url in links:
        st.sidebar.markdown(f"[{label}]({url})")

    st.sidebar.divider()

    # Logout
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        from database.engine import get_engine as _ge
        from database.session import create_session_factory as _csf
        from database.session import session_scope as _ss
        from services.audit_service import ACTION_LOGOUT
        from services.audit_service import record_audit_event as _rae

        user_id = st.session_state.get("user_id")
        username = st.session_state.get("username")
        try:
            eng = _ge(settings.resolved_database_url())
            fac = _csf(eng)
            with _ss(fac) as s:
                _rae(s, action=ACTION_LOGOUT, user_id=user_id, username_snapshot=username, outcome="success")
        except Exception:  # noqa: S110
            pass
        logout_user()
        st.rerun()

    # ------------------------------------------------------------------
    # Dashboard display
    # ------------------------------------------------------------------
    _render_dashboard(settings, engine, session_factory)

    logger.info("Dashboard rendered successfully")


if __name__ == "__main__":
    main()
