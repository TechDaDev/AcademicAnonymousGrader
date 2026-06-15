"""Metadata parsing tests — dates, durations, grades."""

from __future__ import annotations

from decimal import Decimal

from parsers.normalization import parse_datetime_text, parse_duration_text, parse_grade_text


class TestDatetimeParsing:
    def test_format_dd_mon_yyyy_hh_mm_am(self) -> None:
        parsed, raw, warnings = parse_datetime_text("3 May 2026 9:04 AM")
        assert parsed is not None
        assert raw == "3 May 2026 9:04 AM"
        assert warnings == ()

    def test_format_dd_mon_yyyy_hh_mm(self) -> None:
        parsed, raw, warnings = parse_datetime_text("03 May 2026 09:04")
        assert parsed is not None
        assert warnings == ()

    def test_format_yyyy_mm_dd_hh_mm(self) -> None:
        parsed, raw, warnings = parse_datetime_text("2026-05-03 10:00")
        assert parsed is not None
        assert warnings == ()

    def test_format_iso8601(self) -> None:
        parsed, raw, warnings = parse_datetime_text("2026-05-06T09:00:00")
        assert parsed is not None
        assert warnings == ()

    def test_malformed_date_produces_warning(self) -> None:
        parsed, raw, warnings = parse_datetime_text("not-a-date")
        assert parsed is None
        assert raw == "not-a-date"
        assert len(warnings) == 1
        assert "Could not parse datetime" in warnings[0]

    def test_empty_returns_none(self) -> None:
        parsed, raw, warnings = parse_datetime_text("")
        assert parsed is None
        assert raw is None
        assert warnings == ()

    def test_none_returns_none(self) -> None:
        parsed, raw, warnings = parse_datetime_text(None)
        assert parsed is None
        assert raw is None
        assert warnings == ()


class TestDurationParsing:
    def test_one_hour_24_mins(self) -> None:
        parsed, raw, warnings = parse_duration_text("1 hour 24 mins")
        assert parsed == 5_040
        assert raw == "1 hour 24 mins"
        assert warnings == ()

    def test_45_mins(self) -> None:
        parsed, raw, warnings = parse_duration_text("45 mins")
        assert parsed == 2_700
        assert warnings == ()

    def test_30_mins(self) -> None:
        parsed, raw, warnings = parse_duration_text("30 mins")
        assert parsed == 1_800
        assert warnings == ()

    def test_58_mins(self) -> None:
        parsed, raw, warnings = parse_duration_text("58 mins")
        assert parsed == 3_480
        assert warnings == ()

    def test_clock_format(self) -> None:
        parsed, raw, warnings = parse_duration_text("01:30:00")
        assert parsed == 5_400
        assert warnings == ()

    def test_clock_format_hours_omitted(self) -> None:
        parsed, raw, warnings = parse_duration_text("45:00")
        assert parsed == 2_700
        assert warnings == ()

    def test_one_hour_45_mins(self) -> None:
        parsed, raw, warnings = parse_duration_text("1 hour 45 mins")
        assert parsed == 6_300
        assert warnings == ()

    def test_malformed_duration_produces_warning(self) -> None:
        parsed, raw, warnings = parse_duration_text("bogus")
        assert parsed is None
        assert raw == "bogus"
        assert len(warnings) == 1

    def test_empty_returns_none(self) -> None:
        parsed, raw, warnings = parse_duration_text("")
        assert parsed is None
        assert raw is None
        assert warnings == ()


class TestGradeParsing:
    def test_not_yet_graded(self) -> None:
        parsed, maximum, raw, warnings = parse_grade_text("Not yet graded")
        assert parsed is None
        assert maximum is None
        assert raw == "Not yet graded"
        assert warnings == ()

    def test_blank_grade(self) -> None:
        parsed, maximum, raw, warnings = parse_grade_text("")
        assert parsed is None
        assert maximum is None
        assert raw is None
        assert warnings == ()

    def test_decimal_grade(self) -> None:
        parsed, maximum, raw, warnings = parse_grade_text("7.5")
        assert parsed is not None and str(parsed) == "7.5"
        assert maximum is None
        assert raw == "7.5"
        assert warnings == ()

    def test_grade_with_denominator(self) -> None:
        parsed, maximum, raw, warnings = parse_grade_text("7.50/10.00")
        assert parsed is not None and str(parsed) == "7.50"
        assert maximum is not None and str(maximum) == "10.00"
        assert raw == "7.50/10.00"
        assert warnings == ()

    def test_grade_6_dot_5_over_10(self) -> None:
        parsed, maximum, raw, warnings = parse_grade_text("6.5/10")
        assert parsed is not None and str(parsed) == "6.5"
        assert maximum is not None and str(maximum) == "10"
        assert warnings == ()

    def test_malformed_grade_warning(self) -> None:
        parsed, maximum, raw, warnings = parse_grade_text("abc/def")
        assert parsed is None
        assert maximum is None
        assert raw == "abc/def"
        assert len(warnings) == 1

    def test_decimal_exactness_preserved(self) -> None:
        parsed, maximum, raw, warnings = parse_grade_text("9.00/10.00")
        assert parsed is not None and parsed == Decimal("9.00")
        assert maximum is not None and maximum == Decimal("10.00")
        assert warnings == ()
