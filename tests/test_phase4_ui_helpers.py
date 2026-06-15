"""Phase 4 UI helpers and masking tests."""

from __future__ import annotations

from services.identity_matching_service import (
    _mask_email,
    _mask_id,
    _mask_text,
)


class TestMaskText:
    def test_normal_name(self) -> None:
        result = _mask_text("John")
        assert result == "J**n"
        assert len(result) == 4

    def test_two_chars(self) -> None:
        result = _mask_text("Ab")
        assert result == "A*"

    def test_single_char(self) -> None:
        result = _mask_text("A")
        assert result == "A*"

    def test_empty(self) -> None:
        assert _mask_text("") == ""

    def test_none(self) -> None:
        assert _mask_text(None) == ""


class TestMaskEmail:
    def test_normal_email(self) -> None:
        result = _mask_email("john.doe@example.com")
        assert "@" in result
        assert result.endswith("@example.com")
        assert "john.doe" not in result

    def test_short_local_part(self) -> None:
        result = _mask_email("ab@test.com")
        assert result == "a*@test.com"

    def test_none(self) -> None:
        assert _mask_email(None) == ""

    def test_no_at_sign(self) -> None:
        """If there's no @, treat as regular text."""
        result = _mask_email("invalid")
        assert result == "i*****d"


class TestMaskId:
    def test_normal_id(self) -> None:
        result = _mask_id("S1234567")
        assert result == "S1****67"

    def test_short_id(self) -> None:
        result = _mask_id("AB")
        assert result == "**"

    def test_four_char_id(self) -> None:
        result = _mask_id("1234")
        assert result == "****"

    def test_none(self) -> None:
        assert _mask_id(None) == ""
