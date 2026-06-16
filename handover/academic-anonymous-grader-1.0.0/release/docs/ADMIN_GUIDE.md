# Administrator Guide

## Overview

This guide covers administrative tasks for the Academic Anonymous Grader, including instructor assignments, progress monitoring, finalization, and Docker management.

## Instructor Assignments

### Assignment Model

Each instructor (role: `grader`) can be assigned to one or more assessments. The assignment is **active-only unique**: only one active assignment per (instructor, assessment) pair. Historical (inactive) assignments are preserved indefinitely.

### Creating Assignments

1. Navigate to **Instructor Assignments** page (admin only).
2. Select the material (to filter assessments).
3. Select the assessment.
4. Select one or more instructors.
5. Click **Create Assignment(s)**.

### Deactivating Assignments

- Active assignments can be deactivated. This does not delete grades or history.
- To reactivate, create a new assignment record.
- Reassignment: deactivate the old assignment and create a new one in one step.

### Viewing Progress

The **Workload Summary** tab shows:
- Instructor name
- Active assignment count
- Total submissions
- Claimed, draft, completed counts
- Completion percentage

### Finalization Blockers

An assessment cannot be finalized when:
- Required submissions are ungraded
- Submissions remain in draft
- Corrections are unresolved
- Active grading claims exist
- Existing Phase 7 conditions fail (missing grades, question mismatch, etc.)

## First Administrator Creation

```bash
# Docker
docker compose run --rm app python -m scripts.create_admin

# Local development
python -m scripts.create_admin
```

## Backup and Restore

### Creating a Backup

Use the **Backup** page to create password-protected ZIP archives containing:
- Database file (encrypted at rest)
- Schema version metadata
- Application version

### Restoring a Backup

1. Go to **Backup** page.
2. Upload a backup file.
3. Enter the backup password.
4. Confirm the restore (a pre-restore backup is created automatically).

### Guardrails

- Backup contains NO `.env`, encryption keys, or fingerprint keys.
- Corrupted backups are rejected with a safe error.
- Restore requires administrator privileges.

## Docker Commands

```bash
# Build
docker compose build --no-cache

# Start
docker compose up -d

# Health check
docker compose exec app python -m scripts.health_check

# View logs
docker compose logs -f

# Stop
docker compose down

# Run admin tasks
docker compose run --rm app python -m scripts.health_check
docker compose run --rm app python -m scripts.create_admin
```
