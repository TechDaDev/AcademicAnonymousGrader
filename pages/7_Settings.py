# Academic Anonymous Grader — Settings Page
"""Application settings display. No business logic."""

from __future__ import annotations

import streamlit as st

from config import get_settings
from ui.layout import configure_page, render_app_header, render_safe_error

configure_page("Settings")
render_app_header()
st.subheader("Settings")

try:
    settings = get_settings()
except ValueError as exc:
    render_safe_error(f"Configuration error: {exc}")
    st.stop()

st.markdown("### Application Configuration")
st.markdown(f"- **Application Name:** {settings.app_name}")
st.markdown(f"- **Environment:** `{settings.app_env}`")
st.markdown(f"- **Debug Mode:** `{settings.app_debug}`")
st.markdown(f"- **Data Directory:** `{settings.resolved_data_dir}`")
st.markdown(f"- **Export Directory:** `{settings.resolved_export_dir}`")
st.markdown(f"- **Upload Directory:** `{settings.resolved_upload_dir}`")
st.markdown(f"- **Backup Directory:** `{settings.resolved_backup_dir}`")

st.divider()
st.markdown(
    "⚠️ **Security Note:** Sensitive configuration values (encryption keys, "
    "database credentials) are never displayed on this page."
)
st.caption(
    "Full configuration management and backup functionality will be "
    "implemented in a later phase."
)
