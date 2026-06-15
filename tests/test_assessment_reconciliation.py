"""Assessment reconciliation tests."""

from __future__ import annotations

from parsers import HtmlImportParser
from parsers.base import ParserLimits
from parsers.models import ParsedImport
from services.import_preview_service import reconcile_assessment
from tests.test_import_parser import load_fixture


def _parse(name: str) -> ParsedImport:
    parser = HtmlImportParser()
    return parser.parse(load_fixture(name), name, limits=ParserLimits(
        max_upload_size_bytes=2_000_000,
        max_html_tables=10,
        max_import_rows=100,
        max_import_columns=100,
        max_cell_text_length=10_000,
    ))


class TestReconciliation:
    def test_exact_match(self) -> None:
        pi = _parse("sample_responses.html")
        r = reconcile_assessment(pi, (1, 2))
        assert r.exact_match is True
        assert r.mapped_response_numbers == (1, 2)
        assert r.missing_question_numbers == ()
        assert r.extra_response_numbers == ()
        assert r.duplicate_response_numbers == ()

    def test_fewer_responses_than_questions(self) -> None:
        pi = _parse("sample_responses.html")
        r = reconcile_assessment(pi, (1, 2, 3))
        assert r.exact_match is False
        assert r.missing_question_numbers == (3,)

    def test_more_responses_than_questions(self) -> None:
        pi = _parse("response_10.html")
        r = reconcile_assessment(pi, (1,))
        assert r.exact_match is False
        assert 10 in r.extra_response_numbers

    def test_missing_question_number(self) -> None:
        pi = _parse("non_consecutive_responses.html")
        r = reconcile_assessment(pi, (1, 2, 3, 10))
        assert r.exact_match is False
        assert r.missing_question_numbers == (2,)

    def test_extra_response_number(self) -> None:
        pi = _parse("non_consecutive_responses.html")
        r = reconcile_assessment(pi, (1, 3))
        assert r.exact_match is False
        assert 10 in r.extra_response_numbers

    def test_non_consecutive_detected(self) -> None:
        pi = _parse("non_consecutive_responses.html")
        r = reconcile_assessment(pi, (1, 2, 3))
        assert r.non_consecutive is True

    def test_unresolved_blocks_readiness(self) -> None:
        pi = _parse("non_consecutive_responses.html")
        r = reconcile_assessment(pi, (1,))
        assert r.unresolved is True

    def test_corrected_mapping_becomes_ready(self) -> None:
        """If we reconcile with the exact numbers present, it should match."""
        pi = _parse("non_consecutive_responses.html")
        r = reconcile_assessment(pi, (1, 3, 10))
        assert r.exact_match is True
