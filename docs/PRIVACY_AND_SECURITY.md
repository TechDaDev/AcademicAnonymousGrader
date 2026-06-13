# Academic Anonymous Grader — Privacy and Security

## Key Terminology

| Term | Definition | Used in this system? |
|------|------------|----------------------|
| **Anonymisation** | The irreversible removal or alteration of identifying data so that individuals cannot be re-identified by any means. | **No.** The system must restore identities for final export, so irreversible anonymisation is not suitable. |
| **Pseudonymisation** | The replacement of identifying data with artificial identifiers. Re-identification is possible with authorised access to the mapping. | **Yes.** This is the core privacy approach of the system. |
| **Hashing** | A one-way mathematical transformation of data. While hashing is one-way, it can be reversed via rainbow tables if the input space is small (e.g., names). | **No, not for identity protection.** Hashing is unsuitable because student name spaces are small and easily brute-forced. Hashing may be used for file integrity verification (e.g., SHA-256 of imported files). |
| **Encryption** | A reversible transformation that requires a secret key to restore the original data. | **Yes (Phase 4).** Identity fields will be encrypted at rest in Phase 4. |
| **Keyed hash (HMAC)** | A keyed, one-way cryptographic hash that prevents rainbow-table attacks. Used for identity fingerprints. | **Yes (Phase 4).** Identity fingerprints use HMAC-SHA256 with a dedicated key separate from the encryption key. |
| **Random anonymous identifiers** | Randomly generated tokens with no mathematical relationship to the original identity. | **Yes.** Anonymous IDs are generated using cryptographically secure random functions. |

## Privacy Model

1. **Grading interface displays only anonymous IDs.**
   - The Grading page never loads or accesses student names or email addresses.
   - Anonymous IDs are the sole identifier visible during grading.

2. **Names and email addresses are stored separately.**
   - `StudentIdentity` table (contains PII) is in a logically separate concern from `GradeRecord` and `Response`.
   - Application queries for grading never join with identity tables.

3. **Anonymous IDs are generated using cryptographically secure random values.**
   - Python's `secrets` module is used (e.g., `secrets.token_urlsafe()` or `secrets.randbelow()`).
   - IDs must not contain initials, email fragments, student numbers, or any name-derived value.
   - The mapping between identity and anonymous ID is stored in the `AnonymousStudent` table.

4. **Identity fields must be encrypted at rest, implemented in Phase 4.**
   - All PII fields on `StudentIdentity` (first_name, last_name, email, institutional_student_id) are encrypted using authenticated encryption.
   - AES-256-GCM or Fernet are the implementation candidates.
   - Encryption keys are loaded from environment variables and stored outside the SQLite database.
   - If the encryption key is unavailable at startup, the application must either fail with a clear error or operate in a restricted mode that does not access identity data.
   - An incorrect or changed key must be handled gracefully, with appropriate error messages indicating a key mismatch rather than silent data corruption.

5. **Encryption keys must be stored outside the database.**
   - Keys are stored in environment variables loaded from `.env`.
   - `.env` is excluded from Git via `.gitignore`.

6. **Secrets must not be committed to Git.**
   - `.env`, `*.key`, and credential files are in `.gitignore`.
   - No hardcoded secrets in source code.

7. **A dedicated identity fingerprint key must be used.**
   - Identity fingerprints use HMAC-SHA256 with a dedicated `IDENTITY_FINGERPRINT_KEY` environment variable.
   - This key is separate from the identity encryption key.
   - The fingerprint key is never stored in SQLite or committed to Git.
   - Changing the fingerprint key is an operational migration because stored fingerprints become invalid.

8. **Application logs must not include names, emails, or response content.**
   - Log messages reference anonymous IDs where student references are needed.
   - Response text is never logged.

9. **Student responses must never be executed.**
   - Responses are displayed as plain text within `<pre>` or `code` blocks.
   - No `eval()`, `exec()`, `subprocess`, or dynamic code execution is performed on response content.
   - HTML responses are parsed with BeautifulSoup (safe parser), never rendered as active HTML in the grading interface.

10. **Exporting identifiable results is a privileged operation.**
    - The Export page displays a clear warning before restoring identities.
    - The lecturer must explicitly confirm the action.
    - Every export is recorded in `ExportRecord` for audit.

11. **Temporary uploaded files must be deleted or protected.**
    - Uploaded HTML files are stored in a temporary directory.
    - Temporary files are deleted after successful import or on application exit.

12. **Database backups must be treated as sensitive.**
    - Backups contain encrypted (or encryptable) identity data.
    - Backup files should be stored in a secure, access-controlled location.

## Threat Model

### T01: Lecturer accidentally seeing identities while grading

| Aspect | Detail |
|--------|--------|
| **Threat** | A UI bug or data-leakage query causes real names or emails to appear on the Grading page. |
| **Likelihood** | Low |
| **Impact** | High — defeats the purpose of anonymous grading. |
| **Mitigation** | Grading page queries use views or queries that explicitly exclude identity columns. Identity tables are never joined in grading queries. Automated tests verify that identity data returns empty results from grading endpoints. |

### T02: Database theft

| Aspect | Detail |
|--------|--------|
| **Threat** | An attacker gains access to the SQLite database file. |
| **Likelihood** | Low (local machine, single user) |
| **Impact** | High — all student data exposed. |
| **Mitigation** | Identity fields encrypted at rest (Phase 4). The database is stored in the user's application data directory with default OS permissions. The lecturer is advised to enable full-disk encryption (BitLocker). |

### T03: Secret key exposure

