#!/bin/bash
set -eu
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.production.yml"
cd "$REPO_ROOT"
docker compose -f "$COMPOSE_FILE" stop
echo "Application stopped. Volumes preserved."
