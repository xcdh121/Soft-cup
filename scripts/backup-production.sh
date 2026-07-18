#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yaml"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DEST="$BACKUP_ROOT/$STAMP"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

mkdir -p "$DEST"
chmod 700 "$BACKUP_ROOT" "$DEST"
cd "$ROOT_DIR"
export PRODUCTION_ENV_FILE="$ENV_FILE"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
  sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
  > "$DEST/database.dump"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
  tar -C /app/.localdata -czf - . > "$DEST/storage.tar.gz"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$DEST" && sha256sum database.dump storage.tar.gz > SHA256SUMS)
fi

echo "Backup created at $DEST"
