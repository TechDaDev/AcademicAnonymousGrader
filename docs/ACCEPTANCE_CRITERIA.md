# Academic Anonymous Grader — Acceptance Criteria

## Phase 0: Specification and Rules

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-P0-01 | All required documents exist: `PROJECT_SPECIFICATION.md`, `WORKFLOW.md`, `DATA_MODEL.md`, `PRIVACY_AND_SECURITY.md`, `IMPORT_FILE_SPECIFICATION.md`, `VALIDATION_RULES.md`, `UI_REQUIREMENTS.md`, `ACCEPTANCE_CRITERIA.md`, `PHASE_ROADMAP.md`, `README.md`, `.gitignore`. | Manual file check. |
| AC-P0-02 | Documents do not contradict each other on terminology or design decisions. | Cross-document review. |
| AC-P0-03 | Privacy terminology correctly distinguishes anonymisation, pseudonymisation, hashing, and encryption. | Review of `PRIVACY_AND_SECURITY.md`. |
| AC-P0-04 | The system explicitly does NOT use anonymisation (since identities must be restored). | Review of `PRIVACY_AND_SECURITY.md` and `PROJECT_SPECIFICATION.md`. |
| AC-P0-05 | Response column detection is dynamic (not hardcoded to exactly two). | Review of `IMPORT_FILE_SPECIFICATION.md` and `DATA_MODEL.md`. |
| AC-P0-06 | Identity and grading data are stored in separate entities/tables. | Review of `DATA_MODEL.md`. |
| AC-P0-07 | Windows 11 is confirmed as the initial environment. | Review of `PROJECT_SPECIFICATION.md`. |
| AC-P0-08 | Streamlit is confirmed as the initial UI framework. | Review of `PROJECT_SPECIFICATION.md`. |
| AC-P0-09 | SQLite is confirmed as the initial database. | Review of `PROJECT_SPECIFICATION.md`. |
| AC-P0-10 | HTML is confirmed as the first import format. | Review of `PROJECT_SPECIFICATION.md` and `IMPORT_FILE_SPECIFICATION.md`. |
| AC-P0-11 | Excel (.xlsx) is confirmed as the export format. | Review of `PROJECT_SPECIFICATION.md`. |
| AC-P0-12 | No application code (Python files, Streamlit pages, database models, services) has been created. | Manual file check — only `.md`, `.gitignore`, and `README.md` exist. |
| AC-P0-13 | Anonymous IDs must be generated using cryptographically secure randomness, not derived from names. | Review of `PRIVACY_AND_SECURITY.md` and `DATA_MODEL.md`. |
| AC-P0-14 | The grading interface must not display real student names or email addresses. | Review of `UI_REQUIREMENTS.md` and `WORKFLOW.md`. |
| AC-P0-15 | Source grades from the import file are informational and are not automatically accepted as final grades. | Review of `VALIDATION_RULES.md` and `PROJECT_SPECIFICATION.md`. |
| AC-P0-16 | Student identity uses an internally generated UUID as primary key, not email. | Review of `DATA_MODEL.md`. |
| AC-P0-17 | Identity matching follows a documented hierarchy: institutional ID → email → fingerprint → manual. | Review of `IMPORT_FILE_SPECIFICATION.md`. |
| AC-P0-18 | Names alone never trigger automatic student merging. | Review of `IMPORT_FILE_SPECIFICATION.md` and `VALIDATION_RULES.md`. |
| AC-P0-19 | Ambiguous identity matches block import and require lecturer review. | Review of `IMPORT_FILE_SPECIFICATION.md` and `VALIDATION_RULES.md`. |
| AC-P0-20 | Anonymous IDs use a readable format (`STU-XXXXXXXX`) with collision checking and regeneration. | Review of `DATA_MODEL.md`. |
| AC-P0-21 | Identity field encryption (first name, last name, email, institutional ID) is explicitly assigned to Phase 4. | Review of `PHASE_ROADMAP.md` and `PRIVACY_AND_SECURITY.md`. |
| AC-P0-22 | Identity fingerprints use HMAC-SHA256 with a dedicated key separate from the identity encryption key. | Review of `IMPORT_FILE_SPECIFICATION.md` and `DATA_MODEL.md`. |
| AC-P0-23 | The fingerprint key is stored in an environment variable, never in SQLite or Git. | Review of `PRIVACY_AND_SECURITY.md`. |
| AC-P0-24 | S010 (missing institutional student ID) is informational and does not block import. | Review of `VALIDATION_RULES.md`. |

## Phase 1: Project Foundation

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-P1-01 | Python 3.12 virtual environment can be created and activated. | Manual test. |
| AC-P1-02 | All required packages can be installed via pip without errors. | `pip install` test. |
| AC-P1-03 | Streamlit application starts without errors. | `streamlit run` test. |
| AC-P1-04 | Application displays "Academic Anonymous Grader" as the title. | Visual verification. |
| AC-P1-05 | Navigation sidebar contains links to all documented pages. | Visual verification. |
| AC-P1-06 | SQLite database is created on first run. | File system check. |
| AC-P1-07 | Database tables match the data model in `DATA_MODEL.md`. | Schema inspection. |
| AC-P1-08 | `pytest` can discover and run tests. | `pytest --collect-only` test. |
| AC-P1-09 | Phase 0 documentation was reviewed and approved before Phase 1 began. | Process check. |

