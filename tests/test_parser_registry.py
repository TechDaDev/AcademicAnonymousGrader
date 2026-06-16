"""Tests for the parser registry."""
from __future__ import annotations

import pytest

from parsers.exceptions import UnsupportedFileTypeError
from parsers.parser_registry import (
    get_parser_for_filename,
    get_supported_extensions_display,
    list_parsers,
)


class TestParserRegistry:
    """Test parser registry lookup."""

    def test_get_html_parser(self) -> None:
        """HTML files return HtmlImportParser."""
        parser = get_parser_for_filename("grades.html")
        assert parser.parser_name == "html-bs4-lxml"

    def test_get_htm_parser(self) -> None:
        """.htm files return HtmlImportParser."""
        parser = get_parser_for_filename("grades.htm")
        assert parser.parser_name == "html-bs4-lxml"

    def test_get_xlsx_parser(self) -> None:
        """.xlsx files return XlsxImportParser."""
        parser = get_parser_for_filename("grades.xlsx")
        assert parser.parser_name == "xlsx"

    def test_get_csv_parser(self) -> None:
        """.csv files return CsvImportParser."""
        parser = get_parser_for_filename("grades.csv")
        assert parser.parser_name == "csv"

    def test_unsupported_extension_raises(self) -> None:
        """Unsupported extensions raise UnsupportedFileTypeError."""
        with pytest.raises(UnsupportedFileTypeError, match="Unsupported file type"):
            get_parser_for_filename("file.pdf")

    def test_unsupported_xls_raises(self) -> None:
        """Legacy .xls is not supported by the registry."""
        with pytest.raises(UnsupportedFileTypeError):
            get_parser_for_filename("legacy.xls")

    def test_no_extension_raises(self) -> None:
        """Files without extensions raise."""
        with pytest.raises(UnsupportedFileTypeError):
            get_parser_for_filename("README")

    def test_supported_extensions_display(self) -> None:
        """Display string contains all extensions."""
        display = get_supported_extensions_display()
        assert ".html" in display
        assert ".htm" in display
        assert ".xlsx" in display
        assert ".csv" in display

    def test_list_parsers(self) -> None:
        """list_parsers returns all registered parsers."""
        parsers = list_parsers()
        assert len(parsers) >= 3
        names = {p.parser_name for p in parsers}
        assert "html-bs4-lxml" in names
        assert "xlsx" in names
        assert "csv" in names
