"""Anonymous ID generation using cryptographically secure randomness."""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from security.exceptions import AnonymousCodeCollisionError

_ANONYMOUS_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no O/0, I/1
_CODE_PREFIX = "STU-"
_CODE_LENGTH = 8


def generate_anonymous_code() -> str:
    """Generate a cryptographically secure random anonymous code."""
    chars = [secrets.choice(_ANONYMOUS_CHARS) for _ in range(_CODE_LENGTH)]
    return _CODE_PREFIX + "".join(chars)


def validate_anonymous_code_format(code: str) -> bool:
    """Validate that a code matches the STU-XXXXXXXX format."""
    if not code.startswith(_CODE_PREFIX):
        return False
    suffix = code[len(_CODE_PREFIX):]
    if len(suffix) != _CODE_LENGTH:
        return False
    return all(c in _ANONYMOUS_CHARS for c in suffix)


def get_or_create_anonymous_student(
    session: Session, identity_id: str
) -> str:
    """Get existing or create new AnonymousStudent for a StudentIdentity.

    Returns the anonymous code.
    """
    from models.anonymous_student import AnonymousStudent

    existing = (
        session.query(AnonymousStudent)
        .filter_by(student_identity_id=identity_id)
        .first()
    )
    if existing:
        return existing.anonymous_code

    for attempt in range(20):
        code = generate_anonymous_code()
        collision = (
            session.query(AnonymousStudent)
            .filter_by(anonymous_code=code)
            .first()
        )
        if not collision:
            anon = AnonymousStudent(
                student_identity_id=identity_id,
                anonymous_code=code,
            )
            session.add(anon)
            return code

    raise AnonymousCodeCollisionError("Failed to generate unique anonymous code after 20 attempts")
