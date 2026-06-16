"""Tests for CSV parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from parsers.base import ParserLimits
from parsers.csv_parser import CsvImportParser
from parsers.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    ImportLimitExceededError,
    MalformedCsvError,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def parser() -> CsvImportParser:
    return CsvImportParser()


@pytest.fixture
def limits() -> ParserLimits:
    return ParserLimits(max_upload_size_bytes=10_000_000)


def _load(name: str) -> bytes:
    with open(FIXTURE_DIR / name, "rb") as f:
        return f.read()


class TestCsvParser:
    """Core CSV parsing tests."""

    def test_valid_utf8_parses(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Valid UTF-8 CSV parses successfully."""
        result = parser.parse(_load("valid_utf8.csv"), "test.csv", limits=limits)
        assert result.source_format == "csv"
        assert result.statistics.total_rows == 2

    def test_utf8_bom_parses(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """UTF-8 BOM CSV parses successfully."""
        result = parser.parse(_load("valid_utf8_bom.csv"), "bom.csv", limits=limits)
        assert result.statistics.total_rows == 2
        assert result.encoding == "utf-8-sig"

    def test_semicolon_delimiter_detected(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Semicolon-delimited CSV is detected."""
        result = parser.parse(_load("valid_semicolon.csv"), "semi.csv", limits=limits)
        assert result.delimiter == ";"
        assert result.statistics.total_rows == 2

    def test_arabic_preserved(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Arabic text in CSV is preserved."""
        result = parser.parse(_load("arabic_utf8.csv"), "arabic.csv", limits=limits)
        assert result.statistics.total_rows == 2
        # Check Arabic name
        row = result.rows[0]
        assert row.first_name == "أحمد"
        assert row.last_name == "محمد"

    def test_leading_zero_id_preserved(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Leading-zero institutional IDs are preserved as strings."""
        result = parser.parse(_load("leading_zero_id.csv"), "leading.csv", limits=limits)
        # Check the first row's institutional_student_id
        row = result.rows[0]
        assert row.institutional_student_id == "001234"

    def test_headers_detected(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Column headers are correctly detected."""
        result = parser.parse(_load("valid_utf8.csv"), "test.csv", limits=limits)
        # First Name, Last Name, Email, Institutional ID, Response 1, Response 2
        assert len(result.columns) == 6
        assert result.statistics.response_column_count == 2

    def test_duplicate_headers_detected(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Duplicate headers produce warnings."""
        result = parser.parse(_load("duplicate_headers.csv"), "dup.csv", limits=limits)
        dup_warnings = [w for w in result.warnings if "Duplicate header" in w.message]
        assert len(dup_warnings) >= 1

    def test_empty_file_raises(self, parser: CsvImportParser) -> None:
        """Empty file raises EmptyFileError."""
        with pytest.raises(EmptyFileError):
            parser.parse(b"", "empty.csv")

    def test_binary_file_rejected(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Binary file with null bytes is rejected."""
        data = b"col1,col2\nval1,\x00val2"
        with pytest.raises(MalformedCsvError, match="NUL"):
            parser.parse(data, "bad.csv", limits=limits)

    def test_file_size_limit(self, parser: CsvImportParser) -> None:
        """Oversized file is rejected."""
        small_limits = ParserLimits(max_upload_size_bytes=10)
        with pytest.raises(FileTooLargeError):
            parser.parse(b"a" * 100, "big.csv", limits=small_limits)

    def test_row_limit(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Excessive rows are rejected."""
        small_limits = ParserLimits(max_import_rows=1)
        with pytest.raises(ImportLimitExceededError):
            parser.parse(_load("valid_utf8.csv"), "test.csv", limits=small_limits)

    def test_headers_only_produces_no_rows(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """CSV with only headers produces no rows."""
        result = parser.parse(_load("headers_only.csv"), "headers.csv", limits=limits)
        assert result.statistics.total_rows == 0

    def test_multiline_quoted_field(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Multiline quoted fields are preserved."""
        result = parser.parse(_load("multiline_quoted.csv"), "multi.csv", limits=limits)
        assert result.statistics.total_rows == 1
        assert len(result.rows[0].responses) > 0
        assert "\n" in result.rows[0].responses[0].text

    def test_encoding_detected(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Encoding is reported in result."""
        result = parser.parse(_load("valid_utf8.csv"), "test.csv", limits=limits)
        assert result.encoding is not None

    def test_delimiter_detected(self, parser: CsvImportParser, limits: ParserLimits) -> None:
        """Delimiter is reported in result."""
        result = parser.parse(_load("valid_utf8.csv"), "test.csv", limits=limits)
        assert result.delimiter == ","
