#!/bin/bash
# Install Academic Anonymous Grader on Linux / macOS
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.production.yml"
PROJECT_NAME="academicanonymousgrader"

echo ">>> Academic Anonymous Grader — Install"

# 1. Check Docker
if ! command -v docker &>/dev/null; then
    echo "FAIL: Docker not found. Install Docker first."
    exit 1
fi
DOCKER_VER=$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)
if [ -z "$DOCKER_VER" ]; then
    echo "FAIL: Docker daemon not reachable."
    exit 1
fi
echo "  Docker v$DOCKER_VER"

# 2. Run preflight
echo ">>> Running preflight checks..."
cd "$REPO_ROOT"
python3 -m deployment.checks.preflight || true

# 3. Create .env if needed
echo ">>> Setting up environment..."
if [ ! -f "$REPO_ROOT/.env" ]; then
    cd "$REPO_ROOT"
    python3 -m scripts.setup_environment --force
    echo "  Environment created."
else
    echo "  .env exists."
fi

# 4. Build image
echo ">>> Building Docker image..."
APP_VERSION="$(cat "$REPO_ROOT/VERSION" 2>/dev/null || echo '1.0.0-rc1')"
IMAGE_TAG="academic-anonymous-grader:${APP_VERSION}"
cd "$REPO_ROOT"
docker build -t "$IMAGE_TAG" .
docker tag "$IMAGE_TAG" "academic-anonymous-grader:latest" 2>/dev/null || true
echo "  Image $IMAGE_TAG built"

# 5. Create volumes
echo ">>> Creating persistent volumes..."
for vol in grader_data grader_backups grader_exports grader_logs; do
    docker volume create "$vol" 2>/dev/null || true
done

# 6. Start
echo ">>> Starting application..."
cd "$REPO_ROOT"
docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d

# 7. Wait for health
echo ">>> Waiting for healthy status..."
for i in $(seq 1 12); do
    sleep 5
    STATUS=$(docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps --format '{{.Status}}' 2>/dev/null || true)
    if echo "$STATUS" | grep -q "healthy"; then
        echo "  Container healthy"
        break
    fi
done

# 8. Check admin
echo ">>> Checking for Administrators..."
ADMIN_COUNT=$(docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T app python -c "
from config import get_settings; from database.engine import get_engine;
from database.session import create_session_factory; from models.user import User;
settings = get_settings(); engine = get_engine(settings.resolved_database_url());
factory = create_session_factory(engine); session = factory();
count = session.query(User).filter(User.role == 'administrator').count();
session.close(); print(count)" 2>/dev/null || echo "0")
if [ "$ADMIN_COUNT" = "0" ]; then
    echo ">>> Creating first Administrator..."
    docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -it app python -m scripts.create_admin
fi

# 9. Post-install
cd "$REPO_ROOT"
python3 -m deployment.checks.post_install || true

echo ""
echo "========================================"
echo "  Academic Anonymous Grader installed!"
echo "========================================"
echo ""
echo "  Open: http://localhost:8501"
echo ""
echo "Commands:"
echo "  ./deployment/linux/status.sh"
echo "  ./deployment/linux/stop.sh"
echo "  ./deployment/linux/backup.sh"
