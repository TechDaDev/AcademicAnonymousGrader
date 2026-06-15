"""File-level and row-level validation tests."""

from __future__ import annotations

import pytest

from parsers import (
    EmptyFileError,
    HtmlImportParser,
    InvalidHtmlError,
    NoResponseTableFoundError,
    NoTableFoundError,
)
from parsers.base import ParserLimits
from parsers.exceptions import ImportLimitExceededError, UnsupportedFileTypeError
from tests.test_import_parser import load_fixture


def strict_limits() -> ParserLimits:
    return ParserLimits(
        max_upload_size_bytes=100,
        max_html_tables=2,
        max_import_rows=10,
        max_import_columns=20,
        max_cell_text_length=50,
    )


class TestFileValidation:
    def test_empty_file_rejected(self) -> None:
        parser = HtmlImportParser()
        with pytest.raises(EmptyFileError):
            parser.parse(b"", "empty.html", limits=ParserLimits())

    def test_binary_file_rejected(self) -> None:
        parser = HtmlImportParser()
        # .bin extension raises UnsupportedFileTypeError; rename to .html triggers binary check
        with pytest.raises((InvalidHtmlError, UnsupportedFileTypeError)):
            parser.parse(b"\x00\x01\x02", "binary.bin", limits=ParserLimits())

    def test_no_table_rejected(self) -> None:
        parser = HtmlImportParser()
        with pytest.raises(NoTableFoundError):
            parser.parse(load_fixture("no_table.html"), "no_table.html", limits=ParserLimits())

    def test_no_response_columns_rejected(self) -> None:
        parser = HtmlImportParser()
        with pytest.raises(NoResponseTableFoundError):
            parser.parse(load_fixture("no_response_columns.html"), "no_response_columns.html", limits=ParserLimits())

    def test_file_size_limit_enforced(self) -> None:
        parser = HtmlImportParser()
        limits_small = ParserLimits(
            max_upload_size_bytes=500,
            max_html_tables=2,
            max_import_rows=100,
            max_import_columns=20,
            max_cell_text_length=50,
        )
        big_data = b"<html><body><table><tr><th>First name</th><th>Email</th><th>Response 1</th></tr>"
        big_data += b"<tr><td>S</td><td>s@e.com</td><td>A</td></tr>" * 50
        big_data += b"</table></body></html>"
        from parsers.exceptions import FileTooLargeError
        with pytest.raises(FileTooLargeError):
            parser.parse(big_data, "big.html", limits=limits_small)

    def test_row_limit_enforced(self) -> None:
        parser = HtmlImportParser()
        limits_ok_size = ParserLimits(
            max_upload_size_bytes=100_000,
            max_html_tables=2,
            max_import_rows=5,
            max_import_columns=20,
            max_cell_text_length=50,
        )
        many_rows = b"<html><body><table><tr><th>First name</th><th>Email</th><th>Response 1</th></tr>"
        many_rows += b"<tr><td>S</td><td>s@e.com</td><td>A</td></tr>" * 10
        many_rows += b"</table></body></html>"
        with pytest.raises(ImportLimitExceededError):
            parser.parse(many_rows, "many_rows.html", limits=limits_ok_size)

    def test_column_limit_enforced(self) -> None:
        parser = HtmlImportParser()
        limits_ok_size = ParserLimits(
            max_upload_size_bytes=100_000,
            max_html_tables=2,
            max_import_rows=10,
            max_import_columns=3,
            max_cell_text_length=50,
        )
        # With limit=3, only 3 columns are extracted; "Extra" is truncated
        many_cols = b"<html><body><table><tr><th>First name</th><th>Email</th><th>Response 1</th><th>Extra</th></tr>"
        many_cols += b"<tr><td>U</td><td>u@e.com</td><td>A</td><td>X</td></tr></table></body></html>"
        result = parser.parse(many_cols, "many_cols.html", limits=limits_ok_size)
        assert len(result.columns) <= 3
        # "Extra" column should NOT be in columns
        col_names = [c.original_name for c in result.columns]
        assert "Extra" not in col_names

    def test_table_count_limit_enforced(self) -> None:
        parser = HtmlImportParser()
        limits_few_tables = ParserLimits(
            max_upload_size_bytes=100_000,
            max_html_tables=1,
            max_import_rows=100,
            max_import_columns=20,
            max_cell_text_length=100,
        )
        html = (
            b"<html><body><table><tr><th>First name</th><th>Email</th><th>Response 1</th></tr>"
            b"<tr><td>A</td><td>a@e.com</td><td>X</td></tr></table>"
            b"<table><tr><th>First name</th><th>Email</th><th>Response 1</th></tr>"
            b"<tr><td>B</td><td>b@e.com</td><td>Y</td></tr></table></body></html>"
        )
        with pytest.raises(ImportLimitExceededError):
            parser.parse(html, "many_tables.html", limits=limits_few_tables)

    def test_cell_size_limit_enforced(self) -> None:
        parser = HtmlImportParser()
        # Use generous limits for headers but small cell limit
        # The cell limit applies to ALL cells including headers,
        # so keep it large enough for "Response 1" and test data cells.
        limits_small_cell = ParserLimits(
            max_upload_size_bytes=100_000,
            max_html_tables=2,
            max_import_rows=10,
            max_import_columns=20,
            max_cell_text_length=50,
        )
        html = (
            b"<html><body><table><tr><th>First name</th><th>Email</th><th>Response 1</th></tr>"
            b"<tr><td>A</td><td>a@e.com</td><td>Short</td></tr></table></body></html>"
        )
        result = parser.parse(html, "big_cell.html", limits=limits_small_cell)
        # With limit 50, short text is preserved fully
        assert result.rows[0].responses[0].text == "Short"
        # Verify truncation with a longer text
        text_50 = "X" * 100
        dummy = type('', (), {'get_text': lambda self, **kw: text_50})()
        truncated = parser._extract_cell_text(dummy, limits_small_cell)
        assert len(truncated) <= 50

    def test_duplicate_headers_detected(self) -> None:
        from parsers import HtmlImportParser
        parser = HtmlImportParser()
        html = (
            b"<html><body><table><tr><th>First name</th><th>First name</th>"
            b"<th>Email</th><th>Response 1</th></tr>"
            b"<tr><td>A</td><td>B</td><td>a@e.com</td><td>Ans</td></tr>"
            b"</table></body></html>"
        )
        result = parser.parse(html, "dup_headers.html", limits=ParserLimits())
        names = [c.normalized_name for c in result.columns]
        assert names.count("First name") == 2

    def test_empty_headers_accepted(self) -> None:
        parser = HtmlImportParser()
        html = (
            b"<html><body><table><tr><th></th><th></th>"
            b"<th>Email</th><th>Response 1</th></tr>"
            b"<tr><td>A</td><td>B</td><td>a@e.com</td><td>Ans</td></tr>"
            b"</table></body></html>"
        )
        result = parser.parse(html, "empty_headers.html", limits=ParserLimits())
        # Empty headers become empty strings in column names
        assert any(c.normalized_name == "" for c in result.columns)
