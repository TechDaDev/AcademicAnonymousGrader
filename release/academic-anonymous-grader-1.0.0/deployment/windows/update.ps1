<#
.SYNOPSIS
    Update Academic Anonymous Grader to a new version.
.PARAMETER Version
    Target version tag (e.g., "1.0.1"). Default: read from VERSION file.
.PARAMETER Image
    Optional image name. Default: academic-anonymous-grader.
#>
param(
    [string]$Version = "",
    [string]$Image = "academic-anonymous-grader"
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"
$ProjectName = "academicanonymousgrader"
$versionFile = Join-Path $RepoRoot "VERSION"

if (-not $Version -and (Test-Path $versionFile)) {
    $Version = (Get-Content $versionFile -Raw).Trim()
}
if (-not $Version) { Write-Host "ERROR: No version specified." -ForegroundColor Red; exit 1 }

$currentImage = "$($Image):$Version"
$oldTag = "$($Image):previous"

Write-Host ">>> Updating to $currentImage ..." -ForegroundColor Cyan

# 1. Preflight
Push-Location $RepoRoot
try { & python -m deployment.checks.preflight 2>&1; Write-Host "  Preflight OK" -ForegroundColor Green }
catch { Write-Host "  WARNING Preflight: $_" -ForegroundColor Yellow }
finally { Pop-Location }

# 2. Backup
Write-Host ">>> Creating pre-update backup..." -ForegroundColor Cyan
& "$PSScriptRoot\backup.ps1" -SkipAppBackup

# 3. Build or pull target image
Write-Host ">>> Building $currentImage ..." -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    & docker build -t $currentImage . 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Build failed" -ForegroundColor Red; exit 1 }
} finally { Pop-Location }

# 4. Tag previous image for rollback
& docker tag "$($Image):latest" $oldTag 2>$null
& docker tag $currentImage "$($Image):latest"

# 5. Stop and restart
Write-Host ">>> Restarting with new image..." -ForegroundColor Cyan
& docker compose -f $ComposeFile -p $ProjectName up -d 2>&1

# 6. Wait for health
Start-Sleep -Seconds 15
$health = & docker compose -f $ComposeFile -p $ProjectName exec -T app python -m scripts.health_check 2>&1
if ($health -match "healthy") {
    Write-Host "  Health: PASS" -ForegroundColor Green
} else {
    Write-Host "  Health: FAIL — rolling back..." -ForegroundColor Red
    & docker tag $oldTag "$($Image):latest"
    & docker compose -f $ComposeFile -p $ProjectName up -d 2>&1
    exit 1
}

# 7. Post-install
Push-Location $RepoRoot
try { & python -m deployment.checks.post_install 2>&1; Write-Host "  Post-install OK" -ForegroundColor Green }
catch { Write-Host "  WARNING Post-install: $_" -ForegroundColor Yellow }
finally { Pop-Location }

Write-Host "Update to $Version complete." -ForegroundColor Green
Write-Host "Previous image retained as $oldTag for rollback."
