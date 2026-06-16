"""Tests for authorization integration in secure import (Phase 9)."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import MagicMock, patch

import pytest

from parsers.models import ParsedImport
from services.authorization_service import AuthContext
from services.exceptions import InsufficientPermissionsError
from services.secure_import_service import execute_secure_import


@pytest.fixture
def parsed_import() -> ParsedImport:
    """Minimal valid ParsedImport with identity and response columns."""
    from datetime import datetime

    from parsers.models import (
        ColumnClassification,
        ImportStatistics,
        ParsedColumn,
        ParsedResponse,
        ParsedStudentRow,
    )

    cols = (
        ParsedColumn(
            original_name="First Name",
            normalized_name="first name",
            index=0,
            classification=ColumnClassification.IDENTITY,
            mapped_field="first_name",
            is_required=True,
            confidence=1.0,
            warnings=(),
            response_number=None,
        ),
        ParsedColumn(
            original_name="Response 1",
            normalized_name="response 1",
            index=1,
            classification=ColumnClassification.RESPONSE,
            mapped_field="response_1",
            is_required=False,
            confidence=1.0,
            warnings=(),
            response_number=1,
        ),
    )
    rows = (
        ParsedStudentRow(
            row_number=2,
            first_name="Test",
            last_name=None,
            email=None,
            institutional_student_id=None,
            status=None,
            started=None,
            completed=None,
            duration_seconds=None,
            source_grade=None,
            raw_source_grade=None,
            source_grade_maximum=None,
            responses=(ParsedResponse(question_number=1, column_name="Response 1", text="Answer", is_blank=False),),
            unknown_values={},
            warnings=(),
            errors=(),
        ),
    )

    return ParsedImport(
        source_filename="test.xlsx",
        parser_name="xlsx",
        table_index=0,
        columns=cols,
        rows=rows,
        response_columns=(cols[1],),
        unknown_columns=(),
        warnings=(),
        errors=(),
        statistics=ImportStatistics(
            total_rows=1,
            valid_rows=1,
            warning_rows=0,
            error_rows=0,
            blank_response_count=0,
            response_column_count=1,
            duplicate_email_count=0,
        ),
        parse_started_at=datetime.now(UTC),
        parse_completed_at=datetime.now(UTC),
        source_format="xlsx",
    )


class TestSecureImportAuth:
    """Authorization enforcement in execute_secure_import."""

    @patch("services.secure_import_service.authorize_context")
    def test_admin_can_execute_import(
        self, mock_authorize: MagicMock, parsed_import: ParsedImport
    ) -> None:
        """Administrator context calls authorize_context with PERM_IMPORT_EXECUTE."""
        mock_sesh = MagicMock()
        mock_sesh.query.return_value.filter.return_value.first.return_value = None
        ctx = AuthContext(user_id="admin1", role="administrator")
        execute_secure_import(
            session=mock_sesh,
            parsed=parsed_import,
            assessment_id="new-id-5678",
            assessment_question_numbers=(1,),
            file_bytes=b"unique-test-data",
            source_filename="test.xlsx",
            table_index=None,
            auth_ctx=ctx,
        )
        mock_authorize.assert_called_once()

    @patch("services.secure_import_service.authorize_context")
    def test_unauthorized_role_raises(
        self, mock_authorize: MagicMock, parsed_import: ParsedImport
    ) -> None:
        """When authorization fails, InsufficientPermissionsError is raised."""
        mock_authorize.side_effect = InsufficientPermissionsError("Not authorized")
        mock_sesh = MagicMock()
        ctx = AuthContext(user_id="instructor1", role="grader")
        with pytest.raises(InsufficientPermissionsError):
            execute_secure_import(
                session=mock_sesh,
                parsed=parsed_import,
                assessment_id="new-id-5678",
                assessment_question_numbers=(1,),
                file_bytes=b"unique-test-data",
                source_filename="test.xlsx",
                table_index=None,
                auth_ctx=ctx,
            )

    @patch("services.secure_import_service.authorize_context")
    def test_auth_ctx_required_not_optional(
        self, mock_authorize: MagicMock, parsed_import: ParsedImport
    ) -> None:
        """Calling execute_secure_import without auth_ctx is a TypeError."""
        mock_sesh = MagicMock()
        with pytest.raises(TypeError):
            execute_secure_import(  # type: ignore[call-arg]
                session=mock_sesh,
                parsed=parsed_import,
                assessment_id="new-id-5678",
                assessment_question_numbers=(1,),
                file_bytes=b"unique-test-data",
                source_filename="test.xlsx",
                table_index=None,
                # auth_ctx intentionally omitted — should raise TypeError
            )
