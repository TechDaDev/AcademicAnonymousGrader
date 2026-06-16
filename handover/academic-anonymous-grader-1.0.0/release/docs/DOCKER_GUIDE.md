# Docker Guide

## Prerequisites

- Docker Engine 24+ and Docker Compose v2+
- `.env` file with required configuration (copy from `.env.example`)

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your keys

# 2. Build and start
docker compose build --no-cache
docker compose up -d

# 3. Verify health
docker compose ps
docker compose logs --no-color

# 4. Create initial administrator
docker compose run --rm app python -m scripts.create_admin

# 5. Open http://localhost:8501
```

## Production Deployment

### Required Environment Variables

| Variable | Description |
|---|---|
| `APP_ENV=production` | Production mode |
| `IDENTITY_ENCRYPTION_KEY` | 32-byte base64url-encoded AES key |
| `IDENTITY_FINGERPRINT_KEY` | 32-byte base64url-encoded HMAC key |

Generate keys:
```bash
python -c "from security.key_validation import generate_encryption_key, generate_fingerprint_key; print(f'IDENTITY_ENCRYPTION_KEY={generate_encryption_key()}'); print(f'IDENTITY_FINGERPRINT_KEY={generate_fingerprint_key()}')"
```

### Persistent Volumes

| Volume | Container Path | Purpose |
|---|---|---|
| `grader_data` | `/app/data` | SQLite database |
| `grader_backups` | `/app/backups` | Backup archives |
| `grader_exports` | `/app/exports` | Exported files |
| `grader_logs` | `/app/logs` | Log files |

### Useful Commands

```bash
# View logs
docker compose logs -f

# Run health check
docker compose exec app python -m scripts.health_check

# Create admin user
docker compose run --rm app python -m scripts.create_admin

# Backup database
docker compose exec app python -c "..."

# Stop and remove container (preserves volumes)
docker compose down

# Full cleanup (destroys volumes)
docker compose down -v
```

### Moving to Another Machine

1. Stop the container: `docker compose down`
2. Backup volumes: `docker run --rm -v grader_data:/data -v $(pwd):/backup busybox tar czf /backup/grader_data.tar.gz -C /data .`
3. Repeat for all volumes
4. Copy the backup archives and `.env` to the new machine
5. Restore: `docker run --rm -v grader_data:/data -v $(pwd):/backup busybox tar xzf /backup/grader_data.tar.gz -C /data`

## Development

```bash
docker compose -f docker-compose.dev.yml up -d
```
