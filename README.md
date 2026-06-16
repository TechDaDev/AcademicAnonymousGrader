# Academic Anonymous Grader (AAG)

**Anonymously grade academic assessment responses, then export authorised results.**

A lightweight, locally run tool that imports assessment response files from a learning management system, pseudonymises student identities for unbiased grading, and produces a final authorised Excel report with identities restored.

---

## Current Status: Revised Authorization — Administrator & Instructor

The application uses two operational roles:
- **Administrator** — full access to materials, assessments, import, grading, review, finalization, export (with identity restoration), users, audit, backup, restore, and settings
- **Instructor** — anonymous grading only; never sees student identity; cannot import, export, manage users, or access administrative functions

Legacy roles (`reviewer`, `exporter`, `viewer`) exist in the database for backward compatibility but are **not assignable** to new users. They are stripped of operational permissions.

### Role Display

The internal role value `grader` is displayed to users as **Instructor**. Legacy roles display with a `(legacy)` tag.

### Access Control

- All pages enforce authentication and role-based access at the entry point
- Unauthorized direct URL access is rejected with a safe error message
- Service-layer functions require a valid `AuthContext` — missing context raises an error
- The last active Administrator cannot be deactivated or downgraded
- **Authorization** — administrator and grader only
- **24 new automated tests**
- **838 total automated tests**

### What Phase 7 Implements (prior)

- Finalization readiness — validation checks FA001–FA011
- Explicit finalization with locking
- Excel workbook generation (4 sheets)
- Identity restoration for export only
- Re-export support

- **Anonymous grading workflow** — select assessment, view submissions, grade questions
- **GradeRecord per submission+question** — unique constraint prevents duplicates
- **Grade validation** — Decimal precision, 0 to question max, with clear error messages
- **Save Draft** — saves partial grades without requiring completion
- **Mark Submission Graded** — validates all questions graded and total within assessment max
- **Grading progress tracking** — ungraded, in progress, graded with completion percentage
- **Submission navigation** — previous/next between anonymous submissions
- **Status filters** — All, Ungraded, In progress, Graded
- **Anonymous display** — only anonymous codes shown; no names, emails, or IDs
- **Editor comments** — optional free-text feedback per question
- **Identity separation** — grading service never queries StudentIdentity

### What Phase 4 Implements

- **Safe HTML table parsing** with BeautifulSoup/lxml (Phase 3)
- **Dynamic response-column detection** (Response N, Answer N, Question N) (Phase 3)
- **Anonymous code generation** — cryptographically secure `STU-XXXXXXXX` format
- **AES-256-GCM identity encryption** — all PII encrypted at rest
- **Secure import** — single-transaction encrypted import
- **HMAC-SHA256 identity fingerprinting** with dedicated key

### Secure Import Workflow

1. Select an active material
2. Select a draft or ready assessment
3. Upload an HTML response export file
4. Auto-detect candidate response tables
5. If multiple strong candidates exist, select the correct table
6. Review detected columns with editable mapping
7. Adjust column mappings as needed (identity, metadata, response, ignore)
8. Reconcile mapped response numbers with assessment question numbers
9. Review per-row preview with expandable details
10. Confirm Phase 3 validation readiness
11. **Phase 4 — Identity matching dry run** (matched, new, ambiguous counts)
12. **Phase 4 — Manual identity resolution** (resolve ambiguous or missing-identity rows)
13. **Phase 4 — Secure import confirmation** (checkbox + button)
14. **Phase 4 — Import result** (counts-only success screen with batch reference)

### HTML Parser Features

- **Safety:** JavaScript, iframe, script, style, and event-handler attributes are removed. No eval or exec. No network requests.
- **File limits:** Configurable max file size (20 MB), tables (20), rows (10,000), columns (500), cell length (1,000,000).
- **Column aliases:** ~30 known aliases for identity, metadata, and response fields.
- **Response detection:** Patterns `Response N`, `Answer N`, `Question N` with non-consecutive and high-number support.
- **Metadata parsing:** Multiple datetime formats, duration text (e.g. "1 hour 24 mins"), grades with/without denominators.
- **Unicode:** Arabic text, code indentation, and HTML entities are preserved.
- **Preview only:** No student, submission, or response records are created.

### Sample Files Policy

A local `samples/` folder is provided for manual testing with real academic exports.