## Phase 2: Materials and Assessments

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-P2-01 | Given a lecturer on the Materials page, when they enter a material name and click Create, then a new material is created and displayed. | Manual test. |
| AC-P2-02 | Given a material exists, when the lecturer navigates to Assessments, then they see the assessment list. | Manual test. |
| AC-P2-03 | Given an assessment is being created, when the lecturer enters an invalid max grade, then an error message is displayed. | Manual test. |
| AC-P2-04 | Given an assessment exists, when the lecturer adds questions, then the sum-of-marks validation runs. | Manual test. |
| AC-P2-05 | Given an assessment with submissions exists, when the lecturer tries to delete it, then deletion is blocked. | Manual test. |

## Phase 3: HTML Parser

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-P3-01 | Given a valid HTML response file, when the parser processes it, then all student identities are extracted. | Unit test. |
| AC-P3-02 | Given a valid HTML response file, when the parser processes it, then all response columns are dynamically detected regardless of count. | Unit test with 1, 3, and 5 response columns. |
| AC-P3-03 | Given an HTML file with Arabic text in responses, when parsed, then Arabic characters are preserved correctly. | Unit test. |
| AC-P3-04 | Given an HTML file with multiline responses, when parsed, then line breaks are preserved. | Unit test. |
| AC-P3-05 | Given an HTML file with code in responses, when parsed, then code indentation is preserved. | Unit test. |
| AC-P3-06 | Given an HTML file with HTML entities, when parsed, then entities are decoded. | Unit test. |
| AC-P3-07 | Given an HTML file with JavaScript, when parsed, then JavaScript is not executed. | Unit test (mock/browser check). |
| AC-P3-08 | Given a malformed HTML file, when parsed, then the parser recovers gracefully or returns a clear error. | Unit test. |
| AC-P3-09 | Given an empty HTML file, when parsed, then a clear error is returned. | Unit test. |
| AC-P3-10 | Given an HTML file with unknown columns, when parsed, then unknown columns are flagged for review. | Unit test. |

## Phase 4: Pseudonymisation and Identity Encryption

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-P4-01 | Given a list of imported students, when anonymous IDs are generated, then each ID is unique. | Unit test. |
| AC-P4-02 | Given a list of imported students, when anonymous IDs are generated, then IDs cannot be reverse-engineered from names. | Verification that IDs are random (not hash-based). |
| AC-P4-03 | Given an identity mapping exists, when the system queries grading data, then no names or emails are returned. | Integration test. |
| AC-P4-04 | Given the same student is imported for a different assessment, when anonymous IDs are generated, then a new (different) anonymous ID is assigned per assessment. | Unit test (decision: per-assessment anonymous ID). |
| AC-P4-05 | Given the same student is reimported for the same assessment, when anonymous IDs are generated, then the same anonymous ID is reused. | Unit test. |
| AC-P4-06 | Given student identity data exists, when the database is queried directly, then first name, last name, email, and institutional student ID are encrypted at rest. | Database-level inspection. |
| AC-P4-07 | Given an encryption key exists in the environment, when the application starts, then identity fields can be decrypted successfully. | Integration test. |
| AC-P4-08 | Given the encryption key is missing from the environment, when the application starts, then startup fails with a clear error or enters a restricted mode. | Integration test. |
| AC-P4-09 | Given the encryption key is incorrect or changed, when the application attempts to decrypt identity data, then a clear error is raised (not silent data corruption). | Integration test. |
| AC-P4-10 | Given anonymous IDs are generated using `STU-XXXXXXXX` format, when a collision occurs, then the ID is regenerated. | Unit test (mock collision). |
| AC-P4-11 | Given a student's institutional student ID or email, when the identity fingerprint is computed, then it uses HMAC-SHA256 with a dedicated key. | Unit test. |
| AC-P4-12 | Given the fingerprint key is changed, when existing fingerprints are compared against newly computed ones, then they do not match. | Integration test. |

