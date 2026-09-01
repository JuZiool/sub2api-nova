#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_STATE_FILE="${SUB2API_DEPLOY_STATE_FILE:-$SCRIPT_DIR/.deploy-state.json}"
UPDATE_LOCK_FILE="${SUB2API_UPDATE_LOCK_FILE:-$SCRIPT_DIR/.update.lock}"
DEFAULT_IMAGE="ghcr.io/juziool/sub2api-nova:latest"
HEALTH_TIMEOUT="${SUB2API_HEALTH_TIMEOUT:-180}"
COMPOSE_MODE=""
COMPOSE_COMMAND_LABEL="docker compose"
ROLLBACK=false
PRUNE_CACHE=false
TEMP_FILES=()

log() { printf '[Sub2API 更新] %s\n' "$*"; }
warn() { printf '[Sub2API 更新] 警告：%s\n' "$*" >&2; }
die() { printf '[Sub2API 更新] 错误：%s\n' "$*" >&2; exit 1; }
cleanup() { local file; for file in "${TEMP_FILES[@]}"; do rm -f -- "$file"; done; }
trap cleanup EXIT

usage() {
  cat <<'EOF'
Sub2API Nova 镜像更新脚本

用法：
  cd /部署目录 && bash update.sh

选项：
  --rollback     回滚到上一次成功更新前的应用镜像
  --prune-cache  更新成功后清理超过 7 天的构建缓存
  -h, --help     显示帮助

环境变量：
  SUB2API_IMAGE              指定镜像 tag 或 digest
  SUB2API_HEALTH_TIMEOUT     健康检查超时秒数，默认 180
  SUB2API_DEPLOY_STATE_FILE  部署状态文件路径
  SUB2API_UPDATE_LOCK_FILE   更新锁文件路径
EOF
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --rollback) ROLLBACK=true; shift ;;
      --prune-cache) PRUNE_CACHE=true; shift ;;
      -h | --help) usage; exit 0 ;;
      *) die "未知选项：$1" ;;
    esac
  done
}

require_files() {
  [[ -f "$SCRIPT_DIR/.env" ]] || die "缺少 .env，请先完成安装。"
  [[ -f "$SCRIPT_DIR/docker-compose.local.yml" ]] || die "缺少 docker-compose.local.yml。"
  [[ -f "$SCRIPT_DIR/docker-compose.ghcr.yml" ]] || die "缺少 docker-compose.ghcr.yml。"
  command -v flock >/dev/null 2>&1 || die "未安装 flock，无法防止并发更新。"
}

detect_docker_compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_MODE="plugin"
    COMPOSE_COMMAND_LABEL="docker compose"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    COMPOSE_MODE="standalone"
    COMPOSE_COMMAND_LABEL="docker-compose"
    return 0
  fi
  return 1
}

docker_compose() {
  case "$COMPOSE_MODE" in
    plugin) docker compose "$@" ;;
    standalone) docker-compose "$@" ;;
    *) die "未检测到 Docker Compose。" ;;
  esac
}

compose() {
  (
    cd -- "$SCRIPT_DIR"
    docker_compose --env-file .env \
      -f docker-compose.local.yml \
      -f docker-compose.ghcr.yml \
      "$@"
  )
}

read_env_value() {
  local key="$1" fallback="$2" value=""
  value="$(sed -n "s/^${key}=//p" "$SCRIPT_DIR/.env" | tail -n 1 | tr -d '\r')"
  value="${value#\"}"; value="${value%\"}"; value="${value#\'}"; value="${value%\'}"
  printf '%s' "${value:-$fallback}"
}

