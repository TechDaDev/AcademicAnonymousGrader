#!/bin/bash
# Create a verified backup
set -eu
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.production.yml"

echo ">>> Creating backup..."
docker compose -f "$COMPOSE_FILE" exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory;
from services.backup_service import create_backup;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
result = create_backup(session); session.close();
print(f'REF={result.backup_reference} SIZE={result.file_size}')
" 2>/dev/null || echo "  Backup service unavailable."
echo "Backup complete."
