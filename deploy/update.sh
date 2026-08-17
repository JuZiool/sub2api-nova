#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
BRANCH="${SUB2API_BRANCH:-main}"
HEALTH_TIMEOUT="${SUB2API_HEALTH_TIMEOUT:-180}"
PRUNE_CACHE=false
LOCAL_BUILD=false
COMPOSE_OVERLAY="docker-compose.ghcr.yml"
OLD_IMAGE_ID=""

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
  --prune-cache  更新成功后清理超过 7 天的 Docker 构建缓存
  -h, --help     显示帮助

环境变量：
  SUB2API_BRANCH          更新分支，默认 main
  SUB2API_HEALTH_TIMEOUT  健康检查超时秒数，默认 180
  SUB2API_IMAGE           自定义预构建镜像；默认使用当前提交对应的 GHCR 镜像
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
  docker compose version >/dev/null 2>&1 || die "未安装 Docker Compose v2。"
  docker info >/dev/null 2>&1 || die "Docker 服务未运行，或当前用户无权访问 Docker。"
  git check-ref-format --branch "$BRANCH" >/dev/null 2>&1 || die "无效的 Git 分支名称：$BRANCH"
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
          return
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
  die "应用未在 ${HEALTH_TIMEOUT} 秒内通过健康检查。"
}

remove_previous_image() {
  local new_image_id

  [[ -n "$OLD_IMAGE_ID" ]] || return 0
  new_image_id="$(compose images -q sub2api 2>/dev/null | head -n 1 || true)"
  [[ -n "$new_image_id" && "$new_image_id" != "$OLD_IMAGE_ID" ]] || return 0

  if ! docker image inspect "$OLD_IMAGE_ID" >/dev/null 2>&1; then
    log "上一版应用镜像已由 Docker 自动回收。"
    return 0
  fi

  if docker image rm "$OLD_IMAGE_ID" >/dev/null 2>&1; then
    log "已删除被替换的上一版应用镜像。"
  else
    warn "上一版应用镜像仍被其他容器使用，已保留。"
  fi
}

deploy_application() {
  export BUILD_COMMIT
  export SUB2API_IMAGE
  BUILD_COMMIT="$(repo_git rev-parse --short HEAD)"
  SUB2API_IMAGE="${SUB2API_IMAGE:-ghcr.io/juziool/sub2api-nova:sha-$(repo_git rev-parse HEAD)}"
  OLD_IMAGE_ID="$(compose images -q sub2api 2>/dev/null | head -n 1 || true)"

  log "校验 Docker Compose 配置。"
  compose config --quiet

  if [[ "$LOCAL_BUILD" == true ]]; then
    log "使用本地构建缓存更新应用容器。"
    compose up -d --build sub2api
  else
    log "拉取预构建镜像：$SUB2API_IMAGE"
    if ! compose pull sub2api; then
      die "镜像尚未发布或 GHCR 无法访问。请确认 GitHub Actions 已完成后重试，或使用 --build 在服务器本地构建。"
    fi
    compose up -d sub2api
  fi
  wait_for_application
  remove_previous_image

  if [[ "$PRUNE_CACHE" == true ]]; then
    log "清理超过 7 天的 Docker 构建缓存。"
    docker builder prune -f --filter 'until=168h'
  fi
}

print_result() {
  local commit
  commit="$(repo_git rev-parse --short HEAD)"

  printf '\n'
  log "更新完成，当前版本：$commit"
  compose ps
}

main() {
  parse_args "$@"
  ensure_requirements
  ensure_clean_worktree
  update_repository
  deploy_application
  print_result
}

main "$@"
