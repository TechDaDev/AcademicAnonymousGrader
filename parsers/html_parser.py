"""HTML parser for Phase 3 preview imports."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup, Tag

from parsers.base import ImportParser, ParserLimits
from parsers.column_aliases import get_mapped_field, mapped_response_number
from parsers.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    ImportLimitExceededError,
    InvalidHtmlError,
    MissingIdentityColumnsError,
    MissingResponseColumnsError,
    MultipleCandidateTablesError,
    NoResponseTableFoundError,
    NoTableFoundError,
    UnsupportedFileTypeError,
)
from parsers.models import (
    ColumnClassification,
    ImportStatistics,
    ParsedColumn,
    ParsedImport,
    ParsedResponse,
    ParsedStudentRow,
    ParsedValidationMessage,
    TableCandidate,
    ValidationSeverity,
)
from parsers.normalization import (
    normalize_header,
    normalize_lookup_key,
    normalize_text_cell,
    parse_datetime_text,
    parse_duration_text,
    parse_grade_text,
)

_DISALLOWED_TAGS = {"script", "style", "iframe", "object", "embed", "form", "link", "meta"}


class HtmlImportParser(ImportParser):
    """Safe HTML table parser for anonymous response files."""

    parser_name = "html-bs4-lxml"
    SUPPORTED_EXTENSIONS = frozenset({".html", ".htm"})

    def parse(
        self,
        file_bytes: bytes,
        source_filename: str,
        *,
        limits: ParserLimits,
        table_index: int | None = None,
    ) -> ParsedImport:
        started_at = datetime.now(UTC)
        self._validate_input(file_bytes, source_filename, limits)
        soup = BeautifulSoup(file_bytes, "lxml")
        self._sanitize(soup)

        tables = soup.find_all("table")
        if not tables:
            raise NoTableFoundError("No HTML table was found in the uploaded file")
        if len(tables) > limits.max_html_tables:
            raise ImportLimitExceededError("The uploaded file contains too many tables")

        candidates: list[TableCandidate] = []
        if table_index is not None:
            if table_index < 0 or table_index >= len(tables):
                raise NoTableFoundError(
                    f"Selected table index {table_index} is out of range "
                    f"(0–{len(tables) - 1})"
                )
            selected_index = table_index
            selected_table = tables[selected_index]
            columns, rows, parse_messages = self._parse_table(selected_table, limits)
        else:
            candidates = self._find_candidates(tables, limits)
            if not candidates:
                raise NoResponseTableFoundError("No candidate response table was detected")

            best_score = max(candidate.score for candidate in candidates)
            best = [candidate for candidate in candidates if candidate.score == best_score]
            if len(best) > 1:
                raise MultipleCandidateTablesError("Multiple candidate response tables were detected")

            selected_index = best[0].index
            selected_table = tables[selected_index]
            columns, rows, parse_messages = self._parse_table(selected_table, limits)

        if not any(column.classification is ColumnClassification.IDENTITY for column in columns):
            raise MissingIdentityColumnsError("No identity columns were detected")
        if not any(column.classification is ColumnClassification.RESPONSE for column in columns):
            raise MissingResponseColumnsError("No response columns were detected")

        response_columns = tuple(column for column in columns if column.classification is ColumnClassification.RESPONSE)
        unknown_columns = tuple(column for column in columns if column.classification is ColumnClassification.UNKNOWN)
        statistics = self._build_statistics(columns, rows)

        return ParsedImport(
            source_filename=source_filename,
            parser_name=self.parser_name,
            table_index=selected_index,
            columns=columns,
            rows=rows,
            response_columns=response_columns,
            unknown_columns=unknown_columns,
            warnings=tuple(message for message in parse_messages if message.severity is ValidationSeverity.WARNING),
            errors=tuple(message for message in parse_messages if message.severity is ValidationSeverity.ERROR),
            statistics=statistics,
            parse_started_at=started_at,
            parse_completed_at=datetime.now(UTC),
            candidate_tables=tuple(candidates),
        )

    def _validate_input(self, file_bytes: bytes, source_filename: str, limits: ParserLimits) -> None:
        if not source_filename.lower().endswith((".html", ".htm")):
            raise UnsupportedFileTypeError("Only .html and .htm files are supported")
        if not file_bytes:
            raise EmptyFileError("The uploaded file is empty")
        if len(file_bytes) > limits.max_upload_size_bytes:
            raise FileTooLargeError("The uploaded file exceeds the configured size limit")
        if b"\x00" in file_bytes[:4096]:
            raise InvalidHtmlError("The uploaded file appears to be binary")

    def _sanitize(self, soup: BeautifulSoup) -> None:
        for tag in soup.find_all(True):
            if tag.name in _DISALLOWED_TAGS:
                tag.decompose()
                continue
            for attr in list(tag.attrs):
                if attr.lower().startswith("on"):
                    del tag.attrs[attr]

    def _find_candidates(self, tables: list[Tag], limits: ParserLimits) -> list[TableCandidate]:
        candidates: list[TableCandidate] = []
        for index, table in enumerate(tables):
            headers = self._extract_headers(table, limits)
            if not headers:
                continue
            if len(headers) > limits.max_import_columns:
                raise ImportLimitExceededError("A table exceeds the configured column limit")
            normalized_headers = [normalize_header(header) for header in headers]
            identity_fields = {"first_name", "last_name", "email", "institutional_student_id"}
            identity_count = sum(1 for h in normalized_headers if get_mapped_field(h) in identity_fields)
            metadata_fields = {"status", "started", "completed", "duration", "source_grade"}
            metadata_count = sum(1 for h in normalized_headers if get_mapped_field(h) in metadata_fields)
            response_count = sum(1 for header in normalized_headers if self._is_response_header(header))
            row_count = max(len(table.find_all("tr")) - 1, 0)
            score = identity_count * 3 + metadata_count * 2 + response_count * 4 + (2 if row_count else 0)
            if response_count:
                candidates.append(
                    TableCandidate(
                        index=index,
                        score=score,
                        headers=tuple(normalized_headers),
                        row_count=row_count,
                        identity_columns=identity_count,
                        response_columns=response_count,
                        metadata_columns=metadata_count,
                    )
                )
        return candidates

    def _parse_table(
        self, table: Tag, limits: ParserLimits
    ) -> tuple[tuple[ParsedColumn, ...], tuple[ParsedStudentRow, ...], tuple[ParsedValidationMessage, ...]]:
        rows = table.find_all("tr")
        if not rows:
            raise NoTableFoundError("The selected table has no rows")
        header_row = rows[0]
        headers = self._extract_row_texts(header_row, limits)
        if not headers:
            raise NoTableFoundError("The selected table has no headers")

        columns: list[ParsedColumn] = []
        parse_messages: list[ParsedValidationMessage] = []
        _ = limits  # used via _extract_row_texts
        next_response_number = 1
        used_response_numbers: set[int] = set()

        for index, header in enumerate(headers):
            normalized = normalize_header(header)
            mapped_field = get_mapped_field(normalized)
            classification = ColumnClassification.UNKNOWN
            response_number = None
            confidence = 0.15
            if mapped_field in {"first_name", "last_name", "email", "institutional_student_id"}:
                classification = ColumnClassification.IDENTITY
                confidence = 0.98
            elif mapped_field in {"status", "started", "completed", "duration", "source_grade"}:
                classification = ColumnClassification.METADATA
                confidence = 0.94
            elif self._is_response_header(normalized):
                classification = ColumnClassification.RESPONSE
                response_number = mapped_response_number(normalized)
                if response_number is None:
                    while next_response_number in used_response_numbers:
                        next_response_number += 1
                    response_number = next_response_number
                    used_response_numbers.add(response_number)
                    next_response_number += 1
                    parse_messages.append(
                        ParsedValidationMessage(
                            code="R001",
                            severity=ValidationSeverity.WARNING,
                            message=(
                        f"Response column '{header}' had no number "
                        "and was assigned a sequential question number"
                    ),
                            column_name=header,
                            blocking_stage="column mapping",
                        )
                    )
                confidence = 0.9
            columns.append(
                ParsedColumn(
                    original_name=header,
                    normalized_name=normalized,
                    index=index,
                    classification=classification,
                    mapped_field=mapped_field,
                    is_required=mapped_field in {"first_name", "email"},
                    confidence=confidence,
                    warnings=(),
                    response_number=response_number,
                )
            )

        if len(columns) > limits.max_import_columns:
            raise ImportLimitExceededError("The selected table exceeds the configured column limit")

        student_rows: list[ParsedStudentRow] = []
        seen_emails: set[str] = set()
        seen_student_ids: set[str] = set()
        for row_number, row in enumerate(rows[1:], start=1):
            if row_number > limits.max_import_rows:
                raise ImportLimitExceededError("The selected table exceeds the configured row limit")
            cell_texts = self._extract_row_texts(row, limits)
            raw_values = {
                column.original_name: cell_texts[index] if index < len(cell_texts) else ""
                for index, column in enumerate(columns)
            }
            student_rows.append(
                self._build_row(
                    row_number, tuple(columns), raw_values, limits,
                    seen_emails, seen_student_ids,
                )
            )

        return tuple(columns), tuple(student_rows), tuple(parse_messages)

    def _build_row(
        self,
        row_number: int,
        columns: tuple[ParsedColumn, ...],
        raw_values: dict[str, str],
        limits: ParserLimits,
        seen_emails: set[str],
        seen_student_ids: set[str],
    ) -> ParsedStudentRow:
        warnings: list[ParsedValidationMessage] = []
        errors: list[ParsedValidationMessage] = []
        first_name = None
        last_name = None
        email = None
        institutional_student_id = None
        status = None
        started = None
        completed = None
        duration_seconds = None
        source_grade = None
        source_grade_maximum = None
        raw_source_grade = None
        responses: list[ParsedResponse] = []
        unknown_values: dict[str, str] = {}

        for column in columns:
            value = normalize_text_cell(raw_values.get(column.original_name, ""))
            if column.classification is ColumnClassification.IDENTITY:
                if column.mapped_field == "first_name":
                    first_name = value or None
                elif column.mapped_field == "last_name":
                    last_name = value or None
                elif column.mapped_field == "email":
                    email = value.casefold() or None
                elif column.mapped_field == "institutional_student_id":
                    institutional_student_id = value or None
            elif column.classification is ColumnClassification.METADATA:
                if column.mapped_field == "status":
                    status = value or None
                elif column.mapped_field == "started":
                    started, _, dt_warnings = parse_datetime_text(value)
                    warnings.extend(
                        ParsedValidationMessage(
                            code="SM002",
                            severity=ValidationSeverity.WARNING,
                            message=message,
                            row_number=row_number,
                            column_name=column.original_name,
                            blocking_stage="metadata parsing",
                        )
                        for message in dt_warnings
                    )
                elif column.mapped_field == "completed":
                    completed, _, dt_warnings = parse_datetime_text(value)
                    warnings.extend(
                        ParsedValidationMessage(
                            code="SM003",
                            severity=ValidationSeverity.WARNING,
                            message=message,
                            row_number=row_number,
                            column_name=column.original_name,
                            blocking_stage="metadata parsing",
                        )
                        for message in dt_warnings
                    )
                elif column.mapped_field == "duration":
                    duration_seconds, _, duration_warnings = parse_duration_text(value)
                    warnings.extend(
                        ParsedValidationMessage(
                            code="SM005",
                            severity=ValidationSeverity.WARNING,
                            message=message,
                            row_number=row_number,
                            column_name=column.original_name,
                            blocking_stage="metadata parsing",
                        )
                        for message in duration_warnings
                    )
                elif column.mapped_field == "source_grade":
                    source_grade, source_grade_maximum, raw_source_grade, grade_warnings = parse_grade_text(value)
                    warnings.extend(
                        ParsedValidationMessage(
                            code="SM006",
                            severity=ValidationSeverity.WARNING,
                            message=message,
                            row_number=row_number,
                            column_name=column.original_name,
                            blocking_stage="metadata parsing",
                        )
                        for message in grade_warnings
                    )
            elif column.classification is ColumnClassification.RESPONSE:
                responses.append(
                    ParsedResponse(
                        question_number=column.response_number or 0,
                        column_name=column.original_name,
                        text=value,
                        is_blank=not value.strip(),
                    )
                )
            elif value:
                unknown_values[column.original_name] = value

        if email and email in seen_emails:
            warnings.append(
                ParsedValidationMessage(
                    code="S005",
                    severity=ValidationSeverity.WARNING,
                    message="Duplicate email within the same file",
                    row_number=row_number,
                    column_name="email",
                    blocking_stage="row validation",
                )
            )
        elif email:
            seen_emails.add(email)

        if institutional_student_id and institutional_student_id in seen_student_ids:
            warnings.append(
                ParsedValidationMessage(
                    code="S006",
                    severity=ValidationSeverity.WARNING,
                    message="Duplicate institutional student ID within the same file",
                    row_number=row_number,
                    column_name="institutional_student_id",
                    blocking_stage="row validation",
                )
            )
        elif institutional_student_id:
            seen_student_ids.add(institutional_student_id)

        if started and completed and completed < started:
            warnings.append(
                ParsedValidationMessage(
                    code="SM004",
                    severity=ValidationSeverity.WARNING,
                    message="Completed time is before started time",
                    row_number=row_number,
                    column_name="completed",
                    blocking_stage="row validation",
                )
            )

        has_identity = any([first_name, last_name, email, institutional_student_id])
        has_responses = any(not response.is_blank for response in responses)
        if not has_identity and has_responses:
            errors.append(
                ParsedValidationMessage(
                    code="S016",
                    severity=ValidationSeverity.ERROR,
                    message="Rows with responses but no identity are blocking errors",
                    row_number=row_number,
                    blocking_stage="row validation",
                )
            )
        if not has_identity and not has_responses:
            warnings.append(
                ParsedValidationMessage(
                    code="S000",
                    severity=ValidationSeverity.INFORMATION,
                    message="Row has no usable identity fields and no responses",
                    row_number=row_number,
                    blocking_stage="row validation",
                )
            )

        return ParsedStudentRow(
            row_number=row_number,
            first_name=first_name,
            last_name=last_name,
            email=email,
            institutional_student_id=institutional_student_id,
            status=status,
            started=started,
            completed=completed,
            duration_seconds=duration_seconds,
            source_grade=source_grade,
            raw_source_grade=raw_source_grade,
            source_grade_maximum=source_grade_maximum,
            responses=tuple(responses),
            unknown_values=unknown_values,
            warnings=tuple(warnings),
            errors=tuple(errors),
            ignored=not has_identity and not has_responses,
        )

    def _build_statistics(
        self, columns: tuple[ParsedColumn, ...], rows: tuple[ParsedStudentRow, ...]
    ) -> ImportStatistics:
        return ImportStatistics(
            total_rows=len(rows),
            valid_rows=sum(1 for row in rows if not row.errors),
            warning_rows=sum(1 for row in rows if row.warnings),
            error_rows=sum(1 for row in rows if row.errors),
            blank_response_count=sum(1 for row in rows for response in row.responses if response.is_blank),
            response_column_count=sum(
                1 for column in columns
                if column.classification is ColumnClassification.RESPONSE
            ),
            duplicate_email_count=sum(1 for row in rows for message in row.warnings if message.code == "S005"),
            duplicate_student_id_count=sum(1 for row in rows for message in row.warnings if message.code == "S006"),
            unfinished_submission_count=sum(1 for row in rows for message in row.warnings if message.code == "SM001"),
            unknown_column_count=sum(1 for column in columns if column.classification is ColumnClassification.UNKNOWN),
        )

    def _extract_row_texts(self, row: Tag, limits: ParserLimits) -> list[str]:
        cells = row.find_all(["th", "td"], recursive=False)
        return [self._extract_cell_text(cell, limits) for cell in cells[: limits.max_import_columns]]

    def _extract_headers(self, table: Tag, limits: ParserLimits) -> list[str]:
        first_row = table.find("tr")
        if not first_row:
            return []
        return self._extract_row_texts(first_row, limits)

    def _extract_cell_text(self, cell: Tag, limits: ParserLimits) -> str:
        text = cell.get_text(separator="\n", strip=False)
        normalized = normalize_text_cell(text)
        if len(normalized) > limits.max_cell_text_length:
            return normalized[: limits.max_cell_text_length]
        return normalized

    def _is_response_header(self, value: str) -> bool:
        return bool(re.search(r"(?:response|answer|question)", normalize_lookup_key(value)))
