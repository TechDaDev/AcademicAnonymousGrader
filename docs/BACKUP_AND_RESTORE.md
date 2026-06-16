# Backup and Restore Guide

## Backup

### Windows

```powershell
.\deployment\windows\backup.ps1
```

### Linux / macOS

```bash
./deployment/linux/backup.sh
```

### What the Backup Contains

- SQLite database dump
- Application version
- Schema version
- Manifest (JSON)
- Checksum (SHA-256)

### What the Backup Excludes

- `.env` and all secrets
- Encryption keys and passwords
- Application logs
- Exported workbooks
- Docker image layers

### Backup Verification

The backup script automatically verifies the archive after creation.

To manually verify:

```bash
docker compose exec app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory;
from services.backup_service import verify_backup;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
result = verify_backup(session, 'BKP-XXXXXXXX');
session.close(); print(f'Integrity: {result.file_hash[:16]}...')
"
```

## Restore

### Windows

```powershell
.\deployment\windows\restore.ps1 -BackupReference BKP-XXXXXXXX
```

### What Restore Does

1. Creates a pre-restore backup of current data
2. Stops the application
3. Verifies backup integrity
4. Verifies manifest and schema compatibility
5. Requires explicit confirmation (`RESTORE`)
6. Restores the database
7. Restarts the application
8. Runs health check

### Restore Safety Checks

| Condition | Action |
|-----------|--------|
| Corrupted archive | Rejected before any changes |
| Checksum mismatch | Rejected |
| Missing manifest | Rejected |
| Incompatible schema version | Rejected |
| Missing original `.env` | Warning displayed |

Restore never modifies `.env` or encryption keys.

## Scheduled Backups

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create a new task
3. Trigger: Daily at your preferred time
4. Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-File "C:\path\to\deployment\windows\backup.ps1"`

### Linux (cron)

```bash
crontab -e
# Add: 0 2 * * * /path/to/deployment/linux/backup.sh
```

### Linux (systemd timer)

See `deployment/linux/` for a timer template if needed.

## Backup Retention

Default retention policy:

| Type | Count |
|------|-------|
| Daily | Last 7 |
| Weekly | Last 4 |
| Monthly | Last 6 |

Or configure manually. The system never deletes the only valid backup.
