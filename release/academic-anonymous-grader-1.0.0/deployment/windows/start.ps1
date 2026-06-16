<#
.SYNOPSIS
    Start Academic Anonymous Grader.
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"
Push-Location $RepoRoot
try {
    & docker compose -f $ComposeFile up -d 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Host "Application started." -ForegroundColor Green }
    else { Write-Host "Failed to start." -ForegroundColor Red; exit 1 }
} finally { Pop-Location }
