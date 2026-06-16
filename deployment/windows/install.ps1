<#
.SYNOPSIS
    Install Academic Anonymous Grader on Windows.
.DESCRIPTION
    Fresh installation workflow:
      1. Verify Docker Desktop
      2. Run preflight checks
      3. Create or validate .env
      4. Build versioned Docker image
      5. Create named volumes
      6. Start application
      7. Wait for healthy status
      8. Create first Administrator (if needed)
      9. Run post-install validation
     10. Display http://localhost:8501

    Requires: Docker Desktop, PowerShell 5.1+
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ComposeFile = Join-Path $RepoRoot "docker-compose.production.yml"
$ProjectName = "academicanonymousgrader"

# --- Helpers ---
function Write-Step($msg) { Write-Host ">>> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  FAIL $msg" -ForegroundColor Red; exit 1 }

# --- 1. Verify Docker Desktop ---
Write-Step "Checking Docker Desktop"
$dockerExe = Get-Command "docker" -ErrorAction SilentlyContinue
if (-not $dockerExe) { Write-Fail "Docker not found on PATH. Install Docker Desktop first." }

$dockerVer = & docker version --format "{{.Server.Version}}" 2>$null
if (-not $dockerVer) { Write-Fail "Docker daemon not reachable. Is Docker Desktop running?" }
Write-OK "Docker v$dockerVer"

# --- 2. Run preflight ---
Write-Step "Running preflight checks"
Push-Location $RepoRoot
try {
    & python -m deployment.checks.preflight 2>&1
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 2) { Write-Fail "Preflight checks failed (exit $LASTEXITCODE)" }
    Write-OK "Preflight passed"
} catch { Write-Fail "Preflight error: $_" }
finally { Pop-Location }

# --- 3. Create or validate .env ---
Write-Step "Setting up environment"
$envPath = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Step "Generating fresh .env..."
    Push-Location $RepoRoot
    try { & python -m scripts.setup_environment --force 2>&1; Write-OK "Environment created" }
    catch { Write-Fail "Environment setup failed: $_" }
    finally { Pop-Location }
} else {
    Write-Step "Validating existing .env..."
    Push-Location $RepoRoot
    try { & python -m scripts.setup_environment --validate 2>&1; Write-OK ".env valid" }
    catch { Write-Host "  WARNING .env validation issue: $_" -ForegroundColor Yellow }
    finally { Pop-Location }
}

# --- 4. Build versioned Docker image ---
Write-Step "Building Docker image"
$versionFile = Join-Path $RepoRoot "VERSION"
$appVersion = "1.0.0"
if (Test-Path $versionFile) { $appVersion = (Get-Content $versionFile -Raw).Trim() }
$imageTag = "academic-anonymous-grader:$appVersion"

Push-Location $RepoRoot
try {
    & docker build -t $imageTag . 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Fail "Docker build failed" }
    & docker tag $imageTag "academic-anonymous-grader:latest" 2>$null
    Write-OK "Image $imageTag built"
} catch { Write-Fail "Docker build error: $_" }
finally { Pop-Location }

# --- 5. Create named volumes ---
Write-Step "Creating persistent volumes"
foreach ($vol in @("grader_data","grader_backups","grader_exports","grader_logs")) {
    & docker volume create $vol 2>$null
}
Write-OK "Volumes ready"

# --- 6. Start application ---
Write-Step "Starting application"
Push-Location $RepoRoot
try {
    & docker compose -f $ComposeFile -p $ProjectName up -d 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Fail "docker compose up failed" }
    Write-OK "Container started"
}
catch { Write-Fail "Start failed: $_" }
finally { Pop-Location }

# --- 7. Wait for healthy status ---
Write-Step "Waiting for healthy status (up to 60s)..."
$healthy = $false
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 5
    $status = & docker compose -f $ComposeFile -p $ProjectName ps --format "{{.Status}}" 2>$null
    if ($status -like "*healthy*") { $healthy = $true; break }
}
if (-not $healthy) {
    & docker compose -f $ComposeFile -p $ProjectName logs --no-color --tail 20 2>&1
    Write-Fail "Container did not become healthy"
}
Write-OK "Container healthy"

# --- 8. Create first Administrator ---
Write-Step "Checking for Administrators"
Push-Location $RepoRoot
try {
    $adminCheck = & docker compose -f $ComposeFile -p $ProjectName exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory; from models.user import User;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
count = session.query(User).filter(User.role == 'administrator').count();
session.close(); print(count)" 2>$null
    if ($adminCheck -eq "0") {
        Write-Step "Creating first Administrator account..."
        & docker compose -f $ComposeFile -p $ProjectName exec -it app python -m scripts.create_admin 2>&1
        Write-OK "Administrator created"
    } else {
        Write-OK "Administrator already exists ($adminCheck)"
    }
} catch { Write-Host "  WARNING Could not check admin: $_" -ForegroundColor Yellow }
finally { Pop-Location }

# --- 9. Run post-install validation ---
Write-Step "Running post-install validation"
Push-Location $RepoRoot
try {
    & python -m deployment.checks.post_install 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Fail "Post-install validation failed" }
    Write-OK "Post-install passed"
} catch { Write-Host "  WARNING Post-install error: $_" -ForegroundColor Yellow }
finally { Pop-Location }

# --- 10. Done ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Academic Anonymous Grader installed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Open: http://localhost:8501" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Login with the Administrator account you just created."
Write-Host "  2. Go to Academic Structure to review defaults."
Write-Host "  3. Create materials and assessments."
Write-Host "  4. Configure backup schedule."
Write-Host ""
Write-Host "Commands:"
Write-Host "  .\deployment\windows\status.ps1   — Check status"
Write-Host "  .\deployment\windows\stop.ps1     — Stop application"
Write-Host "  .\deployment\windows\backup.ps1   — Create backup"
Write-Host "  .\deployment\windows\update.ps1   — Update to new version"
