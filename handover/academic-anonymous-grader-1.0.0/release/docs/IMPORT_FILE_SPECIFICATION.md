# Academic Anonymous Grader — Import File Specification

## Supported Format (Phase 1)

- **Initial format:** HTML (`.html` or `.htm`)
- **Planned for later phases:** XLSX (`.xlsx`), CSV (`.csv`)

## Expected HTML Structure

The HTML file is expected to be an export from a learning management system. It typically contains a single HTML table (`<table>`) where:

- The first row (`<thead>` or first `<tr>`) contains column headers.
- Subsequent rows contain student data.
- Each row represents one student's submission.

## Expected Identity Columns

| Normalised Name | Example in Source | Classification | Required? |
|-----------------|-------------------|----------------|-----------|
| `first_name` | `First name`, `FirstName`, `First Name` | Identity | Yes |
| `last_name` | `Last name`, `LastName`, `Last Name`, `Surname` | Identity | Optional (recommended) |
| `email` | `Email address`, `Email`, `E-mail` | Identity | Optional (recommended for matching) |
| `institutional_student_id` | `Student ID`, `ID`, `Student number`, `Matric` | Identity | Optional (highest matching priority when present) |

## Optional Submission Metadata Columns

| Normalised Name | Example in Source | Classification | Notes |
|-----------------|-------------------|----------------|-------|
| `status` | `Status` | Metadata | E.g., "Finished", "In progress" |
| `started` | `Started` | Metadata | Date/time string |
| `completed` | `Completed` | Metadata | Date/time string |
| `duration` | `Duration` | Metadata | E.g., "45 min 12 sec" |
| `grade` | `Grade/10.00`, `Grade/100`, `Grade` | Metadata | Source grade; informational only |

## Dynamic Response Columns

| Normalised Pattern | Example in Source | Classification |
|--------------------|-------------------|----------------|
| `response_N` | `Response 1`, `Response 2`, … `Response N` | Response |
| `response_N` | `Response 1 (7 marks)`, `Question 1 response` | Response (after normalisation) |

**Critical rule:** The system must detect response columns **dynamically**. There is no assumption that an assessment contains exactly two questions. Any column whose normalised name matches a response pattern is treated as a response column.

## Column Normalisation Rules

| Rule | Description |
|------|-------------|
| Trim spaces | Leading and trailing whitespace is removed from column names. |
| Collapse internal spaces | Repeated internal spaces are collapsed to a single space where safe. |
| Case-insensitive matching | Column names are compared case-insensitively against known patterns. |
| Preserve original labels | The original column label is stored for audit and display. |
| Decode HTML entities | `&amp;`, `&lt;`, `&gt;`, `&nbsp;`, etc., are decoded to their Unicode equivalents. |
| Preserve Unicode | All Unicode characters (including Arabic) are preserved. |
| Preserve line breaks | Line breaks within response cells are preserved as `\n`. |
| Preserve code indentation | Whitespace indentation in responses is preserved. |
| Do not execute JavaScript | JavaScript is never executed during parsing. |
| Do not execute code | Code in response cells is extracted as plain text only. |
| Ignore visual CSS | CSS styling is ignored for data extraction; only table structure matters. |
| Sanitise active content | `<script>`, `<iframe>`, `<object>`, event handlers (`onclick=`, etc.) are stripped during parsing. |

## Identity Matching Strategy

When importing students, the system matches against existing identities using the following hierarchy:

1. **Institutional student ID** — If the source file contains a recognised institutional student ID column and the value matches an existing `StudentIdentity.institutional_student_id`, it is considered an exact match.
2. **Normalised email** — If no institutional ID is available, the system normalises the email address (lowercase, trimmed) and searches for an existing match. Matching is unambiguous only when exactly one record matches.
3. **Keyed identity fingerprint** — If neither ID nor email produces an unambiguous match, the system computes a keyed, non-reversible HMAC-SHA256 fingerprint from the best available identifier and compares it against stored fingerprints. This is a supporting signal, not a primary key.
4. **Manual resolution** — If all automatic methods produce ambiguous results (zero matches, multiple matches, or conflicting signals), the import is blocked and the lecturer is prompted to resolve the identity manually.

### Identity Fingerprint Design

- **Algorithm:** HMAC-SHA256.
- **Dedicated key:** A separate `IDENTITY_FINGERPRINT_KEY` environment variable, distinct from the identity encryption key.
- **Storage:** The key is never stored in SQLite or committed to Git.
- **Input priority:** Normalised institutional student ID is the preferred fingerprint input when available. Otherwise, normalised email (lowercased, trimmed) is used when present and unambiguous. Lower-confidence fallback data (e.g., name fragments) may be used only to propose a possible match for manual review — such proposals must never generate an automatic identity match.
- **Names alone:** Never used as fingerprint input for automatic matching.
- **Exposure:** The fingerprint must not expose names, email addresses, or student IDs. HMAC-SHA256 with a secret key ensures the output reveals nothing about the input.
- **Role:** Fingerprints are matching aids, not database primary keys.
- **Key migration:** Changing the fingerprint key is an operational migration because existing stored fingerprints will no longer match newly computed fingerprints.

