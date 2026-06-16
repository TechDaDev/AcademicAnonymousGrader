# Moving an Installation to Another Laptop

## Controlling Rule

**A fresh installation may use newly generated keys.**
**An existing encrypted installation must always move with its original database and matching encryption/fingerprint keys.**

## Overview

Moving an installation requires two separate transfer packages:

- **Package A (Data):** Database backup, manifest, checksums
- **Package B (Secrets):** `.env` file with original encryption keys

These must be transferred separately using secure channels.

## Step 1: Prepare the Source (Old Laptop)

Run the move-preparation script:

### Windows

```powershell
.\deployment\windows\move-installation.ps1
```

### Linux / macOS

```bash
./deployment/linux/move-installation.sh
```

This creates a database backup and displays the backup reference and version info.

### Manual Secret Export

The `.env` file must be copied separately via a secure channel (USB drive, encrypted email, password manager):

```
copy .env D:\secure\academic-grader-secrets\ 
```

## Step 2: Prepare the Target (New Laptop)

1. Install Docker Desktop
2. Clone or copy the application repository (same version as source)
3. Place the original `.env` file into the repository root
4. Verify the `.env` has the correct keys (without printing them):
   ```bash
   python -m scripts.setup_environment --validate
   ```

## Step 3: Restore the Database

```powershell
# Windows
.\deployment\windows\restore.ps1 -BackupReference BKP-XXXXXXXX
```

```bash
# Follow the restore prompts
```

## Step 4: Verify

```bash
docker compose -f docker-compose.production.yml exec app python -m scripts.health_check
docker compose -f docker-compose.production.yml exec app python -m deployment.checks.post_install
```

## What NOT to Do

| Action | Risk |
|--------|------|
| Install fresh and restore old backup | Key mismatch — identities unreadable |
| Generate new keys for existing database | Encrypted data becomes unrecoverable |
| Lose the original `.env` | Cannot decrypt existing student identities |
| Transfer `.env` in the same ZIP as the backup | Combined exposure of keys and data |

## Data Export Option

If you only need the final grades (not the live application), export workbooks
from the source before decommissioning it. Workbooks contain decrypted data
and do not require the original keys.
