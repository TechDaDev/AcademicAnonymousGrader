# Deployment Guide

Academic Anonymous Grader can be deployed in two modes:

- **Mode A — Fresh Installation**: New database, new keys, new administrator
- **Mode B — Existing Installation Migration**: Existing database moved with original keys

## Quick Start

### Windows

```powershell
.\deployment\windows\install.ps1
```

### Linux / macOS

```bash
./deployment/linux/install.sh
```

## Deployment Architecture

The application runs as a single Docker container behind Docker Compose:

- **Container**: `academic-anonymous-grader:1.0.0-rc1`
- **Web server**: Streamlit on port 8501 (configurable)
- **Database**: SQLite in a persistent named volume (`grader_data`)
- **Backups**: Stored in `grader_backups` volume
- **Exports**: Stored in `grader_exports` volume

## Production Compose File

Use `docker-compose.production.yml` for production deployments:

```bash
docker compose -f docker-compose.production.yml up -d
```

Key differences from `docker-compose.yml`:
- Explicit versioned image tag (not `latest`)
- Configurable host port and bind address
- Production-only environment defaults

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `install.ps1` / `install.sh` | Full fresh installation |
| `start.ps1` / `start.sh` | Start application |
| `stop.ps1` / `stop.sh` | Stop application |
| `status.ps1` / `status.sh` | Check status |
| `backup.ps1` / `backup.sh` | Create verified backup |
| `restore.ps1` / `restore.sh` | Restore from backup |
| `update.ps1` / `update.sh` | Update to new version |
| `uninstall.ps1` / `uninstall.sh` | Controlled uninstall |
| `move-installation.ps1` / `move-installation.sh` | Prepare for migration |

## Documentation

- [INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md)
- [INSTALLATION_LINUX.md](INSTALLATION_LINUX.md)
- [INSTALLATION_MACOS.md](INSTALLATION_MACOS.md)
- [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md)
- [ROLLBACK_GUIDE.md](ROLLBACK_GUIDE.md)
- [MOVE_TO_ANOTHER_LAPTOP.md](MOVE_TO_ANOTHER_LAPTOP.md)
- [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md)
- [OFFLINE_INSTALLATION.md](OFFLINE_INSTALLATION.md)
- [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md)
- [TROUBLESHOOTING_DEPLOYMENT.md](TROUBLESHOOTING_DEPLOYMENT.md)
