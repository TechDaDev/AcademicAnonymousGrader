# Academic Anonymous Grader — Validation Rules

## Rule Categories

1. Material validation
2. Assessment validation
3. Question validation
4. File validation
5. Student validation
6. Submission validation
7. Response validation
8. Grade validation
9. Finalisation validation
10. Export validation

---

## Severity Levels

| Severity | Meaning | Behaviour |
|----------|---------|-----------|
| **Error** | A blocking issue that prevents the operation. | Operation cannot proceed until resolved. |
| **Warning** | A non-blocking issue that should be reviewed. | Operation can proceed; warning is recorded and displayed. |
| **Information** | An informational message for the user. | Displayed but does not block or warn. |

---

## Material Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| M001 | A material name is required and must not be empty. | Error | Creating/updating material | Creation/update |
| M002 | A material name must not exceed 200 characters. | Error | Creating/updating material | Creation/update |
| M003 | A material code, if provided, must not exceed 20 characters. | Warning | Creating/updating material | — |
| M004 | Material name must be unique per lecturer. | Error | Creating/updating material | Creation/update |
| M005 | At least one material must exist before creating an assessment. | Information | Creating assessment | — |

## Assessment Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| A001 | An assessment must belong to a material. | Error | Creating/updating assessment | Creation/update |
| A002 | An assessment name is required and must not be empty. | Error | Creating/updating assessment | Creation/update |
| A003 | An assessment name must not exceed 200 characters. | Error | Creating/updating assessment | Creation/update |
| A004 | Assessment name must be unique within a material. | Error | Creating/updating assessment | Creation/update |
| A005 | Assessment maximum grade must be a positive number. | Error | Creating/updating assessment | Creation/update |
| A006 | Assessment maximum grade must not exceed 999999. | Warning | Creating/updating assessment | — |
| A007 | Assessment must contain at least one question before importing. | Error | Starting import | Import |
| A008 | An assessment cannot be deleted after submissions exist. | Error | Deleting assessment | Deletion |

## Question Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| Q001 | Question numbers must be unique within an assessment. | Error | Creating/updating questions | Creation/update |
| Q002 | Question numbers must be positive integers. | Error | Creating/updating questions | Creation/update |
| Q003 | Question maximum mark must be greater than zero. | Error | Creating/updating questions | Creation/update |
| Q004 | Question maximum mark must not exceed the assessment maximum grade. | Error | Creating/updating questions | Creation/update |
| Q005 | The sum of all question maximum marks must equal the assessment maximum grade. | Warning | Creating/updating questions | — |
| Q006 | At least one question must exist before importing response files. | Error | Starting import | Import |

## File Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| F001 | The uploaded file must have a `.html` or `.htm` extension. | Error | File upload | Upload |
| F002 | The uploaded file must not be empty. | Error | File upload | Upload |
| F003 | The file must contain at least one HTML table with data. | Error | File parsing | Import |
| F004 | The file must contain at least one identity column (First name, Last name, Email). | Error | Column detection | Import |
| F005 | The file must contain at least one response column. | Error | Column detection | Import |
| F006 | The file size must not exceed 50 MB. | Error | File upload | Upload |
| F007 | The HTML must be parsable (valid enough to extract a table). | Error | File parsing | Import |
| F008 | Unknown columns must be reviewed by the lecturer before proceeding. | Warning | Column mapping | — |
| F009 | Response-column count does not match question count. | Warning | Column mapping | — |
| F010 | The same file (by hash) was already imported. Duplicate import requires confirmation. | Warning | Import confirmation | — |

## Student Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| S001 | First name must not be empty for any row. | Error | Row parsing | Import of that row |
| S002 | Last name should not be empty for any row (if present). | Warning | Row parsing | — |
| S003 | Email address may be empty; if missing, identity matching falls back to institutional ID or manual resolution. | Warning | Row parsing | — |
| S004 | Email address, when present, should contain an `@` symbol. | Warning | Row parsing | — |
| S005 | Duplicate email within the same file. First occurrence imported; duplicates flagged for lecturer review. | Warning | Row parsing | Import of duplicate row (blocked unless reviewed) |
| S006 | Student already exists from a previous import. Identity is matched using the hierarchy (institutional ID → email → fingerprint → manual). | Information | Import confirmation | — |
| S007 | Email address matches multiple existing identities. Block import and require manual resolution. | Error | Identity matching | Import of that row |
| S008 | Same full name with different email address. These must be treated as separate students; automatic merging is prohibited. | Warning | Identity matching | — |
| S009 | Different names with the same email address. This is an ambiguous match; block automatic import and require lecturer review. | Error | Identity matching | Import of that row |
| S010 | Institutional student ID is unavailable; identity matching will use lower-priority identifiers (email, fingerprint, or manual resolution). | Information | Import validation | — |
| S011 | Duplicate institutional student ID within the same file. First occurrence imported; duplicates flagged for lecturer review. | Error | Identity matching | Import of duplicate row |
| S012 | Institutional student ID matches multiple existing records. Block import and require manual resolution. | Error | Identity matching | Import of that row |
| S013 | Institutional student ID conflicts with normalised email match (ID points to one identity, email points to another). Block import and require manual resolution. | Error | Identity matching | Import of that row |
| S014 | Missing institutional student ID when an assessment or import profile explicitly requires it. | Error | Import validation | Import |
| S015 | Institutional student ID does not match an optional configured format pattern. | Warning | Row parsing | — |
| S016 | Identity match is ambiguous (no single reliable signal). Block import and require manual lecturer resolution. | Error | Identity matching | Import of that row |
| S017 | Names alone must never trigger automatic identity merging. | Error | Identity matching | Import of that row |
| S018 | Manual identity resolution is required for this row. The lecturer must confirm the correct identity mapping before the row can be imported. | Error | Identity matching | Import of that row |

