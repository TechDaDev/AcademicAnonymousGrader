# Academic Anonymous Grader — Project Specification

## Project Name

**Academic Anonymous Grader (AAG)**

## Problem Statement

Lecturers who use learning management systems (LMS) to collect student assessment responses often face a tension: they want to grade anonymously to avoid unconscious bias, but the exported response files from the LMS contain full student identities (names, email addresses) alongside the answers. Manually anonymising these files is error-prone, labour-intensive, and does not scale beyond a handful of students. Furthermore, after grading, identities must be restored to publish final results — a process that is equally fragile when done by hand.

Existing tools either lack the required anonymisation workflow, assume a specific LMS format, or require network connectivity that may not be available. There is a need for a lightweight, locally run tool that ingests LMS assessment exports, pseudonymises student identities, provides a clean grading interface, and produces a final authorised Excel report with real identities restored.

## Project Objectives

1. **Import** assessment response files exported from a learning platform.
2. **Extract** student identity, submission metadata, source grade, and all question responses.
3. **Pseudonymise** student identities by replacing visible names with random anonymous IDs during grading.
4. **Store** identity mappings separately from grading data so that graders never see personal information.
5. **Enable** a lecturer to assign a score and optional feedback to every response through a clean web interface.
6. **Save** grading progress immediately after every action so no work is lost.
7. **Validate** all grades before finalisation.
8. **Restore** real student identities only when generating the final authorised Excel report.
9. **Support** multiple academic materials and multiple assessments per material.
10. **Support** HTML as the initial import format, with XLSX and CSV planned for later phases.
11. **Never execute** code contained in student responses.

## Intended Users

- **Primary:** Individual lecturers or instructors who grade their own assessments.
- **Secondary (future):** Teaching assistants acting under lecturer authorisation.
- **Not intended:** Students, institutional administrators, or external auditors in the first release.

## Scope of the First Usable Version

- Single lecturer operating on a local Windows 11 machine.
- Local SQLite database with no public network exposure.
- No student accounts — students never interact with the system.
- No AI-assisted grading.
- Import of HTML-formatted assessment response files from a supported LMS.
- Manual scoring and feedback entry per response.
- Pseudonymised grading interface.
- Excel export with restored identities.
- Basic audit logging.

## Out-of-Scope Features

- AI or automatic grading in the first release.
- Student-facing portals or dashboards.
- Multi-user concurrent grading.
- LDAP, OAuth, or SSO integration.
- Cloud deployment or hosted service.
- Real-time synchronisation between graders.
- Plagiarism detection.
- Rubric-based scoring with weighted sub-criteria.
- Integration with any specific LMS API (file-based import only).

## Functional Requirements

| ID | Requirement |
|----|------------|
| F01 | The system shall import HTML files containing assessment responses. |
| F02 | The system shall detect identity columns (First name, Last name, Email address). |
| F03 | The system shall detect submission metadata columns (Status, Started, Completed, Duration, Grade). |
| F04 | The system shall dynamically detect response columns (Response 1, Response 2, …, Response N). |
| F05 | The system shall normalise column names to match known identifiers. |
| F06 | The system shall assign a cryptographically random anonymous ID to each student. |
| F07 | The system shall present only anonymous IDs during grading. |
| F08 | The system shall allow the lecturer to enter a numeric score per response. |
| F09 | The system shall allow the lecturer to enter optional text feedback per response. |
| F10 | The system shall save grading progress immediately after each score or feedback change. |
| F11 | The system shall validate that no grade exceeds the question maximum. |
| F12 | The system shall require explicit confirmation before restoring identities for export. |
| F13 | The system shall generate an authorised Excel workbook (.xlsx) with real identities. |
| F14 | The system shall support multiple academic materials. |
| F15 | The system shall support multiple assessments per material. |
| F16 | The system shall never execute JavaScript, Python, or any code from uploaded files. |
| F17 | The system shall preserve Arabic text, multiline answers, code indentation, and decoded HTML entities. |
| F18 | The system shall allow reimporting the same file without duplicating records. |
| F19 | The system shall allow importing an updated version of a file. |
| F20 | The system shall allow a lecturer to reopen a finalised assessment to correct grades. |
| F21 | The system shall support an institutional student ID column in addition to name and email. |
| F22 | The system shall match imported students against existing identities using a hierarchical strategy: institutional ID, then email, then manual resolution. |
| F23 | The system shall block automatic merging when identity matches are ambiguous and require lecturer review. |
| F24 | The system shall not merge students using names alone. |
| F25 | The system shall compute identity fingerprints using HMAC-SHA256 with a dedicated key separate from the identity encryption key. |
| F26 | The system shall use identity fingerprints only as supporting matching signals, never as primary keys. |

