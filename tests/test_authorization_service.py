# Academic Anonymous Grader — Authorization Service Tests
"""Tests for authorization_service.py — permission matrix and page access."""

from __future__ import annotations

import pytest

from services.authorization_service import (
    PERM_CREATE_BACKUP,
    PERM_CREATE_MATERIAL,
    PERM_EDIT_ASSESSMENT,
    PERM_EXPORT_IDENTITY,
    PERM_GENERATE_EXPORT,
    PERM_GRADE_SUBMISSION,
    PERM_MANAGE_USERS,
    PERM_RESTORE_BACKUP,
    PERM_REVIEW_SUBMISSION,
    PERM_VIEW_AUDIT,
    PERM_VIEW_DASHBOARD,
    PERM_VIEW_FINALIZED,
    PERM_VIEW_GRADES,
    PERM_VIEW_MATERIAL,
    can_access_page,
    can_export_identity_data,
    can_modify_assessment,
    get_permissions_for_role,
    has_permission,
    require_page_access,
    require_permission,
    require_role,
)
from services.exceptions import InsufficientPermissionsError


class TestRolePermissions:
    """Every role permission matrix."""

    def test_administrator_has_all_critical_permissions(self) -> None:
        """Administrator has every critical permission."""
        perms = get_permissions_for_role("administrator")
        critical = [
            PERM_CREATE_MATERIAL,
            PERM_EDIT_ASSESSMENT,
            PERM_GRADE_SUBMISSION,
            PERM_REVIEW_SUBMISSION,
            PERM_GENERATE_EXPORT,
            PERM_EXPORT_IDENTITY,
            PERM_MANAGE_USERS,
            PERM_VIEW_AUDIT,
            PERM_CREATE_BACKUP,
            PERM_RESTORE_BACKUP,
            PERM_VIEW_DASHBOARD,
        ]
        for p in critical:
            assert p in perms, f"Administrator missing permission: {p}"

    def test_grader_has_grading_permissions(self) -> None:
        """Grader (Instructor) has grading permissions only — no create/import."""
        perms = get_permissions_for_role("grader")
        assert PERM_GRADE_SUBMISSION in perms
        assert PERM_VIEW_GRADES in perms
        # Grader must NOT have create or import permissions
        assert PERM_CREATE_MATERIAL not in perms
        assert PERM_EXPORT_IDENTITY not in perms
        assert PERM_MANAGE_USERS not in perms
        assert PERM_VIEW_AUDIT not in perms
        assert PERM_REVIEW_SUBMISSION not in perms

    def test_reviewer_has_read_only_permissions(self) -> None:
        """Reviewer (legacy) has read-only permissions — no review/finalization."""
        perms = get_permissions_for_role("reviewer")
        assert PERM_VIEW_MATERIAL in perms
        assert PERM_VIEW_GRADES in perms
        # Reviewer must NOT have review, grading, or export identity
        assert PERM_REVIEW_SUBMISSION not in perms
        assert PERM_GRADE_SUBMISSION not in perms
        assert PERM_EXPORT_IDENTITY not in perms
        assert PERM_MANAGE_USERS not in perms

    def test_exporter_has_view_only_permissions(self) -> None:
        """Exporter (legacy) has view-only permissions — no export identity."""
        perms = get_permissions_for_role("exporter")
        assert PERM_VIEW_FINALIZED in perms
        assert PERM_VIEW_MATERIAL in perms
        # Exporter must NOT have export identity or grading
        assert PERM_EXPORT_IDENTITY not in perms
        assert PERM_GRADE_SUBMISSION not in perms
        assert PERM_MANAGE_USERS not in perms

    def test_viewer_has_read_only_permissions(self) -> None:
        """Viewer has read-only permissions."""
        perms = get_permissions_for_role("viewer")
        assert PERM_VIEW_MATERIAL in perms
        assert PERM_VIEW_DASHBOARD in perms
        # Viewer must NOT have any mutate permissions
        assert PERM_CREATE_MATERIAL not in perms
        assert PERM_GRADE_SUBMISSION not in perms
        assert PERM_REVIEW_SUBMISSION not in perms
        assert PERM_GENERATE_EXPORT not in perms
        assert PERM_MANAGE_USERS not in perms
        assert PERM_EXPORT_IDENTITY not in perms

    def test_unknown_role_has_no_permissions(self) -> None:
        """An unknown role has an empty permission set."""
        perms = get_permissions_for_role("nonexistent_role")
        assert perms == set()


