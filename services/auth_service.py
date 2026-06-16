# Academic Anonymous Grader — Authentication Service
"""Local user authentication with bcrypt password hashing,
account lockout, and role-based user management.

SECURITY:
- Passwords hashed with bcrypt (never stored in plaintext)
- Constant-time verification via bcrypt.checkpw
- Generic login failure messages (no username enumeration)
- Failed-attempt counter with automatic lockout
- No password or hash logging
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import bcrypt

from services.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    DuplicateUsernameError,
    InvalidCredentialsError,
    UserNotFoundError,
    WeakPasswordError,
)

try:
    from models.user import LOCKOUT_DURATION_MINUTES, MAX_FAILED_ATTEMPTS, User
except ImportError:
    # Allow imports before model is fully initialized
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

# Minimum password requirements
MIN_PASSWORD_LENGTH = 8
MIN_UPPERCASE = 1
MIN_LOWERCASE = 1
MIN_DIGITS = 1

# Valid roles
VALID_ROLES = frozenset({"administrator", "grader", "reviewer", "exporter", "viewer"})


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt with a generated salt.

    Parameters
    ----------
    password : str
        Plaintext password to hash.

    Returns
    -------
    str
        bcrypt hash string.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash.

    Uses bcrypt.checkpw which provides constant-time comparison.

    Parameters
    ----------
    password : str
        Plaintext password to verify.
    password_hash : str
        Stored bcrypt hash.

    Returns
    -------
    bool
        True if password matches the hash.
    """
    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hash_bytes)