## Submission Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| SM001 | Submission status, if present, must be one of: "Finished", "In progress", "Submitted", or similar known values. | Warning | Row parsing | — |
| SM002 | Submission started date, if present, should be parseable as a date/time. | Warning | Row parsing | — |
| SM003 | Submission completed date, if present, should be parseable as a date/time. | Warning | Row parsing | — |
| SM004 | Completed date should not be before started date. | Warning | Row parsing | — |
| SM005 | Duration, if present, should be parseable as a time duration. | Warning | Row parsing | — |
| SM006 | Source grade, if present, should be a numeric value or numeric fraction (e.g., "7/10"). | Warning | Row parsing | — |

## Response Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| R001 | Every question must have a corresponding response record (may be blank). | Error | Import | Import |
| R002 | Blank responses must be retained rather than deleted. | Information | Import | — |
| R003 | Response text must not exceed 100,000 characters. | Warning | Import | — |
| R004 | Response text must be stored as plain text; active HTML content must be stripped. | Error | Import | Import |

## Grade Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| G001 | Score must be a numeric value. | Error | Grading | Save |
| G002 | Score may use decimals (up to 2 decimal places recommended). | Information | Grading | — |
| G003 | Score cannot be negative. | Error | Grading | Save |
| G004 | Score cannot exceed the question maximum mark. | Error | Grading | Save |
| G005 | Score must not be null when saving a grade (use 0 for zero score). | Error | Grading | Save |
| G006 | Feedback text, if provided, must not exceed 5,000 characters. | Warning | Grading | — |
| G007 | Every response must receive a grade before finalisation. | Error | Finalisation check | Finalisation |
| G008 | A grade record must exist for every response before finalisation. | Error | Finalisation check | Finalisation |

## Finalisation Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| FA001 | Assessment must have at least one question defined. | Error | Readiness check | Finalisation |
| FA002 | Sum of question maximum grades must equal assessment maximum grade. | Error | Readiness check | Finalisation |
| FA003 | Assessment must have at least one submission. | Error | Readiness check | Finalisation |
| FA004 | Every submission must have an associated anonymous student. | Error | Readiness check | Finalisation |
| FA005 | All submissions must be in "approved" review status. | Error | Readiness check | Finalisation |
| FA006 | A GradeRecord must exist for every (submission, question) pair. | Error | Readiness check | Finalisation |
| FA007 | GradeRecord grade must not be null. | Error | Readiness check | Finalisation |
| FA008 | GradeRecord grade must not be negative. | Error | Readiness check | Finalisation |
| FA009 | GradeRecord grade must not exceed the question maximum grade. | Error | Readiness check | Finalisation |
| FA010 | GradeRecord grading_status must be "graded". | Error | Readiness check | Finalisation |
| FA011 | Submission total grade must not exceed assessment maximum grade. | Error | Readiness check | Finalisation |
| FA012 | Explicit lecturer confirmation checkbox must be checked. | Error | Finalisation action | Finalisation |
| FA013 | Assessment must not already be finalized. | Error | Finalisation action | Finalisation |

## Export Validation

| ID | Description | Severity | When It Runs | Blocks |
|----|-------------|----------|--------------|--------|
| E001 | Assessment must be in "finalized" status (finalization_status = "finalized"). | Error | Before export | Export |
| E002 | Assessment must have at least one question defined. | Error | Before export | Export |
| E003 | Assessment must have at least one submission. | Error | Before export | Export |
| E004 | Every submission must have an associated anonymous student. | Error | During export | Export |
| E005 | A GradeRecord must exist for every (submission, question) pair. | Error | During export | Export |
| E006 | GradeRecord grade must not be null. | Error | During export | Export |
| E007 | Encryption key must be available to decrypt identities for export. | Error | Before export | Export |
| E008 | All exported text beginning with `=`, `+`, `-`, or `@` must be escaped with a leading `'` to prevent formula injection. | Error | During export | Export |

## Summary Table

| Category | Total Rules | Errors | Warnings | Information |
|----------|-------------|--------|----------|-------------|
| Material | 5 | 3 | 1 | 1 |
| Assessment | 8 | 6 | 1 | 1 |
| Question | 6 | 4 | 1 | 1 |
| File | 10 | 7 | 3 | 0 |
| Student | 18 | 9 | 6 | 3 |
| Submission | 6 | 0 | 5 | 1 |
| Response | 4 | 2 | 1 | 1 |
| Grade | 8 | 5 | 2 | 1 |
| Finalisation | 13 | 13 | 0 | 0 |
| Export | 8 | 8 | 0 | 0 |
| **Total** | **86** | **57** | **20** | **9** |
