# Academic Anonymous Grader — Audit Service
"""Privacy-safe audit logging.

SECURITY:
- Never log passwords, password hashes, or encryption keys
- Never log decrypted names, emails, or institutional IDs
- Never log student responses or grader feedback
- Sanitize metadata recursively before persistence
- Audit failures do not corrupt the main transaction
- Uses a separate savepoint for audit events
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc

from models.audit_event import AuditEvent

# ---------------------------------------------------------------------------
# Audit action constants
# ---------------------------------------------------------------------------

ACTION_LOGIN_SUCCESS = "login_success"
ACTION_LOGIN_FAILURE = "login_failure"
ACTION_LOGOUT = "logout"
ACTION_USER_CREATED = "user_created"
ACTION_USER_DEACTIVATED = "user_deactivated"
ACTION_USER_REACTIVATED = "user_reactivated"
ACTION_PASSWORD_CHANGED = "password_changed"  # noqa: S105
ACTION_IMPORT_PREVIEW = "import_preview"
ACTION_IMPORT_COMPLETED = "import_completed"
ACTION_GRADING_DRAFT_SAVED = "grading_draft_saved"
ACTION_SUBMISSION_MARKED_GRADED = "submission_marked_graded"
ACTION_REVIEW_APPROVED = "review_approved"
ACTION_REVIEW_NEEDS_CORRECTION = "review_needs_correction"
ACTION_ASSESSMENT_FINALIZED = "assessment_finalized"
ACTION_EXPORT_GENERATED = "export_generated"
ACTION_BACKUP_CREATED = "backup_created"
ACTION_RESTORE_STARTED = "restore_started"
ACTION_RESTORE_COMPLETED = "restore_completed"
ACTION_RESTORE_FAILED = "restore_failed"

# ---------------------------------------------------------------------------
# Fields that must never appear in audit metadata
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = frozenset({
    "password",
    "password_hash",
    "new_password",
    "current_password",
    "encryption_key",
    "fingerprint_key",
    "identity_key",
    "decrypted",
    "plaintext",
    "ciphertext",
    "workbook_bytes",
    "backup_password",
})


def _sanitize_value(value: Any, path: str = "") -> Any:
    """Recursively sanitize a value, removing sensitive data."""
    if isinstance(value, dict):
        return {k: _sanitize_value(v, f"{path}.{k}" if path else k) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item, path) for item in value]
    if isinstance(value, str):
        # Check for sensitive key names
        key_lower = path.lower()
        for sensitive in _SENSITIVE_KEYS:
            if sensitive in key_lower:
                return "[REDACTED]"
    return value


def sanitize_audit_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sanitize metadata dict before persistence.

    Recursively removes or redacts sensitive fields.

    Parameters
    ----------
    metadata : dict[str, Any] | None
        Raw metadata dict.

    Returns
    -------
    dict[str, Any] | None
        Sanitized metadata safe for persistence.
    """
    if metadata is None:
        return None
    sanitized = _sanitize_value(metadata)
    if isinstance(sanitized, dict):
        return sanitized
    return metadata


