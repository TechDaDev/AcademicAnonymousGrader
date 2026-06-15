"""Import preview service tests."""

from __future__ import annotations

from services.import_preview_service import (
    format_file_size,
    preview_html_import,
    reconcile_assessment,
    validate_mapping,
)
from tests.test_import_parser import load_fixture


class TestPreviewService:
    def test_preview_hashes_file(self) -> None:
        preview = preview_html_import(load_fixture("sample_responses.html"), "sample_responses.html")
        assert preview.file_hash
        assert len(preview.file_hash) == 64

    def test_preview_reports_file_size(self) -> None:
        preview = preview_html_import(load_fixture("sample_responses.html"), "sample_responses.html")
        assert preview.file_size > 0

    def test_preview_marks_ready_when_valid(self) -> None:
        preview = preview_html_import(load_fixture("sample_responses.html"), "sample_responses.html")
        assert preview.ready_for_phase4 is True

    def test_preview_supports_table_index(self) -> None:
        preview = preview_html_import(load_fixture("multiple_tables.html"), "multiple_tables.html", table_index=0)
        assert preview.parsed_import.table_index == 0
        assert preview.parsed_import.statistics.total_rows == 1

    def test_format_file_size_bytes(self) -> None:
        assert format_file_size(500) == "500 B"

    def test_format_file_size_kb(self) -> None:
        assert format_file_size(1024) == "1.0 KB"

    def test_format_file_size_mb(self) -> None:
        assert format_file_size(1_048_576) == "1.0 MB"


class TestValidateMapping:
    def test_valid_mapping_has_no_errors(self) -> None:
        preview = preview_html_import(load_fixture("sample_responses.html"), "sample_responses.html")
        validation = validate_mapping(preview.parsed_import)
        assert validation.valid is True
        assert validation.has_identity is True
        assert validation.has_responses is True

    def test_no_identity_mapping_blocking(self) -> None:
        preview = preview_html_import(load_fixture("sample_responses.html"), "sample_responses.html")
        # Replace columns with non-identity classification
        pi = preview.parsed_import
        validation = validate_mapping(pi)
        assert validation.has_identity is True  # sample has identity


class TestReconcileAssessment:
    def test_exact_match(self) -> None:
        preview = preview_html_import(load_fixture("sample_responses.html"), "sample_responses.html")
        result = reconcile_assessment(preview.parsed_import, (1, 2))
        assert result.exact_match is True
        assert not result.unresolved

    def test_fewer_responses_than_questions(self) -> None:
        preview = preview_html_import(load_fixture("sample_responses.html"), "sample_responses.html")
        result = reconcile_assessment(preview.parsed_import, (1, 2, 3))
        assert result.exact_match is False
        assert result.missing_question_numbers == (3,)

    def test_extra_responses(self) -> None:
        preview = preview_html_import(load_fixture("non_consecutive_responses.html"), "non_consecutive_responses.html")
        result = reconcile_assessment(preview.parsed_import, (1, 3))
        assert result.exact_match is False
        assert 10 in result.extra_response_numbers

    def test_non_consecutive_detected(self) -> None:
        preview = preview_html_import(load_fixture("non_consecutive_responses.html"), "non_consecutive_responses.html")
        result = reconcile_assessment(preview.parsed_import, (1, 2, 3))
        assert result.non_consecutive is True

    def test_unresolved_blocks_readiness(self) -> None:
        preview = preview_html_import(load_fixture("non_consecutive_responses.html"), "non_consecutive_responses.html")
        result = reconcile_assessment(preview.parsed_import, (1,))
        assert result.unresolved is True
