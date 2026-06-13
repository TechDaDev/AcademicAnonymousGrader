# Academic Anonymous Grader (AAG)

**Anonymously grade academic assessment responses, then export authorised results.**

A lightweight, locally run tool that imports assessment response files from a learning management system, pseudonymises student identities for unbiased grading, and produces a final authorised Excel report with identities restored.

---

## Current Status: Phase 1 — Project Foundation

Phase 1 establishes the working project structure, Python environment, database schema, and basic Streamlit application shell.

### What Phase 1 Implements

- Project directory structure
- Dependency configuration (`requirements.txt`, `pyproject.toml`)
- Environment-variable configuration (`.env.example`)
- SQLAlchemy 2.x database models for all 11 entities
- Automatic database initialisation (idempotent)
- Privacy-safe logging with redaction filters
- Streamlit application shell with sidebar navigation
- Dashboard with summary metrics
- 7 placeholder pages (Materials, Assessments, Import, Grading, Review, Export, Settings)
- Automated test suite (pytest)

### What Phase 1 Intentionally Excludes

- HTML parsing, XLSX/CSV parsing, file uploads
- Student identity matching logic
- HMAC fingerprint generation
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
