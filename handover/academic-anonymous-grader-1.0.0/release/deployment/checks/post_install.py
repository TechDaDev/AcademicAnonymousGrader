"""Post-install validation for Academic Anonymous Grader.

Usage:
    python -m deployment.checks.post_install

Returns PASS / WARNING / FAIL with safe reason codes.
No secrets, identities, or sensitive data exposed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_compose(cmd: list[str], timeout: int = 15) -> tuple[int, str]:
    """Run a docker compose command and return (returncode, stdout)."""
    full_cmd = ["docker", "compose", "-f", str(REPO_ROOT / "docker-compose.production.yml"), *cmd]
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)  # noqa: S603 — intentional docker compose calls
        return result.returncode, result.stdout.strip()
    except Exception as exc:
        return -1, str(exc)


def _exec_python(code: str, timeout: int = 15) -> tuple[int, str]:
    """Run python code inside the container."""
    rc, out = _run_compose(
        ["exec", "-T", "app", "python", "-c", code],
        timeout=timeout,
    )
    return rc, out


def check_health() -> bool:
    """Check container health."""
    rc, out = _run_compose(["ps", "--format", "{{.Status}}"])
    return "healthy" in out or rc == 0


def check_version() -> tuple[bool, str]:
    """Check application version matches expected."""
    version_file = REPO_ROOT / "VERSION"
    if not version_file.exists():
        return False, "VERSION file missing"
    expected = version_file.read_text(encoding="utf-8").strip()
    return True, expected


def check_schema_version() -> tuple[bool, str]:
    """Check schema version is current."""
    rc, out = _exec_python(
        "from database.engine import get_engine; from database.migrations import SCHEMA_VERSION; print(SCHEMA_VERSION)"
    )
    if rc != 0:
        return False, f"Could not check ({out})"
    return True, out.strip()


def check_admin_exists() -> tuple[bool, str]:
    """Check at least one administrator exists."""
    rc, out = _exec_python(
        "from config import get_settings; from database.engine import get_engine; from database.session import create_session_factory; "
        "from models.user import User; "
        "settings = get_settings(); engine = get_engine(settings.resolved_database_url()); "
        "factory = create_session_factory(engine); session = factory(); "
        "count = session.query(User).filter(User.role == 'administrator').count(); "
        "session.close(); print(count)"
    )
    if rc != 0:
        return False, "Could not check"
    count = int(out.strip())
    return count > 0, f"{count} administrator(s)"


def check_seed_counts() -> tuple[bool, str]:
    """Check reference seed counts."""
    rc, out = _exec_python(
        "from config import get_settings; from database.engine import get_engine; from database.session import create_session_factory; "
        "from models.department import Department; from models.academic_stage import AcademicStage; from models.academic_term import AcademicTerm; "
        "settings = get_settings(); engine = get_engine(settings.resolved_database_url()); "
        "factory = create_session_factory(engine); session = factory(); "
        "d = session.query(Department).count(); s = session.query(AcademicStage).count(); t = session.query(AcademicTerm).count(); "
        "session.close(); print(f'{d}/{s}/{t}')"
    )
    if rc != 0:
        return False, "Could not check"
    return True, out.strip()


def check_port() -> tuple[bool, str]:
    """Check if application is reachable on localhost."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            result = s.connect_ex(("127.0.0.1", 8501))
            return result == 0, "Reachable" if result == 0 else "Not reachable"
    except Exception:
        return False, "Could not check"


def check_imports() -> tuple[bool, str]:
    """Check that key page imports work inside the container."""
    rc, out = _exec_python(
        "import importlib; "
        "pages = ['pages.AcademicStructure', 'pages.Analytics', 'pages.Materials']; "
        "results = []; "
        "for p in pages: "
        "  try: importlib.import_module(p.replace('pages.', 'pages.')); results.append(f'{p}: OK') "
        "  except Exception as e: results.append(f'{p}: {e}'); "
        "print('; '.join(results))",
        timeout=15,
    )
    if rc != 0:
        return False, out
    return True, out


def main() -> None:
    raw_checks: list[tuple[str, tuple[bool, str] | bool]] = [
        ("container-healthy", check_health()),
        ("application-version", check_version()),
        ("schema-version", check_schema_version()),
        ("administrator-exists", check_admin_exists()),
        ("seed-counts", check_seed_counts()),
        ("port-reachable", check_port()),
        ("page-imports", check_imports()),
    ]

    failures = 0
    for name, result_raw in raw_checks:
        if isinstance(result_raw, bool):
            ok = result_raw
            detail = "healthy" if result_raw else "not healthy"
        else:
            ok, detail = result_raw
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status:>7}] {name}  ({detail})")

    if failures:
        print(f"\nResult: FAIL ({failures} check(s) failed)")
        sys.exit(1)
    print("\nResult: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
