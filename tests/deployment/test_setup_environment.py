"""Tests for the safe environment setup script."""

from __future__ import annotations

import os
from pathlib import Path


class TestSetupEnvironment:
    """Test environment setup safety and correctness."""

    REPO_ROOT = Path(__file__).resolve().parent.parent.parent

    def _run_setup(self, args: list[str] | None, cwd_path: Path, db_path: str | None = None) -> tuple[int, str, str]:
        """Run setup_environment and return (exit_code, stdout, stderr)."""
        import subprocess
        import sys
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        cmd = [sys.executable, "-m", "scripts.setup_environment"]
        if args:
            cmd.extend(args)
        if db_path:
            cmd.extend(["--db-path", db_path])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env, cwd=str(cwd_path))  # noqa: S603
        return result.returncode, result.stdout, result.stderr

    def test_fresh_env_created(self, tmp_path: Path) -> None:
        """Fresh environment creates .env with keys."""
        example = self.REPO_ROOT / ".env.example"
        if example.exists():
            (tmp_path / ".env.example").write_text(example.read_text())
        rc, stdout, stderr = self._run_setup(["--force"], tmp_path)
        assert rc == 0, f"stdout={stdout} stderr={stderr}"
        env_file = tmp_path / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "IDENTITY_ENCRYPTION_KEY=" in content
        assert "IDENTITY_FINGERPRINT_KEY=" in content
        assert "APP_ENV=production" in content
        assert "APP_DEBUG=false" in content

    def test_existing_env_not_overwritten(self, tmp_path: Path) -> None:
        """Existing .env is not overwritten without --force."""
        (tmp_path / ".env").write_text("EXISTING=true\nIDENTITY_ENCRYPTION_KEY=test\nIDENTITY_FINGERPRINT_KEY=test2\n")
        rc, stdout, stderr = self._run_setup(None, tmp_path)
        assert rc == 1
        assert "already exists" in (stdout + stderr)

    def test_existing_env_force_overwrite(self, tmp_path: Path) -> None:
        """--force overwrites existing .env."""
        (tmp_path / ".env.example").write_text("APP_ENV=development\nAPP_DEBUG=true\nIDENTITY_ENCRYPTION_KEY=\nIDENTITY_FINGERPRINT_KEY=\n")
        (tmp_path / ".env").write_text("OLD=true\n")
        rc, stdout, stderr = self._run_setup(["--force"], tmp_path)
        assert rc == 0
        content = (tmp_path / ".env").read_text()
        assert "IDENTITY_ENCRYPTION_KEY=" in content

    def test_keys_valid_and_different(self, tmp_path: Path) -> None:
        """Generated encryption and fingerprint keys are different."""
        import re
        (tmp_path / ".env.example").write_text("IDENTITY_ENCRYPTION_KEY=\nIDENTITY_FINGERPRINT_KEY=\n")
        rc, stdout, stderr = self._run_setup(["--force"], tmp_path)
        content = (tmp_path / ".env").read_text()
        enc = re.search(r"IDENTITY_ENCRYPTION_KEY=(\S+)", content)
        fp = re.search(r"IDENTITY_FINGERPRINT_KEY=(\S+)", content)
        assert enc and fp
        # Keys must be non-empty and different
        assert len(enc.group(1)) > 10
        assert len(fp.group(1)) > 10
        assert enc.group(1) != fp.group(1)

    def test_validate_passes_for_good_env(self, tmp_path: Path) -> None:
        """--validate passes for a valid env."""
        (tmp_path / ".env").write_text(
            "APP_ENV=production\nAPP_DEBUG=false\n"
            "IDENTITY_ENCRYPTION_KEY=YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE=\n"
            "IDENTITY_FINGERPRINT_KEY=YmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmI=\n"
        )
        rc, stdout, stderr = self._run_setup(["--validate"], tmp_path)
        assert rc == 0

    def test_secrets_not_in_stdout(self, tmp_path: Path) -> None:
        """Secret values are not printed to stdout."""
        (tmp_path / ".env.example").write_text("IDENTITY_ENCRYPTION_KEY=\nIDENTITY_FINGERPRINT_KEY=\n")
        rc, stdout, stderr = self._run_setup(["--force"], tmp_path)
        for line in stdout.splitlines():
            assert "IDENTITY_ENCRYPTION_KEY=" not in line or line.strip().endswith("=")


class TestPreflight:
    """Test preflight checker (unit tests for individual checks)."""

    def test_os_check(self) -> None:
        from deployment.checks.preflight import _check_os
        result = _check_os()
        assert result.status in ("PASS", "WARNING")

    def test_repo_files_check(self) -> None:
        from deployment.checks.preflight import _check_repository_files
        result = _check_repository_files()
        assert result.status in ("PASS", "FAIL")

    def test_version_check(self) -> None:
        from deployment.checks.preflight import _check_version
        result = _check_version()
        assert result.status in ("PASS", "FAIL")


class TestPreflightRun:
    """Test the full preflight run."""

    def test_run_checks_structure(self) -> None:
        from deployment.checks.preflight import run_checks
        results = run_checks()
        assert len(results) > 5
        for r in results:
            assert r.status in ("PASS", "WARNING", "FAIL")
            assert r.name


class TestReleasePackage:
    """Test release package creation."""

    def test_collect_files(self, tmp_path: Path) -> None:
        from scripts.create_release_package import _collect_files
        # Just verify the functions exist and run
        files = _collect_files("1.0.0-rc1")
        assert len(files) > 0

    def test_exclude_temp(self) -> None:
        from pathlib import Path

        from scripts.create_release_package import _exclude_file
        repo_root = Path(__file__).resolve().parent.parent.parent
        # Temp script should be excluded
        temp = repo_root / "_temp_debug.py"
        if not temp.exists():
            temp.write_text("x")
        try:
            assert _exclude_file(temp)
        finally:
            if temp.exists():
                temp.unlink()
        # Regular file should not be excluded
        regular = repo_root / "app.py"
        assert not _exclude_file(regular)


class TestDiagnosticBundle:
    """Test diagnostic bundle collection (structure only; DB not required)."""

    def test_collect_structure(self) -> None:
        from scripts.create_diagnostic_bundle import collect
        data = collect()
        # Should run without error
        assert "generated_at" in data
        assert "docker" in data
        # Should not contain secret key values
        json_str = str(data)
        assert "IDENTITY_ENCRYPTION_KEY=" not in json_str
        assert "IDENTITY_FINGERPRINT_KEY=" not in json_str
