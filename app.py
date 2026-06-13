# Academic Anonymous Grader — Main Application Entry Point
"""Phase 1 — Project Foundation.

This is a foundation build. The application shell, database, and navigation
are in place, but no business logic has been implemented yet.
"""

from __future__ import annotations

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.init_db import initialize_database
from database.session import create_session_factory, session_scope
from services.dashboard_service import get_dashboard_stats
from services.logging_service import configure_logging
from ui.components import render_foundation_warning, render_metric_card
from ui.layout import configure_page, render_app_header, render_safe_error


def main() -> None:
    """Application entry point."""
    configure_page()
    render_app_header()

    # ------------------------------------------------------------------
    # Startup: load settings, configure logging, create dirs, init DB
    # ------------------------------------------------------------------
    try:
        settings = get_settings()
    except ValueError as exc:
        render_safe_error(f"Configuration error: {exc}")
        st.stop()

    # Configure logging
    logger = configure_logging(
        log_file=settings.resolved_log_file,
        log_level=settings.log_level,
    )
    logger.info("Starting Academic Anonymous Grader — Phase 1")

    try:
        settings.create_directories(settings)
    except OSError as exc:
        logger.error("Failed to create required directories: %s", exc)
        render_safe_error("Could not create required application directories.")
        st.stop()

    # Initialize database
    try:
        database_url = settings.resolved_database_url
        engine = get_engine(database_url, echo=settings.app_debug)
        initialize_database(engine)
        logger.info("Database initialized successfully")
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
        render_safe_error("Database initialization failed. Check configuration and permissions.")
        st.stop()

    # ------------------------------------------------------------------
    # Dashboard display
    # ------------------------------------------------------------------
    session_factory = create_session_factory(engine)

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

    # System information
    st.subheader("System Information")
    info_col1, info_col2, info_col3 = st.columns(3)
    with info_col1:
        st.markdown(f"**Environment:** `{settings.app_env}`")
    with info_col2:
        db_status = "✅ Connected" if engine else "❌ Not connected"
        st.markdown(f"**Database:** {db_status}")
    with info_col3:
        st.markdown("**Current Phase:** `Phase 1 — Project Foundation`")

    render_foundation_warning()

    logger.info("Dashboard rendered successfully")


if __name__ == "__main__":
    main()
