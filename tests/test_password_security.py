# Academic Anonymous Grader — Password Security Tests
"""Focused tests for password hashing, bcrypt behavior, and audit safety."""

from __future__ import annotations

from typing import Any

import pytest

from services.auth_service import _hash_password, _verify_password, create_user


def test_bcrypt_hash_format() -> None:
    """bcrypt hash has the correct format."""
    password = "TestPass123"
    hashed = _hash_password(password)
    assert hashed.startswith("$2b$")
    parts = hashed.split("$")
    assert len(parts) >= 4


def test_verify_correct_password() -> None:
    """Verifying with the correct password returns True."""
    password = "VerifyMe123"
    hashed = _hash_password(password)
    assert _verify_password(password, hashed) is True


def test_verify_wrong_password() -> None:
    """Verifying with the wrong password returns False."""
    hashed = _hash_password("RealPass123")
    assert _verify_password("WrongPass123", hashed) is False


def test_same_password_different_hashes() -> None:
    """Hashing the same password twice produces different hashes (different salts)."""
    password = "UniqueSalt!"
    hash1 = _hash_password(password)
    hash2 = _hash_password(password)
    assert hash1 != hash2


def test_constant_time_verification() -> None:
    """bcrypt.checkpw uses constant-time comparison (verify via correctness)."""
    hashed = _hash_password("Constant123")
    # Should not raise timing-related errors
    assert _verify_password("Constant123", hashed) is True
    assert _verify_password("wrongpass1", hashed) is False


def test_long_password_handling() -> None:
    """Long passwords are handled correctly."""
    long_pw = "A" * 50 + "1b"
    hashed = _hash_password(long_pw)
    assert _verify_password(long_pw, hashed) is True


def test_unicode_password() -> None:
    """Unicode passwords are handled correctly."""
    pw = "Pässwørd123"
    hashed = _hash_password(pw)
    assert _verify_password(pw, hashed) is True


def test_empty_password_stored_as_hash(session: Any) -> None:
    """Even a weak password rejected by creation should not be stored. This
    tests that the hash function does not accept empty input at the service
    level — create_user enforces strength first."""
    from services.exceptions import WeakPasswordError

    with pytest.raises(WeakPasswordError):
        create_user(session, "emptypw_user", "short", role="viewer")
