# Academic Anonymous Grader — Workflow

## Full Lecturer Workflow

### 1. Start the Application

```
streamlit run app.py
```

The application opens in the default web browser. The dashboard is displayed.

### 2. Log In

> *Authentication is not implemented in the first release. This step is documented here for the planned authentication phase.*

- Enter username and password.
- On first use, create a lecturer account.

### 3. Create or Select an Academic Material

- From the dashboard or Materials page, choose an existing material or create a new one.
- **Create:** Enter a material name (e.g., "DBOAIC1101 — Object-Oriented Programming") and optional code.
- **Select:** Choose from a list of existing materials.

### 4. Create or Select an Assessment

- Within a material, create a new assessment or select an existing one.
- **Create:** Enter assessment name (e.g., "Midterm Exam"), total maximum grade, and optional description.

### 5. Define Assessment Questions and Maximum Marks

- For each question, enter:
  - Question number (automatically suggested)
  - Question title or prompt
  - Maximum mark (must be greater than zero)
- The sum of all question maximum marks must equal the assessment maximum grade.

### 6. Upload a Response File

- From the Import page, select the assessment.
- Click to upload an HTML file.
- The system reads the file header row and normalises column names.

### 7. Detect and Map Columns

- The system displays detected columns and their classifications:
  - **Identity:** First name, Last name, Email
  - **Submission metadata:** Status, Started, Completed, Duration, Grade/10.00
  - **Response columns:** Response 1, Response 2, …, Response N
  - **Unknown:** Any columns that could not be classified
- The lecturer confirms or adjusts the mapping.

### 8. Preview Import Results

- A table preview shows the first few rows with normalised columns.
- Unknown columns are flagged for review.

### 9. Validate the File

- The system runs file-level validation:
  - Identity columns are present.
  - At least one response column exists.
  - Required data is not entirely missing.
- Validation errors are displayed and block import.

### 10. Match Identities

- The system attempts to match each imported row against existing student identities.
- Matching follows this hierarchy:
  1. **Institutional student ID** — exact match when present.
  2. **Normalised email** — exact, unambiguous email match.
  3. **Identity fingerprint** — keyed HMAC-SHA256 computed from the best available identifier (institutional ID or email); never derived from names alone.
  4. **Manual resolution** — when automatic methods are ambiguous.
- Names alone never trigger automatic merging.
- Ambiguous matches block import and require lecturer review.

### 11. Import Students and Submissions (continued)

- On confirmation, the system:
  - Records an import batch.
  - Extracts student identities.
  - Generates anonymous IDs (format `STU-XXXXXXXX`).
  - Stores identity mappings.
  - Encrypts identity fields at rest (Phase 4+).
  - Creates submission and response records.
- Duplicate detection uses the identity-matching hierarchy to prevent re-importing the same students for the same assessment.

### 12. Generate Anonymous Student IDs

- A cryptographically secure random ID (format `STU-XXXXXXXX`) is generated for each student.
- Collisions are checked — if one occurs the ID is regenerated.
- The mapping between real identity and anonymous ID is stored in a separate identity table.
- **Identity is NOT visible during grading.**

### 13. Grade Responses Anonymously

- The Grading page shows one response at a time.
- Only the anonymous ID is displayed — never the student's name or email.
- For each response, the lecturer:
  - Reads the response (displayed in a monospaced, scrollable area).
  - Enters a numeric score.
  - Optionally enters text feedback.
  - Clicks **Save** (data is saved immediately).
  - Navigates to the next response.
- Additional actions: Skip, Mark for Review, Previous.

### 14. Save Scores and Feedback

- Every score or feedback change is committed to the database immediately on save.
- A save-confirmation indicator is displayed.

### 15. Review and Validate Graded Submissions

- The Review page shows all submissions with their review status and validation summaries.
- Filters allow the lecturer to see:
  - All submissions
  - Not Ready (ungraded or partially graded)
  - Ready for Review (fully graded, awaiting review)
  - Needs Correction (flagged by reviewer)
  - Approved (review passed)
- Each submission displays validation errors (RV001–RV006) and warnings (RVW001–RVW003).
- The lecturer can:
  - **Approve** a submission (optionally with a reviewer note).
  - **Mark as Needs Correction** (reviewer note is required).
  - **Return to Grading** (resets review status to `not_ready` and clears the note).