def record_audit_event(
    session: Any,
    action: str,
    user_id: str | None = None,
    username_snapshot: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    assessment_id: str | None = None,
    anonymous_code: str | None = None,
    outcome: str = "success",
    reason_code: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> AuditEvent:
    """Record an audit event.

    Uses a savepoint so that audit logging failures do not roll back the
    main transaction. If the savepoint fails, the error is logged at the
    service layer but the main transaction continues.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    action : str
        Action identifier (e.g., 'login_success', 'export_generated').
    user_id : str | None
        ID of the user who performed the action.
    username_snapshot : str | None
        Username at time of action (survives user deletion).
    entity_type : str | None
        Type of entity affected (e.g., 'assessment', 'user').
    entity_id : str | None
        ID of the entity affected.
    assessment_id : str | None
        Assessment ID if the action is scoped to an assessment.
    anonymous_code : str | None
        Anonymous code if relevant (never the real identity).
    outcome : str
        'success' or 'failure'.
    reason_code : str | None
        Optional short reason code (e.g., 'INVALID_CREDENTIALS').
    metadata_json : dict[str, Any] | None
        Additional metadata. Will be sanitized before persistence.

    Returns
    -------
    AuditEvent
        The created audit event, or a fallback event if logging failed.
    """
    sanitized = sanitize_audit_metadata(metadata_json)

    event = AuditEvent(
        id=str(uuid.uuid4()),
        event_type=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_reference=username_snapshot or user_id,
        event_metadata=json.dumps(
            {
                "user_id": user_id,
                "assessment_id": assessment_id,
                "anonymous_code": anonymous_code,
                "outcome": outcome,
                "reason_code": reason_code,
                **(sanitized or {}),
            },
            default=str,
        ),
        created_at=datetime.now(UTC),
    )

    try:
        # Use a savepoint so audit failure doesn't corrupt main transaction
        session.begin_nested()
        session.add(event)
        session.flush()
    except Exception:
        # Audit logging failure must not corrupt main transaction
        import logging

        logging.getLogger("audit_service").exception(
            "Failed to record audit event (action=%s)", action
        )

    return event


def query_audit_events(
    session: Any,
    *,
    username: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    outcome: str | None = None,
    assessment_id: str | None = None,
    anonymous_code: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query audit events with optional filters.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    username : str | None
        Filter by username.
    action : str | None
        Filter by action.
    entity_type : str | None
        Filter by entity type.
    outcome : str | None
        Filter by outcome.
    assessment_id : str | None
        Filter by assessment ID.
    anonymous_code : str | None
        Filter by anonymous code.
    date_from : datetime | None
        Filter by start date.
    date_to : datetime | None
        Filter by end date.
    limit : int
        Maximum results. Default 500.
    offset : int
        Result offset. Default 0.

    Returns
    -------
    list[dict[str, Any]]
        List of event dicts with parsed metadata.
    """
    query = session.query(AuditEvent)

    if username:
        query = query.filter(AuditEvent.user_reference.ilike(f"%{username}%"))
    if action:
        query = query.filter(AuditEvent.event_type == action)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if date_from:
        query = query.filter(AuditEvent.created_at >= date_from)
    if date_to:
        query = query.filter(AuditEvent.created_at <= date_to)

    if any([outcome, assessment_id, anonymous_code]):
        # Need to filter in metadata JSON — do post-filtering
        events = query.order_by(desc(AuditEvent.created_at)).limit(limit).offset(offset).all()
        result = []
        for event in events:
            meta = _parse_metadata(event.event_metadata)
            if outcome and meta.get("outcome") != outcome:
                continue
            if assessment_id and meta.get("assessment_id") != assessment_id:
                continue
            if anonymous_code and meta.get("anonymous_code") != anonymous_code:
                continue
            result.append(_event_to_dict(event, meta))
        return result

    events = query.order_by(desc(AuditEvent.created_at)).limit(limit).offset(offset).all()
    return [_event_to_dict(e) for e in events]


def export_audit_summary(
    session: Any,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict[str, Any]]:
    """Export a privacy-safe audit summary.

    Returns only timestamp, actor, action, entity, and outcome.
    No PII, no decrypted identities, no metadata content.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    date_from : datetime | None
        Filter by start date.
    date_to : datetime | None
        Filter by end date.

    Returns
    -------
    list[dict[str, Any]]
        List of safe summary dicts.
    """
    query = session.query(AuditEvent)
    if date_from:
        query = query.filter(AuditEvent.created_at >= date_from)
    if date_to:
        query = query.filter(AuditEvent.created_at <= date_to)

    events = query.order_by(desc(AuditEvent.created_at)).limit(5000).all()
    return [
        {
            "timestamp": e.created_at.isoformat(),
            "actor": e.user_reference,
            "action": e.event_type,
            "entity": e.entity_type,
            "entity_id": e.entity_id,
        }
        for e in events
    ]


def _parse_metadata(raw: str | None) -> dict[str, Any]:
    """Parse JSON metadata string safely."""
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _event_to_dict(event: AuditEvent, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert an AuditEvent to a safe dict."""
    if meta is None:
        meta = _parse_metadata(event.event_metadata)
    return {
        "id": event.id,
        "timestamp": event.created_at.isoformat(),
        "actor": event.user_reference,
        "action": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "outcome": meta.get("outcome", "unknown"),
        "reason_code": meta.get("reason_code"),
        "assessment_id": meta.get("assessment_id"),
        "anonymous_code": meta.get("anonymous_code"),
    }
