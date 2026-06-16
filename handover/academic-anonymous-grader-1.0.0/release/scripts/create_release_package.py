"""Create a release package for Academic Anonymous Grader.

Usage:
    python -m scripts.create_release_package [--version 1.0.0-rc1] [--include-image]

Creates:
    release/academic-anonymous-grader-<version>/
        docker-compose.production.yml
        .env.production.example
        deployment/
        docs/
        VERSION
        RELEASE_NOTES.md
        CHECKSUMS.txt
        optional-image.tar  (only with --include-image)

Excludes: .git, .env, database, backups, exports, logs,
samples, IDE files, caches, temp scripts, credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _collect_files(version: str) -> list[Path]:
    """Collect files for the release package."""
    include_patterns = [
        "docker-compose.production.yml",
        "docker-compose.yml",
        "Dockerfile",
        ".dockerignore",
        ".env.example",
        ".gitignore",
        "VERSION",
        "pyproject.toml",
        "pytest.ini",
        "requirements.txt",
        "requirements-dev.txt",
        "README.md",
        "docker/",
        "deployment/",
        "scripts/",
        "docs/",
        "config/",
        "database/",
        "models/",
        "services/",
        "security/",
        "analytics/",
        "pages/",
        "parsers/",
        "ui/",
    ]
    files: list[Path] = []
    for pattern in include_patterns:
        p = REPO_ROOT / pattern
        if p.exists():
            if p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file():
                        files.append(f)
            else:
                files.append(p)
    return files


def _exclude_file(path: Path) -> bool:
    """Return True if file should be excluded from release."""
    rel = path.relative_to(REPO_ROOT)
    # Exclude patterns
    excluded_parts = [
        "__pycache__", ".pytest_cache", ".git", ".env",
        ".mypy_cache", ".ruff_cache", ".coverage",
        "node_modules", ".venv", "venv",
    ]
    for part in path.parts:
        if part in excluded_parts:
            return True
    # Exclude temporary and debug files
    if rel.name.startswith("_") and rel.suffix == ".py":
        return True
    if rel.suffix in (".pyc", ".pyo", ".pyd", ".so"):
        return True
    return False


def _compute_checksum(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build_release_package(version: str, include_image: bool = False) -> Path:
    """Build the release package and return the release directory path."""
    release_dir = REPO_ROOT / "release" / f"academic-anonymous-grader-{version}"
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)

    files = _collect_files(version)
    checksums: dict[str, str] = {}

    for src in files:
        if _exclude_file(src):
            continue
        rel_path = src.relative_to(REPO_ROOT)
        dest = release_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        checksums[str(rel_path)] = _compute_checksum(dest)

    # Write CHECKSUMS.txt
    checksum_lines = []
    for name, chk in sorted(checksums.items()):
        checksum_lines.append(f"{chk}  {name}")
    (release_dir / "CHECKSUMS.txt").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )

    # Write or update RELEASE_NOTES.md
    release_notes = release_dir / "RELEASE_NOTES.md"
    if not release_notes.exists():
        release_notes.write_text(
            f"# Academic Anonymous Grader — Release {version}\n\n"
            f"Release date: {datetime.now(UTC).strftime('%Y-%m-%d')}\n\n"
            "## Changes\n\n"
            "- Initial release candidate.\n\n"
            "## Upgrade Notes\n\n"
            "See docs/UPGRADE_GUIDE.md\n",
            encoding="utf-8",
        )

    # Update manifest timestamp
    manifest_path = release_dir / "release-manifest.json"
    if not manifest_path.exists():
        shutil.copy2(REPO_ROOT / "release-manifest.json", manifest_path)

    import json
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["release_timestamp"] = datetime.now(UTC).isoformat()
            manifest["checksums"] = checksums
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        except Exception:
            pass

    # Optional: save Docker image archive
    if include_image:
        image_name = f"academic-anonymous-grader:{version}"
        archive_path = release_dir / f"academic-grader-{version}.tar"
        result = subprocess.run(
            ["docker", "save", image_name, "-o", str(archive_path)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            checksums[str(archive_path.name)] = _compute_checksum(archive_path)
            # Update checksums file
            with open(release_dir / "CHECKSUMS.txt", "a") as f:
                f.write(f"{checksums[str(archive_path.name)]}  {archive_path.name}\n")

    print(f"Release package created: {release_dir}")
    print(f"  Files: {len(files)}")
    print(f"  Size: {sum(f.stat().st_size for f in release_dir.rglob('*') if f.is_file()) / 1024:.0f} KB")

    return release_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Create release package")
    parser.add_argument("--version", default="1.0.0-rc1", help="Version string")
    parser.add_argument("--include-image", action="store_true", help="Include Docker image archive")
    args = parser.parse_args()

    build_release_package(args.version, include_image=args.include_image)
    sys.exit(0)


if __name__ == "__main__":
    main()
