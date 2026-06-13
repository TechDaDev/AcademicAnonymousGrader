# Academic Anonymous Grader — Phase Roadmap

## Phase 0: Specification and Rules

| Aspect | Detail |
|--------|--------|
| **Goal** | Define the complete project specification, data model, workflow, validation rules, UI requirements, and acceptance criteria. No application code is written. |
| **Included work** | Create all documentation files; define technology stack; design data model; specify import format; define validation rules; design UI layout; write acceptance criteria; plan all phases. |
| **Excluded work** | Any Python code, Streamlit pages, database models, service modules, or test files. No dependency installation. |
| **Dependencies** | None. |
| **Deliverables** | `PROJECT_SPECIFICATION.md`, `WORKFLOW.md`, `DATA_MODEL.md`, `PRIVACY_AND_SECURITY.md`, `IMPORT_FILE_SPECIFICATION.md`, `VALIDATION_RULES.md`, `UI_REQUIREMENTS.md`, `ACCEPTANCE_CRITERIA.md`, `PHASE_ROADMAP.md`, `README.md`, `.gitignore`. |
| **Tests** | None (specification only). |
| **Completion conditions** | All deliverables exist, are internally consistent, use correct privacy terminology, and are approved by human review. |

---

## Phase 1: Project Foundation

| Aspect | Detail |
|--------|--------|
| **Goal** | Establish the working project structure, Python environment, database schema, and basic Streamlit application shell. |
| **Included work** | Create project directory structure; set up Python virtual environment (`.venv`); create `requirements.txt` with all documented dependencies; create `.env.example`; create `app.py` entry point with basic Streamlit configuration; create `src/` package structure; initialise SQLite database with SQLAlchemy models matching `DATA_MODEL.md`; configure logging; set up `pytest` with `conftest.py`; create database initialisation and migration utilities; verify application starts and navigation sidebar renders all documented pages as stubs. |
| **Excluded work** | Any business logic (parsing, grading, export); actual Streamlit page content beyond stubs; authentication; encryption. |
| **Dependencies** | Approval of all Phase 0 documentation. |
| **Deliverables** | Working Streamlit application with navigation stubs; SQLite database with all tables; `requirements.txt`; `src/` package structure; test suite skeleton. |
| **Tests** | Verify `pytest` discovers tests; verify database schema matches data model; verify application starts without errors. |
| **Completion conditions** | All dependencies install cleanly; application starts; database tables exist; tests run; Phase 0 documentation is accessible from the application. |

---

## Phase 2: Materials and Assessments

| Aspect | Detail |
|--------|--------|
| **Goal** | Implement CRUD operations for academic materials and assessments with question configuration. |
| **Included work** | Implement `Material` service and Streamlit page; implement `Assessment` service and page; implement `Question` configuration; implement validation rules M001–M005, A001–A008, Q001–Q006; create database CRUD operations for all three entities; add navigation flow from Materials to Assessments to Questions. |
| **Excluded work** | Import, grading, or export functionality. |
| **Dependencies** | Phase 1 (database, app structure). |
| **Deliverables** | Functional Materials, Assessments, and Questions pages; validation error handling. |
| **Tests** | Unit tests for validation rules; integration tests for CRUD operations. |
| **Completion conditions** | All CRUD operations work; validation rules are enforced; error messages are displayed; acceptance criteria AC-P2-01 through AC-P2-05 pass. |

---

## Phase 3: HTML Parser

| Aspect | Detail |
|--------|--------|
| **Goal** | Implement the HTML response file parser with dynamic column detection, data extraction, and import preview. |
| **Included work** | Implement HTML parsing service using BeautifulSoup; implement column normalisation and detection; implement dynamic response-column detection; implement import preview display; implement import validation rules F001–F010 and S001–S006; implement edge-case handling (Arabic text, line breaks, code indentation, HTML entities, blank responses, duplicate emails, malformed data); implement ImportBatch recording; implement `ImportResult` data structure. |
| **Excluded work** | Pseudonymisation (Phase 4); grading (Phase 5); XLSX or CSV import (Phase 9). |
| **Dependencies** | Phase 1 (database, app structure); Phase 2 (assessments and questions for mapping). |
| **Deliverables** | HTML parser module; Import page with upload, preview, column mapping, and validation. |
| **Tests** | Unit tests for parser with various HTML files; edge-case tests for all documented scenarios; integration tests for import flow. |
| **Completion conditions** | All acceptance criteria AC-P3-01 through AC-P3-10 pass; the sample file imports correctly; edge cases are handled. |

---

## Phase 4: Pseudonymisation and Identity Encryption

