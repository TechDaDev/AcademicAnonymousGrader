# Academic Anonymous Grader — UI Layout Helpers
"""Reusable Streamlit layout helpers."""

from __future__ import annotations

import streamlit as st


def configure_page(title: str = "Academic Anonymous Grader") -> None:
    """Set Streamlit page configuration.

    Must be the first Streamlit command on each page.

    Parameters
    ----------
    title : str
        Browser tab title.
    """
    st.set_page_config(
        page_title=title,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_app_header() -> None:
    """Render the application header with project name and phase indicator."""
    st.markdown(
        "<h1 style='margin-bottom: 0;'>📚 Academic Anonymous Grader</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Phase 10 — Instructor Assignment & Production Readiness")
    st.divider()


def render_phase_notice(phase_name: str) -> None:
    """Render a notice that a feature will be implemented in a future phase.

    Parameters
    ----------
    phase_name : str
        Name of the phase that will implement this feature.
    """
    st.info(f"🔜 **{phase_name}** — This feature is not yet implemented.")
    st.caption(
        "This placeholder exists to validate the application shell. "
        "Full functionality will be added in the specified phase."
    )


def render_placeholder_page(title: str, phase: str) -> None:
    """Render a complete placeholder page with header and phase notice.

    Parameters
    ----------
    title : str
        Page title to display.
    phase : str
        Phase that will implement this feature.
    """
    configure_page(title)
    render_app_header()
    st.subheader(title)
    render_phase_notice(phase)


def render_safe_error(message: str) -> None:
    """Render an error message that does not expose secrets or internals.

    Parameters
    ----------
    message : str
        User-safe error description.
    """
    st.error(f"⚠️ {message}")
