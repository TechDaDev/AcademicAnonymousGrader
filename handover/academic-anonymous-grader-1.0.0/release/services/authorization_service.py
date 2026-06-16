# Academic Anonymous Grader — Authorization Service
"""Centralized role-based permissions.

Each role has a set of granted permissions. The service provides helpers
to check access at both the UI and service layers.

Roles and their permissions:

**administrator**
  - All application functions
  - Create, edit, archive materials
  - Create, edit assessments and questions
  - Upload and preview HTML, XLSX, CSV
  - Import and map columns
  - Review and approve
  - Finalize assessments
  - Generate identity-bearing Excel exports
  - User management
  - Audit log access
  - Backups and restore

**grader** (displayed as Instructor)
  - View materials and assessments (read-only, as needed for grading)
  - Grade anonymous submissions
  - Enter feedback, save drafts
  - Correct grades before finalization
  - No import, no export, no user management
  - Never sees student identity

**reviewer** (legacy — not assignable to new users)
  - Read-only anonymous summaries
  - No grading, review, finalization, import, or export

**exporter** (legacy — not assignable to new users)
  - View finalized assessments
  - No identity restoration

**viewer** (legacy — not assignable to new users)
  - Read-only anonymous summaries
  - No grading, review, finalization, import, or export
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.exceptions import InsufficientPermissionsError


@dataclass(frozen=True)
class AuthContext:
    """Lightweight authorization context passed to service functions.

    Never stores the ORM User object, password, or password hash.
    Created from Streamlit session state or test fixtures.
    """

    user_id: str = ""
    username: str = ""
    role: str = ""
    display_name: str | None = None

# ---------------------------------------------------------------------------
# Permission definitions
# ---------------------------------------------------------------------------

# Materials
PERM_CREATE_MATERIAL = "create_material"
PERM_EDIT_MATERIAL = "edit_material"
PERM_ARCHIVE_MATERIAL = "archive_material"
PERM_VIEW_MATERIAL = "view_material"

# Assessments
PERM_CREATE_ASSESSMENT = "create_assessment"
PERM_EDIT_ASSESSMENT = "edit_assessment"
PERM_ARCHIVE_ASSESSMENT = "archive_assessment"
PERM_VIEW_ASSESSMENT = "view_assessment"

# Import
PERM_IMPORT_PREVIEW = "import_preview"
PERM_IMPORT_EXECUTE = "import_execute"

# Grading
PERM_GRADE_SUBMISSION = "grade_submission"
PERM_VIEW_GRADES = "view_grades"

# Review
PERM_REVIEW_SUBMISSION = "review_submission"
PERM_APPROVE_SUBMISSION = "approve_submission"
PERM_RETURN_TO_GRADING = "return_to_grading"

# Finalization
PERM_FINALIZE_ASSESSMENT = "finalize_assessment"
PERM_VIEW_FINALIZED = "view_finalized"

# Export
PERM_GENERATE_EXPORT = "generate_export"
PERM_DOWNLOAD_EXPORT = "download_export"
PERM_EXPORT_IDENTITY = "export_identity"

# User management
PERM_MANAGE_USERS = "manage_users"

# Audit
PERM_VIEW_AUDIT = "view_audit"

# Backup
PERM_CREATE_BACKUP = "create_backup"
PERM_RESTORE_BACKUP = "restore_backup"

# Phase 10 — Instructor assignments
PERM_MANAGE_ASSIGNMENTS = "manage_assignments"
PERM_VIEW_ASSIGNMENTS = "view_assignments"

# Phase 12 — Analytics
PERM_VIEW_ANALYTICS = "view_analytics"
PERM_VIEW_ALL_ANALYTICS = "view_all_analytics"
PERM_VIEW_INSTRUCTOR_WORKLOAD = "view_instructor_workload"
PERM_EXPORT_ANALYTICS = "export_analytics"
PERM_CONFIGURE_ANALYTICS = "configure_analytics"

# Phase 12.1 — Academic Structure
PERM_MANAGE_ACADEMIC_STRUCTURE = "manage_academic_structure"
PERM_VIEW_ACADEMIC_STRUCTURE = "view_academic_structure"

# Viewer read-only
PERM_VIEW_DASHBOARD = "view_dashboard"

# ---------------------------------------------------------------------------
# Role-permission mapping
# ---------------------------------------------------------------------------

_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "administrator": {
        PERM_CREATE_MATERIAL,
        PERM_EDIT_MATERIAL,
        PERM_ARCHIVE_MATERIAL,
        PERM_VIEW_MATERIAL,
        PERM_CREATE_ASSESSMENT,
        PERM_EDIT_ASSESSMENT,
        PERM_ARCHIVE_ASSESSMENT,
        PERM_VIEW_ASSESSMENT,
        PERM_IMPORT_PREVIEW,
        PERM_IMPORT_EXECUTE,
        PERM_GRADE_SUBMISSION,
        PERM_VIEW_GRADES,
        PERM_REVIEW_SUBMISSION,
        PERM_APPROVE_SUBMISSION,
        PERM_RETURN_TO_GRADING,
        PERM_FINALIZE_ASSESSMENT,
        PERM_VIEW_FINALIZED,
        PERM_GENERATE_EXPORT,
        PERM_DOWNLOAD_EXPORT,
        PERM_EXPORT_IDENTITY,
        PERM_MANAGE_USERS,
        PERM_VIEW_AUDIT,
        PERM_CREATE_BACKUP,
        PERM_RESTORE_BACKUP,
        PERM_MANAGE_ASSIGNMENTS,
        PERM_VIEW_ASSIGNMENTS,
        PERM_VIEW_ANALYTICS,
        PERM_VIEW_ALL_ANALYTICS,
        PERM_VIEW_INSTRUCTOR_WORKLOAD,
        PERM_EXPORT_ANALYTICS,
        PERM_CONFIGURE_ANALYTICS,
        PERM_VIEW_DASHBOARD,
        PERM_MANAGE_ACADEMIC_STRUCTURE,
        PERM_VIEW_ACADEMIC_STRUCTURE,
    },
    "grader": {
        # Instructor — only anonymous grading and read-only access
        PERM_VIEW_MATERIAL,
        PERM_VIEW_ASSESSMENT,
        PERM_GRADE_SUBMISSION,
        PERM_VIEW_GRADES,
        PERM_VIEW_FINALIZED,
        PERM_VIEW_ANALYTICS,
        PERM_VIEW_DASHBOARD,
    },
    "reviewer": {
        # Legacy role — not assignable to new users
        PERM_VIEW_MATERIAL,
        PERM_VIEW_ASSESSMENT,
        PERM_VIEW_GRADES,
        PERM_VIEW_FINALIZED,
        PERM_VIEW_DASHBOARD,
    },
    "exporter": {
        # Legacy role — not assignable to new users
        PERM_VIEW_MATERIAL,
        PERM_VIEW_ASSESSMENT,
        PERM_VIEW_FINALIZED,
        PERM_GENERATE_EXPORT,
        PERM_DOWNLOAD_EXPORT,
        PERM_VIEW_DASHBOARD,
    },
    "viewer": {
        # Legacy role — not assignable to new users
        PERM_VIEW_MATERIAL,
        PERM_VIEW_ASSESSMENT,
        PERM_VIEW_DASHBOARD,
    },
}

# ---------------------------------------------------------------------------
# Page access mappings
# ---------------------------------------------------------------------------

_PAGE_ROLES: dict[str, set[str]] = {
    "app": {"administrator", "grader", "reviewer", "exporter", "viewer"},
    "Materials": {"administrator"},
    "Assessments": {"administrator"},
    "Import": {"administrator"},
    "Grading": {"administrator", "grader"},
    "Review": {"administrator"},
    "Export": {"administrator"},
    "Users": {"administrator"},
    "Audit": {"administrator"},
    "Backup": {"administrator"},
    "Settings": {"administrator"},  # Only admins access security-related settings
    "InstructorAssignments": {"administrator"},
    "Analytics": {"administrator", "grader"},
    "AcademicStructure": {"administrator"},
}


def get_permissions_for_role(role: str) -> set[str]:
    """Return the set of permissions granted to a role.

    Parameters
    ----------
    role : str
        Role name.

    Returns
    -------
    set[str]
        Set of permission strings. Returns empty set for unknown roles.
    """
    return _ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, permission: str) -> bool:
    """Check whether a role has a specific permission.

    Parameters
    ----------
    role : str
        Role name.
    permission : str
        Permission string.

    Returns
    -------
    bool
        True if the role has the permission.
    """
    return permission in _ROLE_PERMISSIONS.get(role, set())


def require_permission(role: str, permission: str) -> None:
    """Require that a role has a specific permission.

    Parameters
    ----------
    role : str
        Role name.
    permission : str
        Permission string.

    Raises
    ------
    InsufficientPermissionsError
        If the role lacks the permission.
    """
    if not has_permission(role, permission):
        raise InsufficientPermissionsError(
            f"Role '{role}' does not have permission '{permission}'."
        )


def require_role(role: str, allowed_roles: set[str]) -> None:
    """Require that a role is in the allowed set.

    Parameters
    ----------
    role : str
        Role to check.
    allowed_roles : set[str]
        Set of allowed roles.

    Raises
    ------
    InsufficientPermissionsError
        If the role is not in the allowed set.
    """
    if role not in allowed_roles:
        raise InsufficientPermissionsError(
            f"Role '{role}' does not have access. Required one of: {sorted(allowed_roles)}."
        )


def can_access_page(role: str, page_name: str) -> bool:
    """Check whether a role can access a given page.

    Parameters
    ----------
    role : str
        Role name.
    page_name : str
        Page name (e.g., 'Grading', 'Export').

    Returns
    -------
    bool
        True if the role can access the page.
    """
    allowed = _PAGE_ROLES.get(page_name)
    if allowed is None:
        return False
    return role in allowed


def require_page_access(role: str, page_name: str) -> None:
    """Require that a role can access a page.

    In Streamlit context, shows a safe error and stops execution.
    In non-Streamlit context, raises InsufficientPermissionsError.

    Parameters
    ----------
    role : str
        Role name.
    page_name : str
        Page name.
    """
    if not can_access_page(role, page_name):
        try:
            import streamlit as st

            from ui.layout import render_safe_error

            render_safe_error(
                f"Access denied: Role '{role}' does not have access to '{page_name}'."
            )
            st.stop()
        except ImportError:
            raise InsufficientPermissionsError(
                f"Role '{role}' does not have access to '{page_name}'."
            )


def can_modify_assessment(role: str) -> bool:
    """Check whether a role can modify assessments.

    Parameters
    ----------
    role : str
        Role name.

    Returns
    -------
    bool
        True if the role can modify assessments.
    """
    return has_permission(role, PERM_EDIT_ASSESSMENT)


def can_export_identity_data(role: str) -> bool:
    """Check whether a role can export decrypted identity data.

    Parameters
    ----------
    role : str
        Role name.

    Returns
    -------
    bool
        True if the role can export identity data.
    """
    return has_permission(role, PERM_EXPORT_IDENTITY)


def get_session_user_role(session_state: Any) -> str:
    """Get the role from Streamlit session state.

    Parameters
    ----------
    session_state : dict-like
        Streamlit session state.

    Returns
    -------
    str
        Role string. Returns 'anonymous' if not authenticated.
    """
    if session_state.get("authenticated") and session_state.get("role"):
        role_val = session_state.get("role")
        return str(role_val) if role_val is not None else "anonymous"
    return "anonymous"


def is_authenticated(session_state: Any) -> bool:
    """Check whether the session has an authenticated user.

    Parameters
    ----------
    session_state : dict-like
        Streamlit session state.

    Returns
    -------
    bool
        True if authenticated.
    """
    return bool(session_state.get("authenticated")) and bool(session_state.get("user_id"))


def get_auth_context(session_state: Any) -> AuthContext:
    """Build an AuthContext from Streamlit session state.

    Parameters
    ----------
    session_state : dict-like
        Streamlit session state.

    Returns
    -------
    AuthContext
        Authorization context. Returns empty AuthContext if not authenticated.
    """
    if not is_authenticated(session_state):
        return AuthContext()
    return AuthContext(
        user_id=str(session_state.get("user_id", "")),
        username=str(session_state.get("username", "")),
        role=str(session_state.get("role", "")),
        display_name=session_state.get("display_name"),
    )


def authorize(role: str, permission: str) -> None:
    """Check that a role has a specific permission.

    Parameters
    ----------
    role : str
        Role to check.
    permission : str
        Required permission constant.

    Raises
    ------
    InsufficientPermissionsError
        If the role lacks the permission.
    """
    require_permission(role, permission)


def authorize_context(ctx: AuthContext, permission: str) -> None:
    """Check that an AuthContext grants a specific permission.

    Parameters
    ----------
    ctx : AuthContext
        Authorization context.
    permission : str
        Required permission constant.

    Raises
    ------
    InsufficientPermissionsError
        If the context's role lacks the permission.
    """
    require_permission(ctx.role, permission)


def require_role_is(ctx: AuthContext, *roles: str) -> None:
    """Require that the AuthContext's role matches one of the given roles.

    Parameters
    ----------
    ctx : AuthContext
        Authorization context.
    *roles : str
        One or more allowed role names.

    Raises
    ------
    InsufficientPermissionsError
        If the context's role is not in the allowed set.
    """
    if ctx.role not in roles:
        raise InsufficientPermissionsError(
            f"Role '{ctx.role}' is not permitted. Required one of: {sorted(roles)}."
        )


# ── Role display helpers ──────────────────────────────────────────

LEGACY_ROLES: frozenset[str] = frozenset({"reviewer", "exporter", "viewer"})

ASSIGNABLE_ROLES: list[tuple[str, str]] = [
    ("administrator", "Administrator"),
    ("grader", "Instructor"),
]


def get_assignable_roles() -> list[tuple[str, str]]:
    """Return roles available for new user creation.

    Returns
    -------
    list[tuple[str, str]]
        List of (internal_role, display_name) tuples.
        Only 'Administrator' and 'Instructor' are assignable.
    """
    return list(ASSIGNABLE_ROLES)


def display_role(role: str) -> str:
    """Get the user-facing name for an internal role.

    Parameters
    ----------
    role : str
        Internal role string (e.g. 'grader', 'administrator').

    Returns
    -------
    str
        Display name (e.g. 'Instructor', 'Administrator').
    """
    display_map: dict[str, str] = {
        "administrator": "Administrator",
        "grader": "Instructor",
        "reviewer": "Reviewer (legacy)",
        "exporter": "Exporter (legacy)",
        "viewer": "Viewer (legacy)",
    }
    return display_map.get(role, role.capitalize())


def is_legacy_role(role: str) -> bool:
    """Check whether a role is a legacy role no longer assignable.

    Parameters
    ----------
    role : str
        Internal role string.

    Returns
    -------
    bool
        True if the role is legacy.
    """
    return role in LEGACY_ROLES
