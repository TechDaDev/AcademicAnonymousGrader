"""Deeper XLSX security tests (ZIP bomb, path traversal, etc.)."""

from __future__ import annotations

import io
import zipfile

import pytest

from parsers.base import ParserLimits
from parsers.exceptions import SecurityValidationError, UnsupportedFormatError
from parsers.xlsx_parser import XlsxImportParser


@pytest.fixture
def parser() -> XlsxImportParser:
    return XlsxImportParser()


@pytest.fixture
def limits() -> ParserLimits:
    return ParserLimits(max_upload_size_bytes=10 * 1024 * 1024)


class TestXlsxSecurity:
    """Security validation edge cases."""

    def test_external_link_detected(self, parser: XlsxImportParser, limits: ParserLimits) -> None:
        """External link entries trigger a warning."""
        # Directly test the _detect_external_links_and_dde method
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "[Content_Types].xml",
                b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
            )
            zf.writestr("xl/workbook.xml", b"<workbook/>")
            zf.writestr("xl/_rels/workbook.xml.rels", b"<rels/>")
            zf.writestr("xl/externalLinks/externalLink1.xml", b"<externalLink/>")

        data = buf.getvalue()
        warnings = parser._detect_external_links_and_dde(data)
        codes = [w.code for w in warnings]
        assert "W006" in codes, "External link warning not raised"

    def test_not_a_zip_rejected(self, parser: XlsxImportParser, limits: ParserLimits) -> None:
        """Plain text file raises UnsupportedFormatError."""
        with pytest.raises(UnsupportedFormatError):
            parser.parse(b"not a zip file", "bad.xlsx", limits=limits)

    def test_empty_zip_rejected(self, parser: XlsxImportParser, limits: ParserLimits) -> None:
        """Empty ZIP archive raises UnsupportedFormatError."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("empty.xml", b"<empty/>")
        data = buf.getvalue()
        with pytest.raises(UnsupportedFormatError):
            parser.parse(data, "empty.xlsx", limits=limits)

    def test_per_entry_compression_ratio(self, parser: XlsxImportParser, limits: ParserLimits) -> None:
        """A single highly compressed entry triggers security error."""
        huge = b"X" * 100_000
        # Use ZIP_DEFLATED which will give a high compression ratio
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "[Content_Types].xml",
                b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
            )
            zf.writestr("xl/workbook.xml", b"<workbook/>")
            zf.writestr("xl/_rels/workbook.xml.rels", b"<rels/>")
            # Bomb entry: highly compressible
            zf.writestr("xl/worksheets/sheet1.xml", huge)
        data = buf.getvalue()
        with pytest.raises(SecurityValidationError, match="compression ratio|ZIP bomb"):
            parser.parse(data, "bomb.xlsx", limits=limits)

    def test_valid_workbook_no_security_errors(self, parser: XlsxImportParser, limits: ParserLimits) -> None:
        """A normal workbook does not raise security errors."""
        from pathlib import Path
        path = Path(__file__).parent / "fixtures" / "valid.xlsx"
        data = path.read_bytes()
        result = parser.parse(data, "valid.xlsx", limits=limits)
        assert result.statistics.total_rows == 2
