"""Preview-only import service for Phase 3–9 (HTML, XLSX, CSV)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256

from config import get_settings
from parsers.base import ParserLimits
from parsers.models import (
    ColumnClassification,
    MappingValidation,
    ParsedImport,
    ParsedValidationMessage,
    ReconciliationResult,
    ValidationSeverity,
)
from parsers.parser_registry import get_parser_for_filename


@dataclass(frozen=True, slots=True)
class ImportPreviewResult:
    parsed_import: ParsedImport
    file_hash: str
    file_size: int
    file_name: str
    ready_for_phase4: bool


def build_parser_limits() -> ParserLimits:
    """Convert application settings into parser limits."""
    settings = get_settings()
    return ParserLimits(
        max_upload_size_bytes=settings.max_upload_size_bytes,
        max_html_tables=settings.max_html_tables,
        max_import_rows=settings.max_import_rows,
        max_import_columns=settings.max_import_columns,
        max_cell_text_length=settings.max_cell_text_length,
    )


def preview_import(file_bytes: bytes, source_filename: str, table_index: int | None = None) -> ImportPreviewResult:
    """Parse an uploaded file (HTML, XLSX, or CSV) and return a UI-safe preview result.

    Uses the parser registry to select the correct parser by file extension.

    Parameters
    ----------
    file_bytes : bytes
        Raw file content.
    source_filename : str
        Original filename including extension.
    table_index : int | None
        For HTML: table index. For XLSX: sheet index into visible sheets.

    Returns
    -------
    ImportPreviewResult
        Normalized preview result.

    Raises
    ------
    ImportParserError
        If the file cannot be parsed or format is unsupported.
    """
    parser = get_parser_for_filename(source_filename)
    parsed_import = parser.parse(
        file_bytes, source_filename, limits=build_parser_limits(), table_index=table_index
    )
    ready_for_phase4 = not parsed_import.errors and all(not row.errors for row in parsed_import.rows)
    return ImportPreviewResult(
        parsed_import=parsed_import,
        file_hash=sha256(file_bytes).hexdigest(),
        file_size=len(file_bytes),
        file_name=source_filename,
        ready_for_phase4=ready_for_phase4,
    )


# Keep backward-compatible alias
preview_html_import = preview_import


def reconcile_assessment(
    parsed_import: ParsedImport,
    assessment_question_numbers: tuple[int, ...],
) -> ReconciliationResult:
    """Compare mapped response numbers with assessment question numbers."""
    mapped_numbers: list[int] = []
    for col in parsed_import.columns:
        if col.classification is ColumnClassification.RESPONSE and col.response_number is not None:
            mapped_numbers.append(col.response_number)

    mapped_set = set(mapped_numbers)
    question_set = set(assessment_question_numbers)
    missing = sorted(question_set - mapped_set)
    extra = sorted(mapped_set - question_set)

    counts = Counter(mapped_numbers)
    duplicates = sorted(n for n, c in counts.items() if c > 1)

    non_consec = False
    if mapped_numbers:
        sorted_mapped = sorted(set(mapped_numbers))
        expected = list(range(sorted_mapped[0], sorted_mapped[-1] + 1))
        # Only flag non-consecutive if the gap is not in the assessment itself
        if sorted_mapped != expected:
            # Check if the gaps correspond to gaps in the assessment question numbers
            sorted_questions = sorted(set(assessment_question_numbers))
            if sorted_questions != expected:
                # Assessment itself is non-consecutive — mapped numbers should
                # match the assessment's structure instead of a full range
                non_consec = sorted_mapped != sorted_questions
            else:
                non_consec = True

    unresolved = bool(missing or duplicates or non_consec)

    parts: list[str] = []
    if missing:
        parts.append(f"Missing question(s): {missing}")
    if duplicates:
        parts.append(f"Duplicate response column(s): {duplicates}")
    if non_consec:
        parts.append("Response columns are not consecutive.")
    if not unresolved:
        parts.append("All questions matched.")

    return ReconciliationResult(
        exact_match=not unresolved and not extra,
        mapped_response_numbers=tuple(sorted(set(mapped_numbers))),
        assessment_question_numbers=assessment_question_numbers,
        missing_question_numbers=tuple(missing),
        extra_response_numbers=tuple(extra),
        duplicate_response_numbers=tuple(duplicates),
        non_consecutive=non_consec,
        unresolved=unresolved,
        message=" | ".join(parts),
    )


def validate_mapping(
    parsed_import: ParsedImport,
) -> MappingValidation:
    """Validate that the column mapping has required identity and response columns."""
    messages: list[ParsedValidationMessage] = []
    identity_fields: set[str] = set()
    response_numbers: list[int] = []
    duplicate_identity: list[str] = []
    duplicate_response_nums: list[int] = []
    has_identity = False
    has_responses = False

    seen_identity: dict[str, int] = {}
    seen_responses: set[int] = set()

    for col in parsed_import.columns:
        if col.classification is ColumnClassification.IDENTITY and col.mapped_field:
            has_identity = True
            if col.mapped_field in seen_identity:
                duplicate_identity.append(col.mapped_field)
            seen_identity[col.mapped_field] = seen_identity.get(col.mapped_field, 0) + 1
            identity_fields.add(col.mapped_field)

        if col.classification is ColumnClassification.RESPONSE and col.response_number is not None:
            has_responses = True
            if col.response_number in seen_responses:
                duplicate_response_nums.append(col.response_number)
            seen_responses.add(col.response_number)
            response_numbers.append(col.response_number)

    if not has_identity:
        messages.append(
            ParsedValidationMessage(
                code="M001",
                severity=ValidationSeverity.ERROR,
                message=(
                    "No identity columns mapped. Map at least one of: "
                    "first name, last name, email, or institutional ID."
                ),
                blocking_stage="mapping",
            )
        )
    if not has_responses:
        messages.append(
            ParsedValidationMessage(
                code="M002",
                severity=ValidationSeverity.ERROR,
                message="No response columns mapped.",
                blocking_stage="mapping",
            )
        )
    if duplicate_identity:
        messages.append(
            ParsedValidationMessage(
                code="M003",
                severity=ValidationSeverity.WARNING,
                message=f"Duplicate identity mapping: {', '.join(duplicate_identity)}.",
                blocking_stage="mapping",
            )
        )
    if duplicate_response_nums:
        messages.append(
            ParsedValidationMessage(
                code="M004",
                severity=ValidationSeverity.ERROR,
                message=f"Duplicate response numbers: {duplicate_response_nums}.",
                blocking_stage="mapping",
            )
        )

    return MappingValidation(
        valid=has_identity and has_responses and not duplicate_response_nums,
        messages=tuple(messages),
        duplicate_identity_fields=tuple(duplicate_identity),
        duplicate_response_numbers=tuple(duplicate_response_nums),
        has_identity=has_identity,
        has_responses=has_responses,
    )


def format_file_size(size_bytes: int) -> str:
    """Format file size in a human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
