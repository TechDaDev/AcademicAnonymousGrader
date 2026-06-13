# Academic Anonymous Grader — Configuration
"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import dotenv


def _find_project_root() -> Path:
    """Find the project root by looking for this file's ancestor with a known marker."""
    current = Path(__file__).resolve().parent
    for candidate in [current, current.parent, current.parent.parent]:
        if (candidate / ".env.example").exists() or (candidate / "app.py").exists():
            return candidate
    return Path.cwd().resolve()


PROJECT_ROOT: Final[Path] = _find_project_root()

dotenv.load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Immutable application settings.

    All values are loaded from environment variables with safe defaults
    for local development. Paths are resolved relative to the project root.
    """

    app_name: str = field(
        default_factory=lambda: os.getenv("APP_NAME", "Academic Anonymous Grader")
    )
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    app_debug: bool = field(
        default_factory=lambda: os.getenv("APP_DEBUG", "true").lower() == "true"
    )

    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///data/academic_grader.db"
        )
    )

    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_file: str = field(
        default_factory=lambda: os.getenv("LOG_FILE", "logs/academic_grader.log")
    )

    data_directory: str = field(default_factory=lambda: os.getenv("DATA_DIRECTORY", "data"))
    export_directory: str = field(
        default_factory=lambda: os.getenv("EXPORT_DIRECTORY", "exports")
    )
    upload_directory: str = field(
        default_factory=lambda: os.getenv("UPLOAD_DIRECTORY", "uploads")
    )
    backup_directory: str = field(
        default_factory=lambda: os.getenv("BACKUP_DIRECTORY", "backups")
    )

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        valid_envs = {"development", "testing", "production"}
        if self.app_env not in valid_envs:
            msg = f"APP_ENV must be one of {valid_envs}, got '{self.app_env}'"
            raise ValueError(msg)

        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            msg = f"LOG_LEVEL must be one of {valid_log_levels}, got '{self.log_level}'"
            raise ValueError(msg)

        if not self.database_url:
            raise ValueError("DATABASE_URL must not be empty")

    @property
    def resolved_data_dir(self) -> Path:
        return self._resolve(self.data_directory)

    @property
    def resolved_export_dir(self) -> Path:
        return self._resolve(self.export_directory)

    @property
    def resolved_upload_dir(self) -> Path:
        return self._resolve(self.upload_directory)

    @property
    def resolved_backup_dir(self) -> Path:
        return self._resolve(self.backup_directory)

    @property
    def resolved_log_file(self) -> Path:
        return self._resolve(self.log_file)

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            rel_path = url[len("sqlite:///"):]
            abs_path = PROJECT_ROOT / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{abs_path.as_posix()}"
        return url

    def _resolve(self, path_str: str) -> Path:
        p = Path(path_str)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @staticmethod
    def create_directories(settings: Settings) -> None:
        """Create all required directories."""
        for directory in [
            settings.resolved_data_dir,
            settings.resolved_export_dir,
            settings.resolved_upload_dir,
            settings.resolved_backup_dir,
            settings.resolved_log_file.parent,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Load and return the application settings."""
    return Settings()
