"""Preview-only import service for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from config import get_settings
from parsers.base import ParserLimits
from parsers.html_parser import HtmlImportParser
from parsers.models import (
    ColumnClassification,
    MappingValidation,
    ParsedImport,
    ParsedValidationMessage,
    ReconciliationResult,
    ValidationSeverity,
)


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


def preview_html_import(file_bytes: bytes, source_filename: str, table_index: int | None = None) -> ImportPreviewResult:
    """Parse an uploaded file and return a UI-safe preview result.

    If table_index is provided, only that table is considered.
    """
    parser = HtmlImportParser()
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

    from collections import Counter
    counts = Counter(mapped_numbers)
    duplicates = sorted(n for n, c in counts.items() if c > 1)

    non_consec = False
    if mapped_numbers:
        sorted_mapped = sorted(mapped_numbers)
        for i in range(len(sorted_mapped) - 1):
            if sorted_mapped[i + 1] - sorted_mapped[i] > 1:
                non_consec = True
                break

    unresolved = bool(missing or extra or duplicates)
    exact_match = not unresolved and bool(mapped_numbers)

    if exact_match:
        message = "All response columns match the assessment questions."
    elif unresolved:
        parts = []
        if missing:
            parts.append(f"Missing question number(s): {missing}")
        if extra:
            parts.append(f"Extra response column number(s): {extra}")
        if duplicates:
            parts.append(f"Duplicate response number(s): {duplicates}")
        message = "; ".join(parts) + "." if parts else "Reconciliation unresolved."
    else:
        message = "No response columns mapped yet."

    return ReconciliationResult(
        exact_match=exact_match,
        mapped_response_numbers=tuple(sorted(mapped_numbers)),
        assessment_question_numbers=assessment_question_numbers,
        missing_question_numbers=tuple(missing),
        extra_response_numbers=tuple(extra),
        duplicate_response_numbers=tuple(duplicates),
        non_consecutive=non_consec,
        unresolved=unresolved,
        message=message,
    )


def validate_mapping(parsed_import: ParsedImport) -> MappingValidation:
    """Validate the column mapping configuration."""
    messages: list[ParsedValidationMessage] = []
    seen_identity_fields: dict[str, list[str]] = {}
    seen_response_numbers: dict[int, list[str]] = {}
    has_identity = False
    has_responses = False

    for col in parsed_import.columns:
        if col.classification is ColumnClassification.IDENTITY and col.mapped_field:
            has_identity = True
            if col.mapped_field not in seen_identity_fields:
                seen_identity_fields[col.mapped_field] = []
            seen_identity_fields[col.mapped_field].append(col.original_name)
        if col.classification is ColumnClassification.RESPONSE:
            has_responses = True
            rn = col.response_number
            if rn is not None:
                if rn not in seen_response_numbers:
                    seen_response_numbers[rn] = []
                seen_response_numbers[rn].append(col.original_name)

    dup_identity = tuple(f for f, cols in seen_identity_fields.items() if len(cols) > 1)
    dup_responses = tuple(n for n, cols in seen_response_numbers.items() if len(cols) > 1)

    for field in dup_identity:
        messages.append(ParsedValidationMessage(
            code="M001",
            severity=ValidationSeverity.WARNING,
            message=f"Multiple columns mapped to '{field}': {seen_identity_fields[field]}",
            blocking_stage="column mapping",
        ))

    for num in dup_responses:
        messages.append(ParsedValidationMessage(
            code="M002",
            severity=ValidationSeverity.ERROR,
            message=f"Multiple columns mapped to response number {num}: {seen_response_numbers[num]}",
            blocking_stage="column mapping",
        ))

    if not has_identity:
        messages.append(ParsedValidationMessage(
            code="M003",
            severity=ValidationSeverity.ERROR,
            message="No identity columns mapped",
            blocking_stage="column mapping",
        ))

    if not has_responses:
        messages.append(ParsedValidationMessage(
            code="M004",
            severity=ValidationSeverity.ERROR,
            message="No response columns mapped",
            blocking_stage="column mapping",
        ))

    valid = not any(m.severity is ValidationSeverity.ERROR for m in messages)
    return MappingValidation(
        valid=valid,
        messages=tuple(messages),
        duplicate_identity_fields=dup_identity,
        duplicate_response_numbers=dup_responses,
        has_identity=has_identity,
        has_responses=has_responses,
    )


def format_file_size(size_bytes: int) -> str:
    """Format a byte count for display."""
    units = ["B", "KB", "MB", "GB"]
    value = float(size_bytes)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.1f} {units[unit_index]}"
