#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repo_root"

gateway_variables=$(mktemp "${TMPDIR:-/tmp}/nova-gateway-env.XXXXXX")
compose_lines=$(mktemp "${TMPDIR:-/tmp}/nova-compose-lines.XXXXXX")
cleanup() {
  rm -f "$gateway_variables" "$compose_lines"
}
trap cleanup EXIT HUP INT TERM

awk '
  /^GATEWAY_[A-Z0-9_]+=/ {
    separator = index($0, "=")
    value = substr($0, separator + 1)
    sub(/\r$/, "", value)
    print substr($0, 1, separator - 1) "\t" value
  }
' deploy/.env.example > "$gateway_variables"
sed 's/\r$//' deploy/docker-compose.local.yml > "$compose_lines"

tab=$(printf '\t')
while IFS="$tab" read -r key value; do
  case "$key" in
    GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED) continue ;;
    GATEWAY_MAX_CONNS_PER_HOST) value=1024 ;;
    GATEWAY_MAX_IDLE_CONNS) value=2560 ;;
    GATEWAY_MAX_IDLE_CONNS_PER_HOST) value=120 ;;
  esac

  # shellcheck disable=SC2016 # The Compose interpolation must remain literal.
  expected=$(printf '      - %s=${%s:-%s}' "$key" "$key" "$value")
  expected_count=$(grep -Fxc "$expected" "$compose_lines" || true)
  key_count=$(grep -Ec "^[[:space:]]*-[[:space:]]*${key}=.*$" "$compose_lines" || true)
  if [ "$expected_count" -ne 1 ] || [ "$key_count" -ne 1 ]; then
    printf 'docker-compose.local.yml must pass %s with the expected fallback exactly once\n' "$key" >&2
    exit 1
  fi
done < "$gateway_variables"

printf 'docker compose Gateway environment test passed\n'