- Submission navigation uses anonymous codes for consistent ordering.

### 16. Validate the Assessment

- Before finalisation, the system performs assessment-level validation (RA001–RA007):
  - All submissions have valid grade records.
  - No score exceeds the question maximum.
  - No negative or null scores exist.
  - Total grades do not exceed assessment maximum.
  - No submissions are in needs_correction or not_ready status.
  - At least one question exists.
- Validation results are displayed. Blocking errors prevent finalisation.

### 17. Finalise Assessment

- On the Export page, select the material and assessment.
- The system displays **finalization readiness** with total submissions, approved submissions, and blocking errors (FA001–FA011).
- Blocking errors include: no questions, question total mismatch, no submissions, unapproved submissions, missing GradeRecords, null/negative/above-max grades, non-graded status, total exceeding max.
- When ready, check the confirmation box:
  > "I confirm that all grades and reviews are complete and that finalization will lock grading changes."
- Click **Finalize Assessment**.
- Assessment status changes to **Finalized**.
- After finalization:
  - Grade edits are blocked at the service layer.
  - Review actions (approve, needs correction, return to grading) are blocked.
  - Import into the assessment is blocked.
  - Questions cannot be added or deleted.
  - Re-export remains allowed.

### 18. Export Final Grades

- On the finalized assessment page, click **Generate Workbook**.
- The system produces an `.xlsx` workbook containing:
  - **Final Grades sheet** — Institutional Student ID, First Name, Last Name, Full Name, Email, Anonymous Code, Final Grade, Maximum Grade, Percentage, Review Status, Assessment, Material, Academic Year, Exported At.

---

## Authorization Model

The application uses two operational roles:

- **Administrator** — Full access: materials, assessments, questions, import, grading, review, finalization, export (with identity restoration), users, audit, backup, restore, settings.
- **Instructor** — Anonymous grading only. Never sees student identity. Cannot import, export, manage users, or access administrative functions.

The internal role value `grader` is displayed as **Instructor**. Legacy roles (`reviewer`, `exporter`, `viewer`) are not assignable to new users and have no operational permissions.

### Page Access Matrix

| Page | Administrator | Instructor |
|------|:---:|:---:|
| Dashboard | ✅ | ✅ |
| Materials | ✅ | ❌ |
| Assessments | ✅ | ❌ |
| Import | ✅ | ❌ |
| Grading | ✅ | ✅ |
| Review | ✅ | ❌ |
| Export | ✅ | ❌ |
| Users | ✅ | ❌ |
| Audit | ✅ | ❌ |
| Backup | ✅ | ❌ |
| Settings | ✅ | ❌ |

### Service-Layer Authorization

All sensitive service functions require an `AuthContext` parameter. Missing or unauthorized contexts are rejected:
- `execute_secure_import()` — requires `PERM_IMPORT_EXECUTE` (admin only)
- `finalize_assessment()` — requires `PERM_FINALIZE_ASSESSMENT` (admin only)
- `generate_export_workbook()` — requires `PERM_EXPORT_IDENTITY` (admin only)
- `save_submission_grades()` — requires `PERM_GRADE_SUBMISSION` (admin and instructor)

### Identity Protection

- Student identities are encrypted in the database using AES-256-GCM.
- Instructor-facing interfaces display only anonymous codes (`STU-XXXXXXXX`).
- Real identities are restored **only** inside the administrator-authorized Excel export workflow.
- No decrypted identity enters audit metadata, session state, or grade records.
- The legacy `exporter` role cannot restore identities.
  - **Question Grades sheet** — Per-student grades and maximums for each question.
  - **Feedback sheet** — Per-question feedback with student identifiers.
  - **Export Summary sheet** — Export reference, assessment details, grade statistics, schema version.
- Identity fields are decrypted **only during workbook generation** and never stored back.
- Formula injection is prevented — values starting with `=`, `+`, `-`, or `@` are prefixed with `'`.
- A download button appears with the generated workbook.
- Each export creates a new `ExportRecord` with SHA-256 hash, row count, and file size.

### 19. Re-export

- The lecturer can generate a new workbook at any time after finalization.
- Re-export does not modify grades, review statuses, or finalization state.
- Each re-export creates a new `ExportRecord` with a unique export reference.
- Export history is displayed below the download section.

### 17. Finalise Grades