| Aspect | Detail |
|--------|--------|
| **Goal** | Implement anonymous ID generation, identity mapping storage, privacy-separated data access, and at-rest encryption of identity fields. |
| **Included work** | Implement `secrets`-based anonymous ID generation in `STU-XXXXXXXX` format with collision detection and regeneration; implement `StudentIdentity` and `AnonymousStudent` storage; implement identity mapping lookup for reimports; implement grading data queries that exclude identity columns; verify that the Grading page cannot access identity data at the query level; implement duplicate-detection logic for reimports using the hierarchical matching strategy; encrypt all PII fields on `StudentIdentity` (first_name, last_name, email, institutional_student_id) using authenticated encryption (AES-256-GCM or Fernet); load encryption keys from environment variables; store keys outside the SQLite database; fail startup or enter restricted mode when the encryption key is unavailable; handle incorrect or changed keys with clear error messages; ensure no keys are committed to Git; implement encryption and decryption tests; verify that grading queries do not retrieve identity fields; verify that logs do not contain decrypted identity data; **implement HMAC-SHA256 identity fingerprint generation using a dedicated `IDENTITY_FINGERPRINT_KEY` environment variable separate from the encryption key; generate fingerprints from institutional student ID or email when available; ensure names alone never generate automatic fingerprint matches; implement fingerprint collision and key-change handling; document key-migration implications**. |
| **Excluded work** | Grading UI (Phase 5); operational key rotation and backup encryption (Phase 8). |
| **Dependencies** | Phase 3 (import produces student data to pseudonymise and encrypt). |
| **Deliverables** | Anonymous ID generation module; identity encryption service; identity mapping service; privacy-separated data access layer. |
| **Tests** | Unit tests for ID uniqueness, randomness, and collision recovery; encryption and decryption round-trip tests; key-mismatch handling tests; integration tests confirming grading queries return no PII; **HMAC-SHA256 fingerprint generation tests; fingerprint key-change migration tests;** reimport mapping tests; log-scrubbing verification. |
| **Completion conditions** | All acceptance criteria AC-P4-01 through AC-P4-12 pass; identity fields are encrypted at rest; grading queries verified to exclude PII; encryption-key errors are handled gracefully; fingerprints use HMAC-SHA256 with a dedicated key. |

---

## Phase 5: Manual Grading

| Aspect | Detail |
|--------|--------|
| **Goal** | Implement the anonymous grading interface with score entry, feedback, and immediate save. |
| **Included work** | Implement Grading page UI per `UI_REQUIREMENTS.md`; implement response navigation (next, previous, skip); implement score input with validation G001–G008; implement immediate save on grading action; implement Mark for Review flag; implement progress tracking and display; implement grade persistence in `GradeRecord`; implement save-status indicator. |
| **Excluded work** | Review page (Phase 6); finalisation (Phase 7); bulk operations. |
| **Dependencies** | Phase 3 (import); Phase 4 (anonymous IDs). |
| **Deliverables** | Functional Grading page with full navigation and validation. |
| **Tests** | Unit tests for grade validation; integration tests for save-and-navigate flow; UI tests for anonymous display verification. |
| **Completion conditions** | All acceptance criteria AC-P5-01 through AC-P5-08 pass; grading is fully anonymous; grades are persisted immediately. |

---

## Phase 6: Review and Validation

| Aspect | Detail |
|--------|--------|
| **Goal** | Implement the Review page with filtering and pre-finalisation validation. |
| **Included work** | Implement Review page UI with anonymous ID, scores, totals, status, and flag display; implement filters (incomplete, zero score, marked for review); implement navigation from Review to Grading; implement pre-finalisation validation checks FL001–FL009; display validation results with pass/fail indicators. |
| **Excluded work** | Finalisation action (Phase 7); export (Phase 7). |
| **Dependencies** | Phase 5 (grading produces data to review). |
| **Deliverables** | Functional Review page with filters and validation summary. |
| **Tests** | Integration tests for filter correctness; unit tests for finalisation validation rules. |
| **Completion conditions** | All acceptance criteria AC-P6-01 through AC-P6-04 pass; validation correctly blocks incomplete assessments. |

---

## Phase 7: Finalisation and Excel Export

| Aspect | Detail |
|--------|--------|
| **Goal** | Implement grade finalisation (locking), identity restoration for export, and Excel workbook generation. |
| **Included work** | Implement finalisation action (assessment status → finalised, grades become read-only); implement reopen action (with audit logging); implement Excel export service using openpyxl; implement formula-injection prevention; implement identity restoration for export only; implement export warning and confirmation UI; implement export validation E001–E008; implement `ExportRecord` creation; implement download of generated Excel file. |
| **Excluded work** | Authentication (Phase 8); audit dashboard (Phase 8); backup (Phase 8). |
| **Dependencies** | Phase 5 (grading data); Phase 6 (validation). |
| **Deliverables** | Finalisation workflow; Export page with Excel generation; reopen functionality. |
| **Tests** | Unit tests for Excel generation; formula-injection tests; integration tests for finalisation flow; manual export verification. |
| **Completion conditions** | All acceptance criteria AC-P7-01 through AC-P7-09 pass; Excel file is correct and safe. |

