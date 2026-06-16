# Academic Anonymous Grader — Authentication Service Tests
"""Tests for auth_service.py — user creation, login, password security."""

from __future__ import annotations

from typing import Any

import pytest

from services.auth_service import (
    authenticate_user,
    change_password,
    create_user,
    deactivate_user,
    get_current_user_summary,
    list_users,
    reactivate_user,
    unlock_user,
    verify_password_strength,
)
from services.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    DuplicateUsernameError,
    InvalidCredentialsError,
    WeakPasswordError,
)

pytestmark = pytest.mark.usefixtures("session")


def _count_users(session: Any) -> int:
    from models.user import User

    result = session.query(User).count()
    return int(result)


# ── create_user ──────────────────────────────────────────────────────────


def test_create_user(session: Any) -> None:
    """A user can be created with valid credentials."""
    user = create_user(session, "alice", "Passw0rd", role="grader", display_name="Alice")
    assert user.username == "alice"
    assert user.role == "grader"
    assert user.display_name == "Alice"
    assert user.is_active is True
    assert user.failed_login_attempts == 0
    assert user.password_hash != "Passw0rd"
    assert len(user.password_hash) > 10


def test_create_user_normalizes_username(session: Any) -> None:
    """Usernames are normalized to lowercase."""
    user = create_user(session, "AliceAdmin", "Passw0rd", role="administrator")
    assert user.username == "aliceadmin"


def test_create_user_duplicate_rejected(session: Any) -> None:
    """Duplicate usernames (case-insensitive) are rejected."""
    create_user(session, "bob", "Passw0rd", role="viewer")
    with pytest.raises(DuplicateUsernameError):
        create_user(session, "BOB", "Passw0rd2", role="grader")


def test_create_user_weak_password_rejected(session: Any) -> None:
    """Weak passwords are rejected."""
    with pytest.raises(WeakPasswordError):
        create_user(session, "charlie", "short", role="viewer")


def test_create_user_no_uppercase_rejected(session: Any) -> None:
    """Passwords without uppercase are rejected."""
    with pytest.raises(WeakPasswordError):
        create_user(session, "dave", "lowercase1", role="viewer")


def test_create_user_no_digit_rejected(session: Any) -> None:
    """Passwords without digits are rejected."""
    with pytest.raises(WeakPasswordError):
        create_user(session, "eve", "Passwordd", role="viewer")


def test_create_user_invalid_role(session: Any) -> None:
    """Invalid roles are rejected."""
    with pytest.raises(ValueError, match="Invalid role"):
        create_user(session, "frank", "Passw0rd", role="superadmin")


# ── password_hashing ────────────────────────────────────────────────────


def test_password_is_hashed(session: Any) -> None:
    """Password is stored as a bcrypt hash, not plaintext."""
    user = create_user(session, "grace", "Passw0rd", role="grader")
    assert user.password_hash != "Passw0rd"
    assert user.password_hash.startswith("$2b$")


def test_plaintext_password_not_in_db(session: Any) -> None:
    """Plaintext password must not appear anywhere in the stored hash string."""
    user = create_user(session, "heidi", "Passw0rd", role="viewer")
    assert "Passw0rd" not in user.password_hash


# ── authenticate_user ────────────────────────────────────────────────────


def test_authenticate_valid(session: Any) -> None:
    """A valid username/password combination succeeds."""
    create_user(session, "ivan", "Passw0rd", role="grader")
    user = authenticate_user(session, "ivan", "Passw0rd")
    assert user is not None
    assert user.username == "ivan"


def test_authenticate_wrong_password(session: Any) -> None:
    """Wrong password raises InvalidCredentialsError."""
    create_user(session, "judy", "Passw0rd", role="grader")
    with pytest.raises(InvalidCredentialsError, match="Invalid username or password"):
        authenticate_user(session, "judy", "wrongpass1")


