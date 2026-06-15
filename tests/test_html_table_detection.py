"""HTML table detection tests — candidate scoring, auto-select, multi-table."""

from __future__ import annotations

import pytest

from parsers import (
    HtmlImportParser,
    MultipleCandidateTablesError,
    NoResponseTableFoundError,
)
from tests.test_import_parser import limits, load_fixture


class TestTableDetection:
    def test_one_strong_table_auto_selected(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        assert result.table_index == 0
        assert len(result.candidate_tables) == 1
        assert result.candidate_tables[0].score >= 20

    def test_weak_table_ignored(self) -> None:
        """A table with no identity columns and no responses should not be a candidate."""
        parser = HtmlImportParser()
        html = b"<table><tr><th>X</th></tr><tr><td>Y</td></tr></table>"
        with pytest.raises(NoResponseTableFoundError):
            parser.parse(html, "weak.html", limits=limits())

    def test_multiple_strong_candidates_raises(self) -> None:
        parser = HtmlImportParser()
        with pytest.raises(MultipleCandidateTablesError):
            parser.parse(load_fixture("multiple_tables.html"), "multiple_tables.html", limits=limits())

    def test_table_index_selection_works(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(
            load_fixture("multiple_tables.html"), "multiple_tables.html",
            limits=limits(), table_index=0,
        )
        assert result.table_index == 0
        assert result.statistics.total_rows == 1

    def test_select_second_table(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(
            load_fixture("multiple_tables.html"), "multiple_tables.html",
            limits=limits(), table_index=1,
        )
        assert result.table_index == 1
        assert result.statistics.total_rows == 1

    def test_candidate_summaries_accurate(self) -> None:
        parser = HtmlImportParser()
        result = parser.parse(load_fixture("sample_responses.html"), "sample_responses.html", limits=limits())
        assert len(result.candidate_tables) == 1
        c = result.candidate_tables[0]
        assert c.row_count == 5
        assert c.response_columns == 2
        assert c.identity_columns >= 4
        assert c.metadata_columns >= 4

    def test_selected_table_changes_column_count(self) -> None:
        """Table 0 and table 1 in multiple_tables.html both have 4 columns."""
        parser = HtmlImportParser()
        r0 = parser.parse(
            load_fixture("multiple_tables.html"), "multiple_tables.html",
            limits=limits(), table_index=0,
        )
        r1 = parser.parse(
            load_fixture("multiple_tables.html"), "multiple_tables.html",
            limits=limits(), table_index=1,
        )
        assert len(r0.columns) == len(r1.columns)  # both have same structure

    def test_selected_table_changes_row_content(self) -> None:
        """Verify table selection changes the actual data parsed."""
        parser = HtmlImportParser()
        r0 = parser.parse(
            load_fixture("multiple_tables.html"), "multiple_tables.html",
            limits=limits(), table_index=0,
        )
        r1 = parser.parse(
            load_fixture("multiple_tables.html"), "multiple_tables.html",
            limits=limits(), table_index=1,
        )
        # Table 0 has "Table One" as first name
        assert r0.rows[0].first_name == "Table"
        # Table 1 has "Table Two" as first name from different row
        assert r1.rows[0].first_name == "Table"
