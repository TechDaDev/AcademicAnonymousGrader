# Academic Anonymous Grader — Reusable UI Components
"""Reusable Streamlit UI components."""

from __future__ import annotations

import streamlit as st


def render_metric_card(label: str, value: int | str, help_text: str | None = None) -> None:
    """Render a styled metric card for the dashboard.

    Parameters
    ----------
    label : str
        Metric label.
    value : int | str
        Metric value to display.
    help_text : str | None
        Optional tooltip text.
    """
    st.metric(label=label, value=value, help=help_text)


def render_foundation_warning() -> None:
    """Render a prominent warning that the application is not ready for real data."""
    st.warning(
        "⚠️ **Phase 3 Preview** — HTML import preview is available, but no student records are saved yet. "
        "Do not use with real student data outside approved test fixtures.",
        icon="⚠️",
    )
