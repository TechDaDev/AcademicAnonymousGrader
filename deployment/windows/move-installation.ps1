<#
.SYNOPSIS
    Prepare an existing installation for migration to another laptop.
.DESCRIPTION
    Creates two secure transfer packages:

    Package A — Data: database backup, manifest, checksums
    Package B — Secrets: .env (transferred separately, securely)

    On the target laptop:
      1. Install Docker and matching release.
      2. Restore .env (Package B) to the repository root.
      3. Run deployment\windows\restore.ps1 with the backup reference.
      4. Run health check.
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"
$ProjectName = "academicanonymousgrader"

Write-Host "=== Prepare Installation for Migration ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Database and original encryption keys must remain paired." -ForegroundColor Yellow
Write-Host "  Package A (data) and Package B (keys) must be transferred separately and securely."
Write-Host ""

# 1. Create backup
Write-Host ">>> Step 1: Creating database backup..." -ForegroundColor Cyan
$backupResult = & docker compose -f $ComposeFile -p $ProjectName exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory;
from services.backup_service import create_backup;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
result = create_backup(session); session.close();
print(f'REF={result.backup_reference} SIZE={result.file_size}')
" 2>$null
if (-not $backupResult) {
    Write-Host "FAIL: Could not create backup." -ForegroundColor Red; exit 1
}
Write-Host "  $backupResult" -ForegroundColor Green

# 2. Record version info
Write-Host ">>> Step 2: Recording version information..." -ForegroundColor Cyan
$version = "1.0.0-rc1"
$versionFile = Join-Path $RepoRoot "VERSION"
if (Test-Path $versionFile) { $version = (Get-Content $versionFile -Raw).Trim() }

$schemaVer = & docker compose -f $ComposeFile -p $ProjectName exec -T app python -c "
from database.migrations import SCHEMA_VERSION; print(SCHEMA_VERSION)" 2>$null

Write-Host "  Version: $version" -ForegroundColor Green
Write-Host "  Schema: v$schemaVer" -ForegroundColor Green

# 3. Display instructions
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Migration Package Ready" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Package A (Data):"
Write-Host "  Backup reference: $backupResult"
Write-Host "  Version: $version"
Write-Host "  Schema: v$schemaVer"
Write-Host ""
Write-Host "Package B (Secrets — transfer separately):"
Write-Host "  Copy: $RepoRoot\.env"
Write-Host "  To:   <target>\<repo>\.env"
Write-Host ""
Write-Host "Target laptop steps:"
Write-Host "  1. Install Docker Desktop."
Write-Host "  2. Copy release package (matching version $version)."
Write-Host "  3. Copy .env to repository root."
Write-Host "  4. Run: docker compose -f docker-compose.production.yml up -d"
Write-Host "  5. Run: deployment\windows\restore.ps1 -BackupReference <ref>"
Write-Host "  6. Run: python -m scripts.health_check"
Write-Host ""
Write-Host "WARNING: Never install fresh and restore an existing backup" -ForegroundColor Yellow
Write-Host "  with different keys. Identity decryption will fail." -ForegroundColor Yellow
