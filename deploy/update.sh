#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
BRANCH="${SUB2API_BRANCH:-main}"
HEALTH_TIMEOUT="${SUB2API_HEALTH_TIMEOUT:-180}"
DEPLOY_STATE_FILE="${SUB2API_DEPLOY_STATE_FILE:-$SCRIPT_DIR/.deploy-state.json}"
PRUNE_CACHE=false
LOCAL_BUILD=false
ROLLBACK=false
COMPOSE_OVERLAY="docker-compose.ghcr.yml"
OLD_IMAGE_ID=""
OLD_IMAGE_REF=""
OLD_ROLLBACK_TAG=""
NEW_IMAGE_REF=""
PREVIOUS_COMMIT=""
CURRENT_COMMIT=""

log() {
  printf '[Sub2API 更新] %s\n' "$*"
}

warn() {
  printf '[Sub2API 更新] 警告：%s\n' "$*" >&2
}

die() {
  printf '[Sub2API 更新] 错误：%s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Sub2API Nova 服务器更新脚本

用法：
  bash deploy/update.sh [选项]

选项：
  --build        不拉取 GHCR 镜像，改为在服务器从源码构建
  --rollback     使用上一次成功更新保留的本地镜像回滚，不修改 Git 或数据库
  --prune-cache  更新成功后清理超过 7 天的 Docker 构建缓存
  -h, --help     显示帮助

环境变量：
  SUB2API_BRANCH          更新分支，默认 main
  SUB2API_HEALTH_TIMEOUT  健康检查超时秒数，默认 180
  SUB2API_IMAGE           自定义预构建镜像；默认使用当前提交对应的 GHCR 镜像
  SUB2API_DEPLOY_STATE_FILE  部署状态文件，默认 deploy/.deploy-state.json
EOF
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --build)
        LOCAL_BUILD=true
        COMPOSE_OVERLAY="docker-compose.nova.yml"
        shift
        ;;
      --rollback)
        ROLLBACK=true
        shift
        ;;
      --prune-cache)
        PRUNE_CACHE=true
        shift
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        die "未知选项：$1"
        ;;
    esac
  done
}

repo_git() {
  git -c safe.directory="$REPO_DIR" -C "$REPO_DIR" "$@"
}

compose() {
  (
    cd -- "$SCRIPT_DIR"
    docker compose \
      --env-file .env \
      -f docker-compose.local.yml \
      -f "$COMPOSE_OVERLAY" \
      "$@"
  )
}

ensure_requirements() {
  [[ -d "$REPO_DIR/.git" ]] || die "项目目录不是 Git 仓库：$REPO_DIR"
  [[ -f "$SCRIPT_DIR/.env" ]] || die "缺少 $SCRIPT_DIR/.env，请先完成首次安装。"
  [[ -f "$SCRIPT_DIR/$COMPOSE_OVERLAY" ]] || die "缺少 Compose 配置：$SCRIPT_DIR/$COMPOSE_OVERLAY"
  [[ "$HEALTH_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "健康检查超时必须是正整数。"

  command -v git >/dev/null 2>&1 || die "未安装 Git。"
  command -v docker >/dev/null 2>&1 || die "未安装 Docker。"
  command -v python3 >/dev/null 2>&1 || die "未安装 Python 3，无法写入部署状态。"
  docker compose version >/dev/null 2>&1 || die "未安装 Docker Compose v2。"
  docker info >/dev/null 2>&1 || die "Docker 服务未运行，或当前用户无权访问 Docker。"
  if [[ "$ROLLBACK" != true ]]; then
    git check-ref-format --branch "$BRANCH" >/dev/null 2>&1 || die "无效的 Git 分支名称：$BRANCH"
  fi
}

write_deploy_state() {
  local status="$1"
  local commit="$2"
  local image="$3"
  local image_id="$4"
  local rollback_tag="$5"
  local error_message="${6:-}"
  local previous_commit="${7:-}"
  local previous_image="${8:-}"
  mkdir -p -- "$(dirname -- "$DEPLOY_STATE_FILE")"
  python3 - "$DEPLOY_STATE_FILE" "$status" "$commit" "$image" "$image_id" "$rollback_tag" "$error_message" "$previous_commit" "$previous_image" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

(
    path,
    status,
    commit,
    image,
    image_id,
    rollback_tag,
    error_message,
    previous_commit,
    previous_image,
) = sys.argv[1:]
record = {
    "schema": 1,
    "status": status,
    "commit": commit,
    "image": image,
    "imageId": image_id,
    "rollbackTag": rollback_tag,
    "previousCommit": previous_commit,
    "previousImage": previous_image,
    "recordedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "error": error_message,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(record, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
os.chmod(path, 0o600)
PY
}

read_state_value() {
  local key="$1"
  [[ -f "$DEPLOY_STATE_FILE" ]] || die "缺少部署状态文件：$DEPLOY_STATE_FILE"
  python3 - "$DEPLOY_STATE_FILE" "$key" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle).get(sys.argv[2], "")
if not isinstance(value, str):
    raise SystemExit(1)
print(value)
PY
}

read_state_value_optional() {
  local key="$1"
  [[ -f "$DEPLOY_STATE_FILE" ]] || return 0
  python3 - "$DEPLOY_STATE_FILE" "$key" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle).get(sys.argv[2], "")
if not isinstance(value, str):
    raise SystemExit(1)
print(value)
PY
}

ignore_nas_filemode_changes() {
  local changes
  local summary
  local content_changes
  local staged_changes
  local untracked_changes

  changes="$(repo_git status --porcelain --untracked-files=normal)"
  [[ -n "$changes" ]] || return 0

  summary="$(repo_git diff --summary)"
  content_changes="$(repo_git diff --numstat)"
  staged_changes="$(repo_git diff --cached --name-only)"
  untracked_changes="$(repo_git ls-files --others --exclude-standard)"

  if [[ -n "$summary" && -z "$content_changes" && -z "$staged_changes" && -z "$untracked_changes" ]] && \
    ! grep -Ev '^ mode change [0-9]+ => [0-9]+ .+$' <<<"$summary" | grep -q .; then
    log "检测到 NAS 文件权限位差异，已为当前仓库忽略 filemode。"
    repo_git config core.filemode false
  fi
}

ensure_clean_worktree() {
  local changes

  ignore_nas_filemode_changes
  changes="$(repo_git status --porcelain --untracked-files=normal)"
  if [[ -n "$changes" ]]; then
    printf '%s\n' "$changes" >&2
    die "检测到未提交的源码修改，为避免覆盖已停止更新。"
  fi
}

update_repository() {
  local current_branch

  current_branch="$(repo_git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  [[ -n "$current_branch" ]] || die "当前仓库处于 detached HEAD 状态。"
  [[ "$current_branch" == "$BRANCH" ]] || die "当前分支为 $current_branch，请先切换到 $BRANCH。"

  log "拉取 $BRANCH 分支最新代码。"
  repo_git fetch --prune origin "$BRANCH"
  repo_git merge --ff-only "origin/$BRANCH"
}

wait_for_application() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  local container_id
  local health

  log "等待应用健康检查，最长 ${HEALTH_TIMEOUT} 秒。"
  while ((SECONDS < deadline)); do
    container_id="$(compose ps -q sub2api 2>/dev/null || true)"
    if [[ -n "$container_id" ]]; then
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
      case "$health" in
        healthy)
          return 0
          ;;
        unhealthy | exited | dead)
          break
          ;;
      esac
    fi
    sleep 2
  done

  compose ps >&2 || true
  compose logs --tail=200 sub2api >&2 || true
  return 1
}

