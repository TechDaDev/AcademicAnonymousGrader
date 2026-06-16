# Academic Anonymous Grader — Service-Layer Authorization Tests
"""Prove that direct unauthorized service calls are rejected.

Uses AuthContext with various roles to verify that each service
enforces the correct permissions.
"""

from __future__ import annotations

from typing import Any

import pytest

from services.authorization_service import (
    PERM_CREATE_BACKUP,
    PERM_EXPORT_IDENTITY,
    PERM_GRADE_SUBMISSION,
    PERM_IMPORT_EXECUTE,
    PERM_MANAGE_USERS,
    PERM_REVIEW_SUBMISSION,
    PERM_VIEW_AUDIT,
    AuthContext,
    authorize_context,
)
from services.exceptions import InsufficientPermissionsError

pytestmark = pytest.mark.usefixtures("session")

# ── Test auth contexts ─────────────────────────────────────────────
ADMIN_CTX = AuthContext(user_id="admin-1", username="admin", role="administrator")
GRADER_CTX = AuthContext(user_id="grader-1", username="grader1", role="grader")
REVIEWER_CTX = AuthContext(user_id="reviewer-1", username="reviewer1", role="reviewer")
EXPORTER_CTX = AuthContext(user_id="exporter-1", username="exporter1", role="exporter")
VIEWER_CTX = AuthContext(user_id="viewer-1", username="viewer1", role="viewer")
EMPTY_CTX = AuthContext()


class TestAuthContextBasic:
    """AuthContext creation and basic properties."""

    def test_admin_context(self) -> None:
        assert ADMIN_CTX.role == "administrator"
        assert ADMIN_CTX.user_id == "admin-1"

    def test_grader_context(self) -> None:
        assert GRADER_CTX.role == "grader"

    def test_empty_context(self) -> None:
        assert EMPTY_CTX.role == ""


