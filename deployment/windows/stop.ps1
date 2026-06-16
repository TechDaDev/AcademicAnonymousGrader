<#
.SYNOPSIS
    Stop Academic Anonymous Grader (preserves volumes).
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"
Push-Location $RepoRoot
try {
    & docker compose -f $ComposeFile stop 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Host "Application stopped. Volumes preserved." -ForegroundColor Green }
    else { Write-Host "Failed to stop." -ForegroundColor Red; exit 1 }
} finally { Pop-Location }
