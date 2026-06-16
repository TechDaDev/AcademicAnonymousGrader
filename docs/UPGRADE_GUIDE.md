# Upgrade Guide

## Overview

Upgrading Academic Anonymous Grader involves:
1. Creating a verified backup
2. Building or pulling the new Docker image
3. Applying database migrations
4. Verifying health and data preservation

Upgrades are forward-only. Database schema is migrated incrementally and cannot be automatically downgraded.

## Windows

```powershell
.\deployment\windows\update.ps1 -Version 1.0.1
```

## Linux / macOS

```bash
./deployment/linux/update.sh 1.0.1
```

## Manual Upgrade

### Step 1: Backup

```powershell
# Windows
.\deployment\windows\backup.ps1

# Linux
./deployment/linux/backup.sh
```

### Step 2: Build the New Image

```bash
docker build -t academic-anonymous-grader:1.0.1 .
docker tag academic-anonymous-grader:latest academic-anonymous-grader:previous
docker tag academic-anonymous-grader:1.0.1 academic-anonymous-grader:latest
```

### Step 3: Restart

```bash
docker compose -f docker-compose.production.yml up -d
```

### Step 4: Verify

```bash
docker compose -f docker-compose.production.yml exec app python -m scripts.health_check
docker compose -f docker-compose.production.yml exec app python -m deployment.checks.post_install
```

## What to Expect

- **Version**: Updated in `VERSION` file and image tag
- **Schema**: Migrated forward automatically on first startup
- **Data**: Preserved in persistent volumes
- **Seeds**: Idempotent — existing reference data not duplicated
- **Keys**: Unchanged — `.env` is never modified

## Version Compatibility

| From | To | Migration |
|------|----|-----------|
| 1.0.0-rc1 | 1.0.0 | Schema v3 → v3 (no change) |
| 1.0.0 | 1.0.1 | Forward migration if schema changes |

Check `release-manifest.json` for `migration_required` field.
