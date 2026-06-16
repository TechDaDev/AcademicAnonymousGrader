# Academic Anonymous Grader — Institutional Handover Guide

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Ready for Sign-Off
- **Last Updated:** 2026-06-16

## 1. What Is Being Delivered
Academic Anonymous Grader version 1.0.0 — a Docker-based web application for privacy-preserving anonymous grading.

## 2. Delivery Components

| Component | Description | Location |
|-----------|-------------|----------|
| Release package | `academic-anonymous-grader-1.0.0/` | Handover archive |
| Production Docker image | `academic-anonymous-grader:1.0.0` | Docker registry/image archive |
| Source repository | Full source code | Git repository |
| Documentation | 25+ documents | `docs/` directory |
| Governance policies | 6 policy documents | `docs/` (see Governance section) |
| Installation scripts | Windows `.ps1`, Linux `.sh` | `deployment/` directory |

## 3. Production Version
- **Application Version:** 1.0.0
- **Schema Version:** 3
- **Release Channel:** Production
- **Docker Image:** `academic-anonymous-grader:1.0.0`
- **Base Image:** `python:3.12-slim`

## 4. Deployment Architecture
- Single container running Streamlit application.
- SQLite database persisted in a named Docker volume.
- Four named volumes: `grader_data`, `grader_backups`, `grader_exports`, `grader_logs`.
- Internal port 8501, mapped to host port 8501 (configurable).
- Non-root runtime user (`grader`).

## 5. Hardware/Software Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Operating System | Windows 10+, Linux, macOS | Windows 11 / Ubuntu 24.04 / macOS 14+ |
| RAM | 2 GB | 4 GB |
| Disk Space | 2 GB free | 10 GB free |
| Docker | 24.0 | 29.x |
| Docker Compose | 2.20 | 5.x |

## 6. Release Package Contents
```
academic-anonymous-grader-1.0.0/
├── docker-compose.production.yml
├── Dockerfile
├── .dockerignore
├── .env.example
├── VERSION
├── pyproject.toml
├── requirements.txt
├── docker/
│   └── entrypoint.sh
├── deployment/
│   ├── windows/   (9 scripts)
│   └── linux/     (8 scripts)
├── scripts/       (7 scripts)
├── config/
├── database/
├── models/        (15 models)
├── services/      (26 services)
├── security/      (5 modules)
├── analytics/     (11 modules)
├── pages/         (13 pages)
├── parsers/       (9 parsers)
├── ui/            (3 UI modules)
├── docs/          (25+ documents)
├── CHECKSUMS.txt
├── release-manifest.json
└── RELEASE_NOTES.md
```

## 7. Configuration Ownership
- **`.env` file:** Key Custodian (see Key-Custody Policy).
- `docker-compose.production.yml`: Technical Administrator.
- `VERSION`: Release Approver.
- Port mapping: Technical Administrator.

## 8. Key Ownership
See `docs/KEY_CUSTODY_POLICY.md` for complete key-custody procedures.

## 9. Backup Ownership
See `docs/BACKUP_RECOVERY_POLICY.md` for backup and recovery responsibilities.

## 10. User-Management Ownership
See `docs/ACCESS_CONTROL_POLICY.md` for user and role management.

## 11. Data Ownership
See `docs/DATA_GOVERNANCE_POLICY.md` for data-category ownership.

## 12. Maintenance Ownership
See `docs/MAINTENANCE_PLAN.md` for maintenance schedule and responsibilities.

## 13. Known Limitations
See `docs/KNOWN_LIMITATIONS.md` for the complete list.

## 14. Acceptance Checklist

| Item | Status | Reviewer | Date | Signature |
|------|--------|----------|------|-----------|
| Functional acceptance | □ | | | |
| Privacy acceptance | □ | | | |
| Security acceptance | □ | | | |
| Deployment acceptance | □ | | | |
| Backup acceptance | □ | | | |
| Restore acceptance | □ | | | |
| Update acceptance | □ | | | |
| Documentation acceptance | □ | | | |
| Training acceptance | □ | | | |
| Governance acceptance | □ | | | |
| Release-package acceptance | □ | | | |
| Project-closure acceptance | □ | | | |

## 15. Training Checklist
See `docs/ADMINISTRATOR_TRAINING_CHECKLIST.md` and `docs/INSTRUCTOR_TRAINING_CHECKLIST.md`.

## 16. Handover Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Delivering person (Institution) | | | |
| Receiving person (Institution) | | | |
| Technical Administrator | | | |
| Data Protection Officer | | | |

---
**Institution:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Date:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
