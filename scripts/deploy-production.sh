#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yaml"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE" >&2
  echo "Run: sh scripts/init-production-env.sh" >&2
  exit 1
fi

cd "$ROOT_DIR"
export PRODUCTION_ENV_FILE="$ENV_FILE"
# Avoid parallel image builds exhausting a 4-GB host.
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

attempt=0
until docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T web \
  wget -qO- http://127.0.0.1/api-health >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 45 ]; then
    echo "Deployment started, but the API did not become healthy in time." >&2
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
    exit 1
  fi
  sleep 2
done

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
echo "Deployment is healthy. Open http://<server-public-ip>/"
