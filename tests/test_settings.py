# Academic Anonymous Grader — Configuration Tests
"""Tests for config/settings.py."""

from __future__ import annotations

# Disable .env loading for tests — use defaults
import os
from pathlib import Path

import pytest

from config import Settings, _find_project_root

os.environ.pop("APP_NAME", None)


class TestSettingsDefaults:
    """Verify that default settings load without error."""

    def test_defaults_load_successfully(self) -> None:
        """Default settings should not raise."""
        settings = Settings()
        assert settings.app_name == "Academic Anonymous Grader"
        assert settings.app_env == "development"
        assert settings.app_debug is True

    def test_project_root_resolves_to_repo_root(self) -> None:
        """Project root should be discoverable."""
        root = _find_project_root()
        assert isinstance(root, Path)
        assert root.exists()
        # The project root should contain .env.example or app.py
        assert (root / ".env.example").exists() or (root / "app.py").exists()

    def test_database_url_default(self) -> None:
        """Default database URL should be a SQLite path."""
        settings = Settings()
        assert settings.database_url.startswith("sqlite:///")


class TestSettingsValidation:
    """Verify that invalid settings raise clear errors."""

    def test_invalid_app_env_raises_error(self) -> None:
        """An invalid APP_ENV should raise ValueError."""
        with pytest.raises(ValueError, match="APP_ENV must be one of"):
            Settings(app_env="invalid_env")

    def test_invalid_log_level_raises_error(self) -> None:
        """An invalid LOG_LEVEL should raise ValueError."""
        with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
            Settings(log_level="trace")

    def test_empty_database_url_raises_error(self) -> None:
        """An empty DATABASE_URL should raise ValueError."""
        with pytest.raises(ValueError, match="DATABASE_URL must not be empty"):
            Settings(database_url="")


class TestPathResolution:
    """Verify project-root path resolution on Windows-compatible paths."""

    def test_relative_path_resolves_to_project_root(self) -> None:
        """A relative path should resolve under the project root."""
        settings = Settings()
        resolved = settings.resolved_data_dir
        assert resolved.is_absolute()
        assert resolved.name == "data"

    def test_log_file_resolves_correctly(self) -> None:
        """Log file path should resolve correctly."""
        settings = Settings()
        resolved = settings.resolved_log_file
        assert isinstance(resolved, Path)
        assert resolved.suffix == ".log"
