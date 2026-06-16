# Operations Guide

## Daily Operations

### Start the Application

```powershell
# Windows
.\deployment\windows\start.ps1
```

```bash
# Linux / macOS
./deployment/linux/start.sh
```

### Stop the Application

```powershell
# Windows
.\deployment\windows\stop.ps1
```

### Check Status

```powershell
# Windows
.\deployment\windows\status.ps1
```

Reports: version, schema version, container health, port status, volumes.

### View Logs

```bash
docker compose -f docker-compose.production.yml logs --no-color --tail 50
```

### Health Check

```bash
docker compose -f docker-compose.production.yml exec app python -m scripts.health_check
```

## Backup

See [BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md).

## Upgrade

See [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md).

## Rollback

See [ROLLBACK_GUIDE.md](ROLLBACK_GUIDE.md).

## Disk Management

### Check Disk Usage

```bash
docker system df
docker builder du
```

### Clean Build Cache Safely

```bash
docker builder prune -af
```

### Remove Obsolete Images

```bash
docker image prune -a
```

**Never run:**

```bash
docker system prune --volumes    # DESTRUCTIVE — deletes all data
docker compose down -v           # DESTRUCTIVE — deletes volumes
```

## Automatic Startup

Docker Desktop can be configured to start automatically:

1. Open Docker Desktop → Settings → General
2. Enable "Start Docker Desktop when you log in"
3. The application container has `restart: unless-stopped` in compose

On Linux:

```bash
sudo systemctl enable docker
```

## Monitoring

Administrators should periodically check:

1. Container health status
2. Backup recency (last backup date)
3. Available disk space
4. Schema version matches expected version
5. Sanitized logs for error patterns
