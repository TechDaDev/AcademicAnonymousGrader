"""Tests for the Phase 3 HTML import parser and preview service."""

from __future__ import annotations

from pathlib import Path

import pytest

from parsers import (
    ColumnClassification,
    HtmlImportParser,
    MultipleCandidateTablesError,
    NoResponseTableFoundError,
    ParsedImport,
    ValidationSeverity,
)
from parsers.base import ParserLimits
from parsers.normalization import extract_response_number, normalize_header, parse_duration_text, parse_grade_text
from services.import_preview_service import format_file_size, preview_html_import

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def limits() -> ParserLimits:
    return ParserLimits(
        max_upload_size_bytes=2_000_000,
        max_html_tables=10,
        max_import_rows=100,
        max_import_columns=100,
        max_cell_text_length=10_000,
    )


class TestNormalizationHelpers:
    def test_normalize_header_collapses_whitespace(self) -> None:
        assert normalize_header("  First   name  ") == "First name"

    def test_extract_response_number(self) -> None:
        assert extract_response_number("Answer 12") == 12

    def test_parse_duration_text(self) -> None:
        parsed, raw, warnings = parse_duration_text("1 hour 24 mins")
        assert parsed == 5_040
        assert raw == "1 hour 24 mins"
        assert warnings == ()

    def test_parse_grade_text(self) -> None:
        parsed, maximum, raw, warnings = parse_grade_text("7.5/10")
        assert parsed is not None and str(parsed) == "7.5"
        assert maximum is not None and str(maximum) == "10"
        assert raw == "7.5/10"
        assert warnings == ()


class TestHtmlImportParser:
    def test_parses_sanitized_fixture(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        assert isinstance(result, ParsedImport)
        assert result.table_index == 0
        assert result.statistics.total_rows == 5
        assert result.statistics.response_column_count == 2
        assert len(result.rows) == 5
        assert result.rows[0].first_name == "Amina"
        assert result.rows[0].responses[1].text.startswith("def greet")
        assert result.rows[3].source_grade is None
        assert result.rows[3].warnings == ()
        assert result.rows[4].source_grade is not None and str(result.rows[4].source_grade) == "6.5"

    def test_duplicate_email_produces_warning(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("duplicate_email.html"), "duplicate_email.html", limits=limits())
        assert any(message.code == "S005" for message in result.rows[1].warnings)
        assert result.statistics.duplicate_email_count == 1

    def test_missing_response_columns_raises(self) -> None:
        parser = HtmlImportParser()
        with pytest.raises(NoResponseTableFoundError):
            parser.parse(load_fixture("no_response_columns.html"), "no_response_columns.html", limits=limits())

    def test_multiple_candidate_tables_raises(self) -> None:
        parser = HtmlImportParser()
        with pytest.raises(MultipleCandidateTablesError):
            parser.parse(load_fixture("multiple_tables.html"), "multiple_tables.html", limits=limits())

    def test_preview_service_hashes_file_and_marks_ready(self) -> None:
        preview = preview_html_import(load_fixture("sample_responses.html"), "sample_responses.html")
        assert preview.file_hash
        assert preview.file_size > 0
        assert preview.file_name == "sample_responses.html"
        assert preview.ready_for_phase4 is True

    def test_preview_service_format_file_size(self) -> None:
        assert format_file_size(1024) == "1.0 KB"

    def test_sanitizes_active_content(self) -> None:
        parser = HtmlImportParser()
        html = b"""
        <html><body>
        <table>
          <tr><th>First name</th><th>Last name</th><th>Email</th><th>Response 1</th></tr>
          <tr><td onclick="alert(1)">Safe</td><td>User</td><td>safe@example.com</td>
          <td><script>alert(1)</script>Allowed</td></tr>
        </table>
        </body></html>
        """
        result = parser.parse(html, "sanitized.html", limits=limits())
        assert result.rows[0].responses[0].text == "Allowed"

    def test_alternate_headers_map_cleanly(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("alternate_headers.html"), "alternate_headers.html", limits=limits())
        fields = {column.mapped_field for column in result.columns}
        core_fields = {
            "first_name", "last_name", "email",
            "institutional_student_id", "status", "started",
            "completed", "duration", "source_grade",
        }
        assert core_fields.issubset(fields)
        assert result.rows[0].duration_seconds == 1_200


class TestParserMetadata:
    def test_candidate_tables_exposed(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        assert len(result.candidate_tables) == 1
        assert result.candidate_tables[0].identity_columns >= 4
        assert result.candidate_tables[0].response_columns == 2

    def test_unexpected_columns_are_preserved_as_unknown(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("unexpected_columns.html"), "unexpected_columns.html", limits=limits())
        assert any(column.classification is ColumnClassification.UNKNOWN for column in result.columns)
        assert result.rows[0].unknown_values["Favourite colour"] == "Blue"

    def test_preview_result_reports_error_free_rows(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        assert result.statistics.error_rows == 0
        ok_severities = {ValidationSeverity.INFORMATION, ValidationSeverity.WARNING}
        assert all(message.severity in ok_severities for message in result.warnings)
