"""Safe environment setup — generate keys, create .env, never print secrets.

Modes:
  Fresh installation — generates new keys and writes .env.
  Existing migration  — refuses to overwrite keys; requires importing
                        the original .env or approved secret bundle.

Usage:
    python -m scripts.setup_environment          # fresh install
    python -m scripts.setup_environment --force   # overwrite existing .env
    python -m scripts.setup_environment --validate  # check existing .env
"""

from __future__ import annotations

import argparse
import base64
import os
import secrets
import sys
from pathlib import Path

ENV_PATH = Path(".env")


def _database_has_encrypted_identities(db_path: str | None = None) -> bool:
    """Check if an existing database has StudentIdentity rows."""
    if db_path and os.path.exists(db_path):
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM student_identities")
            count_value = cur.fetchone()[0]
            conn.close()
            return bool(count_value > 0)
        except Exception:
            pass
    return False


def _detect_existing_env() -> bool:
    """Return True if .env exists and has encryption keys."""
    if not ENV_PATH.exists():
        return False
    content = ENV_PATH.read_text(encoding="utf-8")
    return "IDENTITY_ENCRYPTION_KEY=" in content and "IDENTITY_FINGERPRINT_KEY=" in content


def _generate_key() -> str:
    """Generate a 32-byte URL-safe base64 key with padding."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def _generate_backup_password() -> str:
    """Generate a strong random backup password."""
    return secrets.token_hex(16)


def _create_env(
    enc_key: str,
    fp_key: str,
    backup_pw: str,
    *,
    force: bool = False,
) -> str:
    """Write .env with production defaults.  Returns a status message."""
    template = ENV_PATH.with_name(".env.example")
    if template.exists():
        content = template.read_text(encoding="utf-8")
    else:
        content = "# Academic Anonymous Grader — Environment\n"

    # Replace placeholders
    content = content.replace(
        'IDENTITY_ENCRYPTION_KEY=',
        f'IDENTITY_ENCRYPTION_KEY={enc_key}',
    )
    content = content.replace(
        'IDENTITY_FINGERPRINT_KEY=',
        f'IDENTITY_FINGERPRINT_KEY={fp_key}',
    )
    content = content.replace(
        '# BACKUP_PASSWORD=',
        f'BACKUP_PASSWORD={backup_pw}',
    )
    content = content.replace("APP_ENV=development", "APP_ENV=production")
    content = content.replace("APP_DEBUG=true", "APP_DEBUG=false")

    # Add APP_HOST_PORT if not present
    if "APP_HOST_PORT" not in content:
        content += "\nAPP_HOST_PORT=8501\n"

    if ENV_PATH.exists() and not force:
        return "WARNING: .env already exists. Use --force to overwrite."

    ENV_PATH.write_text(content, encoding="utf-8")

    # Set restrictive permissions (Windows: best effort)
    try:
        os.chmod(ENV_PATH, 0o600)
    except Exception:
        pass

    return "Environment created successfully."


def _validate_env() -> list[str]:
    """Validate existing .env.  Returns list of issues."""
    issues: list[str] = []
    if not ENV_PATH.exists():
        issues.append(".env not found.")
        return issues

    import re
    content = ENV_PATH.read_text(encoding="utf-8")

    # Check encryption key
    m = re.search(r"^IDENTITY_ENCRYPTION_KEY=(\S+)", content, re.MULTILINE)
    if not m or not m.group(1):
        issues.append("IDENTITY_ENCRYPTION_KEY is missing or empty.")
    else:
        raw = m.group(1)
        try:
            decoded = secrets.token_urlsafe(32) if False else None  # noqa: F841
            import base64
            key_bytes = base64.urlsafe_b64decode(raw)
            if len(key_bytes) < 32:
                issues.append("IDENTITY_ENCRYPTION_KEY is too short.")
            if raw == "IDENTITY_FINGERPRINT_KEY=":
                issues.append("IDENTITY_ENCRYPTION_KEY appears to be a placeholder.")
        except Exception:
            issues.append("IDENTITY_ENCRYPTION_KEY is not valid base64.")

    # Check fingerprint key
    m = re.search(r"^IDENTITY_FINGERPRINT_KEY=(\S+)", content, re.MULTILINE)
    if not m or not m.group(1):
        issues.append("IDENTITY_FINGERPRINT_KEY is missing or empty.")

    # Check APP_ENV
    if "APP_ENV=production" not in content:
        issues.append("APP_ENV is not set to production.")

    # Check APP_DEBUG
    if "APP_DEBUG=false" not in content:
        issues.append("APP_DEBUG is not set to false.")

    # Check for existing database with identities
    if "--db-path" in sys.argv:
        idx = sys.argv.index("--db-path")
        if idx + 1 < len(sys.argv):
            db_path = sys.argv[idx + 1]
            if _database_has_encrypted_identities(db_path):
                issues.append(
                    "WARNING: Database has encrypted identities. "
                    "Do NOT replace encryption keys."
                )

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up environment for Academic Anonymous Grader")
    parser.add_argument("--force", action="store_true", help="Overwrite existing .env")
    parser.add_argument("--validate", action="store_true", help="Validate existing .env")
    parser.add_argument("--db-path", type=str, default=None, help="Path to database file for safety check")

    args = parser.parse_args()

    if args.validate:
        issues = _validate_env()
        if issues:
            for issue in issues:
                print(f"  - {issue}")
            sys.exit(1)
        else:
            print("Environment validation passed.")
            sys.exit(0)

    # Detect existing installation
    existing = _detect_existing_env()

    if existing and not args.force:
        # Check for encrypted identities
        db_path = args.db_path or os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
        if _database_has_encrypted_identities(db_path):
            print(
                "ERROR: Existing database has encrypted identities.\n"
                "  Do NOT generate new keys.  Copy the original .env file\n"
                "  from the previous installation and re-run without --force.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            "WARNING: .env already exists. Use --force to overwrite.\n"
            "  If this is an existing encrypted installation, copy the original\n"
            "  .env file instead of generating new keys.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Generate fresh keys
    enc_key = _generate_key()
    fp_key = _generate_key()
    backup_pw = _generate_backup_password()

    msg = _create_env(enc_key, fp_key, backup_pw, force=args.force)
    print(msg)
    sys.exit(0)


if __name__ == "__main__":
    main()
