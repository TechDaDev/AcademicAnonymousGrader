# Academic Anonymous Grader — Dependency Inventory

## Version and Status
- **Application Version:** 1.0.0
- **Schema Version:** 3
- **Last Updated:** 2026-06-16

## Direct Dependencies

Listed in `requirements.txt`. Versions shown are as resolved at build time.

| Package | Version | Source | License | Notes |
|---------|---------|--------|---------|-------|
| streamlit | 1.58.0 | PyPI | Apache-2.0 | Web application framework |
| SQLAlchemy | 2.0.51 | PyPI | MIT | ORM and database abstraction |
| python-dotenv | 1.2.2 | PyPI | BSD-3-Clause | Environment file loading |
| beautifulsoup4 | 4.15.0 | PyPI | MIT | HTML parsing |
| lxml | 5.4.0 | PyPI | BSD-3-Clause | XML/HTML parser |
| cryptography | 49.0.0 | PyPI | Apache-2.0 | AES-256-GCM encryption |
| bcrypt | 5.0.0 | PyPI | Apache-2.0 | Password hashing |
| openpyxl | 3.1.5 | PyPI | MIT | XLSX export |

## Transitive Dependencies (Key)
Important transitive dependencies resolved at build time:

| Package | Version | License |
|---------|---------|---------|
| pandas | 3.0.3 | BSD-3-Clause |
| numpy | 2.4.6 | BSD-3-Clause |
| altair | 6.2.1 | BSD-3-Clause |
| pillow | 12.2.0 | Historical |
| pyarrow | 24.0.0 | Apache-2.0 |

## Runtime Environment
- **Python:** 3.12 (Docker image `python:3.12-slim`)
- **Base OS:** Debian (slim variant)
- **Docker:** 24.0+ (recommended 29.x)
- **Docker Compose:** 2.20+ (recommended 5.x)

## Update Policy
- Dependency updates should be tested on an isolated copy before production deployment.
- Major-version updates require full regression testing.
- Security patches should be prioritized and tested promptly.
- See `docs/MAINTENANCE_PLAN.md` for the complete update procedure.

## SBOM Regeneration Command
```bash
# From the repository root, using the project's Python environment:
python -c "
import json, subprocess, sys, re
from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import distribution

result = subprocess.run([sys.executable, '-m', 'pip', 'list', '--format=json', '--not-required'], capture_output=True, text=True)
installed = json.loads(result.stdout)
packages = []
# ... (see SBOM.spdx.json for the full generation script)
"
```

The complete SBOM in SPDX 2.3 format is available at `SBOM.spdx.json`.
