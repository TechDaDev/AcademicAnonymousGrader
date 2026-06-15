"""Comprehensive HTML parser tests using fixtures."""

from __future__ import annotations

import pytest

from parsers import (
    ColumnClassification,
    HtmlImportParser,
    MissingIdentityColumnsError,
)
from tests.test_import_parser import limits, load_fixture


class TestHtmlParser:
    def test_sample_fixture_returns_exactly_5_rows(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        assert result.statistics.total_rows == 5
        assert len(result.rows) == 5

    def test_arabic_text_preserved(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        assert "مرحبا بالعالم" in result.rows[2].responses[0].text

    def test_multiline_code_indentation_preserved(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        text = result.rows[0].responses[1].text
        assert text.startswith("def greet(name):")
        assert "    return f" in text or "\t" in text or "    " in text

    def test_blank_response_retained(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        assert result.statistics.blank_response_count >= 1

    def test_unknown_columns_retained(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("unexpected_columns.html"), "unexpected_columns.html", limits=limits())
        assert any(col.classification is ColumnClassification.UNKNOWN for col in result.columns)
        assert "Favourite colour" in result.rows[0].unknown_values

    def test_unfinished_submission_flagged(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        # Yuki (row 4, 0-indexed row 3) is unfinished
        assert result.rows[3].status == "In progress"

    def test_missing_first_name_accepted(self) -> None:
        parser = HtmlImportParser()
        html = (
            b"<table><tr><th>Last name</th><th>Email</th><th>Response 1</th></tr>"
            b"<tr><td>User</td><td>u@example.com</td><td>A</td></tr></table>"
        )
        result = parser.parse(html, "no_first.html", limits=limits())
        assert result.rows[0].first_name is None

    def test_missing_last_name_accepted(self) -> None:
        parser = HtmlImportParser()
        html = (
            b"<table><tr><th>First name</th><th>Email</th><th>Response 1</th></tr>"
            b"<tr><td>User</td><td>u@example.com</td><td>A</td></tr></table>"
        )
        result = parser.parse(html, "no_last.html", limits=limits())
        assert result.rows[0].last_name is None

    def test_missing_email_accepted(self) -> None:
        parser = HtmlImportParser()
        html = (
            b"<table><tr><th>First name</th><th>Last name</th><th>Response 1</th></tr>"
            b"<tr><td>User</td><td>Name</td><td>A</td></tr></table>"
        )
        result = parser.parse(html, "no_email.html", limits=limits())
        assert result.rows[0].email is None

    def test_response_without_identity_blocked(self) -> None:
        parser = HtmlImportParser()
        html = b"<table><tr><th>Response 1</th></tr><tr><td>Answer</td></tr></table>"
        with pytest.raises(MissingIdentityColumnsError):
            parser.parse(html, "no_identity.html", limits=limits())

    def test_duplicate_email_detected(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("duplicate_email.html"), "duplicate_email.html", limits=limits())
        assert any(msg.code == "S005" for msg in result.rows[1].warnings)
        assert result.statistics.duplicate_email_count == 1

    def test_duplicate_student_id_detected(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("duplicate_student_id.html"), "duplicate_student_id.html", limits=limits())
        assert any(msg.code == "S006" for msg in result.rows[1].warnings)
        assert result.statistics.duplicate_student_id_count == 1

    def test_alternate_headers_map_cleanly(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("alternate_headers.html"), "alternate_headers.html", limits=limits())
        fields = {col.mapped_field for col in result.columns}
        core = {
            "first_name", "last_name", "email",
            "institutional_student_id", "status",
            "started", "completed", "duration", "source_grade",
        }
        assert core.issubset(fields), f"Missing: {core - fields}"