state_value() {
  local key="$1" value
  [[ -f "$DEPLOY_STATE_FILE" ]] || return 0
  value="$(tr '\n' ' ' < "$DEPLOY_STATE_FILE" | sed -nE 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p')"
  printf '%s' "$value"
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

write_state() {
  local status="$1" image="$2" image_id="$3" rollback_tag="$4" previous_image="$5" error_message="${6:-}"
  local target temp
  target="$DEPLOY_STATE_FILE"
  temp="$(mktemp "${target}.tmp.XXXXXX")"
  TEMP_FILES+=("$temp")
  mkdir -p -- "$(dirname -- "$target")"
  {
    printf '{\n'
    printf '  "schema": 1,\n'
    printf '  "status": "%s",\n' "$(json_escape "$status")"
    printf '  "image": "%s",\n' "$(json_escape "$image")"
    printf '  "imageId": "%s",\n' "$(json_escape "$image_id")"
    printf '  "rollbackTag": "%s",\n' "$(json_escape "$rollback_tag")"
    printf '  "previousImage": "%s",\n' "$(json_escape "$previous_image")"
    printf '  "recordedAt": "%s",\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf '  "error": "%s"\n' "$(json_escape "$error_message")"
    printf '}\n'
  } >"$temp"
  chmod 600 "$temp"
  mv -f -- "$temp" "$target"
}

wait_for_application() {
  local port deadline
  port="$(read_env_value SERVER_PORT 8080)"
  deadline=$((SECONDS + HEALTH_TIMEOUT))
  local container_id health
  log "等待应用健康检查：http://127.0.0.1:${port}/health"
  while ((SECONDS < deadline)); do
    container_id="$(compose ps -q sub2api 2>/dev/null || true)"
    if [[ -n "$container_id" ]]; then
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
      [[ "$health" == "healthy" ]] && return 0
      [[ "$health" == "unhealthy" || "$health" == "exited" || "$health" == "dead" ]] && break
    fi
    sleep 3
  done
  compose ps >&2 || true
  compose logs --tail=200 sub2api >&2 || true
  return 1
}

rollback_application() {
  local image
  image="$(state_value rollbackTag)"
  [[ -n "$image" ]] || die "没有可用的回滚镜像。"
  docker image inspect "$image" >/dev/null 2>&1 || die "本地不存在回滚镜像：$image"
  log "回滚到应用镜像：$image"
  SUB2API_IMAGE="$image" compose up -d --no-build --force-recreate sub2api || die "回滚容器启动失败。"
  wait_for_application || die "回滚后健康检查失败。"
  write_state "rollback-success" "$image" "$(docker image inspect -q "$image")" "" "$(state_value image)"
}

upgrade_application() {
  local image old_id old_image rollback_tag
  image="${SUB2API_IMAGE:-$(read_env_value SUB2API_IMAGE "$DEFAULT_IMAGE")}"
  old_id="$(compose images -q sub2api 2>/dev/null | head -n 1 || true)"
  old_image="$(compose images --format '{{.Repository}}:{{.Tag}}' sub2api 2>/dev/null | head -n 1 || true)"
  [[ -n "$old_id" ]] || old_id="$(state_value imageId)"
  [[ -n "$old_image" ]] || old_image="$(state_value image)"
  rollback_tag=""
  if [[ -n "$old_id" ]]; then
    rollback_tag="sub2api-nova:rollback-$(date +%Y%m%d%H%M%S)"
    docker tag "$old_id" "$rollback_tag" || rollback_tag=""
  fi

  export SUB2API_IMAGE="$image"
  log "拉取应用镜像：$SUB2API_IMAGE"
  compose config --quiet
  compose pull sub2api || {
    write_state "failed" "$old_image" "$old_id" "$rollback_tag" "$old_image" "镜像拉取失败"
    die "镜像拉取失败。"
  }
  if ! compose up -d --force-recreate --remove-orphans sub2api || ! wait_for_application; then
    warn "应用升级失败。"
    if [[ -n "$rollback_tag" ]]; then
      SUB2API_IMAGE="$rollback_tag" compose up -d --no-build --force-recreate sub2api || true
      if wait_for_application; then
        write_state "failed-recovered" "$old_image" "$old_id" "" "$old_image" "应用升级失败，已恢复旧镜像"
        die "升级失败，已恢复旧镜像。"
      fi
    fi
    write_state "failed" "$image" "" "$rollback_tag" "$old_image" "应用升级失败"
    die "升级失败，旧镜像无法自动恢复。"
  fi
  write_state "success" "$image" "$(compose images -q sub2api 2>/dev/null | head -n 1 || true)" "$rollback_tag" "$old_image"
  [[ "$PRUNE_CACHE" == true ]] && docker builder prune -f --filter 'until=168h'
}

main() {
  parse_args "$@"
  require_files
  detect_docker_compose || die "未检测到 Docker Compose。"
  docker info >/dev/null 2>&1 || die "Docker 服务未运行，或当前用户无权访问 Docker。"
  mkdir -p -- "$(dirname -- "$UPDATE_LOCK_FILE")"
  exec 9>"$UPDATE_LOCK_FILE"
  flock -n 9 || die "另一个安装或升级任务正在运行。"
  if [[ "$ROLLBACK" == true ]]; then
    rollback_application
  else
    upgrade_application
  fi
  printf '\n'
  log "操作完成"
  log "部署目录：$SCRIPT_DIR"
  log "查看状态：cd $SCRIPT_DIR && $COMPOSE_COMMAND_LABEL --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml ps"
}

main "$@"
