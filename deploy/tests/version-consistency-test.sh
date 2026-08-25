#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

read_version() {
  tr -d '\r\n' < "$1"
}

fork_version="$(read_version "$ROOT_DIR/FORK_VERSION")"
server_version="$(read_version "$ROOT_DIR/backend/cmd/server/VERSION")"

if [[ -z "$fork_version" || -z "$server_version" ]]; then
  printf 'Nova version files must both be non-empty\n' >&2
  exit 1
fi

if [[ "$fork_version" != "$server_version" ]]; then
  printf 'Nova version files differ: FORK_VERSION=%s server VERSION=%s\n' \
    "$fork_version" "$server_version" >&2
  exit 1
fi

printf 'Nova version files agree: %s\n' "$fork_version"
