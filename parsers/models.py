"""Parser data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class ValidationSeverity(str, Enum):  # noqa: UP042 — StrEnum is 3.11+
    """Validation severity levels."""

    INFORMATION = "information"
    WARNING = "warning"
    ERROR = "error"


class ColumnClassification(str, Enum):  # noqa: UP042 — StrEnum is 3.11+
    """Detected column type."""

    IDENTITY = "identity"
    METADATA = "metadata"
    RESPONSE = "response"
    UNKNOWN = "unknown"
    IGNORED = "ignored"


@dataclass(frozen=True, slots=True)
class ParsedValidationMessage:
    code: str
    severity: ValidationSeverity
    message: str
    row_number: int | None = None
    column_name: str | None = None
    blocking_stage: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedColumn:
    original_name: str
    normalized_name: str
    index: int
    classification: ColumnClassification
    mapped_field: str | None
    is_required: bool
    confidence: float
    warnings: tuple[str, ...] = ()
    response_number: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedResponse:
    question_number: int
    column_name: str
    text: str
    is_blank: bool


@dataclass(frozen=True, slots=True)
class ParsedStudentRow:
    row_number: int
    first_name: str | None
    last_name: str | None
    email: str | None
    institutional_student_id: str | None
    status: str | None
    started: datetime | None
    completed: datetime | None
    duration_seconds: int | None
    source_grade: Decimal | None
    raw_source_grade: str | None
    source_grade_maximum: Decimal | None
    responses: tuple[ParsedResponse, ...]
    unknown_values: dict[str, str]
    warnings: tuple[ParsedValidationMessage, ...] = field(default_factory=tuple)
    errors: tuple[ParsedValidationMessage, ...] = field(default_factory=tuple)
    ignored: bool = False


@dataclass(frozen=True, slots=True)
class TableCandidate:
    index: int
    score: int
    headers: tuple[str, ...]
    row_count: int
    identity_columns: int
    response_columns: int
    metadata_columns: int


@dataclass(frozen=True, slots=True)
class ImportStatistics:
    total_rows: int
    valid_rows: int
    warning_rows: int
    error_rows: int
    blank_response_count: int
    response_column_count: int
    duplicate_email_count: int
    duplicate_student_id_count: int = 0
    unfinished_submission_count: int = 0
    unknown_column_count: int = 0


@dataclass(frozen=True, slots=True)
class ParsedImport:
    source_filename: str
    parser_name: str
    table_index: int | None
    columns: tuple[ParsedColumn, ...]
    rows: tuple[ParsedStudentRow, ...]
    response_columns: tuple[ParsedColumn, ...]
    unknown_columns: tuple[ParsedColumn, ...]
    warnings: tuple[ParsedValidationMessage, ...]
    errors: tuple[ParsedValidationMessage, ...]
    statistics: ImportStatistics
    parse_started_at: datetime
    parse_completed_at: datetime
    candidate_tables: tuple[TableCandidate, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Result of comparing mapped response columns with assessment questions."""

    exact_match: bool
    mapped_response_numbers: tuple[int, ...]
    assessment_question_numbers: tuple[int, ...]
    missing_question_numbers: tuple[int, ...]
    extra_response_numbers: tuple[int, ...]
    duplicate_response_numbers: tuple[int, ...]
    non_consecutive: bool
    unresolved: bool
    message: str


@dataclass(frozen=True, slots=True)
class MappingValidation:
    """Validation result for a column mapping configuration."""

    valid: bool
    messages: tuple[ParsedValidationMessage, ...]
    duplicate_identity_fields: tuple[str, ...]
    duplicate_response_numbers: tuple[int, ...]
    has_identity: bool
    has_responses: bool
