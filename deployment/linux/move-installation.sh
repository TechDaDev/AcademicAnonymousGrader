#!/bin/bash
# Prepare an existing installation for migration to another machine
set -eu
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.production.yml"

echo "=== Prepare Installation for Migration ==="
echo ""
echo "IMPORTANT: Database and original keys must remain paired."
echo ""

# 1. Create backup
echo ">>> Creating backup..."
BACKUP_RESULT=$(docker compose -f "$COMPOSE_FILE" exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory;
from services.backup_service import create_backup;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
result = create_backup(session); session.close();
print(f'REF={result.backup_reference}')
" 2>/dev/null)
echo "  Backup: $BACKUP_RESULT"

# 2. Version
VERSION=$(cat "$REPO_ROOT/VERSION" 2>/dev/null || echo "1.0.0-rc1")
echo "  Version: $VERSION"

echo ""
echo "Target machine steps:"
echo "  1. Install Docker."
echo "  2. Copy release package (version $VERSION)."
echo "  3. Copy .env to repository root (separate secure channel)."
echo "  4. docker compose -f docker-compose.production.yml up -d"
echo "  5. Restore backup using the application."
echo "  6. Run health check."
echo ""
echo "WARNING: Never use fresh keys with an existing backup."