- The lecturer confirms finalisation.
- The system locks the assessment grades (read-only).
- A confirmation message is displayed.
- Finalisation is recorded in the audit log.

### 18. Restore Student Identities for Authorised Export

- On the Export page, the lecturer selects the assessment.
- The system displays a **clear warning** that identities will be restored.
- The lecturer must explicitly confirm.
- The system retrieves identity mappings and joins them with grading data.

### 19. Generate an Excel Workbook

- The system produces an `.xlsx` file containing:
  - Student names and email addresses
  - Anonymous IDs (for cross-reference)
  - Individual question scores
  - Total score
  - Feedback (if entered)
- The export is protected against formula injection.
- Export metadata (timestamp, user, file) is recorded.

### 20. Back Up the Database

- The lecturer can initiate a database backup from Settings.
- The backup is saved to a configured location with a timestamped filename.

---

## Separate Workflows

### New Assessment

1. Create material (or select existing).
2. Create assessment.
3. Define questions.
4. Import response file.
5. Grade.
6. Review.
7. Finalise.
8. Export.

### Continuing an Unfinished Grading Session

1. Select material.
2. Select assessment.
3. The system detects incomplete grading status.
4. The Grading page opens to the first ungraded response.
5. Resume grading.

### Correcting a Grade Before Finalisation

1. Navigate to the Grading page for the assessment.
2. Locate the response (by anonymous ID or navigation).
3. Update the score or feedback.
4. Save (immediate).
5. Changes are reflected in the Review page.

### Reopening a Finalised Assessment

1. From the Assessment settings or a dedicated action:
   - Confirmation prompt warns that reopening allows grade changes.
   - The action is recorded in the audit log.
2. The assessment status returns to "grading in progress."
3. Grades can be edited.
4. Must be re-finalised after corrections.
5. Re-export for updated results.

### Handling a Failed or Invalid Import

1. Import validation displays error messages.
2. The lecturer can:
   - Correct the file and re-upload.
   - Adjust column mappings.
   - Cancel the import.
3. No database records are created until the import is confirmed.

### Reimporting the Same File

1. The system detects that the file (by filename or import batch hash) was already imported.
2. The lecturer is informed that the file already exists.
3. Options:
   - Cancel (no changes).
   - Reimport (replaces existing import data for that batch).
   - Import as new batch (if the file has been updated).
4. Identity matching uses the hierarchy (institutional ID → email → fingerprint → manual) to link rows to existing students.

### Importing an Updated Version of a File

1. The lecturer uploads the updated file.
2. The system detects differences (e.g., different hash, different row count).
3. The lecturer confirms the update.
4. Identity matching runs against existing records using the hierarchy (institutional ID → email → fingerprint → manual).
5. New submissions are added; existing graded submissions are left unchanged.
6. Previously ungraded submissions are updated with the new response content.
7. Ambiguous identity matches block the update and require lecturer review.

---

## Identity Visibility by Step

| Step | Real Identities Visible? | Notes |
|------|--------------------------|-------|
| Start application | No | Only dashboard statistics (counts, summary). |
| Log in | No | Authentication page. |
| Create/select material | No | Material names only. |
| Create/select assessment | No | Assessment names only. |
| Define questions | No | Question configuration only. |
| Upload response file | Yes (during mapping/preview) | **Only step** where identities are visible — necessary for column mapping verification. |
| Detect and map columns | Yes | Preview table may show raw data. |
| Preview import | Yes | Lecturer must verify the mapping is correct. |
| Validate file | Yes | Validation reports reference raw data. |
| Match identities | Yes (when ambiguous) | Lecturer may need to resolve ambiguous identity matches manually. |
| Import and generate anonymous IDs | No | After import, identities are stored separately and encrypted at rest. |
| **Grade responses** | **No** | **Anonymous IDs only.** |
| Review progress | No | Anonymous IDs only. |
| Validate assessment | No | Aggregate statistics, anonymous IDs only. |
| Finalise grades | No | Anonymous IDs only. |
| Restore identities for export | Yes | **Explicitly confirmed by lecturer.** |
| Generate Excel | Yes | Full identities in output file. |
| Back up database | N/A | File operation; contains encrypted identity data. |

> **Key principle:** After the initial import preview, real student identities are never displayed in the application again unless the lecturer explicitly requests an authorised export.
