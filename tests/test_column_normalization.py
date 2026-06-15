"""Column normalization and header detection tests."""

from __future__ import annotations

from parsers.normalization import extract_response_number, normalize_header, normalize_lookup_key, normalize_text_cell


class TestNormalizeHeader:
    def test_collapses_repeated_whitespace(self) -> None:
        assert normalize_header("  First   name  ") == "First name"

    def test_decodes_html_entities(self) -> None:
        assert normalize_header("Grade &amp; Score") == "Grade & Score"

    def test_non_breaking_space_converted(self) -> None:
        assert normalize_header("First\xa0name") == "First name"

    def test_empty_input_returns_empty(self) -> None:
        assert normalize_header("") == ""

    def test_none_input_returns_empty(self) -> None:
        assert normalize_header(None) == ""

    def test_unicode_preserved(self) -> None:
        assert normalize_header("الاسم الأول") == "الاسم الأول"

    def test_tab_and_newline_collapsed(self) -> None:
        assert normalize_header("First\tname\nhere") == "First name here"


class TestNormalizeLookupKey:
    def test_strips_punctuation(self) -> None:
        assert normalize_lookup_key("Grade/10.00") == "grade 10 00"

    def test_hyphen_normalized(self) -> None:
        assert normalize_lookup_key("Response-5") == "response 5"

    def test_underscore_normalized(self) -> None:
        assert normalize_lookup_key("Response_4") == "response 4"

    def test_case_insensitive(self) -> None:
        assert normalize_lookup_key("FIRST NAME") == "first name"

    def test_arabic_preserved(self) -> None:
        assert normalize_lookup_key("الاسم الأول") == "الاسم الأول"


class TestExtractResponseNumber:
    def test_response_1(self) -> None:
        assert extract_response_number("Response 1") == 1

    def test_response_2(self) -> None:
        assert extract_response_number("Response 2") == 2

    def test_response_10(self) -> None:
        assert extract_response_number("Response 10") == 10

    def test_response_4_underscore(self) -> None:
        assert extract_response_number("Response_4") == 4

    def test_response_5_hyphen(self) -> None:
        assert extract_response_number("Response-5") == 5

    def test_answer_1(self) -> None:
        assert extract_response_number("Answer 1") == 1

    def test_answer_12(self) -> None:
        assert extract_response_number("Answer 12") == 12

    def test_question_1_response(self) -> None:
        assert extract_response_number("Question 1 Response") == 1

    def test_no_match_returns_none(self) -> None:
        assert extract_response_number("Notes") is None

    def test_none_returns_none(self) -> None:
        assert extract_response_number(None) is None


class TestNormalizeTextCell:
    def test_decodes_html_entities(self) -> None:
        assert normalize_text_cell("Hello &amp; welcome") == "Hello & welcome"

    def test_preserves_newlines(self) -> None:
        assert normalize_text_cell("line1\nline2") == "line1\nline2"

    def test_windows_line_endings_converted(self) -> None:
        assert normalize_text_cell("line1\r\nline2") == "line1\nline2"

    def test_old_mac_line_endings_converted(self) -> None:
        assert normalize_text_cell("line1\rline2") == "line1\nline2"

    def test_trailing_newline_stripped(self) -> None:
        assert normalize_text_cell("text\n") == "text"

    def test_trailing_spaces_stripped_per_line(self) -> None:
        assert normalize_text_cell("line1   \nline2  ") == "line1\nline2"

    def test_internal_spaces_preserved(self) -> None:
        # Leading whitespace preserved, trailing whitespace stripped per line
        result = normalize_text_cell("  hello  world  ")
        assert result == "  hello  world"

    def test_none_returns_empty(self) -> None:
        assert normalize_text_cell(None) == ""

    def test_blank_response(self) -> None:
        assert normalize_text_cell("") == ""
