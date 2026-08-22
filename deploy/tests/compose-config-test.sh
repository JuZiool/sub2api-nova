#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

cat > "$TEMP_DIR/.env" <<'EOF'
POSTGRES_PASSWORD=compose-test-postgres-password
POSTGRES_USER=compose_test
POSTGRES_DB=compose_test
BIND_HOST=127.0.0.1
SERVER_PORT=18081
SUB2API_IMAGE=sub2api-nova:compose-test
BUILD_COMMIT=compose-test
EOF

for overlay in docker-compose.nova.yml docker-compose.ghcr.yml; do
  docker compose \
    --project-name "nova-compose-config-test-${RANDOM}" \
    --env-file "$TEMP_DIR/.env" \
    -f "$ROOT_DIR/deploy/docker-compose.local.yml" \
    -f "$ROOT_DIR/deploy/$overlay" \
    config --quiet
done

printf 'compose configuration checks passed\n'
