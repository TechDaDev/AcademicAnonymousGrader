"""Parser registry — detects format by extension and returns the correct parser.

SECURITY:
- Extension/content mismatch is detected where possible
- Only known formats are accepted
- Unrecognized formats are rejected with a clear message
"""

from __future__ import annotations

from parsers.base import ImportParser
from parsers.csv_parser import CsvImportParser
from parsers.exceptions import UnsupportedFileTypeError
from parsers.html_parser import HtmlImportParser
from parsers.xlsx_parser import XlsxImportParser

# Registry of supported parsers by extension
_PARSER_REGISTRY: list[ImportParser] = [
    HtmlImportParser(),
    XlsxImportParser(),
    CsvImportParser(),
]

# Build extension-to-parser map
_EXTENSION_MAP: dict[str, ImportParser] = {}
for parser in _PARSER_REGISTRY:
    for ext in parser.SUPPORTED_EXTENSIONS:  # type: ignore[attr-defined]
        _EXTENSION_MAP[ext] = parser


SUPPORTED_EXTENSIONS = frozenset(_EXTENSION_MAP.keys())


def get_parser_for_filename(filename: str) -> ImportParser:
    """Return the appropriate parser for a given filename.

    Parameters
    ----------
    filename : str
        Source filename including extension.

    Returns
    -------
    ImportParser
        Matching parser instance.

    Raises
    ------
    UnsupportedFileTypeError
        If the file extension is not supported.
    """
    ext = _get_extension(filename)
    parser = _EXTENSION_MAP.get(ext)
    if parser is None:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext}'. Supported formats: {supported}"
        )
    return parser


def get_supported_extensions_display() -> str:
    """Return a human-readable list of supported extensions."""
    return ", ".join(sorted(SUPPORTED_EXTENSIONS))


def list_parsers() -> list[ImportParser]:
    """Return all registered parsers."""
    return list(_PARSER_REGISTRY)


def _get_extension(filename: str) -> str:
    """Get the lowercase file extension from a filename."""
    idx = filename.rfind(".")
    if idx == -1:
        return ""
    return filename[idx:].lower()
