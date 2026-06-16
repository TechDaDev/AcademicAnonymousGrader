"""Parser-specific exceptions."""


class ImportParserError(Exception):
    """Base parser exception."""


class UnsupportedFileTypeError(ImportParserError):
    """Raised when the uploaded file is not HTML."""


class FileTooLargeError(ImportParserError):
    """Raised when the uploaded file exceeds the configured limit."""


class EmptyFileError(ImportParserError):
    """Raised when the uploaded file has no content."""


class InvalidHtmlError(ImportParserError):
    """Raised when HTML cannot be parsed."""


class NoTableFoundError(ImportParserError):
    """Raised when no table exists in the file."""


class NoResponseTableFoundError(ImportParserError):
    """Raised when no response table can be identified."""


class MultipleCandidateTablesError(ImportParserError):
    """Raised when multiple tables look like response tables."""


class MissingIdentityColumnsError(ImportParserError):
    """Raised when required identity columns are absent."""


class MissingResponseColumnsError(ImportParserError):
    """Raised when no response columns are detected."""


class ImportLimitExceededError(ImportParserError):
    """Raised when a configured import limit is exceeded."""


class ColumnMappingError(ImportParserError):
    """Raised when a column mapping is invalid."""


class ResponseMappingConflictError(ColumnMappingError):
    """Raised when response column mappings conflict."""


class UnsupportedFormatError(ImportParserError):
    """Raised when the file format is not supported (e.g., legacy .xls)."""


class EncryptedWorkbookError(ImportParserError):
    """Raised when an XLSX workbook is password-protected."""


class MacroEnabledWorkbookError(ImportParserError):
    """Raised when a macro-enabled workbook (.xlsm) is uploaded."""


class SheetSelectionError(ImportParserError):
    """Raised when sheet selection is invalid or empty."""


class EncodingDetectionError(ImportParserError):
    """Raised when the encoding of a CSV file cannot be determined."""


class DelimiterDetectionError(ImportParserError):
    """Raised when the delimiter of a CSV file cannot be determined."""


class MalformedCsvError(ImportParserError):
    """Raised when a CSV file is malformed."""


class FormulaExecutionError(ImportParserError):
    """Raised when formulas would be executed (blocked)."""


class SecurityValidationError(ImportParserError):
    """Raised when a file fails security validation (ZIP bomb, path traversal, etc.)."""