preserve_previous_image() {
  [[ -n "$OLD_IMAGE_ID" ]] || return 0
  OLD_ROLLBACK_TAG="sub2api-nova:rollback-${PREVIOUS_COMMIT:0:12}"
  [[ -n "$PREVIOUS_COMMIT" ]] || OLD_ROLLBACK_TAG="sub2api-nova:rollback-previous"
  docker tag "$OLD_IMAGE_ID" "$OLD_ROLLBACK_TAG"
  log "已保留上一版镜像回滚标签：$OLD_ROLLBACK_TAG"
}

restore_previous_image() {
  [[ -n "$OLD_ROLLBACK_TAG" ]] || return 1
  log "正在恢复上一版应用镜像：$OLD_ROLLBACK_TAG"
  SUB2API_IMAGE="$OLD_ROLLBACK_TAG" compose up -d --no-build --force-recreate sub2api
  if wait_for_application; then
    log "上一版应用镜像已恢复并通过健康检查。"
    return 0
  fi
  warn "上一版应用镜像恢复后仍未通过健康检查。"
  return 1
}

handle_deploy_failure() {
  local error_message="$1"
  local recovered=false
  warn "$error_message"
  if [[ -n "$OLD_ROLLBACK_TAG" ]] && restore_previous_image; then
    recovered=true
  fi
  write_deploy_state \
    "failed" \
    "$CURRENT_COMMIT" \
    "$NEW_IMAGE_REF" \
    "$(compose images -q sub2api 2>/dev/null | head -n 1 || true)" \
    "$OLD_ROLLBACK_TAG" \
    "$error_message" \
    "$PREVIOUS_COMMIT" \
    "$OLD_IMAGE_REF"
  if [[ "$recovered" == true ]]; then
    die "更新失败，已恢复上一版应用镜像。"
  fi
  die "更新失败，且上一版应用镜像无法恢复。"
}