- **Only `samples/.gitkeep` and `samples/README.md` are tracked by Git.**
- All other files in `samples/` are ignored by `.gitignore`.
- Sample files may contain real student data — never commit them.
- Use `tests/fixtures/` for committed synthetic test data.
- Remove or anonymize local sample files before sharing or archiving the repository.

### Fixture Policy

All HTML fixture files under `tests/fixtures/` contain **fictional data only**:

- Names are synthetic (Amina Hassan, Omar Saleh, etc.)
- Emails use `example.com`
- No real student identities, institutional IDs, grades, or responses are used
- Never copy real sample content into `tests/fixtures/`

### Material Management Workflow

1. Create a material with name (required), code, academic year, stage, department, and notes
2. View the material list with search and archive filtering
3. Edit material details
4. Archive a material (soft delete — all assessments preserved)
5. Restore an archived material
6. Duplicate names are allowed if academic year, stage, or department differ

### Assessment Configuration Workflow

1. Select a parent material
2. Create an assessment with title, type, academic year, and maximum grade
3. Add questions with numbers, titles, and maximum grades
4. Validation ensures question total equals assessment maximum grade before marking ready
5. Mark assessment as Ready when configuration is valid
6. Return a Ready assessment to Draft for editing
7. Duplicate an assessment (including all questions)
8. Archive and restore assessments

### Question Configuration

- Add questions with auto-incrementing numbers
- Edit question number, title, maximum grade, and rubric
- Remove questions from draft assessments
- Reorder questions (drag-to-order via checkboxes)
- Questions are protected when responses exist (future phase)

### Validation Rules

| Area | Key Rules |
|------|-----------|
| Material | Name required (max 200), code max 50, duplicate detection by name+year+stage+dept |
| Assessment | Title required (max 200), max grade > 0, Decimal precision 2, parent must be active |
| Question | Number > 0, max grade > 0, unique numbers per assessment, max grade Decimal 2 |
| State | Draft→Ready only when question total = assessment max; Ready→Draft allowed; Grading/Finalized protected |

### What Phase 5 Intentionally Excludes

- Review and validation (Phase 6)
- Finalisation and Excel export (Phase 7)
- Finalisation and Excel export (Phase 7)
- Authentication (Phase 8)
- XLSX or CSV parsing (Phase 9)
- AI grading (Phase 11)

---

## Initial Technology Choices

| Technology | Purpose |
|------------|---------|
| **Python 3.12** | Programming language |
| **Streamlit** | User interface |
| **SQLite** | Database |
| **SQLAlchemy** | ORM and database management |
| **pandas** | Data processing (future) |
| **BeautifulSoup** | HTML parsing (Phase 3) |
| **openpyxl** | Excel export (future) |
| **cryptography** | Secure random IDs and encryption (future) |
| **python-dotenv** | Environment configuration |
| **pytest** | Testing |

> *Dependencies for later phases will be installed when those phases begin.*

---

## Privacy Principle

This system uses **pseudonymisation**, not anonymisation. Student identities are replaced with random anonymous IDs during grading (`STU-XXXXXXXX`). Real identities are stored encrypted at rest using AES-256-GCM with a versioned ciphertext envelope. Identity matching uses HMAC-SHA256 fingerprints with a separate, dedicated key. Identities are restored **only** when the lecturer explicitly generates an authorised Excel export. The grading interface never displays student names or email addresses.

Key privacy guarantees:
- All PII (first name, last name, email, institutional student ID) is encrypted at rest
- No plaintext identity data appears in raw database text columns (verified by automated plaintext audit)
- Logs never contain names, emails, IDs, ciphertext, fingerprints, or keys
- Anonymous codes are cryptographically random — not derived from UUIDs, names, emails, IDs, fingerprints, or import order
- Names alone never trigger automatic identity matching
- Encryption and fingerprint keys are enforced to be different
- Without keys, the application enters preview-only mode with a clear message

---

## Planned Workflow

1. Create or select an academic material (course)
2. Create or select an assessment (exam, quiz)
3. Define questions and maximum marks
4. Upload the LMS response file (HTML) — *Phase 3 — implemented*
5. System detects columns and pseudonymises students — *Phase 4 — implemented*
6. Grade responses anonymously — *Phase 5 — implemented*
7. Review and validate — *Phase 6*
8. Finalise grades — *Phase 7*
9. Export authorised Excel report with identities restored — *Phase 7*

---

## Windows 11 Development Environment

### Prerequisites

