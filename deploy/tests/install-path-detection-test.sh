#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

FUNCTIONS_FILE="$TEMP_DIR/install-functions.sh"
sed '/^main "$@"$/d' "$ROOT_DIR/deploy/install.sh" > "$FUNCTIONS_FILE"

load_install_functions() {
  # shellcheck source=/dev/null
  source "$FUNCTIONS_FILE"
}

CURRENT_LAYOUT="$TEMP_DIR/current-layout"
mkdir -p -- "$CURRENT_LAYOUT/deploy"
printf 'POSTGRES_PASSWORD=test\n' > "$CURRENT_LAYOUT/.env"
printf 'POSTGRES_PASSWORD=legacy-test\n' > "$CURRENT_LAYOUT/deploy/.env"
(
  cd -- "$CURRENT_LAYOUT"
  load_install_functions
  MODE=3
  resolve_upgrade_deploy_dir
  [[ "$DEPLOY_DIR" == "$(pwd -P)" ]]
)

LEGACY_LAYOUT="$TEMP_DIR/legacy-layout"
mkdir -p -- "$LEGACY_LAYOUT/deploy"
printf 'POSTGRES_PASSWORD=test\n' > "$LEGACY_LAYOUT/deploy/.env"
(
  cd -- "$LEGACY_LAYOUT"
  load_install_functions
  MODE=3
  resolve_upgrade_deploy_dir
  [[ "$DEPLOY_DIR" == "$(cd -- deploy && pwd -P)" ]]
)

EXPLICIT_LAYOUT="$TEMP_DIR/explicit layout"
mkdir -p -- "$EXPLICIT_LAYOUT/deploy"
printf 'POSTGRES_PASSWORD=test\n' > "$EXPLICIT_LAYOUT/deploy/.env"
(
  cd -- "$TEMP_DIR"
  load_install_functions
  parse_args --mode 3 --dir "$EXPLICIT_LAYOUT"
  resolve_upgrade_deploy_dir
  [[ "$DEPLOY_DIR" == "$(cd -- "$EXPLICIT_LAYOUT/deploy" && pwd -P)" ]]
)

(
  cd -- "$LEGACY_LAYOUT"
  load_install_functions
  MODE=2
  original_dir="$DEPLOY_DIR"
  resolve_upgrade_deploy_dir
  [[ "$DEPLOY_DIR" == "$original_dir" ]]
)

MISSING_LAYOUT="$TEMP_DIR/missing-layout"
MISSING_OUTPUT="$TEMP_DIR/missing-output.log"
SIDE_EFFECT_LOG="$TEMP_DIR/side-effect.log"
mkdir -p -- "$MISSING_LAYOUT"
if (
  cd -- "$TEMP_DIR"
  load_install_functions
  # shellcheck disable=SC2317
  require_root() { :; }
  # shellcheck disable=SC2317
  detect_platform() { printf 'detect_platform\n' >> "$SIDE_EFFECT_LOG"; }
  # shellcheck disable=SC2317
  ensure_base_dependencies() { printf 'ensure_base_dependencies\n' >> "$SIDE_EFFECT_LOG"; }
  # shellcheck disable=SC2317
  mkdir() { printf 'mkdir\n' >> "$SIDE_EFFECT_LOG"; }
  # shellcheck disable=SC2317
  ensure_docker() { printf 'ensure_docker\n' >> "$SIDE_EFFECT_LOG"; }
  # shellcheck disable=SC2317
  prepare_runtime_files() { printf 'prepare_runtime_files\n' >> "$SIDE_EFFECT_LOG"; }
  main --mode 3 --dir "$MISSING_LAYOUT"
) > "$MISSING_OUTPUT" 2>&1; then
  printf 'missing .env unexpectedly passed deployment directory detection\n' >&2
  exit 1
fi

if ! grep -Fq "未在 $MISSING_LAYOUT 或 $MISSING_LAYOUT/deploy 找到 .env" "$MISSING_OUTPUT"; then
  printf 'missing .env did not report the expected deployment directory error\n' >&2
  cat "$MISSING_OUTPUT" >&2
  exit 1
fi

if [[ -e "$SIDE_EFFECT_LOG" ]]; then
  printf 'deployment side effects ran before rejecting the path:\n' >&2
  cat "$SIDE_EFFECT_LOG" >&2
  exit 1
fi

if [[ -n "$(find "$MISSING_LAYOUT" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  printf 'deployment directory detection wrote files before rejecting the path\n' >&2
  exit 1
fi

printf 'install deployment path detection checks passed\n'