## Non-Functional Requirements

| ID | Requirement |
|----|------------|
| N01 | **Performance:** Import of a file with up to 500 students and 20 responses each shall complete within 30 seconds. |
| N02 | **Usability:** A lecturer with basic computer skills shall be able to complete a grading session without external documentation. |
| N03 | **Reliability:** Unsaved grading progress shall not be lost; autosave occurs after every grading action. |
| N04 | **Security:** Student identity data shall be stored separately from grading data. |
| N05 | **Security:** Anonymous IDs shall be generated using cryptographically secure randomness. |
| N06 | **Security:** Secrets shall not be committed to source control. |
| N07 | **Portability:** The application shall run on Windows 11 without WSL. |
| N08 | **Maintainability:** The codebase shall separate import, pseudonymisation, grading, and export concerns. |
| N09 | **Testability:** Core logic (parsing, validation, pseudonymisation) shall be unit-testable without a UI. |

## Technology Decisions

| Concern | Decision | Rationale |
|---------|----------|-----------|
| Language | Python 3.12 | Mature ecosystem, strong data-processing libraries, cross-platform. |
| UI framework | Streamlit | Rapid development, Python-native, sufficient for single-user local tool. |
| Database | SQLite | Zero-configuration, file-based, suitable for single-user local use. |
| ORM | SQLAlchemy 2.x | Mature, well-documented, supports SQLite and future migrations. |
| Data processing | pandas | Efficient columnar data handling, import transformation pipeline. |
| HTML parsing | BeautifulSoup (bs4) | Robust HTML parsing, handles real-world malformed markup. |
| Excel export | openpyxl | Full control over Excel formatting and formula-injection prevention. |
| Cryptography | cryptography | Secure random generation; Phase 4 at-rest encryption of identity fields. |
| Environment | python-dotenv | Manage secrets and configuration outside source code. |
| Testing | pytest | Standard Python testing framework with rich fixture support. |

> **Note:** These technologies are **recorded in Phase 0** but will not be installed until Phase 1. No dependencies have been installed at this time.

## Initial Deployment Model

| Aspect | Decision |
|--------|----------|
| Operator | Single lecturer |
| Machine | Local Windows 11 |
| Database | Local SQLite file |
| Network | No public exposure; no remote access |
| Student accounts | None |
| AI grading | Not in the first usable release |

## Assumptions

1. The lecturer has basic familiarity with running a Python/Streamlit application.
2. The lecturer has installed Python 3.12 and required system dependencies.
3. The exported HTML file follows a predictable table structure with headers in a `<thead>` or first `<tr>`.
4. Identity columns are labelled with some variation of "First name", "Last name", and "Email address".
5. Response columns are labelled with some variation of "Response" followed by a number.
6. The lecturer is operating in a trusted local environment.
7. Students are identified by a hierarchical matching process (institutional ID, then email, then keyed fingerprint, then manual resolution), not by any single field alone.
8. A single HTML file represents one assessment attempt for one class section.
9. The existing grade in the source file is informational and may require independent verification.

## Constraints