deploy_application() {
  export BUILD_COMMIT
  export SUB2API_IMAGE
  CURRENT_COMMIT="$(repo_git rev-parse HEAD)"
  BUILD_COMMIT="${CURRENT_COMMIT:0:7}"
  NEW_IMAGE_REF="${SUB2API_IMAGE:-ghcr.io/juziool/sub2api-nova:sha-${CURRENT_COMMIT}}"
  SUB2API_IMAGE="$NEW_IMAGE_REF"
  OLD_IMAGE_ID="$(compose images -q sub2api 2>/dev/null | head -n 1 || true)"
  OLD_IMAGE_REF="$(compose images --format '{{.Repository}}:{{.Tag}}' sub2api 2>/dev/null | head -n 1 || true)"
  case "$(read_state_value_optional status)" in
    failed | rollback-failed)
      PREVIOUS_COMMIT="$(read_state_value_optional previousCommit)"
      ;;
    *)
      PREVIOUS_COMMIT="$(read_state_value_optional commit)"
      ;;
  esac
  preserve_previous_image

  log "校验 Docker Compose 配置。"
  if ! compose config --quiet; then
    handle_deploy_failure "Docker Compose 配置校验失败。"
  fi

  if [[ "$LOCAL_BUILD" == true ]]; then
    log "使用本地构建缓存更新应用容器。"
    if ! compose up -d --build sub2api; then
      handle_deploy_failure "本地构建或启动应用容器失败。"
    fi
  else
    log "拉取预构建镜像：$SUB2API_IMAGE"
    if ! compose pull sub2api; then
      handle_deploy_failure "镜像尚未发布或 GHCR 无法访问。"
    fi
    if ! compose up -d sub2api; then
      handle_deploy_failure "预构建镜像启动失败。"
    fi
  fi
  if ! wait_for_application; then
    handle_deploy_failure "应用未在 ${HEALTH_TIMEOUT} 秒内通过健康检查。"
  fi

  write_deploy_state \
    "success" \
    "$CURRENT_COMMIT" \
    "$NEW_IMAGE_REF" \
    "$(compose images -q sub2api 2>/dev/null | head -n 1 || true)" \
    "$OLD_ROLLBACK_TAG" \
    "" \
    "$PREVIOUS_COMMIT" \
    "$OLD_IMAGE_REF"

  if [[ "$PRUNE_CACHE" == true ]]; then
    log "清理超过 7 天的 Docker 构建缓存。"
    docker builder prune -f --filter 'until=168h'
  fi
}

rollback_application() {
  local rollback_tag
  local rollback_commit
  local current_commit
  local current_image
  local current_image_id
  local next_rollback_tag
  local rollback_image_id

  rollback_tag="$(read_state_value rollbackTag)"
  rollback_commit="$(read_state_value_optional previousCommit)"
  current_commit="$(read_state_value commit)"
  current_image="$(read_state_value image)"
  [[ -n "$rollback_tag" ]] || die "部署状态中没有可用的回滚镜像标签。"
  [[ -n "$rollback_commit" ]] || rollback_commit="unknown"
  [[ -n "$current_commit" ]] || current_commit="unknown"
  docker image inspect "$rollback_tag" >/dev/null 2>&1 || die "本地不存在回滚镜像：$rollback_tag"

  current_image_id="$(compose images -q sub2api 2>/dev/null | head -n 1 || true)"
  next_rollback_tag="sub2api-nova:rollback-${current_commit:0:12}"
  if [[ -n "$current_image_id" && "$current_image_id" != "$(docker image inspect -q "$rollback_tag" 2>/dev/null || true)" ]]; then
    docker tag "$current_image_id" "$next_rollback_tag"
  fi
  rollback_image_id="$(docker image inspect -q "$rollback_tag")"

  log "回滚到提交 ${rollback_commit:0:7}，不修改 Git 或数据库。"
  export SUB2API_IMAGE="$rollback_tag"
  if ! compose config --quiet; then
    write_deploy_state "rollback-failed" "$rollback_commit" "$rollback_tag" "$rollback_image_id" "$next_rollback_tag" "回滚 Compose 配置校验失败。" "$current_commit" "$current_image"
    die "回滚 Compose 配置校验失败。"
  fi
  if ! compose up -d --no-build --force-recreate sub2api; then
    write_deploy_state "rollback-failed" "$rollback_commit" "$rollback_tag" "$rollback_image_id" "$next_rollback_tag" "回滚容器启动失败。" "$current_commit" "$current_image"
    die "回滚容器启动失败。"
  fi
  if ! wait_for_application; then
    write_deploy_state "rollback-failed" "$rollback_commit" "$rollback_tag" "$rollback_image_id" "$next_rollback_tag" "回滚后健康检查失败。" "$current_commit" "$current_image"
    die "回滚后健康检查失败。"
  fi
  write_deploy_state "rollback-success" "$rollback_commit" "$rollback_tag" "$rollback_image_id" "$next_rollback_tag" "" "$current_commit" "$current_image"
  log "回滚完成，当前应用镜像：$rollback_tag"
}

print_result() {
  local commit
  local image
  commit="$(repo_git rev-parse --short HEAD)"
  image="$(read_state_value_optional image)"

  printf '\n'
  log "操作完成，Git 提交：$commit"
  if [[ -n "$image" ]]; then
    log "当前应用镜像：$image"
  fi
  compose ps
}

main() {
  parse_args "$@"
  ensure_requirements
  if [[ "$ROLLBACK" == true ]]; then
    rollback_application
    print_result
    return
  fi
  ensure_clean_worktree
  update_repository
  deploy_application
  print_result
}

main "$@"