| Aspect | Detail |
|--------|--------|
| **Threat** | The encryption key for identity fields is leaked via Git, logs, or screenshots. |
| **Likelihood** | Medium |
| **Impact** | High — encrypted data becomes readable. |
| **Mitigation** | Keys are stored in `.env` excluded from Git. Keys are never printed in logs. The lecturer is advised on secure key storage. |

### T04: Predictable student IDs

| Threat | An attacker (or another student) guesses the anonymous ID of a specific student. |
|--------|-------|
| **Likelihood** | Low |
| **Impact** | Medium — could allow associating grades with identities if the mapping is also compromised. |
| **Mitigation** | Anonymous IDs are generated using `secrets.token_urlsafe(6)` producing at least 48 bits of entropy. Sequential or name-derived IDs are strictly forbidden. |

### T05: Accidental duplicate import

| Aspect | Detail |
|--------|--------|
| **Threat** | The same file is imported twice, creating duplicate student or submission records. |
| **Likelihood** | Medium |
| **Impact** | Medium — duplicate records cause confusion and may produce incorrect reports. |
| **Mitigation** | Import batch tracking prevents silent duplicates. Deduplication uses the identity-matching hierarchy (institutional ID → email → fingerprint → manual). The same file (detected by hash) is flagged. |

### T06: Accidental grade modification

| Aspect | Detail |
|--------|--------|
| **Threat** | Grades are accidentally changed after finalisation without authorisation or audit. |
| **Likelihood** | Low |
| **Impact** | High — undermines grade integrity. |
| **Mitigation** | Finalised assessments are read-only. Reopening requires explicit confirmation and is logged. |

### T07: Unauthorised Excel export

| Aspect | Detail |
|--------|--------|
| **Threat** | A person other than the lecturer gains access to the application and exports identifiable results. |
| **Likelihood** | Low (single-user local app) |
| **Impact** | High — student data leaked. |
| **Mitigation** | Export requires explicit confirmation. Future authentication phase will require login before any operation. |

### T08: Spreadsheet leakage

| Aspect | Detail |
|--------|--------|
| **Threat** | The exported Excel file is shared inappropriately. |
| **Likelihood** | Medium |
| **Impact** | High — student data exposed. |
| **Mitigation** | The application warns the lecturer that the file contains identifiable data. The lecturer is responsible for secure handling. Future versions may add optional password protection. |

### T09: Malicious content in uploaded HTML

| Aspect | Detail |
|--------|--------|
| **Threat** | The uploaded HTML file contains JavaScript, trackers, or other active content. |
| **Likelihood** | Low |
| **Impact** | Medium — potential XSS or data exfiltration if rendered in a browser. |
| **Mitigation** | HTML is parsed with BeautifulSoup using a safe parser (`html.parser`). JavaScript is never executed. Active content (scripts, event handlers) is stripped during parsing. Data is extracted from table structure only. |

### T10: Formula injection in exported Excel files

| Aspect | Detail |
|--------|--------|
| **Threat** | A student response beginning with `=`, `+`, `-`, or `@` is interpreted as an Excel formula when the workbook is opened. |
| **Likelihood** | Low |
| **Impact** | Medium — could execute arbitrary Excel functions or leak data. |
| **Mitigation** | All exported text fields are prefixed with a single quote (`'`) or formatted as plain text using openpyxl to prevent formula interpretation. Cells are explicitly set to text format. |

### T11: Code execution from student answers

| Aspect | Detail |
|--------|--------|
| **Threat** | A student submits code as an answer, and the system accidentally executes it. |
| **Likelihood** | Low |
| **Impact** | Critical — arbitrary code execution on the lecturer's machine. |
| **Mitigation** | Responses are stored as plain text and displayed in a read-only code block. No `eval()`, `exec()`, `compile()`, or `subprocess` call is ever made on response content. Streamlit's `code()` or `text()` functions are used for display, not `markdown()` with unsafe HTML. |

### T12: Local machine compromise

| Aspect | Detail |
|--------|--------|
| **Threat** | The lecturer's machine is infected with malware that accesses the database or exported files. |
| **Likelihood** | Low |
| **Impact** | Very High — full data exposure. |
| **Mitigation** | This is outside the application's scope. The lecturer is advised to maintain OS security updates, use antivirus software, enable full-disk encryption, and follow general security best practices. |

## Excel Formula Injection Prevention Rule

> **All exported text beginning with `=`, `+`, `-`, or `@` must be safely escaped.**

Implementation guidance:
- In openpyxl, set cell formatting to `@` (text format) for all data columns.
- Alternatively, prepend a single quote (`'`) to values that start with `=`, `+`, `-`, or `@`.
- Use openpyxl's `DataOnly()` or set `number_format = '@'` to force text interpretation.

## Data Classification

| Data Category | Examples | Classification | Handling Requirements |
|---------------|----------|----------------|----------------------|
| Student identity | First name, Last name, Email | **Sensitive** | Encrypt at rest; never display during grading; log only anonymous ID. |
| Anonymous ID | A3F9K2B1 | **Internal** | No encryption needed; subject to access control via application. |
| Grading data | Score, Feedback | **Internal** | Store normally; feedback should not contain PII. |
| Response content | Student answers | **Sensitive** | May contain self-identifying info; display as text only; never execute. |
| Export files | Excel workbooks | **Sensitive** | Contain restored identities; warn before creation; lecturer responsible for secure handling. |
| Audit logs | Event records | **Internal** | Must not contain student PII. |
| Database backup | SQLite file | **Sensitive** | Contains all data; treat with same care as live database. |
