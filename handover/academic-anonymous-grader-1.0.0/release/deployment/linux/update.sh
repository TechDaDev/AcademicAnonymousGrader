#!/bin/bash
# Update to a new version
set -eu
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.production.yml"
VERSION="${1:-$(cat "$REPO_ROOT/VERSION" 2>/dev/null || echo "1.0.0-rc1")}"
IMAGE="academic-anonymous-grader"
CURRENT_TAG="${IMAGE}:${VERSION}"
OLD_TAG="${IMAGE}:previous"

echo ">>> Updating to $CURRENT_TAG ..."

# Pre-update backup
echo ">>> Creating pre-update backup..."
cd "$REPO_ROOT"
"$(dirname "$0")/backup.sh"

# Build
echo ">>> Building $CURRENT_TAG ..."
cd "$REPO_ROOT"
docker build -t "$CURRENT_TAG" .
docker tag "${IMAGE}:latest" "$OLD_TAG" 2>/dev/null || true
docker tag "$CURRENT_TAG" "${IMAGE}:latest"

# Restart
echo ">>> Restarting..."
docker compose -f "$COMPOSE_FILE" up -d
sleep 15

# Health check
docker compose -f "$COMPOSE_FILE" exec -T app python -m scripts.health_check || {
    echo "Health check failed. Rolling back..."
    docker tag "$OLD_TAG" "${IMAGE}:latest"
    docker compose -f "$COMPOSE_FILE" up -d
    exit 1
}

# Post-install
cd "$REPO_ROOT"
python3 -m deployment.checks.post_install || true

echo "Update to $VERSION complete."
echo "Previous image retained as $OLD_TAG for rollback."
