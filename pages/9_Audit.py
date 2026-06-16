# Academic Anonymous Grader — Audit Log Page
"""Administrator-only audit log viewer."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.init_db import initialize_database
from database.session import create_session_factory, session_scope
from services.audit_service import export_audit_summary, query_audit_events
from services.logging_service import get_logger
from ui.layout import configure_page, render_app_header, render_safe_error
from ui.session import render_logout_button, require_authentication, require_page_access_safe

logger = get_logger("audit_page")


def _get_session_factory() -> Any:  # noqa: ANN401
    settings = get_settings()
    engine = get_engine(settings.resolved_database_url(), echo=settings.app_debug)
    initialize_database(engine)
    return create_session_factory(engine)


def _render_filters() -> dict[str, Any]:
    """Render filter controls and return filter dict."""
    st.subheader("🔍 Filters")

    cols = st.columns(3)
    with cols[0]:
        action = st.text_input("Action", placeholder="e.g., login_success")
    with cols[1]:
        username = st.text_input("Username", placeholder="Filter by actor")
    with cols[2]:
        entity_type = st.text_input("Entity Type", placeholder="e.g., assessment")

    cols2 = st.columns(3)
    with cols2[0]:
        outcome = st.selectbox(
            "Outcome", ["All", "success", "failure"], index=0
        )
    with cols2[1]:
        default_from = date.today() - timedelta(days=7)
        date_from = st.date_input("From", value=default_from)
    with cols2[2]:
        date_to = st.date_input("To", value=date.today())

    _ = st.button("🔍 Apply Filters", use_container_width=True)

    filters: dict[str, Any] = {
        "action": action.strip() if action else None,
        "username": username.strip() if username else None,
        "entity_type": entity_type.strip() if entity_type else None,
        "outcome": outcome if outcome != "All" else None,
        "date_from": datetime.combine(date_from, datetime.min.time()).replace(tzinfo=UTC) if date_from else None,
        "date_to": datetime.combine(date_to, datetime.max.time()).replace(tzinfo=UTC) if date_to else None,
    }
    return filters


def _render_events(events: list[dict[str, Any]]) -> None:
    """Render audit event list."""
    if not events:
        st.info("No audit events match the current filters.")
        return

    st.caption(f"Showing {len(events)} event(s)")

    for event in events:
        with st.container(border=True):
            cols = st.columns([2, 1.5, 1.5, 1, 1])
            with cols[0]:
                st.markdown(f"**{event['action']}**")
                st.caption(event["timestamp"])
            with cols[1]:
                st.caption(f"Actor: `{event['actor'] or 'N/A'}`")
            with cols[2]:
                st.caption(f"Entity: `{event['entity_type'] or 'N/A'}`")
                if event["entity_id"]:
                    st.caption(f"ID: `{event['entity_id'][:8]}...`")
            with cols[3]:
                outcome = event.get("outcome", "unknown")
                icon = "✅" if outcome == "success" else ("❌" if outcome == "failure" else "❓")
                st.caption(f"{icon} {outcome}")
            with cols[4]:
                if event.get("reason_code"):
                    st.caption(f"Reason: `{event['reason_code']}`")
                if event.get("anonymous_code"):
                    st.caption(f"Anon: `{event['anonymous_code']}`")


def _render_csv_export(factory: Any, filters: dict[str, Any]) -> None:  # noqa: ANN401
    """Render CSV export button for audit summaries."""
    if st.button("📥 Export Audit Summary (CSV)", use_container_width=True):
        try:
            with session_scope(factory) as session:
                summary = export_audit_summary(
                    session,
                    date_from=filters.get("date_from"),
                    date_to=filters.get("date_to"),
                )

            if not summary:
                st.info("No events to export.")
                return

            import csv
            import io

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["timestamp", "actor", "action", "entity", "entity_id"])
            writer.writeheader()
            writer.writerows(summary)

            csv_bytes = output.getvalue().encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_bytes,
                file_name=f"audit_summary_{date.today().isoformat()}.csv",
                mime="text/csv",
            )
        except Exception as exc:
            render_safe_error(f"Failed to export audit summary: {exc}")


def main() -> None:
    """Audit log viewer — administrator only."""
    configure_page("Audit Log")
    require_authentication()
    require_page_access_safe("Audit")
    render_logout_button()
    render_app_header()
    st.subheader("📋 Audit Log")
    st.caption("Privacy-safe event log for accountability.")

    # Privacy notice
    st.info(
        "🔒 **Audit Privacy** — This log never contains passwords, "
        "decrypted identities, student responses, or grader feedback."
    )

    factory = _get_session_factory()
    filters = _render_filters()

    st.divider()
    _render_csv_export(factory, filters)

    try:
        with session_scope(factory) as session:
            events = query_audit_events(
                session,
                username=filters["username"],
                action=filters["action"],
                entity_type=filters["entity_type"],
                outcome=filters["outcome"],
                date_from=filters["date_from"],
                date_to=filters["date_to"],
            )
        _render_events(events)
    except Exception:
        logger.exception("Failed to query audit events")
        render_safe_error("Could not load audit events.")


if __name__ == "__main__":
    main()
