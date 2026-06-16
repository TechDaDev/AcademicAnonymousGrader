#!/bin/bash
# Controlled uninstall — preserves volumes by default
set -eu
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.production.yml"

REMOVE_IMAGES="${1:-}"
REMOVE_DATA="${2:-}"

echo "=== Uninstall Academic Anonymous Grader ==="

# Stop and remove containers
echo ">>> Removing containers..."
docker compose -f "$COMPOSE_FILE" down
echo "  Containers removed. Volumes preserved."

# Remove images
if [ "$REMOVE_IMAGES" = "--remove-images" ]; then
    echo ">>> Removing images..."
    docker rmi "academic-anonymous-grader:latest" 2>/dev/null || true
    docker rmi "academic-anonymous-grader:previous" 2>/dev/null || true
    echo "  Images removed."
fi

# Remove data (DESTRUCTIVE)
if [ "$REMOVE_DATA" = "--remove-data" ]; then
    echo ">>> DESTRUCTIVE: Removing persistent volumes..."
    echo "  This will DELETE ALL DATA."
    read -r -p "Type DELETE DATA to confirm: " CONFIRM
    if [ "$CONFIRM" != "DELETE DATA" ]; then
        echo "Cancelled."
        exit 1
    fi
    docker volume rm grader_data grader_backups grader_exports grader_logs
    echo "  Volumes removed."
fi

echo "Uninstall complete."
