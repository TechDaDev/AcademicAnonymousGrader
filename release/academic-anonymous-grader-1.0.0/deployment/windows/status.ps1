<#
.SYNOPSIS
    Check status of Academic Anonymous Grader.
    Reports safe status only — no secrets or academic data.
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"

Write-Host "=== Academic Anonymous Grader — Status ===" -ForegroundColor Cyan

# Container status
$ps = & docker compose -f $ComposeFile ps --format "{{.Name}} {{.Status}}" 2>$null
if ($ps) {
    Write-Host "Container: $ps" -ForegroundColor Green
} else {
    Write-Host "Container: NOT RUNNING" -ForegroundColor Yellow
}

# Health check
$health = & docker compose -f $ComposeFile exec -T app python -m scripts.health_check 2>&1 | Select-String "healthy"
if ($health) { Write-Host "Health:     PASS" -ForegroundColor Green }
else { Write-Host "Health:     UNKNOWN" -ForegroundColor Yellow }

# Version
$versionFile = Join-Path $RepoRoot "VERSION"
if (Test-Path $versionFile) {
    $ver = (Get-Content $versionFile -Raw).Trim()
    Write-Host "Version:    $ver"
}

# Schema version
$schema = & docker compose -f $ComposeFile exec -T app python -c "
from database.migrations import SCHEMA_VERSION; print(SCHEMA_VERSION)" 2>$null
if ($schema) { Write-Host "Schema:     v$schema" }

# Port check
$portCheck = Test-NetConnection -ComputerName 127.0.0.1 -Port 8501 -WarningAction SilentlyContinue 2>$null
if ($portCheck.TcpTestSucceeded) { Write-Host "Port 8501:  OPEN" -ForegroundColor Green }
else { Write-Host "Port 8501:  CLOSED" -ForegroundColor Yellow }

# Volumes
$vols = & docker volume ls --filter name=grader --format "{{.Name}}" 2>$null
if ($vols) { Write-Host "Volumes:    $($vols -join ', ')" }

Write-Host "================================" -ForegroundColor Cyan
