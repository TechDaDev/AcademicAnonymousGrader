# Offline Installation Guide

## Overview

For environments without direct internet access, deploy from a pre-packaged release.

## Creating the Offline Package

On a machine with internet access:

```bash
# 1. Build the Docker image
docker build -t academic-anonymous-grader:1.0.0-rc1 .

# 2. Save the image to a tar archive
docker save academic-anonymous-grader:1.0.0-rc1 -o academic-grader-1.0.0-rc1.tar

# 3. Generate checksum
sha256sum academic-grader-1.0.0-rc1.tar > academic-grader-1.0.0-rc1.tar.sha256

# 4. Create the full release package
python -m scripts.create_release_package --include-image
```

Or create the archive separately:

```powershell
# Windows
docker save academic-anonymous-grader:1.0.0-rc1 -o academic-grader-1.0.0-rc1.tar
certutil -hashfile academic-grader-1.0.0-rc1.tar SHA256
```

## Transferring

Copy the release package or the image archive via:
- USB drive
- Internal network share
- Approved file transfer

## Installing on the Offline Machine

```bash
# 1. Load the Docker image
docker load -i academic-grader-1.0.0-rc1.tar

# 2. Verify the tag
docker images academic-anonymous-grader:1.0.0-rc1

# 3. Create .env
python -m scripts.setup_environment --force

# 4. Start the application
docker compose -f docker-compose.production.yml up -d
```

## What the Image Archive Contains

- Application code and dependencies
- Python runtime
- No database (persistent volumes are created at runtime)
- No `.env` or secrets
- No backups or exports
- No student data
- No development files

## Offline Package Contents

```
release/academic-anonymous-grader-1.0.0-rc1/
├── docker-compose.production.yml
├── .env.production.example
├── deployment/          # Install scripts
├── VERSION
├── RELEASE_NOTES.md
├── CHECKSUMS.txt
├── release-manifest.json
└── academic-grader-1.0.0-rc1.tar   # (optional)
```
