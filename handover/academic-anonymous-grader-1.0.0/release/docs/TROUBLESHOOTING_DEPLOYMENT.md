# Deployment Troubleshooting Guide

## Docker Issues

### Docker Desktop won't start

1. Restart Docker Desktop from the system tray
2. If that fails, run `wsl --shutdown` in PowerShell, then restart Docker Desktop
3. If still failing, restart your computer

### Docker daemon not reachable

```
ERROR: request returned 500 Internal Server Error
```

1. Wait 30 seconds and retry
2. Restart Docker Desktop
3. If persistent, restart WSL: `wsl --shutdown`

### Docker build out of memory

```
cannot allocate memory
```

Increase Docker Desktop memory:
1. Open Docker Desktop → Settings → Resources → Advanced
2. Increase Memory to 4 GB or more
3. Apply and restart

### Docker build times out connecting to registry

Docker Hub connectivity issue. Retry the build command.

## Container Issues

### Container keeps restarting

```bash
docker compose logs --no-color --tail 50
```

Common causes:
- `APP_DEBUG=true` in production (set to `false`)
- Missing `IDENTITY_ENCRYPTION_KEY`
- Database file permission issue

### Health check fails

```bash
docker compose exec app python -m scripts.health_check
```

Check each component: settings, database, schema, crypto keys, directories.

### Port 8501 already in use

Change the host port in `.env`:
```
APP_HOST_PORT=8502
```

Then restart:
```bash
docker compose -f docker-compose.production.yml up -d
```

## Data Issues

### "Encrypted identities unreadable" after move

The encryption keys in `.env` don't match the keys used when the identities were imported.

**Solution:** Restore the original `.env` file from the source installation.
**Never** generate new keys for an existing encrypted database.

### Backup restore fails

```
Backup integrity check failed
```

The backup archive is corrupted or was tampered with. Use a different backup.

```
Incompatible schema version
```

The backup was created from a different application version. Use a matching version.

### Container healthy but web page doesn't load

1. Check the browser URL is `http://localhost:8501`
2. Check the container port mapping: `docker compose ps`
3. Check the container logs for Streamlit errors
4. Try `http://127.0.0.1:8501`

## Environment Issues

### .env validation fails

Run:
```bash
python -m scripts.setup_environment --validate
```

Common issues:
- `APP_ENV` not set to `production`
- `APP_DEBUG` not set to `false`
- Missing or invalid encryption keys
- Missing fingerprint key

### Lost the original .env

If the database has no encrypted identities (StudentIdentity count = 0):
- Generate new keys with `python -m scripts.setup_environment --force`

If the database has encrypted identities:
- Keys must be recovered from backup or password manager
- Without the original keys, identities cannot be decrypted
- The application can still be used, but new imports will use new keys

## Application Issues

### Login fails

Check that the Administrator account was created:
```bash
docker compose exec app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory; from models.user import User;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
count = session.query(User).filter(User.role == 'administrator').count();
session.close(); print(f'Admins: {count}')
"
```

If count is 0, create an admin:
```bash
docker compose exec -it app python -m scripts.create_admin
```
