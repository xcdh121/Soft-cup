#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: RESTORE_CONFIRM=restore-production sh scripts/restore-production.sh <backup-directory>" >&2
  exit 1
fi
if [ "${RESTORE_CONFIRM:-}" != "restore-production" ]; then
  echo "Restore replaces the current database and uploaded files." >&2
  echo "Set RESTORE_CONFIRM=restore-production to continue." >&2
  exit 1
fi

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yaml"
SOURCE=$(CDPATH= cd -- "$1" && pwd)

test -f "$SOURCE/database.dump"
test -f "$SOURCE/storage.tar.gz"
cd "$ROOT_DIR"
export PRODUCTION_ENV_FILE="$ENV_FILE"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" stop web api worker
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  sh -c 'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' \
  < "$SOURCE/database.dump"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm -T --no-deps api \
  sh -c 'find /app/.localdata -mindepth 1 -delete && tar -C /app/.localdata -xzf -' \
  < "$SOURCE/storage.tar.gz"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d api worker web
echo "Restore completed from $SOURCE"
