"""Test that the parser registry correctly handles the real sample files."""

from __future__ import annotations

from pathlib import Path

import pytest

from parsers.base import ParserLimits
from parsers.parser_registry import get_parser_for_filename

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


@pytest.fixture
def limits() -> ParserLimits:
    return ParserLimits(
        max_upload_size_bytes=50 * 1024 * 1024,
        max_html_tables=10,
        max_import_rows=5000,
        max_import_columns=100,
        max_cell_text_length=10000,
    )


def _iter_samples() -> list[Path]:
    """List all sample files."""
    if not SAMPLES_DIR.exists():
        return []
    return sorted(SAMPLES_DIR.glob("*.*"))


class TestSampleCompatibility:
    """Verify parsers handle the bundled sample files."""

    def test_all_samples_have_parsers(self) -> None:
        """Every sample file has a registered parser."""
        samples = _iter_samples()
        if not samples:
            pytest.skip("No sample files found")
        for path in samples:
            if path.suffix.lower() not in (".html", ".htm", ".xlsx", ".csv", ".md", ".txt"):
                continue
            if path.suffix.lower() in (".md", ".txt"):
                continue  # documentation, not importable
            parser = get_parser_for_filename(path.name)
            assert parser is not None, f"No parser for {path.name}"

    def test_html_samples_parse(self, limits: ParserLimits) -> None:
        """All HTML sample files parse without error."""
        samples = [p for p in _iter_samples() if p.suffix.lower() in (".html", ".htm")]
        if not samples:
            pytest.skip("No HTML sample files found")
        for path in samples:
            data = path.read_bytes()
            parser = get_parser_for_filename(path.name)
            result = parser.parse(data, path.name, limits=limits)
            assert result.statistics.total_rows > 0, f"{path.name} produced no rows"

    def test_parser_name_in_result(self, limits: ParserLimits) -> None:
        """Parsed result includes the correct parser name."""
        samples = [p for p in _iter_samples() if p.suffix.lower() in (".html", ".htm")]
        if not samples:
            pytest.skip("No sample files found")
        for path in samples:
            data = path.read_bytes()
            parser = get_parser_for_filename(path.name)
            result = parser.parse(data, path.name, limits=limits)
            assert result.parser_name in ("html", "html-bs4-lxml", "xlsx", "csv")