- **Windows 11**
- **Python 3.12** (download from [python.org](https://www.python.org/downloads/))
- **PowerShell** (built-in)

### Setup Instructions

Open PowerShell and run the following commands:

```powershell
# 1. Navigate to the project directory
cd AcademicAnonymousGrader

# 2. Create a Python 3.12 virtual environment
py -3.12 -m venv .venv

# 3. Activate the virtual environment
# If execution policy blocks scripts, run this first:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 6. Create local .env from example
Copy-Item .env.example .env
```

### Running Tests

```powershell
pytest
```

### Running Linters

```powershell
ruff check .
mypy .
```

### Launching the Application

```powershell
streamlit run app.py
```

The application opens in your default web browser at `http://localhost:8501`.

---

## Database

- **Location:** `data/academic_grader.db` (created automatically on first run)
- **Technology:** SQLite
- **ORM:** SQLAlchemy 2.x
- The database is created and tables are initialised automatically when the application starts.
- Phase 2 added database-level constraints and indexes, including CHECK constraints for positive grades.
- **Note:** If you have an existing Phase 1 database with schema changes, delete `data/academic_grader.db` and restart to recreate it.

### Development-Only Schema Recreation

Phase 2 added `CHECK` constraints that SQLAlchemy's `create_all` cannot retrofit into existing SQLite tables. If you encounter constraint errors after upgrading, recreate the local development database:

```powershell
# 1. Stop Streamlit (Ctrl+C in the terminal where it is running)

# 2. Back up the existing database if uncertain
Copy-Item ".\data\academic_grader.db" ".\backups\academic_grader-pre-phase2.db"

# 3. Confirm the database contains no real or valuable records
#    (Phase 2 has not imported any real student data)

# 4. Delete the old database
Remove-Item ".\data\academic_grader.db"
Remove-Item ".\data\academic_grader.db-wal"
Remove-Item ".\data\academic_grader.db-shm"

# 5. Restart the application — tables are recreated automatically
streamlit run app.py
```

**Important:** The application must never delete the database automatically. This is a manual development-only procedure.

---

## Privacy Warning

⚠️ **This is a foundation build.** Do not use with real student data. No identity encryption, anonymous ID generation, or privacy-separated queries have been implemented yet. Real student response files must not be imported until Phase 3+.

---

## Documentation

All design documentation is located in the [`docs/`](docs/) directory:

| Document | Description |
|----------|-------------|
| [Project Specification](docs/PROJECT_SPECIFICATION.md) | Problem statement, objectives, scope, requirements, technology stack |
| [Workflow](docs/WORKFLOW.md) | Complete lecturer workflow, step by step |
| [Data Model](docs/DATA_MODEL.md) | Entities, relationships, and design decisions |
| [Privacy and Security](docs/PRIVACY_AND_SECURITY.md) | Privacy model, threat model, mitigations |
| [Import File Specification](docs/IMPORT_FILE_SPECIFICATION.md) | HTML format specification, column normalisation |
| [Validation Rules](docs/VALIDATION_RULES.md) | All validation rules with IDs, severity, and blocking status |
| [UI Requirements](docs/UI_REQUIREMENTS.md) | Streamlit page layouts, inputs, actions, privacy restrictions |
| [Acceptance Criteria](docs/ACCEPTANCE_CRITERIA.md) | Measurable criteria for each phase |
| [Phase Roadmap](docs/PHASE_ROADMAP.md) | Complete 12-phase development roadmap |

---

## Project Structure

```
AcademicAnonymousGrader/
├── app.py                     # Main entry point
├── pages/                     # Streamlit page files
│   ├── 1_Materials.py         # Material management (Phase 2)
│   ├── 2_Assessments.py       # Assessment and question management (Phase 2)
│   ├── 3_Import.py            # Placeholder
│   ├── 4_Grading.py           # Placeholder
│   ├── 5_Review.py            # Placeholder
│   ├── 6_Export.py            # Placeholder
│   └── 7_Settings.py          # Settings display
├── config/                    # Application configuration
├── database/                  # Database engine, session, initialisation
├── models/                    # SQLAlchemy ORM models (11 entities)
├── services/                  # Business logic services
│   ├── exceptions.py          # Domain exceptions
│   ├── validation.py          # Reusable validators
│   ├── material_service.py    # Material CRUD
│   ├── assessment_service.py  # Assessment CRUD
│   ├── question_service.py    # Question CRUD
│   ├── dashboard_service.py   # Dashboard statistics
│   └── logging_service.py     # Privacy-safe logging
├── ui/                        # UI layout helpers and components
├── data/                      # SQLite database (gitignored)
├── logs/                      # Application logs (gitignored)
├── exports/                   # Generated exports (gitignored)
├── uploads/                   # Temporary uploads (gitignored)
├── backups/                   # Database backups (gitignored)
├── tests/                     # pytest test suite (117 tests)
├── .env.example               # Environment configuration template
├── .gitignore
├── pyproject.toml             # Project metadata and tool configuration
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Development dependencies
├── pytest.ini                 # pytest configuration
└── README.md
```

---

## Next Phase

**Phase 3 — HTML Parser:** Implement HTML response file parsing with dynamic column detection and import preview.

- Identity encryption
- Anonymous ID generation
- Manual grading workflows
- Grade validation
- Excel export
- Authentication
- Full audit event implementation
- AI grading
- Docker or public deployment

---

## Windows 11 Development Environment

### Prerequisites

- **Windows 11**
- **Python 3.12** (download from [python.org](https://www.python.org/downloads/))
- **PowerShell** (built-in)

### Setup Instructions

Open PowerShell and run the following commands:

```powershell
# 1. Navigate to the project directory
cd AcademicAnonymousGrader

# 2. Create a Python 3.12 virtual environment
py -3.12 -m venv .venv

# 3. Activate the virtual environment
# If execution policy blocks scripts, run this first:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 6. Create local .env from example
Copy-Item .env.example .env
```

### Running Tests

```powershell
pytest
```

### Running Linters

```powershell
ruff check .
mypy .
```

### Launching the Application

```powershell
streamlit run app.py
```

The application opens in your default web browser at `http://localhost:8501`.

---

## Database

- **Location:** `data/academic_grader.db` (created automatically on first run)
- **Technology:** SQLite
- **ORM:** SQLAlchemy 2.x
- The database is created and tables are initialised automatically when the application starts.
- The database file contains the application schema but no real student data in Phase 1.

---

## Privacy Warning

⚠️ **This is a foundation build.** Do not use with real student data. The application is not yet ready for production use. No identity encryption, anonymous ID generation, or privacy-separated queries have been implemented yet.

---

## Documentation

All design documentation is located in the [`docs/`](docs/) directory:

| Document | Description |
|----------|-------------|
| [Project Specification](docs/PROJECT_SPECIFICATION.md) | Problem statement, objectives, scope, requirements, technology stack |
| [Workflow](docs/WORKFLOW.md) | Complete lecturer workflow, step by step |
| [Data Model](docs/DATA_MODEL.md) | Entities, relationships, and design decisions |
| [Privacy and Security](docs/PRIVACY_AND_SECURITY.md) | Privacy model, threat model, mitigations |
| [Import File Specification](docs/IMPORT_FILE_SPECIFICATION.md) | HTML format specification, column normalisation |
| [Validation Rules](docs/VALIDATION_RULES.md) | All validation rules with IDs, severity, and blocking status |
| [UI Requirements](docs/UI_REQUIREMENTS.md) | Streamlit page layouts, inputs, actions, privacy restrictions |
| [Acceptance Criteria](docs/ACCEPTANCE_CRITERIA.md) | Measurable criteria for each phase |
| [Phase Roadmap](docs/PHASE_ROADMAP.md) | Complete 12-phase development roadmap |

---

## Project Structure

```
AcademicAnonymousGrader/
├── app.py                     # Main entry point
├── pages/                     # Streamlit page files
├── config/                    # Application configuration
├── database/                  # Database engine, session, initialisation
├── models/                    # SQLAlchemy ORM models
├── services/                  # Business logic services
├── ui/                        # UI layout helpers and components
├── data/                      # SQLite database (gitignored)
├── logs/                      # Application logs (gitignored)
├── exports/                   # Generated exports (gitignored)
├── uploads/                   # Temporary uploads (gitignored)
├── backups/                   # Database backups (gitignored)
├── tests/                     # pytest test suite
├── .env.example               # Environment configuration template
├── .gitignore
├── pyproject.toml             # Project metadata and tool configuration
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Development dependencies
├── pytest.ini                 # pytest configuration
└── README.md
```

---

## Next Phase

**Phase 2 — Materials and Assessments:** Implement CRUD operations for academic materials and assessments with question configuration.
