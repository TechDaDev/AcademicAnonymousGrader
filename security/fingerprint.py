"""HMAC-SHA256 identity fingerprinting with domain separation."""

from __future__ import annotations

import hashlib
import hmac
import unicodedata

from security.models import FingerprintKey


def _normalize(value: str | None) -> str:
    """Unicode-normalize and strip whitespace."""
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", value).strip()


def normalize_student_id(value: str | None) -> str:
    """Normalize institutional student ID."""
    return _normalize(value)


def normalize_email(value: str | None) -> str:
    """Normalize email: trim, NFKC normalize, lowercase."""
    if value is None:
        return ""
    return _normalize(value).casefold()


def _domain_fingerprint(domain: str, normalized: str, key: FingerprintKey) -> str | None:
    """Generate domain-separated HMAC-SHA256 fingerprint or None for empty input."""
    if not normalized:
        return None
    message = f"{domain}:{normalized}".encode()
    digest = hmac.new(key.key_bytes, message, hashlib.sha256).hexdigest()
    return digest


def fingerprint_email(email: str | None, key: FingerprintKey) -> str | None:
    """Generate domain-separated fingerprint for an email address."""
    return _domain_fingerprint("email:v1", normalize_email(email), key)


def fingerprint_institutional_id(student_id: str | None, key: FingerprintKey) -> str | None:
    """Generate domain-separated fingerprint for an institutional student ID."""
    return _domain_fingerprint("student_id:v1", normalize_student_id(student_id), key)
