# Production Deployment Checklist

## Pre-Deployment

- [ ] `.env` configured with production values
- [ ] `APP_ENV=production`
- [ ] `APP_DEBUG=false`
- [ ] `IDENTITY_ENCRYPTION_KEY` generated (32-byte base64url key)
- [ ] `IDENTITY_FINGERPRINT_KEY` generated (different from encryption key)
- [ ] `BACKUP_PASSWORD` set
- [ ] Sensitive parser limits configured
- [ ] `.dockerignore` excludes secrets, data, samples

## Docker Deployment

- [ ] `docker compose build --no-cache` succeeds
- [ ] `docker compose config` shows no secrets
- [ ] Health check passes: `python -m scripts.health_check`
- [ ] Application accessible at http://localhost:8501
- [ ] Runs as non-root user (check with `docker compose exec app whoami`)
- [ ] Volumes are writable
- [ ] No traceback visible in UI
- [ ] No secrets in logs: `docker compose logs --no-color | grep -i "secret\|key\|password"`

## Verification

- [ ] Create admin user with `docker compose run --rm app python -m scripts.create_admin`
- [ ] Login as administrator
- [ ] Create material and assessment
- [ ] Create instructor users
- [ ] Assign instructors to assessments
- [ ] Login as instructor, verify assessment filtering
- [ ] Finalize and export
- [ ] Backup and restore
- [ ] Verify persistence after restart