1. The system must not require internet connectivity during normal operation.
2. The system must not upload any student data to external services.
3. The system must not execute code embedded in student responses.
4. The first release targets Windows 11 only.
5. All student-identifying data must be encrypted at rest, implemented in Phase 4.
6. The project must use only open-source, freely available dependencies.

## Definitions and Terminology

| Term | Definition |
|------|------------|
| **Anonymisation** | Irreversible removal of identifying data. Not used in this system. |
| **Pseudonymisation** | Replacement of identifying data with artificial identifiers; reversible with authorised access. The approach used by this system. |
| **Anonymous ID** | A random, non-reversible token assigned to a student for the duration of grading. |
| **Identity fingerprint** | A keyed HMAC-SHA256 value computed from a student's best available identifier (institutional ID or email). Used as a supporting signal in identity matching. Not a primary key. |
| **Identity mapping** | The stored relationship between a student's real identity and their anonymous ID. |
| **Material** | An academic course or subject (e.g., "DBOAIC1101 — OOP"). |
| **Assessment** | A specific graded component within a material (e.g., "Midterm Exam"). |
| **Submission** | A single student's submitted responses for one assessment. |
| **Response** | A student's answer to a single question within a submission. |
| **Import batch** | A recorded import operation capturing source file metadata. |
| **Finalisation** | The irreversible (without reopening) lock of grades for an assessment. |
| **Source grade** | The grade present in the imported file; treated as informational only. |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Accidental identity disclosure during grading | Medium | High | Anonymous IDs are the only identifier shown; real names are never loaded into the grading UI. |
| Database file theft | Low | High | Identity fields to be encrypted at rest; database stored in user-controlled location. |
| Secret key exposure | Medium | High | Keys stored in `.env` file, excluded from Git via `.gitignore`. |
| Predictable anonymous IDs | Low | High | Use `secrets.randbelow()` or `secrets.token_urlsafe()` for generation. |
| Accidental duplicate import | Medium | Medium | Import batch tracking; deduplication by email and assessment. |
| Accidental grade modification after finalisation | Low | High | Finalised assessments are read-only until formally reopened; reopening is logged. |
| Unauthorised Excel export | Medium | Medium | Export requires explicit lecturer confirmation; future authentication gate. |
| Formula injection in exported Excel | Medium | Medium | Escape cells beginning with `=`, `+`, `-`, or `@` with a leading apostrophe or text prefix. |
| Malicious HTML content in uploaded file | Low | Medium | Use BeautifulSoup for safe parsing; never execute JavaScript; strip event handlers. |
| Code execution from student answers | Low | High | Responses are displayed as plain text in a code block; never passed to `eval()` or similar. |
| Local machine compromise | Low | Very High | Application assumes a trusted environment; mitigation is outside the application scope (OS-level security). |

## Phase 0 Decisions

| Decision | Value |
|----------|-------|
| UI framework | Streamlit |
| Database | SQLite |
| ORM | SQLAlchemy |
| HTML parser | BeautifulSoup |
| Excel library | openpyxl |
| Import format (initial) | HTML |
| Export format | Excel (.xlsx) |
| Identity method | Pseudonymisation (not anonymisation) |
| Unique student key | Internal UUID (with multi-field matching hierarchy) |
| Target OS | Windows 11 |
| Deployment model | Single-user local |

## Open Decisions (Non-Blocking for Phase 1)

| Decision | Notes |
|----------|-------|
| Anonymous ID format details | Format `STU-XXXXXXXX` decided in Phase 0; exact character set and casing to be confirmed in Phase 4. |
| Encryption key details for identity fields | AES-256-GCM is the implementation candidate; key-management details to be confirmed in Phase 4. |
| Backup strategy details | Frequency, location, and naming convention for database backups. |
| Streamlit theming and colour palette | To be defined during UI implementation in Phase 1. |
| Minimum supported screen resolution | To be tested during Phase 1 UI development. |
| Log file retention policy | How long audit logs are retained before rotation or deletion. |
