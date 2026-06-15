"""Key validation — decode, validate lengths, reject reused keys."""

from __future__ import annotations

import base64
import os

from security.exceptions import (
    InvalidEncryptionKeyError,
    InvalidFingerprintKeyError,
    MissingEncryptionKeyError,
    MissingFingerprintKeyError,
    SameKeyError,
)
from security.models import EncryptionKey, FingerprintKey


def _decode_key(raw: str | None, name: str, expected_bytes: int) -> bytes:
    if not raw:
        if name == "IDENTITY_ENCRYPTION_KEY":
            raise MissingEncryptionKeyError(f"{name} is not set")
        raise MissingFingerprintKeyError(f"{name} is not set")
    try:
        decoded = base64.urlsafe_b64decode(raw)
    except Exception as exc:
        if name == "IDENTITY_ENCRYPTION_KEY":
            raise InvalidEncryptionKeyError(f"{name} is not valid base64") from exc
        raise InvalidFingerprintKeyError(f"{name} is not valid base64") from exc
    if len(decoded) < expected_bytes:
        if name == "IDENTITY_ENCRYPTION_KEY":
            raise InvalidEncryptionKeyError(
                f"{name} decoded length {len(decoded)} is less than {expected_bytes}"
            )
        raise InvalidFingerprintKeyError(
            f"{name} decoded length {len(decoded)} is less than {expected_bytes}"
        )
    return decoded


def load_encryption_key(raw: str | None) -> EncryptionKey:
    """Load and validate a 32-byte encryption key from URL-safe base64."""
    key_bytes = _decode_key(raw, "IDENTITY_ENCRYPTION_KEY", 32)
    return EncryptionKey(key_bytes)


def load_fingerprint_key(raw: str | None) -> FingerprintKey:
    """Load and validate a 32+ byte fingerprint key from URL-safe base64."""
    key_bytes = _decode_key(raw, "IDENTITY_FINGERPRINT_KEY", 32)
    return FingerprintKey(key_bytes)


def load_keys(
    enc_raw: str | None, fp_raw: str | None
) -> tuple[EncryptionKey, FingerprintKey]:
    """Load both keys and verify they are different."""
    enc_key = load_encryption_key(enc_raw)
    fp_key = load_fingerprint_key(fp_raw)
    if enc_key.key_bytes == fp_key.key_bytes:
        raise SameKeyError(
            "IDENTITY_ENCRYPTION_KEY and IDENTITY_FINGERPRINT_KEY must be different"
        )
    return enc_key, fp_key


def generate_encryption_key() -> str:
    """Generate a new URL-safe base64 32-byte encryption key."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def generate_fingerprint_key() -> str:
    """Generate a new URL-safe base64 32-byte fingerprint key."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()
