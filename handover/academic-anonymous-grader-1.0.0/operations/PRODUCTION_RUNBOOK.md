# Academic Anonymous Grader — Production Operations Runbook

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Prerequisites
- Docker Desktop 24.0+ (Windows) or Docker Engine 24.0+ (Linux/macOS)
- Docker Compose 2.20+
- Python 3.12+ (for installer and check scripts only, not for runtime)
- PowerShell 5.1+ (Windows) or Bash (Linux/macOS)
- 2 GB free disk space minimum
- Port 8501 available

## 2. Daily Startup
```powershell
# Windows
cd \path\to\academic-anonymous-grader-1.0.0
.\deployment\windows\start.ps1
```

```bash
# Linux/macOS
cd /path/to/academic-anonymous-grader-1.0.0
./deployment/linux/start.sh
```

## 3. Daily Shutdown
```powershell
# Windows
.\deployment\windows\stop.ps1
```

```bash
# Linux/macOS
./deployment/linux/stop.sh
```

## 4. Status Check
```powershell
.\deployment\windows\status.ps1
```

Reports: version (1.0.0), schema version, container health, port status, volume list, backup recency. No secrets or academic data exposed.

## 5. Health Check
```powershell
docker compose -f docker-compose.production.yml exec -T app python -m scripts.health_check
```

Expected output: `healthy`

## 6. Create First Administrator
```powershell
docker compose -f docker-compose.production.yml exec -it app python -m scripts.create_admin
```

Follow the interactive prompts. Password is not echoed.

## 7. Create Instructor (Grader)
```powershell
docker compose -f docker-compose.production.yml exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.init_db import initialize_database;
from database.session import create_session_factory, session_scope;
from services.auth_service import create_user;
s=get_settings(); e=get_engine(s.resolved_database_url());
initialize_database(e); f=create_session_factory(e);
with session_scope(f) as ss:
    u = create_user(ss, 'username', 'StrongPass1!', 'grader', 'Display Name');
    print('Created:', u.username)
"
```

## 8. Create Academic Year
```powershell
docker compose -f docker-compose.production.yml exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory, session_scope;
from models.academic_year import AcademicYear;
s=get_settings(); e=get_engine(s.resolved_database_url()); f=create_session_factory(e);
with session_scope(f) as ss:
    ay = AcademicYear(name='2025/2026', display_order=1);
    ss.add(ay); print('Created:', ay.name)
"
```

## 9. Create Material
Use the Materials page in the application (Administrator login required).

## 10. Create Assessment
Use the Assessments page in the application (Administrator login required).

## 11. Import Submissions
1. Prepare an import file (CSV, XLSX, or HTML) according to the Import File Specification.
2. Navigate to the Import page.
3. Upload the file.
4. Map columns.
5. Review identity matches.
6. Execute the import.
7. Verify import results.

## 12. Assign Instructor to Assessment
Use the Instructor Assignments page in the application (Administrator login required).

## 13. Grade
Instructors navigate to their assigned assessments and grade using the anonymous codes.

## 14. Review and Finalize
Administrators or Reviewers navigate to Review, verify completeness, and finalize assessments.

## 15. Export
1. Navigate to the Export page.
2. Select assessment.
3. Choose export type (anonymous or identity-bearing).
4. Download the XLSX file.

## 16. Create Backup
```powershell
.\deployment\windows\backup.ps1
```

## 17. Verify Backup
```powershell
docker compose -f docker-compose.production.yml exec -T app python -c "
from pathlib import Path; import zipfile, json;
for b in sorted(Path('/app/backups').glob('*.zip')):
    m = json.loads(zipfile.ZipFile(b).read('manifest.json'));
    print(f'{b.name}: ref={m[\"backup_reference\"]} version={m[\"app_version\"]} schema={m[\"schema_version\"]} tables={m[\"table_count\"]}')
"
```

## 18. Restore
```powershell
.\deployment\windows\restore.ps1 -BackupReference BAK-XXXXXXXX [-Force]
```

Requires typing "RESTORE" to confirm. A pre-restore backup is created automatically.

## 19. Update
```powershell
.\deployment\windows\update.ps1 -Version 1.0.1
```

## 20. Rollback
```powershell
# After a failed update:
docker compose -f docker-compose.production.yml down
docker tag academic-anonymous-grader:previous academic-anonymous-grader:latest
docker compose -f docker-compose.production.yml up -d
```

If the previous image was not tagged, restore from the pre-upgrade backup.

## 21. Move to Another Laptop
See `docs/MOVE_TO_ANOTHER_LAPTOP.md` for the complete two-package transfer procedure.

## 22. Offline Installation
See `docs/OFFLINE_INSTALLATION.md` for the complete procedure using a pre-saved Docker image archive.

## 23. Uninstall
```powershell
.\deployment\windows\uninstall.ps1
```

This removes containers but preserves volumes and `.env`. For destructive removal, use:
```powershell
.\deployment\windows\uninstall.ps1 -DestroyData
```

Destructive removal requires typing the exact confirmation phrase documented in the script.

## 24. Emergency Shutdown
```powershell
docker compose -f docker-compose.production.yml down
```

If the application is unresponsive:
```powershell
docker compose -f docker-compose.production.yml stop --timeout 30
```
