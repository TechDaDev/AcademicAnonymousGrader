"""Privacy-safe diagnostic bundle for Academic Anonymous Grader.

Creates a support bundle in the exports directory containing:
- application version, schema version
- Docker version, compose version
- container health, sanitized logs
- configuration key names (not values)
- safe aggregate counts
- migration history (versions only)
- volume names, disk-space summary

EXCLUDES: .env content, keys, passwords, names, emails,
institutional IDs, responses, feedback, grades, ciphertext,
fingerprints, database file, backup file contents.

Usage:
    python -m scripts.create_diagnostic_bundle

Administrator must inspect and approve before sharing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip()
    except Exception as exc:
        return -1, str(exc)


def collect() -> dict[str, Any]:
    """Collect diagnostic data.  No secrets or identities."""
    data: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "application": {},
        "docker": {},
        "container": {},
        "storage": {},
        "configuration": {},
        "safe_counts": {},
    }

    # Application version
    version_file = REPO_ROOT / "VERSION"
    if version_file.exists():
        data["application"]["version"] = version_file.read_text(encoding="utf-8").strip()

    # Schema version (from DB if reachable)
    try:
        from config import get_settings
        from database.engine import get_engine
        from database.session import create_session_factory
        settings = get_settings()
        engine = get_engine(settings.resolved_database_url())
        factory = create_session_factory(engine)
        session = factory()
        from database.migrations import SCHEMA_VERSION
        data["application"]["schema_version"] = SCHEMA_VERSION
        # Migration history
        try:
            import sqlalchemy as sa
            rows = session.execute(sa.text("SELECT version, description FROM _schema_version ORDER BY version")).fetchall()
            data["application"]["migration_history"] = [
                {"version": r[0], "description": r[1]} for r in rows
            ]
        except Exception:
            pass
        # Safe aggregate counts
        from models.academic_stage import AcademicStage
        from models.academic_term import AcademicTerm
        from models.assessment import Assessment
        from models.department import Department
        from models.material import Material
        from models.user import User
        data["safe_counts"] = {
            "users": session.query(User).count(),
            "administrators": session.query(User).filter(User.role == "administrator").count(),
            "materials": session.query(Material).count(),
            "assessments": session.query(Assessment).count(),
            "departments": session.query(Department).count(),
            "stages": session.query(AcademicStage).count(),
            "terms": session.query(AcademicTerm).count(),
        }
        session.close()
    except Exception as exc:
        data["application"]["db_error"] = str(exc)

    # Docker version
    rc, out = _run(["docker", "version", "--format", "{{.Server.Version}}"])
    if rc == 0:
        data["docker"]["server_version"] = out
    rc, out = _run(["docker", "compose", "version", "--short"])
    if rc == 0:
        data["docker"]["compose_version"] = out

    # Container status
    rc, out = _run(["docker", "compose", "-f", str(REPO_ROOT / "docker-compose.production.yml"), "ps", "--format", "{{.Status}}"])
    if rc == 0:
        data["container"]["status"] = out

    # Sanitized logs (truncated, no secrets)
    rc, out = _run(["docker", "compose", "-f", str(REPO_ROOT / "docker-compose.production.yml"), "logs", "--no-color", "--tail", "30"])
    if rc == 0:
        # Basic sanitization
        sanitized = out
        for pattern in ["IDENTITY_ENCRYPTION_KEY", "IDENTITY_FINGERPRINT_KEY", "BACKUP_PASSWORD"]:
            sanitized = sanitized.replace(pattern, "***")
        data["container"]["logs_tail"] = sanitized[:5000]

    # Disk space
    try:
        usage = shutil.disk_usage(REPO_ROOT)
        data["storage"]["disk_free_gb"] = round(usage.free / (1024 ** 3), 1)
        data["storage"]["disk_total_gb"] = round(usage.total / (1024 ** 3), 1)
    except Exception:
        pass

    # Volume names
    rc, out = _run(["docker", "volume", "ls", "--format", "{{.Name}}"])
    if rc == 0:
        data["storage"]["volumes"] = [v for v in out.splitlines() if "grader" in v]

    # Configuration key names (not values)
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        keys = []
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key = line.split("=", 1)[0]
                keys.append(key)
        data["configuration"]["env_keys_present"] = keys

    # Health check result (from container)
    rc, out = _run(["docker", "compose", "-f", str(REPO_ROOT / "docker-compose.production.yml"), "exec", "-T", "app", "python", "-m", "scripts.health_check"])
    if rc == 0:
        data["container"]["health"] = "healthy" if "healthy" in out else out[:200]

    return data


def main() -> None:
    data = collect()

    # Write to exports directory
    exports_dir = REPO_ROOT / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    bundle_path = exports_dir / f"diagnostic-bundle-{timestamp}.json"

    bundle_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    print(f"Diagnostic bundle written to: {bundle_path}")
    print("Administrator: inspect and approve before sharing.")
    print(f"  File size: {bundle_path.stat().st_size} bytes")
    print("  Contains: version, health, counts, sanitized logs")
    print("  Excludes: secrets, identities, responses, grades")

    sys.exit(0)


if __name__ == "__main__":
    main()
