<#
.SYNOPSIS
    Controlled uninstall of Academic Anonymous Grader.
.DESCRIPTION
    Default: removes containers only. Preserves volumes and .env.
    Use -RemoveData to destroy persistent data (requires confirmation).
#>
param(
    [switch]$RemoveImages,
    [switch]$RemoveData
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"
$ProjectName = "academicanonymousgrader"

Write-Host "=== Uninstall Academic Anonymous Grader ===" -ForegroundColor Cyan

# Stop and remove containers
Write-Host ">>> Removing containers..." -ForegroundColor Cyan
& docker compose -f $ComposeFile -p $ProjectName down 2>&1
Write-Host "  Containers removed. Volumes preserved." -ForegroundColor Green

# Remove images
if ($RemoveImages) {
    Write-Host ">>> Removing Docker images..." -ForegroundColor Cyan
    & docker rmi "academic-anonymous-grader:latest" 2>$null
    & docker rmi "academic-anonymous-grader:previous" 2>$null
    Write-Host "  Images removed." -ForegroundColor Green
}

# Remove data (DESTRUCTIVE)
if ($RemoveData) {
    Write-Host ">>> DESTRUCTIVE: Removing persistent volumes..." -ForegroundColor Red
    $confirm = Read-Host "Type DELETE DATA to confirm"
    if ($confirm -ne "DELETE DATA") { Write-Host "Cancelled. Volumes preserved."; exit 1 }
    & docker volume rm grader_data grader_backups grader_exports grader_logs 2>&1
    Write-Host "  Volumes removed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Uninstall complete." -ForegroundColor Green
if (-not $RemoveData) {
    Write-Host "Data volumes preserved. Reinstall to resume." -ForegroundColor Cyan
}
