#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

REPO_DIR="$TEMP_DIR/repo"
DEPLOY_DIR="$REPO_DIR/deploy"
FAKE_BIN="$TEMP_DIR/bin"
mkdir -p -- "$DEPLOY_DIR" "$FAKE_BIN"

git -C "$REPO_DIR" init -q -b main
git -C "$REPO_DIR" config user.name "Nova rollback fixture"
git -C "$REPO_DIR" config user.email "nova-rollback-fixture@example.invalid"
printf 'fixture\n' > "$REPO_DIR/tracked.txt"
printf 'POSTGRES_PASSWORD=test\n' > "$DEPLOY_DIR/.env"
printf 'services: {}\n' > "$DEPLOY_DIR/docker-compose.local.yml"
printf 'services: {}\n' > "$DEPLOY_DIR/docker-compose.ghcr.yml"
cp -- "$ROOT_DIR/deploy/update.sh" "$DEPLOY_DIR/update.sh"
git -C "$REPO_DIR" add .
git -C "$REPO_DIR" commit -q -m fixture

STATE_FILE="$TEMP_DIR/deploy-state.json"
python3 - "$STATE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(
        {
            "schema": 1,
            "status": "success",
            "commit": "current-commit",
            "image": "ghcr.io/example/sub2api-nova:current",
            "imageId": "sha256:current-image",
            "rollbackTag": "sub2api-nova:rollback-previous",
            "previousCommit": "previous-commit",
            "previousImage": "ghcr.io/example/sub2api-nova:previous",
        },
        handle,
    )
    handle.write("\n")
PY

cp -- "$ROOT_DIR/deploy/tests/fixtures/fake-docker" "$FAKE_BIN/docker"
chmod +x "$FAKE_BIN/docker" "$DEPLOY_DIR/update.sh"
export FAKE_DOCKER_LOG="$TEMP_DIR/docker.log"
export PATH="$FAKE_BIN:$PATH"
export SUB2API_DEPLOY_STATE_FILE="$STATE_FILE"

bash "$DEPLOY_DIR/update.sh" --rollback > "$TEMP_DIR/output.log"

python3 - "$STATE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    state = json.load(handle)
assert state["status"] == "rollback-success", state
assert state["commit"] == "previous-commit", state
assert state["image"] == "sub2api-nova:rollback-previous", state
assert state["rollbackTag"] == "sub2api-nova:rollback-current-comm", state
PY

if git -C "$REPO_DIR" status --porcelain | grep -q .; then
  printf 'rollback changed the fixture repository\n' >&2
  exit 1
fi

printf 'update rollback behavior checks passed\n'