---

## Phase 8: Authentication, Audit, and Backup

| Aspect | Detail |
|--------|--------|
| **Goal** | Add lecturer authentication, audit log viewing, and database backup functionality. |
| **Included work** | Implement authentication system (username/password with hashed passwords); implement login page and session management; protect all pages behind authentication; implement audit event viewing page; implement database backup and restore functionality; implement backup scheduling configuration; enhance `AuditEvent` recording for all major actions. |
| **Excluded work** | OAuth, LDAP, SSO; multi-user support. |
| **Dependencies** | Phase 7 (all core features exist to be authenticated and audited). |
| **Deliverables** | Authentication system; audit log viewer; backup functionality. |
| **Tests** | Authentication flow tests; audit event recording tests; backup and restore tests. |
| **Completion conditions** | Authentication prevents unauthorised access; audit events are recorded for all critical actions; backups can be created and restored. |

---

## Phase 9: XLSX and CSV Import

| Aspect | Detail |
|--------|--------|
| **Goal** | Extend the import system to support XLSX and CSV file formats alongside HTML. |
| **Included work** | Implement XLSX parser using openpyxl; implement CSV parser using pandas or csv module; create a common import interface (strategy pattern); update column normalisation for XLSX/CSV headers; handle format-specific edge cases (multiple sheets, encoding detection, delimiter detection); update file validation rules for new formats; update UI to accept multiple file types. |
| **Excluded work** | Other file formats (PDF, Word); API-based import. |
| **Dependencies** | Phase 3 (HTML parser architecture provides patterns for new parsers). |
| **Deliverables** | XLSX parser module; CSV parser module; unified import interface. |
| **Tests** | Unit tests for XLSX parsing; unit tests for CSV parsing; integration tests for multi-format import flow. |
| **Completion conditions** | XLSX and CSV files import correctly with the same column detection and validation as HTML. |

---

## Phase 10: Multi-Material Production Improvements

| Aspect | Detail |
|--------|--------|
| **Goal** | Improve the application for production use with multiple materials and larger datasets. |
| **Included work** | Performance optimisation for large assessments (500+ students); pagination for materials, assessments, and review lists; improved search and filtering across materials; batch operations; UI polish and theming; error recovery improvements; data export (JSON backup of configuration); keyboard shortcuts for grading. |
| **Excluded work** | AI grading (Phase 11); cloud deployment. |
| **Dependencies** | All prior phases. |
| **Deliverables** | Performance improvements; UI polish; batch operations. |
| **Tests** | Performance benchmarks; regression tests. |
| **Completion conditions** | Smooth operation with 500+ student assessments; all UI is polished and consistent. |

---

## Phase 11: AI-Assisted Grading

| Aspect | Detail |
|--------|--------|
| **Goal** | Add optional AI-assisted grading suggestions to help the lecturer score responses faster. |
| **Included work** | Integrate with an AI/LLM API (configurable endpoint); implement prompt engineering for grading suggestions; implement suggestion display in the grading UI (lecturer reviews and approves/rejects); implement batch AI grading option; implement offline/online toggle; implement cost tracking; implement data privacy warning (student responses sent to external API). |
| **Excluded work** | Fully automatic grading without human review; local AI model hosting. |
| **Dependencies** | Phase 5 (grading UI exists to integrate suggestions into). |
| **Deliverables** | AI grading suggestion module; configuration UI for AI settings; privacy warning flows. |
| **Tests** | Integration tests with mock AI API; privacy warning verification tests. |
| **Completion conditions** | AI suggestions appear in the grading UI; lecturer can accept or override; all suggestions are clearly marked as AI-generated. |

---

## Phase Dependency Diagram

```
Phase 0 (Specification)
    │
    ▼
Phase 1 (Foundation) ◄─── Approval of Phase 0
    │
    ▼
Phase 2 (Materials & Assessments)
    │
    ▼
Phase 3 (HTML Parser) ──► Phase 4 (Pseudonymisation)
                                    │
                                    ▼
                            Phase 5 (Manual Grading)
                                    │
                                    ▼
                            Phase 6 (Review & Validation)
                                    │
                                    ▼
                            Phase 7 (Finalisation & Export)
                                    │
                            ┌───────┴───────┐
                            ▼               ▼
                    Phase 8 (Auth)    Phase 9 (XLSX/CSV)
                            │               │
                            └───────┬───────┘
                                    ▼
                            Phase 10 (Production Improvements)
                                    │
                                    ▼
                            Phase 11 (AI-Assisted Grading)
```
