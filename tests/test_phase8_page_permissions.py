# Academic Anonymous Grader — Phase 8 Page Permission Tests
"""Tests that page access control is enforced for each role."""

from __future__ import annotations

from typing import Any

import pytest

from services.authorization_service import (
    can_access_page,
    is_authenticated,
)


class TestPagePermissions:
    """Verify every role's page access matrix."""

    # (role, page, should_have_access)
    _MATRIX = [
        # Admin can access everything
        ("administrator", "Materials", True),
        ("administrator", "Assessments", True),
        ("administrator", "Import", True),
        ("administrator", "Grading", True),
        ("administrator", "Review", True),
        ("administrator", "Export", True),
        ("administrator", "Users", True),
        ("administrator", "Audit", True),
        ("administrator", "Backup", True),
        ("administrator", "Settings", True),
        # Instructor (grader) can only access dashboard and grading
        ("grader", "Materials", False),
        ("grader", "Assessments", False),
        ("grader", "Import", False),
        ("grader", "Grading", True),
        ("grader", "Review", False),
        ("grader", "Export", False),
        ("grader", "Users", False),
        ("grader", "Audit", False),
        ("grader", "Backup", False),
        ("grader", "Settings", False),
        # Reviewer (legacy) — read-only, no review/finalization powers
        ("reviewer", "Materials", False),
        ("reviewer", "Assessments", False),
        ("reviewer", "Import", False),
        ("reviewer", "Grading", False),
        ("reviewer", "Review", False),
        ("reviewer", "Export", False),
        ("reviewer", "Users", False),
        ("reviewer", "Audit", False),
        ("reviewer", "Backup", False),
        ("reviewer", "Settings", False),
        # Exporter (legacy) — no export or identity access
        ("exporter", "Materials", False),
        ("exporter", "Assessments", False),
        ("exporter", "Import", False),
        ("exporter", "Grading", False),
        ("exporter", "Review", False),
        ("exporter", "Export", False),
        ("exporter", "Users", False),
        ("exporter", "Audit", False),
        ("exporter", "Backup", False),
        ("exporter", "Settings", False),
        # Viewer (legacy) — dashboard only
        ("viewer", "Materials", False),
        ("viewer", "Assessments", False),
        ("viewer", "Import", False),
        ("viewer", "Grading", False),
        ("viewer", "Review", False),
        ("viewer", "Export", False),
        ("viewer", "Users", False),
        ("viewer", "Audit", False),
        ("viewer", "Backup", False),
        ("viewer", "Settings", False),
    ]

    @pytest.mark.parametrize("role,page,expected", _MATRIX)
    def test_page_access_matrix(self, role: str, page: str, expected: bool) -> None:
        """Page access matrix is enforced for all roles."""
        result = can_access_page(role, page)
        assert result == expected, f"Role '{role}' access to '{page}' should be {expected}"

    def test_direct_unauthorized_url_blocked(self) -> None:
        """Direct access to an unauthorized page is blocked (can_access_page returns False)."""
        from services.authorization_service import can_access_page

        assert can_access_page("grader", "Users") is False
        assert can_access_page("grader", "Import") is False
        assert can_access_page("grader", "Export") is False
        assert can_access_page("grader", "Materials") is False
        assert can_access_page("grader", "Assessments") is False
        assert can_access_page("grader", "Review") is False
        assert can_access_page("viewer", "Export") is False
        assert can_access_page("viewer", "Grading") is False

    def test_authorized_url_passes(self) -> None:
        """Authorized page access is granted."""
        from services.authorization_service import can_access_page

        assert can_access_page("administrator", "Backup") is True
        assert can_access_page("administrator", "Import") is True
        assert can_access_page("administrator", "Export") is True
        assert can_access_page("administrator", "Users") is True
        assert can_access_page("grader", "Grading") is True
        """Anonymous users have no page access to protected pages."""
        assert can_access_page("anonymous", "Grading") is False
        assert can_access_page("anonymous", "Export") is False
        assert can_access_page("anonymous", "Users") is False

    def test_is_authenticated_requires_both_keys(self) -> None:
        """is_authenticated checks session state (tested via mock)."""
        # Test the function logic directly
        class FakeState:
            def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
                state = {
                    "authenticated": True,
                    "user_id": "test-user",
                }
                return state.get(key, default)

        result = is_authenticated(FakeState())
        assert result is True

        # Test with missing user_id
        class MissingState:
            def get(self, key: str, default: Any = None) -> Any:  # noqa: ANN401
                state = {
                    "authenticated": True,
                }
                return state.get(key, default)

        result = is_authenticated(MissingState())
        assert result is False
