# Rollback Guide

## Important

Application rollback does not automatically mean database schema rollback.
Migrations are forward-only. If the new schema is incompatible with the old
application image, a backup-based restore is required.

## Image-Only Rollback

If the schema has **not** changed, you can roll back the application image:

```bash
# Restore the previous image tag
docker tag academic-anonymous-grader:previous academic-anonymous-grader:latest

# Restart
docker compose -f docker-compose.production.yml up -d

# Verify
docker compose -f docker-compose.production.yml exec app python -m scripts.health_check
```

## Backup-Based Rollback

If the schema **has** changed, you must restore the pre-upgrade backup:

```powershell
# Windows
.\deployment\windows\restore.ps1 -BackupReference BKP-XXXXXXXX
```

```bash
# Linux / macOS
# Use the application restore service:
docker compose exec app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory;
from services.backup_service import restore_backup;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
result = restore_backup(session, 'BKP-XXXXXXXX');
session.commit(); print(f'Restored: {result.backup_reference}')
"
```

Then run the **previous** image version.

## Rollback Safety

| Scenario | Safe? | Method |
|----------|-------|--------|
| Same schema version | Yes | Image-only rollback |
| New schema, old image incompatible | Conditionally | Backup-based restore + old image |
| Schema downgrade | No | Not supported — forward-only |

## Pre-Rollback Steps

1. Verify the pre-upgrade backup exists and is intact
2. Note the old and new schema versions
3. Confirm the old image is still available (`docker images | findstr previous`)
4. Stop the application before restoring