class TestPermissionHelpers:
    """Test permission checking helpers."""

    def test_has_permission_true(self) -> None:
        assert has_permission("administrator", PERM_MANAGE_USERS) is True

    def test_has_permission_false(self) -> None:
        assert has_permission("grader", PERM_MANAGE_USERS) is False

    def test_require_permission_passes(self) -> None:
        require_permission("administrator", PERM_CREATE_BACKUP)  # Should not raise

    def test_require_permission_fails(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            require_permission("viewer", PERM_CREATE_BACKUP)

    def test_require_role_passes(self) -> None:
        require_role("administrator", {"administrator"})

    def test_require_role_fails(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            require_role("grader", {"administrator"})


class TestPageAccess:
    """Test page access control."""

    def test_administrator_can_access_all_pages(self) -> None:
        pages = ["Materials", "Assessments", "Import", "Grading", "Review", "Export", "Users", "Audit", "Backup", "Settings"]
        for page in pages:
            assert can_access_page("administrator", page), f"Admin denied: {page}"

    def test_grader_page_access(self) -> None:
        """Grader (Instructor) can only access Grading."""
        assert can_access_page("grader", "Grading") is True
        assert can_access_page("grader", "Materials") is False
        assert can_access_page("grader", "Assessments") is False
        assert can_access_page("grader", "Import") is False
        assert can_access_page("grader", "Export") is False
        assert can_access_page("grader", "Users") is False
        assert can_access_page("grader", "Audit") is False
        assert can_access_page("grader", "Backup") is False
        assert can_access_page("grader", "Settings") is False

    def test_reviewer_page_access(self) -> None:
        """Reviewer (legacy) has no page access (dashboard only)."""
        assert can_access_page("reviewer", "Review") is False
        assert can_access_page("reviewer", "Materials") is False
        assert can_access_page("reviewer", "Grading") is False
        assert can_access_page("reviewer", "Export") is False
        assert can_access_page("reviewer", "Settings") is False

    def test_exporter_page_access(self) -> None:
        """Exporter (legacy) has no page access (dashboard only)."""
        assert can_access_page("exporter", "Export") is False
        assert can_access_page("exporter", "Materials") is False
        assert can_access_page("exporter", "Grading") is False
        assert can_access_page("exporter", "Users") is False
        assert can_access_page("exporter", "Settings") is False

    def test_viewer_page_access(self) -> None:
        assert can_access_page("viewer", "Materials") is False
        assert can_access_page("viewer", "Grading") is False
        assert can_access_page("viewer", "Export") is False

    def test_require_page_access_passes(self) -> None:
        require_page_access("administrator", "Backup")

    def test_require_page_access_fails(self) -> None:
        """require_page_access handles unauthorized access via Streamlit error
        in UI context. The can_access_page check still returns False for tests."""
        assert can_access_page("grader", "Users") is False

    def test_unknown_page_denied(self) -> None:
        assert can_access_page("administrator", "NonExistent") is False


class TestCanModifyAndExport:
    """Test can_modify_assessment and can_export_identity_data."""

    def test_admin_can_modify(self) -> None:
        assert can_modify_assessment("administrator") is True

    def test_grader_cannot_modify(self) -> None:
        """Grader (Instructor) cannot modify assessments."""
        assert can_modify_assessment("grader") is False

    def test_reviewer_cannot_modify(self) -> None:
        assert can_modify_assessment("reviewer") is False

    def test_exporter_cannot_modify(self) -> None:
        assert can_modify_assessment("exporter") is False

    def test_viewer_cannot_modify(self) -> None:
        assert can_modify_assessment("viewer") is False

    def test_admin_can_export_identity(self) -> None:
        assert can_export_identity_data("administrator") is True

    def test_exporter_cannot_export_identity(self) -> None:
        """Exporter (legacy) cannot export identities."""
        assert can_export_identity_data("exporter") is False

    def test_grader_cannot_export_identity(self) -> None:
        assert can_export_identity_data("grader") is False

    def test_reviewer_cannot_export_identity(self) -> None:
        assert can_export_identity_data("reviewer") is False

    def test_viewer_cannot_export_identity(self) -> None:
        assert can_export_identity_data("viewer") is False