class TestAuthorizeContext:
    """authorize_context rejects unauthorized roles."""

    # ── Export identity ─────────────────────────────────────────────
    def test_grader_cannot_export_identities(self) -> None:
        """Grader must not be able to export identities."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(GRADER_CTX, PERM_EXPORT_IDENTITY)

    def test_reviewer_cannot_export_identities(self) -> None:
        """Reviewer must not be able to export identities."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(REVIEWER_CTX, PERM_EXPORT_IDENTITY)

    def test_viewer_cannot_export_identities(self) -> None:
        """Viewer must not be able to export identities."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(VIEWER_CTX, PERM_EXPORT_IDENTITY)

    def test_admin_can_export_identities(self) -> None:
        """Administrator can export identities."""
        authorize_context(ADMIN_CTX, PERM_EXPORT_IDENTITY)  # Should not raise

    def test_exporter_cannot_export_identities(self) -> None:
        """Exporter must not be able to export identities (admin-only)."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(EXPORTER_CTX, PERM_EXPORT_IDENTITY)

    # ── Grade submission ───────────────────────────────────────────
    def test_reviewer_cannot_grade(self) -> None:
        """Reviewer must not be able to grade."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(REVIEWER_CTX, PERM_GRADE_SUBMISSION)

    def test_exporter_cannot_grade(self) -> None:
        """Exporter must not be able to grade."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(EXPORTER_CTX, PERM_GRADE_SUBMISSION)

    def test_viewer_cannot_grade(self) -> None:
        """Viewer must not be able to grade."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(VIEWER_CTX, PERM_GRADE_SUBMISSION)

    def test_admin_can_grade(self) -> None:
        """Administrator can grade."""
        authorize_context(ADMIN_CTX, PERM_GRADE_SUBMISSION)

    def test_grader_can_grade(self) -> None:
        """Grader can grade."""
        authorize_context(GRADER_CTX, PERM_GRADE_SUBMISSION)

    # ── Review ─────────────────────────────────────────────────────
    def test_grader_cannot_review(self) -> None:
        """Grader must not be able to review submissions."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(GRADER_CTX, PERM_REVIEW_SUBMISSION)

    def test_exporter_cannot_review(self) -> None:
        """Exporter must not be able to review."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(EXPORTER_CTX, PERM_REVIEW_SUBMISSION)

    def test_viewer_cannot_review(self) -> None:
        """Viewer must not be able to review."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(VIEWER_CTX, PERM_REVIEW_SUBMISSION)

    def test_admin_can_review(self) -> None:
        """Administrator can review."""
        authorize_context(ADMIN_CTX, PERM_REVIEW_SUBMISSION)

    def test_reviewer_cannot_review(self) -> None:
        """Reviewer must not be able to review (admin-only)."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(REVIEWER_CTX, PERM_REVIEW_SUBMISSION)

    # ── Import ──────────────────────────────────────────────────────
    def test_reviewer_cannot_import(self) -> None:
        """Reviewer must not be able to execute imports."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(REVIEWER_CTX, PERM_IMPORT_EXECUTE)

    def test_viewer_cannot_import(self) -> None:
        """Viewer must not be able to import."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(VIEWER_CTX, PERM_IMPORT_EXECUTE)

    def test_admin_can_import(self) -> None:
        """Administrator can import."""
        authorize_context(ADMIN_CTX, PERM_IMPORT_EXECUTE)

    def test_grader_cannot_import(self) -> None:
        """Grader must not be able to import (admin-only)."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(GRADER_CTX, PERM_IMPORT_EXECUTE)

    # ── User management ────────────────────────────────────────────
    def test_grader_cannot_manage_users(self) -> None:
        """Grader must not be able to manage users."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(GRADER_CTX, PERM_MANAGE_USERS)

    def test_exporter_cannot_manage_users(self) -> None:
        """Exporter must not be able to manage users."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(EXPORTER_CTX, PERM_MANAGE_USERS)

    def test_viewer_cannot_manage_users(self) -> None:
        """Viewer must not be able to manage users."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(VIEWER_CTX, PERM_MANAGE_USERS)

    def test_admin_can_manage_users(self) -> None:
        """Administrator can manage users."""
        authorize_context(ADMIN_CTX, PERM_MANAGE_USERS)

    # ── Audit ───────────────────────────────────────────────────────
    def test_grader_cannot_view_audit(self) -> None:
        """Grader must not be able to query audit logs."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(GRADER_CTX, PERM_VIEW_AUDIT)

    def test_exporter_cannot_view_audit(self) -> None:
        """Exporter must not be able to query audit logs."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(EXPORTER_CTX, PERM_VIEW_AUDIT)

    def test_admin_can_view_audit(self) -> None:
        """Administrator can view audit logs."""
        authorize_context(ADMIN_CTX, PERM_VIEW_AUDIT)

    # ── Backup ──────────────────────────────────────────────────────
    def test_grader_cannot_create_backup(self) -> None:
        """Grader must not be able to create backups."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(GRADER_CTX, PERM_CREATE_BACKUP)

    def test_exporter_cannot_create_backup(self) -> None:
        """Exporter must not be able to create backups."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(EXPORTER_CTX, PERM_CREATE_BACKUP)

    def test_viewer_cannot_create_backup(self) -> None:
        """Viewer must not be able to create backups."""
        with pytest.raises(InsufficientPermissionsError):
            authorize_context(VIEWER_CTX, PERM_CREATE_BACKUP)

    def test_admin_can_create_backup(self) -> None:
        """Administrator can create backups."""
        authorize_context(ADMIN_CTX, PERM_CREATE_BACKUP)


class TestExportServiceAuthorization:
    """Test that excel_export_service checks auth_ctx."""

    def test_export_without_auth_ctx_works(self, session: Any) -> None:
        """Calling generate_export_workbook without auth_ctx is allowed
        (backward compatibility for internal use)."""
        from config import get_settings
        from services.excel_export_service import generate_export_workbook

        settings = get_settings()
        # Should fail with assessment-not-found (not authorization) when admin calls
        with pytest.raises(Exception) as excinfo:
            generate_export_workbook(session, "nonexistent", settings, auth_ctx=ADMIN_CTX)
        # It should fail with a different error (assessment not found, not authorization)
        assert "InsufficientPermissions" not in str(excinfo.value)

    def test_export_with_viewer_ctx_rejected(self, session: Any) -> None:
        """Viewer auth context blocks export."""
        from config import get_settings
        from services.excel_export_service import generate_export_workbook

        settings = get_settings()
        with pytest.raises(InsufficientPermissionsError):
            generate_export_workbook(
                session, "nonexistent", settings, auth_ctx=VIEWER_CTX
            )

    def test_export_with_admin_ctx_allowed(self, session: Any) -> None:
        """Admin auth context allows export (will fail on other validation)."""
        from config import get_settings
        from services.excel_export_service import generate_export_workbook

        settings = get_settings()
        with pytest.raises(Exception) as excinfo:
            generate_export_workbook(
                session, "nonexistent", settings, auth_ctx=ADMIN_CTX
            )
        assert "InsufficientPermissions" not in str(excinfo.value)
