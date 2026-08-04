#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEMPLATE="$ROOT_DIR/deploy/production.env.example"
TARGET="${1:-$ROOT_DIR/.env.production}"

if [ -e "$TARGET" ]; then
  echo "Refusing to overwrite existing $TARGET" >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required to generate production secrets" >&2
  exit 1
fi

cp "$TEMPLATE" "$TARGET"
DB_PASSWORD=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 48)
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$DB_PASSWORD/" "$TARGET"
sed -i "s/^AUTH_JWT_SECRET=.*/AUTH_JWT_SECRET=$JWT_SECRET/" "$TARGET"
chmod 600 "$TARGET"

echo "Created $TARGET with generated database and JWT secrets."
echo "Fill the required AI API keys before deploying."
