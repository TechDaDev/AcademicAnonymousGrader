# Academic Anonymous Grader — Audit Service Tests
"""Tests for audit_service.py — event recording, querying, and filtering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from models.audit_event import AuditEvent
from services.audit_service import (
    ACTION_LOGIN_FAILURE,
    ACTION_LOGIN_SUCCESS,
    ACTION_LOGOUT,
    export_audit_summary,
    query_audit_events,
    record_audit_event,
)

pytestmark = pytest.mark.usefixtures("session")


class TestRecordAuditEvent:
    """Test recording audit events."""

    def test_record_login_success(self, session: Any) -> None:
        """A login success event can be recorded."""
        event = record_audit_event(
            session,
            action=ACTION_LOGIN_SUCCESS,
            user_id="user-1",
            username_snapshot="admin",
            outcome="success",
        )
        assert event is not None
        assert event.event_type == ACTION_LOGIN_SUCCESS
        assert event.user_reference == "admin"

    def test_record_login_failure(self, session: Any) -> None:
        """A login failure event can be recorded."""
        event = record_audit_event(
            session,
            action=ACTION_LOGIN_FAILURE,
            outcome="failure",
            reason_code="INVALID_CREDENTIALS",
        )
        assert event is not None
        assert event.event_type == ACTION_LOGIN_FAILURE

    def test_record_with_entity(self, session: Any) -> None:
        """An event can reference an entity."""
        event = record_audit_event(
            session,
            action=ACTION_LOGOUT,
            user_id="user-2",
            username_snapshot="grader1",
            entity_type="session",
            outcome="success",
        )
        assert event.entity_type == "session"

    def test_record_with_assessment_id(self, session: Any) -> None:
        """An event can reference an assessment."""
        event = record_audit_event(
            session,
            action="assessment_finalized",
            user_id="user-3",
            assessment_id="assessment-1",
            outcome="success",
        )
        assert event.event_metadata is not None
        assert '"assessment_id": "assessment-1"' in event.event_metadata

    def test_record_with_anonymous_code(self, session: Any) -> None:
        """An event can reference an anonymous code."""
        event = record_audit_event(
            session,
            action="review_approved",
            user_id="user-4",
            anonymous_code="STU-TEST001",
            outcome="success",
        )
        assert event.event_metadata is not None
        assert '"anonymous_code": "STU-TEST001"' in event.event_metadata

    def test_events_persist_to_db(self, session: Any) -> None:
        """Recorded events are persisted to the database."""
        record_audit_event(
            session,
            action=ACTION_LOGIN_SUCCESS,
            user_id="user-5",
            username_snapshot="persist_user",
            outcome="success",
        )
        session.flush()
        count = session.query(AuditEvent).count()
        assert count >= 1


class TestQueryAuditEvents:
    """Test querying audit events."""

    def test_query_all(self, session: Any) -> None:
        """Querying without filters returns events."""
        record_audit_event(session, action=ACTION_LOGIN_SUCCESS, user_id="u1", outcome="success")
        record_audit_event(session, action=ACTION_LOGOUT, user_id="u1", outcome="success")
        results = query_audit_events(session)
        assert len(results) >= 2

    def test_filter_by_action(self, session: Any) -> None:
        """Filtering by action returns matching events."""
        record_audit_event(session, action=ACTION_LOGIN_SUCCESS, user_id="u2", outcome="success")
        record_audit_event(session, action=ACTION_LOGOUT, user_id="u2", outcome="success")
        results = query_audit_events(session, action=ACTION_LOGIN_SUCCESS)
        for r in results:
            assert r["action"] == ACTION_LOGIN_SUCCESS

    def test_filter_by_outcome(self, session: Any) -> None:
        """Filtering by outcome returns matching events."""
        record_audit_event(session, action=ACTION_LOGIN_FAILURE, outcome="failure")
        results = query_audit_events(session, outcome="failure")
        for r in results:
            assert r["outcome"] == "failure"

    def test_filter_by_date_range(self, session: Any) -> None:
        """Filtering by date range works."""
        record_audit_event(session, action=ACTION_LOGIN_SUCCESS, user_id="u3", outcome="success")
        yesterday = datetime.now(UTC) - timedelta(days=1)
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        results = query_audit_events(session, date_from=yesterday, date_to=tomorrow)
        assert len(results) >= 1

    def test_limit_results(self, session: Any) -> None:
        """Query returns at most `limit` results."""
        for i in range(5):
            record_audit_event(
                session, action=ACTION_LOGIN_SUCCESS, user_id=f"u{i}", outcome="success"
            )
        results = query_audit_events(session, limit=3)
        assert len(results) <= 3

    def test_filter_by_assessment_id(self, session: Any) -> None:
        """Filtering by assessment ID returns matching events."""
        record_audit_event(
            session,
            action="assessment_finalized",
            user_id="u4",
            assessment_id="assess-1",
            outcome="success",
        )
        results = query_audit_events(session, assessment_id="assess-1")
        assert len(results) >= 1
        assert results[0]["assessment_id"] == "assess-1"


class TestExportAuditSummary:
    """Test exporting audit summaries."""

    def test_export_summary_format(self, session: Any) -> None:
        """Export returns safe summary format."""
        record_audit_event(
            session,
            action=ACTION_LOGIN_SUCCESS,
            user_id="u5",
            username_snapshot="export_user",
            outcome="success",
        )
        summary = export_audit_summary(session)
        assert len(summary) >= 1
        entry = summary[0]
        assert "timestamp" in entry
        assert "actor" in entry
        assert "action" in entry
        assert "entity" in entry
        # Must NOT contain sensitive fields
        assert "password" not in str(entry)
        assert "metadata" not in entry

    def test_export_no_sensitive_data(self, session: Any) -> None:
        """Export summary must not contain passwords or secrets."""
        record_audit_event(
            session,
            action="test_action",
            user_id="u6",
            metadata_json={"test": "value", "password": "should_be_redacted"},
            outcome="success",
        )
        summary = export_audit_summary(session)
        summary_str = str(summary)
        assert "should_be_redacted" not in summary_str
