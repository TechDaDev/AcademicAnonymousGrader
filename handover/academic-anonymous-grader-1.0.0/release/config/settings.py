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


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


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

    data_directory: str = field(default_factory=lambda: os.getenv("DATA_DIRECTORY", os.getenv("DATA_DIR", "data")))
    export_directory: str = field(
        default_factory=lambda: os.getenv("EXPORT_DIRECTORY", os.getenv("EXPORT_DIR", "exports"))
    )
    upload_directory: str = field(
        default_factory=lambda: os.getenv("UPLOAD_DIRECTORY", "uploads")
    )
    backup_directory: str = field(
        default_factory=lambda: os.getenv("BACKUP_DIRECTORY", os.getenv("BACKUP_DIR", "backups"))
    )
    log_directory: str = field(
        default_factory=lambda: os.getenv("LOG_DIR", "logs")
    )
    max_upload_size_mb: int = field(default_factory=lambda: _env_int("MAX_UPLOAD_SIZE_MB", 20))
    max_html_tables: int = field(default_factory=lambda: _env_int("MAX_HTML_TABLES", 20))
    max_import_rows: int = field(default_factory=lambda: _env_int("MAX_IMPORT_ROWS", 10_000))
    max_import_columns: int = field(default_factory=lambda: _env_int("MAX_IMPORT_COLUMNS", 500))
    max_cell_text_length: int = field(default_factory=lambda: _env_int("MAX_CELL_TEXT_LENGTH", 1_000_000))

    # Phase 4 encryption and fingerprint keys
    identity_encryption_key: str = field(
        default_factory=lambda: os.getenv("IDENTITY_ENCRYPTION_KEY", "")
    )
    identity_fingerprint_key: str = field(
        default_factory=lambda: os.getenv("IDENTITY_FINGERPRINT_KEY", "")
    )

    # Phase 8 session and backup settings
    session_timeout_minutes: int = field(
        default_factory=lambda: _env_int("SESSION_TIMEOUT_MINUTES", 30)
    )
    backup_password: str = field(
        default_factory=lambda: os.getenv("BACKUP_PASSWORD", "")
    )
    max_failed_login_attempts: int = field(
        default_factory=lambda: _env_int("MAX_FAILED_LOGIN_ATTEMPTS", 5)
    )
    lockout_duration_minutes: int = field(
        default_factory=lambda: _env_int("LOCKOUT_DURATION_MINUTES", 15)
    )

    # Phase 12 — Analytics settings
    analytics_minimum_group_size: int = field(
        default_factory=lambda: _env_int("ANALYTICS_MINIMUM_GROUP_SIZE", 5)
    )
    analytics_default_date_range_days: int = field(
        default_factory=lambda: _env_int("ANALYTICS_DEFAULT_DATE_RANGE_DAYS", 90)
    )
    analytics_max_export_rows: int = field(
        default_factory=lambda: _env_int("ANALYTICS_MAX_EXPORT_ROWS", 10000)
    )
    analytics_cache_ttl_seconds: int = field(
        default_factory=lambda: _env_int("ANALYTICS_CACHE_TTL_SECONDS", 300)
    )
    analytics_enable_instructor_export: bool = field(
        default_factory=lambda: os.getenv("ANALYTICS_ENABLE_INSTRUCTOR_EXPORT", "false").lower() == "true"
    )
    analytics_difficulty_threshold: float = field(
        default_factory=lambda: float(os.getenv("ANALYTICS_DIFFICULTY_THRESHOLD", "0.4"))
    )
    analytics_high_zero_rate_threshold: float = field(
        default_factory=lambda: float(os.getenv("ANALYTICS_HIGH_ZERO_RATE_THRESHOLD", "0.3"))
    )
    analytics_stale_claim_hours: int = field(
        default_factory=lambda: _env_int("ANALYTICS_STALE_CLAIM_HOURS", 4)
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

        for name, value in {
            "MAX_UPLOAD_SIZE_MB": self.max_upload_size_mb,
            "MAX_HTML_TABLES": self.max_html_tables,
            "MAX_IMPORT_ROWS": self.max_import_rows,
            "MAX_IMPORT_COLUMNS": self.max_import_columns,
            "MAX_CELL_TEXT_LENGTH": self.max_cell_text_length,
        }.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")

        # Phase 12 — Analytics settings validation
        if self.analytics_minimum_group_size < 3:
            raise ValueError(
                "ANALYTICS_MINIMUM_GROUP_SIZE must be at least 3."
            )
        if self.analytics_default_date_range_days < 1:
            raise ValueError(
                "ANALYTICS_DEFAULT_DATE_RANGE_DAYS must be positive."
            )
        if self.analytics_max_export_rows < 1:
            raise ValueError(
                "ANALYTICS_MAX_EXPORT_ROWS must be positive."
            )
        if self.analytics_cache_ttl_seconds < 0:
            raise ValueError(
                "ANALYTICS_CACHE_TTL_SECONDS must not be negative."
            )
        if not (0.0 <= self.analytics_difficulty_threshold <= 1.0):
            raise ValueError(
                "ANALYTICS_DIFFICULTY_THRESHOLD must be between 0 and 1."
            )
        if not (0.0 <= self.analytics_high_zero_rate_threshold <= 1.0):
            raise ValueError(
                "ANALYTICS_HIGH_ZERO_RATE_THRESHOLD must be between 0 and 1."
            )
        if self.analytics_stale_claim_hours < 1:
            raise ValueError(
                "ANALYTICS_STALE_CLAIM_HOURS must be at least 1."
            )

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

    def resolved_database_url(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            rel_path = url[len("sqlite:///"):]
            abs_path = PROJECT_ROOT / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{abs_path.as_posix()}"
        return url

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def has_phase4_keys(self) -> bool:
        return bool(self.identity_encryption_key) and bool(self.identity_fingerprint_key)

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