def verify_password_strength(password: str) -> None:
    """Validate password meets strength requirements.

    Parameters
    ----------
    password : str
        Password to validate.

    Raises
    ------
    WeakPasswordError
        If password does not meet requirements.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if sum(1 for c in password if c.isupper()) < MIN_UPPERCASE:
        raise WeakPasswordError(
            f"Password must contain at least {MIN_UPPERCASE} uppercase letter."
        )
    if sum(1 for c in password if c.islower()) < MIN_LOWERCASE:
        raise WeakPasswordError(
            f"Password must contain at least {MIN_LOWERCASE} lowercase letter."
        )
    if sum(1 for c in password if c.isdigit()) < MIN_DIGITS:
        raise WeakPasswordError(
            f"Password must contain at least {MIN_DIGITS} digit."
        )


def _normalize_username(username: str) -> str:
    """Normalize a username to lowercase with whitespace stripped."""
    return username.strip().lower()


def create_user(
    session: Any,
    username: str,
    password: str,
    role: str = "viewer",
    display_name: str | None = None,
) -> User:
    """Create a new user.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    username : str
        Unique username (case-insensitive, normalized).
    password : str
        Plaintext password (will be hashed before storage).
    role : str
        User role. Must be one of VALID_ROLES.
    display_name : str | None
        Optional display name.

    Returns
    -------
    User
        The newly created user.

    Raises
    ------
    WeakPasswordError
        If password does not meet strength requirements.
    DuplicateUsernameError
        If a user with this username already exists.
    ValueError
        If the role is invalid.
    """
    verify_password_strength(password)

    normalized = _normalize_username(username)

    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of {sorted(VALID_ROLES)}.")

    existing = session.query(User).filter(User.username == normalized).first()
    if existing is not None:
        raise DuplicateUsernameError(f"Username '{normalized}' is already taken.")

    password_hash = _hash_password(password)
    now = datetime.now(UTC)

    user = User(
        id=str(uuid.uuid4()),
        username=normalized,
        password_hash=password_hash,
        display_name=display_name,
        role=role,
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        last_login_at=None,
        password_changed_at=now,
        created_at=now,
        updated_at=None,
    )
    session.add(user)
    session.flush()
    return user


def authenticate_user(session: Any, username: str, password: str) -> User:
    """Authenticate a user by username and password.

    Uses constant-time password verification. Returns generic error
    messages to prevent username enumeration.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    username : str
        Username to authenticate.
    password : str
        Plaintext password.

    Returns
    -------
    User
        The authenticated user.

    Raises
    ------
    InvalidCredentialsError
        If username or password is invalid.
    AccountDisabledError
        If the account is disabled.
    AccountLockedError
        If the account is temporarily locked.
    """
    normalized = _normalize_username(username)
    user = session.query(User).filter(User.username == normalized).first()

    if user is None:
        # Generic message to prevent username enumeration
        raise InvalidCredentialsError("Invalid username or password.")

    # Check lockout before password verification
    if user.is_locked:
        remaining = user.lockout_remaining_minutes
        raise AccountLockedError(
            f"Account is locked. Try again in approximately {remaining} minute(s)."
        )

    # Verify password
    if not _verify_password(password, user.password_hash):
        user.increment_failed_attempts()
        session.flush()
        raise InvalidCredentialsError("Invalid username or password.")

    # Check if account is active
    if not user.is_active:
        raise AccountDisabledError("This account has been deactivated. Contact an administrator.")

    # Success — reset attempts and record login
    user.record_login()
    session.flush()
    return user  # type: ignore[no-any-return]


def change_password(
    session: Any,
    user_id: str,
    current_password: str,
    new_password: str,
) -> None:
    """Change a user's password.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    user_id : str
        ID of the user whose password to change.
    current_password : str
        Current password for verification.
    new_password : str
        New password.

    Raises
    ------
    UserNotFoundError
        If the user does not exist.
    InvalidCredentialsError
        If the current password is incorrect.
    WeakPasswordError
        If the new password does not meet strength requirements.
    """
    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        raise UserNotFoundError("User not found.")

    if not _verify_password(current_password, user.password_hash):
        raise InvalidCredentialsError("Current password is incorrect.")

    verify_password_strength(new_password)

    user.password_hash = _hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    session.flush()


def deactivate_user(session: Any, admin_user_id: str, target_user_id: str) -> None:
    """Deactivate a user account.

    Prevents deactivation of the last active administrator.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    admin_user_id : str
        ID of the administrator performing the action.
    target_user_id : str
        ID of the user to deactivate.

    Raises
    ------
    UserNotFoundError
        If the admin or target user does not exist.
    ValueError
        If trying to deactivate the last active administrator.
    """
    target = session.query(User).filter(User.id == target_user_id).first()
    if target is None:
        raise UserNotFoundError("User not found.")

    if target.role == "administrator":
        admin_count = (
            session.query(User)
            .filter(User.role == "administrator", User.is_active == True)  # noqa: E712
            .filter(User.id != target_user_id)
            .count()
        )
        if admin_count == 0:
            raise ValueError("Cannot deactivate the last active administrator.")

    target.is_active = False
    session.flush()


def reactivate_user(session: Any, target_user_id: str) -> None:
    """Reactivate a deactivated user account.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    target_user_id : str
        ID of the user to reactivate.

    Raises
    ------
    UserNotFoundError
        If the target user does not exist.
    """
    target = session.query(User).filter(User.id == target_user_id).first()
    if target is None:
        raise UserNotFoundError("User not found.")
    target.is_active = True
    target.reset_failed_attempts()
    session.flush()


def unlock_user(session: Any, target_user_id: str) -> None:
    """Unlock a locked user account.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    target_user_id : str
        ID of the user to unlock.

    Raises
    ------
    UserNotFoundError
        If the target user does not exist.
    """
    target = session.query(User).filter(User.id == target_user_id).first()
    if target is None:
        raise UserNotFoundError("User not found.")
    target.reset_failed_attempts()
    session.flush()


def change_user_role(
    session: Any,
    actor_user_id: str,
    target_user_id: str,
    new_role: str,
) -> None:
    """Change the role of a user.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    actor_user_id : str
        ID of the administrator performing the change.
    target_user_id : str
        ID of the user to update.
    new_role : str
        New role string.

    Raises
    ------
    UserNotFoundError
        If the target user does not exist.
    ValueError
        If the actor is trying to change their own role (last-admin protection).
    """
    from services.authorization_service import get_assignable_roles

    # Protect last active administrator
    if target_user_id == actor_user_id:
        raise ValueError("Cannot change your own role.")

    target = session.query(User).filter(User.id == target_user_id).first()
    if target is None:
        raise UserNotFoundError("User not found.")

    # Protect last active administrator from role downgrade
    if target.role == "administrator" and new_role != "administrator":
        admin_count = (
            session.query(User)
            .filter(User.role == "administrator", User.is_active == True)  # noqa: E712
            .filter(User.id != target_user_id)
            .count()
        )
        if admin_count == 0:
            raise ValueError(
                "Cannot downgrade the last active administrator. "
                "Promote another user to Administrator first."
            )

    # Validate role is assignable
    assignable_internal = [r for r, _ in get_assignable_roles()]
    if new_role not in assignable_internal:
        raise ValueError(f"Role '{new_role}' is not assignable. Must be one of: {assignable_internal}")

    target.role = new_role
    session.flush()


def list_users(session: Any) -> list[dict[str, Any]]:
    """List all users with safe summaries.

    Returns
    -------
    list[dict[str, Any]]
        List of user summaries. Never includes password or password hash.
    """
    users = session.query(User).order_by(User.username).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "is_locked": u.is_locked,
            "failed_login_attempts": u.failed_login_attempts,
            "last_login_at": u.last_login_at,
            "password_changed_at": u.password_changed_at,
            "created_at": u.created_at,
        }
        for u in users
    ]


def get_current_user_summary(session: Any, user_id: str) -> dict[str, Any] | None:
    """Get a summary of the current user.

    Parameters
    ----------
    session : Session
        SQLAlchemy database session.
    user_id : str
        User ID.

    Returns
    -------
    dict[str, Any] | None
        User summary dict or None if not found.
    """
    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "is_locked": user.is_locked,
        "last_login_at": user.last_login_at,
    }
