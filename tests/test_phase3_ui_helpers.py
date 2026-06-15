"""UI helper tests for Phase 3 — format helpers, label constants."""

from __future__ import annotations

from services.import_preview_service import format_file_size


class TestFormatFileSize:
    def test_bytes(self) -> None:
        assert format_file_size(0) == "0 B"
        assert format_file_size(1) == "1 B"

    def test_kilobytes(self) -> None:
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"

    def test_megabytes(self) -> None:
        assert format_file_size(1_048_576) == "1.0 MB"

    def test_gigabytes(self) -> None:
        assert format_file_size(1_073_741_824) == "1.0 GB"
