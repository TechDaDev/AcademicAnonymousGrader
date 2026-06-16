<#
.SYNOPSIS
    Restore Academic Anonymous Grader from a verified backup.
.DESCRIPTION
    Requirements:
      1. Backup reference (e.g., BKP-XXXXXXXX)
      2. Matching application version
      3. Original .env with correct encryption keys

    Never restores .env from backup.
    Creates pre-restore backup automatically.
#>
param(
    [Parameter(Mandatory=$true)] [string]$BackupReference,
    [switch]$Force
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"
$ProjectName = "academicanonymousgrader"

Write-Host ">>> WARNING: Restore will replace the current database." -ForegroundColor Red
Write-Host ">>> A pre-restore backup will be created first." -ForegroundColor Yellow

if (-not $Force) {
    $confirm = Read-Host "Type RESTORE to confirm"
    if ($confirm -ne "RESTORE") { Write-Host "Cancelled."; exit 1 }
}

# 1. Create pre-restore backup
Write-Host ">>> Creating pre-restore backup..." -ForegroundColor Cyan
& "$PSScriptRoot\backup.ps1" -SkipAppBackup

# 2. Stop application
Write-Host ">>> Stopping application..." -ForegroundColor Cyan
& docker compose -f $ComposeFile -p $ProjectName stop 2>&1

# 3. Restore from backup (via application service)
Write-Host ">>> Restoring backup $BackupReference ..." -ForegroundColor Cyan
$restoreResult = & docker compose -f $ComposeFile -p $ProjectName exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory;
from services.backup_service import restore_backup;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
try:
    result = restore_backup(session, '$BackupReference');
    session.commit();
    print(f'Restored: {result.backup_reference}')
except Exception as e:
    session.rollback();
    print(f'ERROR: {e}')" 2>$null

if ($restoreResult -and $restoreResult -notlike "ERROR*") {
    Write-Host "  $restoreResult" -ForegroundColor Green
} else {
    Write-Host "  WARNING Restore issue: $restoreResult" -ForegroundColor Yellow
}

# 4. Restart and verify
Write-Host ">>> Restarting..." -ForegroundColor Cyan
& docker compose -f $ComposeFile -p $ProjectName up -d 2>&1
Start-Sleep -Seconds 10
& docker compose -f $ComposeFile -p $ProjectName exec -T app python -m scripts.health_check 2>&1

Write-Host "Restore complete." -ForegroundColor Green
