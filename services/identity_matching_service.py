"""Identity matching service — deterministic hierarchy for import matching."""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

from sqlalchemy.orm import Session

from models.student_identity import StudentIdentity
from security.fingerprint import fingerprint_email, fingerprint_institutional_id
from security.models import FingerprintKey


class MatchResultType(str, Enum):  # noqa: UP042 — StrEnum is 3.11+
    MATCHED_BY_INSTITUTIONAL_ID = "matched_by_institutional_id"
    MATCHED_BY_EMAIL = "matched_by_email"
    NEW_IDENTITY = "new_identity"
    AMBIGUOUS_CONFLICT = "ambiguous_conflict"
    MANUAL_RESOLUTION_REQUIRED = "manual_resolution_required"
    INVALID_IDENTITY = "invalid_identity"


class MatchResult(NamedTuple):
    result_type: MatchResultType
    existing_identity_id: str | None
    conflict_reason: str | None
    blocking: bool


def find_matching_identity(
    session: Session,
    institutional_id: str | None,
    email: str | None,
    fp_key: FingerprintKey,
) -> MatchResult:
    """Match using the documented hierarchy.

    1. Institutional ID fingerprint match → existing identity
    2. No ID, email fingerprint match → existing identity
    3. Conflicting ID and email → AMBIGUOUS_CONFLICT
    4. No match → NEW_IDENTITY
    """
    if not institutional_id and not email:
        return MatchResult(
            MatchResultType.MANUAL_RESOLUTION_REQUIRED,
            None,
            "No institutional ID or email provided",
            blocking=True,
        )

    id_fp = fingerprint_institutional_id(institutional_id, fp_key) if institutional_id else None
    email_fp = fingerprint_email(email, fp_key) if email else None

    id_match = None
    email_match = None

    if id_fp:
        id_match = (
            session.query(StudentIdentity)
            .filter(StudentIdentity.institutional_id_fingerprint == id_fp)
            .first()
        )

    if email_fp:
        email_match = (
            session.query(StudentIdentity)
            .filter(StudentIdentity.email_fingerprint == email_fp)
            .first()
        )

    # Conflicting matches
    if id_match and email_match and id_match.id != email_match.id:
        return MatchResult(
            MatchResultType.AMBIGUOUS_CONFLICT,
            None,
            "Institutional ID and email match different existing identities",
            blocking=True,
        )

    # ID match takes precedence
    if id_match:
        return MatchResult(
            MatchResultType.MATCHED_BY_INSTITUTIONAL_ID,
            id_match.id,
            None,
            blocking=False,
        )

    # Email match
    if email_match:
        return MatchResult(
            MatchResultType.MATCHED_BY_EMAIL,
            email_match.id,
            None,
            blocking=False,
        )

    # No match
    return MatchResult(
        MatchResultType.NEW_IDENTITY,
        None,
        None,
        blocking=False,
    )


def get_blocking_rows(
    session: Session,
    rows: tuple,  # type: ignore[type-arg]  # noqa: ANN401
    fp_key: FingerprintKey | None,
) -> list[dict[str, object]]:
    """Return blocking-row details for manual resolution UI.

    Each entry contains a stable row reference, masked identity
    information, match result type, and conflict reason.
    """
    blocking: list[dict[str, object]] = []
    for row in rows:
        if row.errors or row.ignored:
            continue

        if fp_key is not None:
            match = find_matching_identity(session, row.institutional_student_id, row.email, fp_key)
        else:
            match = MatchResult(MatchResultType.MANUAL_RESOLUTION_REQUIRED, None, "Keys unavailable", blocking=True)

        if match.blocking:
            blocking.append({
                "row_ref": f"row:{row.row_number}",
                "row_number": row.row_number,
                "first_name": _mask_text(row.first_name),
                "last_name": _mask_text(row.last_name),
                "email": _mask_email(row.email),
                "institutional_student_id": _mask_id(row.institutional_student_id),
                "match_type": match.result_type.value,
                "conflict_reason": match.conflict_reason or "",
            })
    return blocking


def get_masked_identity_summary(
    identity: StudentIdentity,
    enc_key: object,  # noqa: ANN401
) -> dict[str, str]:
    """Return a masked summary of an identity for manual resolution UI.

    Never exposes full plaintext, ciphertext, or fingerprints.
    """
    from security.encryption import decrypt_text
    first = decrypt_text(enc_key, identity.encrypted_first_name) if identity.encrypted_first_name else None  # type: ignore[arg-type]
    last = decrypt_text(enc_key, identity.encrypted_last_name) if identity.encrypted_last_name else None  # type: ignore[arg-type]
    email = decrypt_text(enc_key, identity.encrypted_email) if identity.encrypted_email else None  # type: ignore[arg-type]
    sid = (decrypt_text(enc_key, identity.encrypted_institutional_student_id)  # type: ignore[arg-type]
            if identity.encrypted_institutional_student_id else None)

    return {
        "identity_id": identity.id,
        "first_name": _mask_text(first),
        "last_name": _mask_text(last),
        "email": _mask_email(email),
        "institutional_student_id": _mask_id(sid),
    }


def _mask_text(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 2:
        return value[0] + "*"
    return value[0] + "*" * (len(value) - 2) + value[-1]


def _mask_email(value: str | None) -> str:
    if not value:
        return ""
    parts = value.split("@")
    if len(parts) != 2:
        return _mask_text(value)
    local = parts[0]
    domain = parts[1]
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _mask_id(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