**Critical rules:**
- Names alone must never cause students to be automatically merged. Two students with identical names but different emails or IDs must be treated as separate individuals requiring manual review.
- Ambiguous matches (e.g., same email matching two different existing identities, or same name with conflicting IDs) must block automatic merging and require lecturer intervention.
- Every imported submission must remain traceable to its `ImportBatch`.

## Column Mapping Behaviour

When a column name in the source file does not exactly match the expected normalised name, the system applies fuzzy matching:

1. Normalise the source name (trim, collapse spaces, decode HTML entities).
2. Compare against a known-name dictionary using case-insensitive equality.
3. If no exact match, try substring matching (e.g., `Response 1 (7 marks)` contains `Response 1`).
4. If still unmatched, classify as `unknown` and flag for lecturer review.

## Import Classifications

| Classification | Description | Behaviour |
|----------------|-------------|-----------|
| **Required** | Must be present in the file. | Import is blocked if missing. |
| **Optional** | May be present. | Imported if present; ignored if absent with a warning. |
| **Ignored** | Deliberately skipped. | Not imported. Logged as ignored. |
| **Unknown** | Not recognised by any rule. | Flagged for lecturer review. May be ignored. |
| **Response column** | Contains a student answer. | Dynamically detected; imported as a response for the corresponding question. |

## Error and Edge Case Handling

| Scenario | Handling |
|----------|----------|
| **Missing first name** | Reject row; log error. Student cannot be identified. |
| **Missing last name** | Accept row; log warning. Identity matching will rely on email or institutional ID. |
| **Missing email** | Accept row if institutional student ID is present; otherwise log warning. Identity matching falls back to institutional ID or manual resolution. |
| **Missing institutional student ID** | Accept row; log informational message. Identity matching will use email or manual resolution. |
| **Duplicate email within same file** | Flag as warning. Import the first occurrence; flag the rest for lecturer review. Do not automatically reject. |
| **Email matching multiple existing identities** | Block import of that row. Flag for manual resolution by the lecturer. |
| **Same name, different email** | Treat as separate students. Do not merge. Log informational message. |
| **Different names, same email** | Flag as ambiguous match. Block automatic import. Require lecturer review. |
| **Duplicate student row (previous import)** | Skip duplicate; log informational message. Identity matching uses the hierarchy (institutional ID → email → fingerprint → manual). |
| **Blank response** | Create a response record with an empty string. Do not skip. Grading will still be required. |
| **Unfinished submission** | Status is "In progress" or similar. Import the submission; mark as incomplete. Grade available responses. |
| **Malformed date** | Attempt to parse; if parsing fails, store as raw string and flag with a warning. |
| **Missing grade column** | The source grade column may be absent. This is acceptable — the informational grade is optional. |
| **Unexpected grade format** | If the grade column exists but contains non-numeric data, store as null and flag with a warning. |
| **Additional unknown columns** | Flag for lecturer review. Lecturer can choose to ignore or map. |
| **Different column ordering** | Handled automatically via column name normalisation. Order does not matter. |
| **More response columns than questions** | Flag for lecturer review. Lecturer must add questions or map the extra columns. |
| **Fewer response columns than questions** | Flag for lecturer review. Some questions will have no corresponding response data. |
| **Multiple HTML tables** | Parse all tables and merge rows. If tables have different structures, flag for review. |
| **Empty file** | Reject with error message indicating the file contains no data. |
| **Invalid HTML** | Attempt to parse with BeautifulSoup's forgiving parser. If parsing yields no table, reject. |
| **Very large files** | Process in a streaming fashion if possible. Show a progress indicator for files exceeding a threshold (to be defined). |

## Normalised Import Result Structure (Conceptual)

After parsing, the system produces an in-memory representation with the following logical structure:

```python
ImportResult:
    source_filename: str
    import_timestamp: datetime
    total_rows: int
    columns: List[ColumnDefinition]
    rows: List[ImportRow]

ColumnDefinition:
    original_name: str          # e.g., "Response 1 (7 marks)"
    normalised_name: str        # e.g., "response_1"
    classification: str         # "identity", "metadata", "response", "unknown"
    is_required: bool

ImportRow:
    first_name: str | None
    last_name: str | None
    email: str | None
    institutional_student_id: str | None
    status: str | None
    started: str | None
    completed: str | None
    duration: str | None
    source_grade: str | None    # Raw string; parsed separately
    responses: Dict[int, str]   # question_number -> response_text
    unknown_fields: Dict[str, str]  # original_name -> value
    matching_status: str        # "new", "matched", "ambiguous", "manual"
    warnings: List[str]
    errors: List[str]           # Errors block import for this row
```
