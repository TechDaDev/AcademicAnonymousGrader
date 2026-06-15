# Academic Anonymous Grader — Validation Tests
"""Tests for services/validation.py."""

from __future__ import annotations

from decimal import Decimal

import pytest

from services.validation import (
    normalize_optional_text,
    normalize_required_text,
    validate_positive_decimal,
    validate_positive_int,
    validate_question_total,
    validate_status_transition,
)


class TestNormalizeRequired:
    def test_required_text(self) -> None:
        assert normalize_required_text("Hello") == "Hello"

    def test_required_trim(self) -> None:
        assert normalize_required_text("  Hello  ") == "Hello"

    def test_required_none_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be blank"):
            normalize_required_text(None)

    def test_required_blank_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be blank"):
            normalize_required_text("   ")

    def test_required_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="must not exceed"):
            normalize_required_text("A" * 300, max_length=200)


class TestNormalizeOptional:
    def test_optional_text(self) -> None:
        assert normalize_optional_text("Hello") == "Hello"

    def test_optional_none(self) -> None:
        assert normalize_optional_text(None) is None

    def test_optional_blank(self) -> None:
        assert normalize_optional_text("   ") is None

    def test_optional_trim(self) -> None:
        assert normalize_optional_text("  Hi  ") == "Hi"

    def test_optional_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="must not exceed"):
            normalize_optional_text("A" * 300, max_length=200)


class TestValidateDecimal:
    def test_positive_decimal(self) -> None:
        assert validate_positive_decimal("10.00") == Decimal("10.00")

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="greater than zero"):
            validate_positive_decimal("0")

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="greater than zero"):
            validate_positive_decimal("-1")

    def test_too_many_decimals_raises(self) -> None:
        with pytest.raises(ValueError, match="at most 2 decimal places"):
            validate_positive_decimal("10.123")


class TestValidateInt:
    def test_positive_int(self) -> None:
        assert validate_positive_int("5") == 5

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="greater than zero"):
            validate_positive_int(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="greater than zero"):
            validate_positive_int(-1)


class TestQuestionTotal:
    def test_exact_match(self) -> None:
        valid, diff, msg = validate_question_total(Decimal("100"), Decimal("100"))
        assert valid is True
        assert diff == Decimal("0")

    def test_below(self) -> None:
        valid, diff, _ = validate_question_total(Decimal("80"), Decimal("100"))
        assert valid is False
        assert diff == Decimal("20")

    def test_above(self) -> None:
        valid, diff, _ = validate_question_total(Decimal("120"), Decimal("100"))
        assert valid is False
        assert diff == Decimal("-20")


class TestStatusTransition:
    def test_draft_to_ready(self) -> None:
        validate_status_transition("draft", "ready")  # no error

    def test_draft_to_archived(self) -> None:
        validate_status_transition("draft", "archived")  # no error

    def test_finalized_to_draft_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot transition"):
            validate_status_transition("finalized", "draft")
