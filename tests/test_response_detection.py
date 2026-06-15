"""Response-column detection tests."""

from __future__ import annotations

import pytest

from parsers.html_parser import HtmlImportParser
from parsers.models import ParsedImport
from tests.test_import_parser import limits, load_fixture


class TestResponseDetection:
    def _parse(self, name: str) -> ParsedImport:
        parser = HtmlImportParser()
        return parser.parse(load_fixture(name), name, limits=limits())

    def assert_response_numbers(self, result: ParsedImport, expected: list[int]) -> None:
        numbers = sorted(
            col.response_number
            for col in result.columns
            if col.response_number is not None
        )
        assert numbers == expected, f"Expected {expected}, got {numbers}"

    def test_response_1_and_2(self) -> None:
        result = self._parse("sample_responses.html")
        self.assert_response_numbers(result, [1, 2])

    def test_non_consecutive_responses(self) -> None:
        result = self._parse("non_consecutive_responses.html")
        self.assert_response_numbers(result, [1, 3, 10])

    def test_response_10(self) -> None:
        result = self._parse("response_10.html")
        self.assert_response_numbers(result, [1, 10])

    def test_alternate_headers_have_response_answers(self) -> None:
        result = self._parse("alternate_headers.html")
        self.assert_response_numbers(result, [1, 2])

    def test_no_response_found_raises(self) -> None:
        from parsers.exceptions import NoResponseTableFoundError
        with pytest.raises(NoResponseTableFoundError):
            self._parse("no_response_columns.html")
