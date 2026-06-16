#!/bin/bash
# Status check — no secrets or academic data
set -eu
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.production.yml"

echo "=== Academic Anonymous Grader — Status ==="

# Container
PS=$(docker compose -f "$COMPOSE_FILE" ps --format '{{.Name}} {{.Status}}' 2>/dev/null || echo "NOT RUNNING")
echo "Container: $PS"

# Health
HEALTH=$(docker compose -f "$COMPOSE_FILE" exec -T app python -m scripts.health_check 2>/dev/null | grep "healthy" || echo "UNKNOWN")
echo "Health:    $HEALTH"

# Version
VERSION_FILE="$REPO_ROOT/VERSION"
if [ -f "$VERSION_FILE" ]; then
    echo "Version:   $(cat "$VERSION_FILE")"
fi

# Schema
SCHEMA=$(docker compose -f "$COMPOSE_FILE" exec -T app python -c "from database.migrations import SCHEMA_VERSION; print(SCHEMA_VERSION)" 2>/dev/null || echo "?")
echo "Schema:    v$SCHEMA"

# Port
(echo >/dev/tcp/127.0.0.1/8501) 2>/dev/null && echo "Port 8501: OPEN" || echo "Port 8501: CLOSED"

# Volumes
VOLUMES=$(docker volume ls --filter name=grader --format '{{.Name}}' 2>/dev/null | tr '\n' ', ' || echo "none")
echo "Volumes:   $VOLUMES"

echo "================================"