def test_authenticate_nonexistent_user(session: Any) -> None:
    """Nonexistent username raises a generic error (no enumeration)."""
    with pytest.raises(InvalidCredentialsError, match="Invalid username or password"):
        authenticate_user(session, "nonexistent", "Passw0rd")


def test_authenticate_case_insensitive_username(session: Any) -> None:
    """Username matching is case-insensitive."""
    create_user(session, "karl", "Passw0rd", role="viewer")
    user = authenticate_user(session, "KARL", "Passw0rd")
    assert user.username == "karl"


# ── disabled_account ────────────────────────────────────────────────────


def test_disabled_account_blocked(session: Any) -> None:
    """Disabled accounts cannot log in."""
    user = create_user(session, "leo", "Passw0rd", role="grader")
    deactivate_user(session, user.id, user.id)
    with pytest.raises(AccountDisabledError):
        authenticate_user(session, "leo", "Passw0rd")


# ── failed_attempts_and_lockout ──────────────────────────────────────────


def test_failed_attempts_increment(session: Any) -> None:
    """Failed login attempts increment."""
    create_user(session, "mallory", "Passw0rd", role="grader")
    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            authenticate_user(session, "mallory", "wrongpass1")
    from models.user import User

    user = session.query(User).filter(User.username == "mallory").first()
    assert user.failed_login_attempts >= 3


def test_lockout_activates(session: Any) -> None:
    """Account locks after sufficient failed attempts."""
    from models.user import MAX_FAILED_ATTEMPTS

    create_user(session, "nancy", "Passw0rd", role="grader")
    for _ in range(MAX_FAILED_ATTEMPTS):
        with pytest.raises(InvalidCredentialsError):
            authenticate_user(session, "nancy", "wrongpass1")
    with pytest.raises(AccountLockedError, match="Account is locked"):
        authenticate_user(session, "nancy", "Passw0rd")


def test_successful_login_resets_attempts(session: Any) -> None:
    """Successful login resets failed attempts counter."""
    create_user(session, "oscar", "Passw0rd", role="grader")
    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            authenticate_user(session, "oscar", "wrongpass1")
    # Successful login
    authenticate_user(session, "oscar", "Passw0rd")
    from models.user import User

    user = session.query(User).filter(User.username == "oscar").first()
    assert user.failed_login_attempts == 0
    assert user.is_locked is False


# ── password_change ──────────────────────────────────────────────────────


def test_change_password(session: Any) -> None:
    """Password change succeeds with correct current password."""
    user = create_user(session, "peggy", "Passw0rd", role="grader")
    change_password(session, user.id, "Passw0rd", "NewPass123")
    authenticate_user(session, "peggy", "NewPass123")


def test_old_password_rejected_after_change(session: Any) -> None:
    """Old password is rejected after change."""
    user = create_user(session, "quinn", "Passw0rd", role="grader")
    change_password(session, user.id, "Passw0rd", "NewPass123")
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(session, "quinn", "Passw0rd")


def test_change_password_wrong_current(session: Any) -> None:
    """Changing password with wrong current password is rejected."""
    user = create_user(session, "rob", "Passw0rd", role="grader")
    with pytest.raises(InvalidCredentialsError, match="Current password is incorrect"):
        change_password(session, user.id, "wrongpass1", "NewPass123")


def test_change_password_weak_new(session: Any) -> None:
    """New password must meet strength requirements."""
    user = create_user(session, "sarah", "Passw0rd", role="grader")
    with pytest.raises(WeakPasswordError):
        change_password(session, user.id, "Passw0rd", "short")


# ── deactivate / reactivate / unlock ────────────────────────────────────


def test_deactivate_user(session: Any) -> None:
    """Deactivating a user sets is_active to False."""
    user = create_user(session, "trent", "Passw0rd", role="grader")
    deactivate_user(session, user.id, user.id)
    from models.user import User

    u = session.query(User).filter(User.id == user.id).first()
    assert u.is_active is False


