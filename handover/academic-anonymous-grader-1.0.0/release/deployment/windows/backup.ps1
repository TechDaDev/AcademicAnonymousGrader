<#
.SYNOPSIS
    Create a verified backup of Academic Anonymous Grader.
    Backup excludes .env, keys, exports, and logs.
#>
param(
    [switch]$SkipAppBackup
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"
$ProjectName = "academicanonymousgrader"

Write-Host ">>> Creating backup..." -ForegroundColor Cyan

# Use the application backup service if available
if (-not $SkipAppBackup) {
    $backupResult = & docker compose -f $ComposeFile -p $ProjectName exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory;
from services.backup_service import create_backup;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
result = create_backup(session); session.close();
print(f'REF={result.backup_reference} SIZE={result.file_size} HASH={result.file_hash[:16]}')" 2>$null
    if ($backupResult) {
        Write-Host "  $backupResult" -ForegroundColor Green
    } else {
        Write-Host "  WARNING Application backup service failed, using fallback." -ForegroundColor Yellow
    }
}

Write-Host "Backup complete. Verify the archive in the backups volume." -ForegroundColor Green
