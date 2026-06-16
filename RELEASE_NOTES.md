# Academic Anonymous Grader — Release Notes

## Version 1.0.0 (Production Release)

**Release Date:** 2026-06-16
**Release Status:** Production
**Schema Version:** 3

Application Purpose: Academic Anonymous Grader is a privacy-preserving anonymous grading system designed for academic institutions. Student identities are encrypted at rest, instructors grade using anonymous codes, and administrators maintain full system control.

### Supported Platforms
- Windows 10+ (via Docker Desktop)
- Linux (via Docker Engine)
- macOS (via Docker Desktop)

### Major Completed Capabilities
- Secure import with identity encryption (AES-256-GCM)
- Anonymous grading workflow
- Review and finalization
- Identity-bearing and de-identified export
- Aggregate analytics with privacy thresholds
- Academic structure management
- Audit logging
- Backup, restore, update, and rollback
- Offline installation
- Diagnostic bundle
- Role-based access control

### Privacy and Anonymity
- All identity fields encrypted at rest
- Grading uses HMAC-SHA256 anonymous codes
- Instructors never see student identities
- Analytics use aggregate data only
- Diagnostic bundles exclude all sensitive data

### Intentionally Excluded
- Phase 11 AI grading was not implemented
- Phase 14 institutional pilot was skipped by project-owner decision
- Phase 16 integrations are outside the closed project scope

### Upgrade Path from 1.0.0-rc1
```powershell
.\deployment\windows\update.ps1 -Version 1.0.0
```

### Features

- Phases 1–9: Core grading, review, finalization
- Phase 10: Instructor assignments, grading claims, Docker deployment
- Phase 12: Analytics and reporting
- Phase 12.1: Academic structure (departments, stages, terms, years), controlled material classification
- Phase 13: Production deployment, multi-laptop installation, update, migration, and recovery

### Deployment

- Windows: `.\deployment\windows\install.ps1`
- Linux/macOS: `./deployment/linux/install.sh`
- Docker image: `academic-anonymous-grader:1.0.0-rc1`
- Schema version: 3

### Upgrade Notes

- Fresh installations: use `python -m scripts.setup_environment` or the installer
- Existing installations: preserve `.env` and named volumes
- See `docs/UPGRADE_GUIDE.md` for full upgrade instructions
- See `docs/MOVE_TO_ANOTHER_LAPTOP.md` for migration instructions

### Known Issues

- Schema migrations are forward-only (no downgrade)
- Docker Desktop requires at least 4 GB memory for builds
- Single-process only (Streamlit + SQLite)

### Release Package Contents

```
academic-anonymous-grader-1.0.0-rc1/
├── docker-compose.production.yml
├── .env.production.example
├── deployment/          # Install/update/backup/restore scripts
├── docs/                # Full documentation
├── VERSION
├── RELEASE_NOTES.md
├── CHECKSUMS.txt
└── release-manifest.json
```

### Checksums

See `CHECKSUMS.txt` in the release package.
