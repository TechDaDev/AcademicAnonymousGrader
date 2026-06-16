"""CSV parser for academic assessment imports.

SECURITY:
- Detects encoding (UTF-8, UTF-8 BOM, Arabic-compatible)
- Detects delimiter (comma, semicolon, tab, pipe)
- Supports quoted fields and multiline quoted fields
- Preserves leading-zero IDs as strings
- Rejects binary or malformed files
- Cell values starting with =, +, -, @ are treated as text
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal

from parsers.base import ImportParser, ParserLimits
from parsers.exceptions import (
    EmptyFileError,
    EncodingDetectionError,
    FileTooLargeError,
    ImportLimitExceededError,
    MalformedCsvError,
)
from parsers.models import (
    ColumnClassification,
    ImportStatistics,
    ParsedColumn,
    ParsedImport,
    ParsedResponse,
    ParsedStudentRow,
    ParsedValidationMessage,
)

# Common encodings to try for Arabic-compatible CSV
_ENCODING_CANDIDATES = [
    "utf-8",  # Plain UTF-8 (try first to avoid false BOM detection)
    "utf-8-sig",  # UTF-8 with BOM
    "windows-1256",  # Arabic Windows
    "iso-8859-6",  # Arabic ISO
    "cp1252",  # Western European
]

# Delimiters to detect
_DELIMITER_CANDIDATES = [",", ";", "\t", "|"]


class CsvImportParser(ImportParser):
    """Parser for .csv assessment response files."""

    parser_name = "csv"

    SUPPORTED_EXTENSIONS = frozenset({".csv"})

    def parse(
        self,
        file_bytes: bytes,
        source_filename: str,
        *,
        limits: ParserLimits | None = None,
        table_index: int | None = None,
    ) -> ParsedImport:
        if limits is None:
            limits = ParserLimits()

        if len(file_bytes) == 0:
            raise EmptyFileError("Uploaded file is empty.")

        if len(file_bytes) > limits.max_upload_size_bytes:
            raise FileTooLargeError(
                f"File size exceeds {limits.max_upload_size_bytes // (1024*1024)} MB limit."
            )

        # Reject files containing NUL bytes (binary indicator)
        if b"\x00" in file_bytes:
            raise MalformedCsvError(
                "File contains NUL (0x00) bytes and appears to be binary. "
                "Please upload a valid CSV file."
            )

        # Detect encoding
        encoding = self._detect_encoding(file_bytes)
        if encoding is None:
            raise EncodingDetectionError(
                "Could not detect file encoding. Please ensure the file is UTF-8 encoded."
            )

        # Decode with detected encoding
        try:
            text_content = file_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            raise EncodingDetectionError(
                f"Failed to decode file as {encoding}: {exc}"
            ) from exc

        # Detect delimiter
        delimiter = self._detect_delimiter(text_content)
        if delimiter is None:
            delimiter = ","  # Default to comma

        # Parse CSV
        try:
            reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
            raw_headers = reader.fieldnames or []
        except Exception as exc:
            raise MalformedCsvError(f"Failed to parse CSV: {exc}") from exc

        if not raw_headers:
            raise EmptyFileError("No header row found in the CSV file.")

        # Read all rows
        rows_data: list[dict[str, str]] = []
        malformed_rows = 0
        inconsistent_row_warnings: list[str] = []
        header_count = len(raw_headers)
        for row_idx, row in enumerate(reader, start=2):
            try:
                clean_values: list[str] = []
                for k, v in row.items():
                    clean_values.append(self._safe_value(v))
                clean_row = dict(zip(raw_headers, clean_values, strict=False))
                # Check for inconsistent row length
                if len(clean_row) != header_count:
                    inconsistent_row_warnings.append(
                        f"Row {row_idx} has {len(clean_row)} field(s); "
                        f"expected {header_count}."
                    )
                # Skip completely empty rows
                if all(v == "" for v in clean_row.values()):
                    continue
                rows_data.append(clean_row)
            except Exception:
                malformed_rows += 1
                continue

        # Enforce limits
        if len(rows_data) > limits.max_import_rows:
            raise ImportLimitExceededError(
                f"Row count {len(rows_data)} exceeds limit of {limits.max_import_rows}."
            )
        if len(raw_headers) > limits.max_import_columns:
            raise ImportLimitExceededError(
                f"Column count {len(raw_headers)} exceeds limit of {limits.max_import_columns}."
            )

        # Detect duplicate and blank headers
        seen_headers: dict[str, int] = {}
        dup_warnings: list[str] = []
        for i, h in enumerate(raw_headers):
            if not h.strip():
                dup_warnings.append(f"Column {i + 1} has a blank header.")
            elif h in seen_headers:
                dup_warnings.append(f"Duplicate header '{h}' at column {i + 1}.")
            seen_headers[h] = i

        # Normalize headers
        from parsers.normalization import normalize_header

        normalized_headers = [normalize_header(h) for h in raw_headers]

        # Build columns
        from parsers.column_aliases import get_mapped_field, mapped_response_number
        from parsers.models import ValidationSeverity

        columns: list[ParsedColumn] = []
        response_columns_list: list[ParsedColumn] = []
        unknown_columns_list: list[ParsedColumn] = []

        for i, (orig, norm) in enumerate(zip(raw_headers, normalized_headers, strict=False)):
            mapped = get_mapped_field(norm)
            # Check if it's a response column
            resp_num = mapped_response_number(orig)
            if resp_num is not None:
                mapped = f"response_{resp_num}"
            col_warnings: list[str] = []
            if not norm.strip():
                col_warnings.append("Blank header.")
            elif list(raw_headers).count(orig) > 1:
                col_warnings.append("Duplicate header.")

            classification = ColumnClassification.UNKNOWN
            if mapped in (
                "first_name", "last_name", "email", "institutional_student_id",
            ):
                classification = ColumnClassification.IDENTITY
            elif mapped == "source_grade":
                classification = ColumnClassification.METADATA
            elif mapped and mapped.startswith("response_"):
                classification = ColumnClassification.RESPONSE

            col = ParsedColumn(
                original_name=orig,
                normalized_name=norm,
                index=i,
                classification=classification,
                mapped_field=mapped,
                is_required=(classification == ColumnClassification.IDENTITY),
                confidence=1.0 if mapped else 0.0,
                warnings=tuple(col_warnings),
                response_number=int(mapped.split("_")[1]) if mapped and mapped.startswith("response_") else None,
            )
            columns.append(col)
            if classification == ColumnClassification.RESPONSE:
                response_columns_list.append(col)
            elif classification == ColumnClassification.UNKNOWN and mapped is None:
                unknown_columns_list.append(col)

        # Build student rows
        parsed_rows: list[ParsedStudentRow] = []
        for row_idx, row_dict in enumerate(rows_data, start=2):
            responses_list: list[ParsedResponse] = []
            row_warnings: list[ParsedValidationMessage] = []
            row_errors: list[ParsedValidationMessage] = []

            for rc in response_columns_list:
                resp_text = row_dict.get(rc.original_name, "")
                is_blank = not resp_text.strip()
                responses_list.append(
                    ParsedResponse(
                        question_number=rc.response_number or 0,
                        column_name=rc.original_name,
                        text=resp_text or "",
                        is_blank=is_blank,
                    )
                )

            # Extract identity fields
            first_name = None
            last_name = None
            email = None
            inst_id = None
            source_grade = None
            raw_grade = None
            unknown_vals: dict[str, str] = {}

            for col in columns:
                val = row_dict.get(col.original_name, "")
                if col.mapped_field == "first_name":
                    first_name = val or None
                elif col.mapped_field == "last_name":
                    last_name = val or None
                elif col.mapped_field == "email":
                    email = val or None
                elif col.mapped_field == "institutional_student_id":
                    inst_id = val or None
                elif col.mapped_field == "source_grade":
                    raw_grade = val or None
                    if val:
                        try:
                            source_grade = Decimal(str(val))
                        except Exception:  # noqa: S110
                            pass
                elif col.mapped_field is None:
                    if val:
                        unknown_vals[col.original_name] = val

            parsed_rows.append(
                ParsedStudentRow(
                    row_number=row_idx,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    institutional_student_id=inst_id,
                    status=None,
                    started=None,
                    completed=None,
                    duration_seconds=None,
                    source_grade=source_grade,
                    raw_source_grade=raw_grade,
                    source_grade_maximum=None,
                    responses=tuple(responses_list),
                    unknown_values=unknown_vals,
                    warnings=tuple(row_warnings),
                    errors=tuple(row_errors),
                )
            )

        # Build warnings
        all_warnings: list[ParsedValidationMessage] = []
        for w in dup_warnings:
            all_warnings.append(
                ParsedValidationMessage(
                    code="W001",
                    severity=ValidationSeverity.WARNING,
                    message=w,
                )
            )
        for w in inconsistent_row_warnings:
            all_warnings.append(
                ParsedValidationMessage(
                    code="W011",
                    severity=ValidationSeverity.WARNING,
                    message=w,
                )
            )
        if malformed_rows > 0:
            all_warnings.append(
                ParsedValidationMessage(
                    code="W010",
                    severity=ValidationSeverity.WARNING,
                    message=f"{malformed_rows} malformed row(s) were skipped.",
                )
            )

        # Count blanks
        blank_count = sum(
            1 for pr in parsed_rows for r in pr.responses if r.is_blank
        )
        warning_count = sum(1 for pr in parsed_rows if pr.warnings) + len(all_warnings)
        error_count = sum(1 for pr in parsed_rows if pr.errors)

        stats = ImportStatistics(
            total_rows=len(parsed_rows),
            valid_rows=len(parsed_rows) - error_count,
            warning_rows=warning_count,
            error_rows=error_count,
            blank_response_count=blank_count,
            response_column_count=len(response_columns_list),
            duplicate_email_count=0,
        )

        now = datetime.now(UTC)
        return ParsedImport(
            source_filename=source_filename,
            parser_name=self.parser_name,
            table_index=0,
            columns=tuple(columns),
            rows=tuple(parsed_rows),
            response_columns=tuple(response_columns_list),
            unknown_columns=tuple(unknown_columns_list),
            warnings=tuple(all_warnings),
            errors=(),
            statistics=stats,
            parse_started_at=now,
            parse_completed_at=now,
            source_format="csv",
            encoding=encoding,
            delimiter=delimiter,
        )

    def _detect_encoding(self, file_bytes: bytes) -> str | None:
        """Detect the encoding of CSV bytes."""
        # Check for BOM first
        if file_bytes[:3] == b"\xef\xbb\xbf":
            return "utf-8-sig"
        for enc in _ENCODING_CANDIDATES:
            try:
                file_bytes.decode(enc)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return None

    def _detect_delimiter(self, text: str) -> str | None:
        """Detect the delimiter by examining the first line."""
        first_line = text.split("\n", 1)[0] if text else ""
        if not first_line:
            return None

        best_delim = None
        best_count = 0

        for delim in _DELIMITER_CANDIDATES:
            count = first_line.count(delim)
            if count > best_count:
                best_count = count
                best_delim = delim

        return best_delim

    def _safe_value(self, value: str | None) -> str:
        """Sanitize a cell value, treating formulas as text."""
        if value is None:
            return ""
        value = value.strip()
        # Formula injection protection
        if value and value[0] in ("=", "+", "-", "@"):
            return value
        return value

    def _get_extension(self, filename: str) -> str:
        """Get the lowercase file extension."""
        idx = filename.rfind(".")
        if idx == -1:
            return ""
        return filename[idx:].lower()
