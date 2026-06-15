"""Abstract parser interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from parsers.models import ParsedImport


@dataclass(frozen=True, slots=True)
class ParserLimits:
    """Configurable limits for parsing."""

    max_upload_size_bytes: int = 20_000_000
    max_html_tables: int = 20
    max_import_rows: int = 10_000
    max_import_columns: int = 500
    max_cell_text_length: int = 1_000_000


class ImportParser(ABC):
    """Abstract base for all import parsers."""

    parser_name: str = ""

    @abstractmethod
    def parse(
        self,
        file_bytes: bytes,
        source_filename: str,
        *,
        limits: ParserLimits,
        table_index: int | None = None,
    ) -> ParsedImport:
        """Parse raw file bytes into a normalized ParsedImport.

        If table_index is specified, only that table is considered.
        Otherwise, auto-detect the best candidate.
        """
