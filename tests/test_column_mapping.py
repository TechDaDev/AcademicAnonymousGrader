"""Column mapping validation tests."""

from __future__ import annotations

from parsers.models import ColumnClassification, ImportStatistics, ParsedColumn, ParsedImport
from services.import_preview_service import validate_mapping


def _make_import(columns: list[ParsedColumn]) -> ParsedImport:
    from datetime import datetime
    return ParsedImport(
        source_filename="test.html",
        parser_name="test",
        table_index=0,
        columns=tuple(columns),
        rows=(),
        response_columns=tuple(c for c in columns if c.classification is ColumnClassification.RESPONSE),
        unknown_columns=tuple(c for c in columns if c.classification is ColumnClassification.UNKNOWN),
        warnings=(),
        errors=(),
        statistics=ImportStatistics(
            total_rows=0, valid_rows=0, warning_rows=0, error_rows=0,
            blank_response_count=0, response_column_count=0,
            duplicate_email_count=0,
        ),
        parse_started_at=datetime.now(),
        parse_completed_at=datetime.now(),
    )


def _col(
    index: int, name: str, cls: ColumnClassification,
    mapped: str | None = None, rnum: int | None = None,
) -> ParsedColumn:
    return ParsedColumn(
        original_name=name,
        normalized_name=name,
        index=index,
        classification=cls,
        mapped_field=mapped,
        is_required=False,
        confidence=0.9,
        warnings=(),
        response_number=rnum,
    )


class TestMappingValidation:
    def test_valid_identity_and_responses(self) -> None:
        cols = [
            _col(0, "First name", ColumnClassification.IDENTITY, "first_name"),
            _col(1, "Last name", ColumnClassification.IDENTITY, "last_name"),
            _col(2, "Email", ColumnClassification.IDENTITY, "email"),
            _col(3, "R1", ColumnClassification.RESPONSE, "response_1", 1),
        ]
        v = validate_mapping(_make_import(cols))
        assert v.valid is True
        assert v.has_identity
        assert v.has_responses

    def test_duplicate_identity_mapping_warning(self) -> None:
        cols = [
            _col(0, "Name1", ColumnClassification.IDENTITY, "first_name"),
            _col(1, "Name2", ColumnClassification.IDENTITY, "first_name"),
            _col(2, "Email", ColumnClassification.IDENTITY, "email"),
            _col(3, "R1", ColumnClassification.RESPONSE, "response_1", 1),
        ]
        v = validate_mapping(_make_import(cols))
        assert "first_name" in v.duplicate_identity_fields
        # Duplicate identity should produce a warning, not a blocking error
        assert v.valid is True  # identity fields still present

    def test_duplicate_response_number_blocking(self) -> None:
        cols = [
            _col(0, "First name", ColumnClassification.IDENTITY, "first_name"),
            _col(1, "Email", ColumnClassification.IDENTITY, "email"),
            _col(2, "R1a", ColumnClassification.RESPONSE, "response_1", 1),
            _col(3, "R1b", ColumnClassification.RESPONSE, "response_1", 1),
        ]
        v = validate_mapping(_make_import(cols))
        assert 1 in v.duplicate_response_numbers
        assert v.valid is False

    def test_no_identity_blocking(self) -> None:
        cols = [
            _col(0, "R1", ColumnClassification.RESPONSE, "response_1", 1),
        ]
        v = validate_mapping(_make_import(cols))
        assert v.has_identity is False
        assert v.valid is False

    def test_no_responses_blocking(self) -> None:
        cols = [
            _col(0, "First name", ColumnClassification.IDENTITY, "first_name"),
            _col(1, "Email", ColumnClassification.IDENTITY, "email"),
        ]
        v = validate_mapping(_make_import(cols))
        assert v.has_responses is False
        assert v.valid is False

    def test_ignored_column_excluded_from_mapped_output(self) -> None:
        cols = [
            _col(0, "First name", ColumnClassification.IDENTITY, "first_name"),
            _col(1, "Email", ColumnClassification.IDENTITY, "email"),
            _col(2, "IgnoreMe", ColumnClassification.IGNORED, None),
            _col(3, "R1", ColumnClassification.RESPONSE, "response_1", 1),
        ]
        v = validate_mapping(_make_import(cols))
        # Ignored column should not affect validity
        assert v.valid is True

    def test_mapping_change_triggers_revalidation(self) -> None:
        """Simulate mapping changes and verify validation state changes."""
        # Valid mapping: has identity + responses
        valid_cols = [
            _col(0, "First name", ColumnClassification.IDENTITY, "first_name"),
            _col(1, "Email", ColumnClassification.IDENTITY, "email"),
            _col(2, "R1", ColumnClassification.RESPONSE, "response_1", 1),
        ]
        v1 = validate_mapping(_make_import(valid_cols))
        assert v1.valid is True

        # After change: remove identity (map all to ignore)
        no_identity_cols = [
            _col(0, "First name", ColumnClassification.IGNORED, None),
            _col(1, "Email", ColumnClassification.IGNORED, None),
            _col(2, "R1", ColumnClassification.RESPONSE, "response_1", 1),
        ]
        v2 = validate_mapping(_make_import(no_identity_cols))
        assert v2.valid is False
        assert v2.has_identity is False

        # After restore: should be valid again
        v3 = validate_mapping(_make_import(valid_cols))
        assert v3.valid is True

    def test_unknown_mapping_preserved(self) -> None:
        cols = [
            _col(0, "First name", ColumnClassification.IDENTITY, "first_name"),
            _col(1, "Mystery", ColumnClassification.UNKNOWN, None),
        ]
        v = validate_mapping(_make_import(cols))
        # Unknown columns are preserved but don't affect validity
        assert v.valid is False  # no responses
