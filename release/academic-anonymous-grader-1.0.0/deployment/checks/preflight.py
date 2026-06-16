"""Pre-flight check for Academic Anonymous Grader deployment.

Usage:
    python -m deployment.checks.preflight

Returns PASS / WARNING / FAIL with safe reason codes.
No secrets, identities, or sensitive paths are exposed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REQUIRED_FILES = [
    "docker-compose.yml",
    "docker-compose.production.yml",
    "Dockerfile",
    ".env.example",
    "VERSION",
    "docker/entrypoint.sh",
    "scripts/health_check.py",
]
REQUIRED_VOLUMES = ["grader_data", "grader_backups", "grader_exports", "grader_logs"]
MIN_DISK_GB = 2
EXPECTED_PORT = 8501


class PreflightResult:
    """Result of a single preflight check."""

    def __init__(self, name: str, status: str, reason: str = "") -> None:
        self.name = name
        self.status = status  # PASS, WARNING, FAIL
        self.reason = reason

    def __repr__(self) -> str:
        return f"[{self.status:>7}] {self.name}" + (f"  ({self.reason})" if self.reason else "")


def _check_os() -> PreflightResult:
    """Check supported operating system."""
    platform = sys.platform.lower()
    if platform.startswith("win"):
        return PreflightResult("operating-system", "PASS", "Windows")
    elif platform.startswith("linux"):
        return PreflightResult("operating-system", "PASS", "Linux")
    elif platform.startswith("darwin"):
        return PreflightResult("operating-system", "PASS", "macOS")
    return PreflightResult("operating-system", "WARNING", f"Untested platform: {platform}")


def _check_docker() -> PreflightResult:
    """Check Docker is installed and daemon reachable."""
    if not shutil.which("docker"):
        return PreflightResult("docker-installed", "FAIL", "docker command not found on PATH")
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return PreflightResult("docker-daemon", "PASS", f"v{result.stdout.strip()}")
        return PreflightResult("docker-daemon", "FAIL", "Daemon not reachable")
    except FileNotFoundError:
        return PreflightResult("docker-installed", "FAIL", "docker command not found")
    except subprocess.TimeoutExpired:
        return PreflightResult("docker-daemon", "FAIL", "Daemon timed out")
    except Exception as exc:
        return PreflightResult("docker-daemon", "FAIL", str(exc))


def _check_compose() -> PreflightResult:
    """Check Docker Compose is available."""
    for candidate in ("docker compose", "docker-compose"):
        cmd = candidate.split()
        try:
            result = subprocess.run(
                [*cmd, "version", "--short"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return PreflightResult("docker-compose", "PASS", result.stdout.strip())
        except Exception:
            continue
    return PreflightResult("docker-compose", "FAIL", "No compose command found")


def _check_disk_space() -> PreflightResult:
    """Check adequate disk space on the repository drive."""
    try:
        free = shutil.disk_usage(REPO_ROOT).free
        free_gb = free / (1024 ** 3)
        if free_gb < MIN_DISK_GB:
            return PreflightResult("disk-space", "FAIL", f"Only {free_gb:.1f} GB free, need {MIN_DISK_GB} GB")
        if free_gb < MIN_DISK_GB * 3:
            return PreflightResult("disk-space", "WARNING", f"{free_gb:.1f} GB free")
        return PreflightResult("disk-space", "PASS", f"{free_gb:.1f} GB free")
    except Exception:
        return PreflightResult("disk-space", "WARNING", "Could not check")


def _check_port(port: int = EXPECTED_PORT) -> PreflightResult:
    """Check if port is available."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            result = s.connect_ex(("127.0.0.1", port))
            if result == 0:
                return PreflightResult("port-availability", "WARNING", f"Port {port} is already in use")
            return PreflightResult("port-availability", "PASS", f"Port {port} available")
    except Exception:
        return PreflightResult("port-availability", "WARNING", "Could not check")


def _check_repository_files() -> PreflightResult:
    """Check required repository files exist."""
    missing = [f for f in REQUIRED_FILES if not (REPO_ROOT / f).exists()]
    if missing:
        return PreflightResult("repository-files", "FAIL", f"Missing: {', '.join(missing)}")
    return PreflightResult("repository-files", "PASS", "All present")


def _check_env_file() -> PreflightResult:
    """Check .env presence."""
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        return PreflightResult("env-file", "PASS", "Present")
    return PreflightResult("env-file", "WARNING", "Not found — first-run mode")


def _check_volumes() -> PreflightResult:
    """Check required Docker volumes exist."""
    try:
        result = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            capture_output=True, text=True, timeout=10,
        )
        existing = set(result.stdout.strip().splitlines())
        missing = [v for v in REQUIRED_VOLUMES if v not in existing]
        if missing:
            return PreflightResult("persistent-volumes", "WARNING", f"Missing: {', '.join(missing)}")
        return PreflightResult("persistent-volumes", "PASS", "All present")
    except Exception:
        return PreflightResult("persistent-volumes", "WARNING", "Could not check")


def _check_backup_dir() -> PreflightResult:
    """Check backup directory is writable."""
    backup_dir = REPO_ROOT / "backups"
    if not backup_dir.exists():
        return PreflightResult("backup-directory", "WARNING", "Not created yet")
    if os.access(str(backup_dir), os.W_OK):
        return PreflightResult("backup-directory", "PASS", "Writable")
    return PreflightResult("backup-directory", "FAIL", "Not writable")


def _check_version() -> PreflightResult:
    """Read application version."""
    version_file = REPO_ROOT / "VERSION"
    if version_file.exists():
        ver = version_file.read_text(encoding="utf-8").strip()
        return PreflightResult("application-version", "PASS", ver)
    return PreflightResult("application-version", "FAIL", "VERSION file missing")


def run_checks() -> list[PreflightResult]:
    """Run all preflight checks and return results."""
    checks = [
        _check_os(),
        _check_docker(),
        _check_compose(),
        _check_daemon := _check_docker(),
        _check_disk_space(),
        _check_port(),
        _check_repository_files(),
        _check_env_file(),
        _check_volumes(),
        _check_backup_dir(),
        _check_version(),
    ]
    return checks


def main() -> None:
    checks = run_checks()
    has_fail = False
    has_warning = False
    for c in checks:
        print(c)
        if c.status == "FAIL":
            has_fail = True
        elif c.status == "WARNING":
            has_warning = True

    if has_fail:
        print("\nResult: FAIL")
        sys.exit(1)
    if has_warning:
        print("\nResult: WARNING")
        sys.exit(0)
    print("\nResult: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