def test_reactivate_user(session: Any) -> None:
    """Reactivating a user restores is_active and resets attempts."""
    user = create_user(session, "ursula", "Passw0rd", role="viewer")
    deactivate_user(session, user.id, user.id)
    reactivate_user(session, user.id)
    from models.user import User

    u = session.query(User).filter(User.id == user.id).first()
    assert u.is_active is True
    assert u.failed_login_attempts == 0


def test_unlock_user(session: Any) -> None:
    """Unlocking a user resets attempts and lockout."""
    create_user(session, "victor", "Passw0rd", role="reviewer")
    from models.user import MAX_FAILED_ATTEMPTS

    for _ in range(MAX_FAILED_ATTEMPTS):
        with pytest.raises(InvalidCredentialsError):
            authenticate_user(session, "victor", "wrongpass1")
    from models.user import User

    user = session.query(User).filter(User.username == "victor").first()
    assert user.is_locked
    unlock_user(session, user.id)

    session.refresh(user)
    assert user.is_locked is False
    assert user.failed_login_attempts == 0


def test_deactivate_last_admin_blocked(session: Any) -> None:
    """Deactivating the last active administrator is blocked."""
    admin = create_user(session, "admin1", "Passw0rd", role="administrator")
    with pytest.raises(ValueError, match="last active administrator"):
        deactivate_user(session, admin.id, admin.id)


def test_deactivate_admin_with_another_active(session: Any) -> None:
    """Deactivating an admin when another active admin exists succeeds."""
    admin1 = create_user(session, "admin1", "Passw0rd", role="administrator")
    create_user(session, "admin2", "Passw0rd2", role="administrator")
    # Should not raise
    deactivate_user(session, admin1.id, admin1.id)


# ── list_users / get_current_user_summary ───────────────────────────────


def test_list_users(session: Any) -> None:
    """List users returns safe summaries without password or hash."""
    create_user(session, "wendy", "Passw0rd", role="grader", display_name="Wendy")
    create_user(session, "xavier", "Passw0rd2", role="viewer")
    summaries = list_users(session)
    assert len(summaries) >= 2
    for s in summaries:
        assert "password" not in s
        assert "password_hash" not in s
        assert "id" in s
        assert "username" in s
        assert "role" in s


def test_get_current_user_summary(session: Any) -> None:
    """get_current_user_summary returns safe dict."""
    user = create_user(session, "yvonne", "Passw0rd", role="reviewer")
    summary = get_current_user_summary(session, user.id)
    assert summary is not None
    assert summary["username"] == "yvonne"
    assert summary["role"] == "reviewer"
    assert "password" not in summary


def test_get_current_user_summary_not_found(session: Any) -> None:
    """Nonexistent user returns None."""
    result = get_current_user_summary(session, "nonexistent-id")
    assert result is None


# ── verify_password_strength ────────────────────────────────────────────


def test_verify_password_strength_valid() -> None:
    """A strong password passes verification."""
    verify_password_strength("Str0ngPass!")  # Should not raise


def test_verify_password_strength_too_short() -> None:
    """A short password is rejected."""
    with pytest.raises(WeakPasswordError, match="at least 8"):
        verify_password_strength("Sh0rt")


def test_verify_password_strength_no_uppercase() -> None:
    """Password without uppercase letter is rejected."""
    with pytest.raises(WeakPasswordError, match="uppercase"):
        verify_password_strength("alllowercase1")


def test_verify_password_strength_no_lowercase() -> None:
    """Password without lowercase letter is rejected."""
    with pytest.raises(WeakPasswordError, match="lowercase"):
        verify_password_strength("ALLUPPERCASE1")


def test_verify_password_strength_no_digit() -> None:
    """Password without digit is rejected."""
    with pytest.raises(WeakPasswordError, match="digit"):
        verify_password_strength("NoDigitsHere")