## Phase 5: Manual Grading

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-P5-01 | Given a graded assessment with submissions, when the lecturer opens the Grading page, then only the anonymous ID is displayed (not the student's name or email). | Manual test + code review. |
| AC-P5-02 | Given the lecturer is on the Grading page, when they enter a valid score and click Save, then the grade is saved and a confirmation is shown. | Manual test. |
| AC-P5-03 | Given the lecturer is on the Grading page, when they enter an invalid score (negative or exceeding max), then an error message is shown and the grade is not saved. | Manual test. |
| AC-P5-04 | Given the lecturer is grading, when they click Save and Next, then the current grade is saved and the next response is displayed. | Manual test. |
| AC-P5-05 | Given the lecturer is grading, when they click Previous, then the previous response is displayed (if any). | Manual test. |
| AC-P5-06 | Given the lecturer is grading, when they click Skip, then the next response is displayed without saving. | Manual test. |
| AC-P5-07 | Given the lecturer is grading, when they click Mark for Review, then the response is flagged. | Manual test. |
| AC-P5-08 | Given grading progress exists, when the page is refreshed, then progress is retained. | Manual test. |

## Phase 6: Review  ✅

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-P6-01 | Given an assessment with graded submissions, when the lecturer opens the Review page, then all submissions are listed with anonymous code, total grade, review status, and error count. | Automated test (`test_list_submissions`) + manual test. |
| AC-P6-02 | Given the Review page is open, when the lecturer selects a submission, then grades per question, optional feedback, and validation messages are displayed. | Automated test (`test_get_submission`) + manual test. |
| AC-P6-03 | Given a fully graded submission with valid grades, when the lecturer approves it, then the review status changes to "approved" and a timestamp is recorded. | Automated test (`test_approve_valid`, `test_approve_with_note`). |
| AC-P6-04 | Given a submission with an invalid grade (null, missing, above max, not graded), when the lecturer attempts to approve it, then approval is blocked with an appropriate error and specific validation code (RV001–RV006). | Automated tests (`test_missing_grade_record_error`, `test_null_grade`, `test_grade_above_max`, `test_not_graded_status`, `test_approve_blocked_with_errors`). |
| AC-P6-05 | Given a reviewed submission, when the lecturer marks it as "Needs Correction", then a reviewer note is required and the status is updated. | Automated tests (`test_mark_needs_correction`, `test_note_required`). |
| AC-P6-06 | Given a submission marked "Needs Correction", when the lecturer returns it to grading, then the review status resets to "not_ready" and the note is cleared. | Automated test (`test_return_to_grading`). |
| AC-P6-07 | Given an assessment with submissions at various review statuses, when the lecturer views progress, then counts for each status and completion percentage are correct. | Automated tests (`test_all_not_ready`, `test_approved`, `test_mixed_statuses`, `test_zero_submissions`). |
| AC-P6-08 | Given an assessment-level validation check, when all submissions are approved and have no errors, then the assessment is marked as ready. | Automated test (`test_ready_assessment`). |
| AC-P6-09 | Given an assessment with submissions needing correction or missing grades, when assessment-level validation runs, then blocking errors are returned (RA001–RA007). | Automated test (`test_needs_correction_blocks_ready`). |
| AC-P6-10 | Given the Review page, when submissions are displayed, then only anonymous codes are shown — no names, emails, or institutional IDs. | Automated tests (`test_list_no_names`, `test_view_no_identities`, `test_safe_repr`). |

## Phase 7: Finalisation and Excel Export  ✅

| ID | Criterion | Verification Method |
|----|-----------|-------------------|
| AC-P7-01 | Given an assessment with all submissions approved and GradeRecords valid, when readiness is checked, then all FA001–FA011 checks pass and is_ready is true. | Automated test (`test_ready_assessment_finalizes`). |
| AC-P7-02 | Given an assessment with an unapproved submission, when readiness is checked, then FA005 blocks finalization. | Automated test (`test_unapproved_submission_blocks`). |
| AC-P7-03 | Given a finalized assessment, when the lecturer attempts to edit a grade, then editing is blocked with `FinalizedAssessmentModificationError`. | Automated test (`test_edit_grade_after_finalization_blocked`). |
| AC-P7-04 | Given a finalized assessment, when the lecturer attempts a review action, then it is blocked with `FinalizedAssessmentModificationError`. | Automated tests (approve, needs-correction, return-to-grading). |
| AC-P7-05 | Given a finalized assessment, when the lecturer attempts to add or delete a question, then it is blocked with `FinalizedAssessmentModificationError`. | Automated tests (`test_add_question_after_finalization_blocked`, `test_delete_question_after_finalization_blocked`). |
| AC-P7-06 | Given a finalized assessment, when the lecturer attempts to import, then it is blocked. | Automated service test. |
| AC-P7-07 | Given a finalized assessment, when the lecturer confirms and finalizes, then an Excel workbook is generated with correct data and formula-injection protection. | Automated tests (workbook generation, sheets, formula safety). |
| AC-P7-08 | Given a finalized assessment, when the lecturer re-exports, then a new ExportRecord is created and grades remain unchanged. | Automated test (`test_reexport_allowed`). |
| AC-P7-09 | Given an exported workbook, when inspected, then no ciphertext, encryption keys, fingerprints, or UUIDs are present in cells. | Automated privacy audit tests. |

## High-Level Acceptance Criteria Summary

| Area | Key Criteria |
|------|-------------|
| **Project foundation** | Application starts, database initialises, navigation works. |
| **Materials and assessments** | CRUD operations work, validation enforces rules, questions are configurable. |
| **HTML parser** | Extracts all data from valid files, handles edge cases gracefully, never executes code. |
| **Pseudonymisation** | IDs are random, unique, and never derived from names; grading queries exclude PII. |
| **Manual grading** | Anonymous grading is enforced, scores are validated, progress is saved immediately. |
| **Review** | Filters work, navigation to grading works, incomplete items are visible. |
| **Finalisation and Excel export** | Validation blocks incomplete assessments, warning precedes identity restoration, formula injection is prevented. |
