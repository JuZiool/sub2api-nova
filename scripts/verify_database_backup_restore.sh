#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:18-alpine}"
CONTAINER_NAME="sub2api-db-restore-${GITHUB_RUN_ID:-local}-$$"
PG_USER="restore_test"
PG_PASSWORD="restore_test_password"
PG_DATABASE="restore_test"
TEMP_ROOT="$(mktemp -d)"
DUMP_FILE="$TEMP_ROOT/database.sql.gz"

log() {
  printf '[数据库恢复验证] %s\n' "$*"
}

die() {
  printf '[数据库恢复验证] 错误：%s\n' "$*" >&2
  exit 1
}

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  rm -rf -- "$TEMP_ROOT"
}

trap cleanup EXIT

require_docker() {
  command -v docker >/dev/null 2>&1 || die "未安装 Docker。"
  docker info >/dev/null 2>&1 || die "Docker 服务未运行，或当前用户无权访问 Docker。"
}

psql_exec() {
  docker exec -e "PGPASSWORD=$PG_PASSWORD" "$CONTAINER_NAME" \
    psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$PG_DATABASE" "$@"
}

wait_for_postgres() {
  local attempt
  for attempt in {1..60}; do
    if docker exec -e "PGPASSWORD=$PG_PASSWORD" "$CONTAINER_NAME" \
      pg_isready -U "$PG_USER" -d "$PG_DATABASE" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  docker logs "$CONTAINER_NAME" >&2 || true
  die "临时 PostgreSQL 未在 120 秒内就绪。"
}

start_postgres() {
  log "启动临时 PostgreSQL 容器：$POSTGRES_IMAGE"
  docker run -d --rm \
    --name "$CONTAINER_NAME" \
    -e POSTGRES_USER="$PG_USER" \
    -e POSTGRES_PASSWORD="$PG_PASSWORD" \
    -e POSTGRES_DB="$PG_DATABASE" \
    "$POSTGRES_IMAGE" >/dev/null
  wait_for_postgres
}

create_test_data() {
  log "创建仅用于恢复验证的测试数据。"
  psql_exec -c "CREATE TABLE backup_restore_probe (id integer PRIMARY KEY, marker text NOT NULL);"
  psql_exec -c "INSERT INTO backup_restore_probe (id, marker) VALUES (1, 'before-backup');"
}

create_backup() {
  log "生成临时逻辑备份：$DUMP_FILE"
  docker exec -e "PGPASSWORD=$PG_PASSWORD" "$CONTAINER_NAME" \
    pg_dump -U "$PG_USER" -d "$PG_DATABASE" | gzip -9 >"$DUMP_FILE"
  [[ -s "$DUMP_FILE" ]] || die "临时逻辑备份为空。"
}

simulate_data_loss() {
  log "删除测试表，模拟需要恢复的数据库状态。"
  psql_exec -c "DROP TABLE backup_restore_probe;"
}

restore_backup() {
  log "从临时逻辑备份恢复数据库。"
  gzip -dc -- "$DUMP_FILE" | docker exec -i -e "PGPASSWORD=$PG_PASSWORD" "$CONTAINER_NAME" \
    psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$PG_DATABASE"
}

verify_restored_data() {
  local marker
  marker="$(psql_exec -Atqc "SELECT marker FROM backup_restore_probe WHERE id = 1;")"
  [[ "$marker" == "before-backup" ]] || die "恢复后的测试数据不匹配：$marker"
  log "恢复验证成功：测试标记数据已恢复。"
}

main() {
  require_docker
  start_postgres
  create_test_data
  create_backup
  simulate_data_loss
  restore_backup
  verify_restored_data
}

main "$@"
