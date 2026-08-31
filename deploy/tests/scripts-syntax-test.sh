#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

scripts=(
  "$ROOT_DIR/deploy/install.sh"
  "$ROOT_DIR/deploy/setup.sh"
  "$ROOT_DIR/deploy/update.sh"
  "$ROOT_DIR/deploy/docker-entrypoint.sh"
  "$ROOT_DIR/scripts/verify_database_backup_restore.sh"
  "$ROOT_DIR/backend/scripts/resolve-version.sh"
  "$ROOT_DIR/deploy/tests/docker-compose-gateway-env-test.sh"
  "$ROOT_DIR/deploy/tests/install-path-detection-test.sh"
  "$ROOT_DIR/deploy/tests/version-consistency-test.sh"
)

for script in "${scripts[@]}"; do
  bash -n "$script"
done

printf 'shell syntax checks passed (%d files)\n' "${#scripts[@]}"
