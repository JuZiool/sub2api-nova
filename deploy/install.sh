#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

readonly DEFAULT_REPO_URL="https://github.com/JuZiool/sub2api-nova.git"
readonly DEFAULT_INSTALL_DIR="/opt/sub2api-nova"
readonly DEFAULT_BRANCH="main"
readonly DEFAULT_HEALTH_TIMEOUT=180

REPO_URL="${SUB2API_REPO_URL:-$DEFAULT_REPO_URL}"
INSTALL_DIR="${SUB2API_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
BRANCH="${SUB2API_BRANCH:-$DEFAULT_BRANCH}"
HEALTH_TIMEOUT="${SUB2API_HEALTH_TIMEOUT:-$DEFAULT_HEALTH_TIMEOUT}"
INSTALL_DIR_EXPLICIT=false
UPDATE_ONLY=false
BACKUP_ENABLED=true
DOCKER_INSTALL_ENABLED=true
LOCK_FILE="/var/lock/sub2api-nova-install.lock"
TEMP_FILES=()
DEPLOY_DIR=""
ACCESS_PORT=""

if [[ -n "${SUB2API_INSTALL_DIR:-}" ]]; then
  INSTALL_DIR_EXPLICIT=true
fi

log() {
  printf '[Sub2API] %s\n' "$*"
}

warn() {
  printf '[Sub2API] 警告：%s\n' "$*" >&2
}

die() {
  printf '[Sub2API] 错误：%s\n' "$*" >&2
  exit 1
}

cleanup() {
  local file
  for file in "${TEMP_FILES[@]}"; do
    rm -f -- "$file"
  done
}

on_error() {
  local exit_code="$1"
  local line_number="$2"
  printf '[Sub2API] 错误：命令执行失败（退出码 %s，行号 %s）。\n' "$exit_code" "$line_number" >&2
  exit "$exit_code"
}

trap cleanup EXIT
trap 'on_error "$?" "$LINENO"' ERR

usage() {
  cat <<'EOF'
Sub2API Nova Linux 一键安装与更新脚本

用法：
  install.sh [选项]

选项：
  --dir <路径>          安装目录，并跳过交互询问
  --repo <地址>         Git 仓库地址
  --branch <名称>       部署分支，默认 main
  --health-timeout <秒> 健康检查超时，默认 180
  --update-only         仅更新，目标目录不存在时退出
  --no-backup           更新前不执行 PostgreSQL 逻辑备份
  --no-install-docker   Docker 缺失时不自动安装
  -h, --help            显示帮助

环境变量：
  SUB2API_INSTALL_DIR
  SUB2API_REPO_URL
  SUB2API_BRANCH
  SUB2API_HEALTH_TIMEOUT
EOF
}

require_option_value() {
  local option="$1"
  local count="$2"
  ((count >= 2)) || die "$option 需要提供参数。"
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --dir)
        require_option_value "$1" "$#"
        INSTALL_DIR="$2"
        INSTALL_DIR_EXPLICIT=true
        shift 2
        ;;
      --repo)
        require_option_value "$1" "$#"
        REPO_URL="$2"
        shift 2
        ;;
      --branch)
        require_option_value "$1" "$#"
        BRANCH="$2"
        shift 2
        ;;
      --health-timeout)
        require_option_value "$1" "$#"
        HEALTH_TIMEOUT="$2"
        shift 2
        ;;
      --update-only)
        UPDATE_ONLY=true
        shift
        ;;
      --no-backup)
        BACKUP_ENABLED=false
        shift
        ;;
      --no-install-docker)
        DOCKER_INSTALL_ENABLED=false
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

prompt_install_dir() {
  local value=""

  [[ "$INSTALL_DIR_EXPLICIT" == false ]] || return 0

  if [[ -t 0 ]]; then
    read -r -p "安装位置（绝对路径）[$DEFAULT_INSTALL_DIR]: " value
  elif [[ -c /dev/tty ]]; then
    if ! read -r -p "安装位置（绝对路径）[$DEFAULT_INSTALL_DIR]: " value </dev/tty; then
      warn "无法从终端读取安装位置，将使用默认路径 $DEFAULT_INSTALL_DIR。"
    fi
  else
    warn "未检测到交互式终端，将使用默认路径 $DEFAULT_INSTALL_DIR。"
  fi

  INSTALL_DIR="${value:-$DEFAULT_INSTALL_DIR}"
}

validate_settings() {
  [[ "$INSTALL_DIR" == /* ]] || die "安装目录必须是绝对路径：$INSTALL_DIR"
  [[ "$INSTALL_DIR" != "/" ]] || die "安装目录不能是根目录。"
  [[ -n "$REPO_URL" ]] || die "Git 仓库地址不能为空。"
  [[ -n "$BRANCH" ]] || die "分支名称不能为空。"
  [[ "$HEALTH_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "健康检查超时必须是正整数。"
}

require_root() {
  if ((EUID != 0)); then
    die "请使用 root 权限运行，例如：curl -fsSL <安装脚本地址> | sudo bash"
  fi
}

install_base_dependencies() {
  log "安装基础依赖。"

  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y ca-certificates curl git gzip openssl util-linux
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y ca-certificates curl git gzip openssl util-linux
  elif command -v yum >/dev/null 2>&1; then
    yum install -y ca-certificates curl git gzip openssl util-linux
  elif command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install ca-certificates curl git gzip openssl util-linux
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache bash ca-certificates curl git gzip openssl util-linux
  else
    die "不支持当前包管理器，请先安装 curl、git、gzip、openssl 和 flock。"
  fi
}

ensure_base_dependencies() {
  local missing=false
  local command_name

  for command_name in curl git gzip openssl flock; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      missing=true
      break
    fi
  done

  if [[ "$missing" == true ]]; then
    install_base_dependencies
  fi

  for command_name in curl git gzip openssl flock; do
    command -v "$command_name" >/dev/null 2>&1 || die "缺少必要命令：$command_name"
  done
}

install_docker() {
  local installer

  [[ "$DOCKER_INSTALL_ENABLED" == true ]] || die "未检测到可用的 Docker Compose v2。"

  if command -v apk >/dev/null 2>&1; then
    log "使用 apk 安装 Docker 和 Docker Compose。"
    apk add --no-cache docker docker-cli-compose
    return
  fi

  warn "未检测到可用的 Docker Compose v2，将运行 Docker 官方安装脚本。"

  installer="$(mktemp)"
  TEMP_FILES+=("$installer")
  curl --proto '=https' --tlsv1.2 -fsSL https://get.docker.com -o "$installer"
  sh "$installer"
}

start_docker() {
  if docker info >/dev/null 2>&1; then
    return
  fi

  log "启动 Docker 服务。"
  if command -v systemctl >/dev/null 2>&1 && systemctl enable --now docker; then
    :
  elif command -v rc-service >/dev/null 2>&1; then
    rc-update add docker default >/dev/null 2>&1 || true
    rc-service docker start
  elif command -v service >/dev/null 2>&1 && service docker start; then
    :
  else
    die "无法自动启动 Docker 服务。"
  fi

  docker info >/dev/null 2>&1 || die "Docker 服务未正常运行。"
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    install_docker
  fi

  command -v docker >/dev/null 2>&1 || die "Docker 安装失败。"
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 安装失败。"
  start_docker
}

acquire_lock() {
  mkdir -p -- "$(dirname -- "$LOCK_FILE")"
  exec 9>"$LOCK_FILE"
  flock -n 9 || die "另一个安装或更新任务正在运行。"
}

compose() {
  (
    cd -- "$DEPLOY_DIR"
    docker compose \
      --env-file .env \
      -f docker-compose.local.yml \
      -f docker-compose.nova.yml \
      "$@"
  )
}

repo_git() {
  git -c safe.directory="$INSTALL_DIR" -C "$INSTALL_DIR" "$@"
}

has_deployment_data() {
  [[ -f "$DEPLOY_DIR/postgres_data/PG_VERSION" ]] || \
    [[ -f "$DEPLOY_DIR/data/config.yaml" ]] || \
    [[ -f "$DEPLOY_DIR/data/.installed" ]]
}

wait_for_postgres() {
  local deadline=$((SECONDS + 90))
  local container_id
  local health

  while ((SECONDS < deadline)); do
    container_id="$(compose ps -q postgres 2>/dev/null || true)"
    if [[ -n "$container_id" ]]; then
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
      if [[ "$health" == "healthy" || "$health" == "running" ]]; then
        return
      fi
    fi
    sleep 2
  done

  die "PostgreSQL 未在 90 秒内就绪，无法执行更新前备份。"
}

backup_database() {
  local backup_root="$DEPLOY_DIR/backups"
  local timestamp
  local backup_dir
  local temp_dump
  local commit

  [[ "$BACKUP_ENABLED" == true ]] || {
    warn "已按参数跳过更新前数据库备份。"
    return
  }

  has_deployment_data || return
  [[ -f "$DEPLOY_DIR/.env" ]] || die "检测到部署数据但缺少 deploy/.env，无法安全备份。"

  if [[ -z "$(compose ps --status running -q postgres 2>/dev/null || true)" ]]; then
    log "启动 PostgreSQL 以执行更新前备份。"
    compose up -d postgres
  fi
  wait_for_postgres

  timestamp="$(date '+%Y%m%d-%H%M%S')"
  backup_dir="$backup_root/$timestamp"
  temp_dump="$backup_dir/database.sql.gz.tmp"
  commit="$(repo_git rev-parse HEAD)"

  install -d -m 700 -- "$backup_dir"
  {
    printf 'created_at=%s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')"
    printf 'git_commit=%s\n' "$commit"
    printf 'branch=%s\n' "$BRANCH"
  } >"$backup_dir/metadata.txt"
  chmod 600 "$backup_dir/metadata.txt"

  log "备份 PostgreSQL 到 $backup_dir/database.sql.gz"
  TEMP_FILES+=("$temp_dump")
  # The database variables intentionally expand inside the PostgreSQL container.
  # shellcheck disable=SC2016
  compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip -9 >"$temp_dump"
  [[ -s "$temp_dump" ]] || die "数据库备份为空，已停止更新。"
  mv -- "$temp_dump" "$backup_dir/database.sql.gz"
  chmod 600 "$backup_dir/database.sql.gz"
}

verify_existing_repository() {
  local current_origin
  local changes

  [[ -d "$INSTALL_DIR/.git" ]] || die "安装目录已存在但不是 Git 仓库：$INSTALL_DIR"

  current_origin="$(repo_git remote get-url origin 2>/dev/null || true)"
  [[ -n "$current_origin" ]] || die "现有仓库缺少 origin 远程地址。"

  changes="$(repo_git status --porcelain --untracked-files=normal)"
  if [[ -n "$changes" ]]; then
    printf '%s\n' "$changes" >&2
    die "检测到未提交的源码修改，为避免覆盖已停止更新。"
  fi

  if [[ "$current_origin" != "$REPO_URL" ]]; then
    die "现有仓库 origin 为 $current_origin，与目标仓库 $REPO_URL 不一致。"
  fi
}

clone_repository() {
  if [[ "$UPDATE_ONLY" == true ]]; then
    die "--update-only 要求安装目录已经存在。"
  fi

  if [[ -e "$INSTALL_DIR" && ! -d "$INSTALL_DIR" ]]; then
    die "安装路径已存在且不是目录：$INSTALL_DIR"
  fi

  if [[ -e "$INSTALL_DIR" && -n "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    die "安装目录已存在且不为空：$INSTALL_DIR"
  fi

  mkdir -p -- "$(dirname -- "$INSTALL_DIR")"
  log "克隆 $BRANCH 分支到 $INSTALL_DIR"
  git clone --branch "$BRANCH" --single-branch -- "$REPO_URL" "$INSTALL_DIR"
}

update_repository() {
  backup_database
  log "拉取 $BRANCH 分支的最新代码。"
  repo_git fetch --prune origin "$BRANCH"

  if repo_git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    repo_git checkout "$BRANCH"
  else
    repo_git checkout -b "$BRANCH" --track "origin/$BRANCH"
  fi

  repo_git merge --ff-only "origin/$BRANCH"
}

initialize_config() {
  if [[ -f "$DEPLOY_DIR/.env" ]]; then
    log "保留现有 deploy/.env 配置。"
    return
  fi

  [[ -x "$DEPLOY_DIR/setup.sh" ]] || chmod +x "$DEPLOY_DIR/setup.sh"
  [[ -r /dev/tty ]] || die "首次安装需要交互式终端来设置管理员账号。"

  log "开始初始化部署配置。"
  (
    cd -- "$DEPLOY_DIR"
    ./setup.sh --no-start </dev/tty
  )
}

read_env_value() {
  local key="$1"
  local default_value="$2"
  local value

  value="$(sed -n "s/^${key}=//p" "$DEPLOY_DIR/.env" | tail -n 1 | tr -d '\r')"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "${value:-$default_value}"
}

wait_for_application() {
  local port
  local bind_host
  local health_host
  local health_url
  local deadline=$((SECONDS + HEALTH_TIMEOUT))

  port="$(read_env_value SERVER_PORT 8080)"
  bind_host="$(read_env_value BIND_HOST 0.0.0.0)"
  health_host="$bind_host"
  if [[ "$bind_host" == "0.0.0.0" || "$bind_host" == "127.0.0.1" ]]; then
    health_host="127.0.0.1"
  fi
  health_url="http://${health_host}:${port}/health"

  log "等待服务健康检查：$health_url"
  while ((SECONDS < deadline)); do
    if curl --noproxy '*' -fsS --max-time 5 "$health_url" >/dev/null 2>&1; then
      ACCESS_PORT="$port"
      return
    fi
    sleep 3
  done

  compose ps >&2 || true
  compose logs --tail=200 sub2api >&2 || true
  die "服务未在 ${HEALTH_TIMEOUT} 秒内通过健康检查。"
}

deploy_application() {
  log "校验 Docker Compose 配置。"
  compose config --quiet

  log "构建并启动 Sub2API Nova。"
  compose up -d --build --remove-orphans
  wait_for_application
}

print_result() {
  local commit
  commit="$(repo_git rev-parse --short HEAD)"

  cat <<EOF

Sub2API Nova 部署成功
安装目录：$INSTALL_DIR
当前版本：$commit
访问地址：http://服务器IP:$ACCESS_PORT
查看状态：cd $DEPLOY_DIR && docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml ps
EOF
}

main() {
  local existing_repository=false

  parse_args "$@"
  require_root
  prompt_install_dir
  validate_settings
  log "安装位置：$INSTALL_DIR"
  ensure_base_dependencies
  git check-ref-format --branch "$BRANCH" >/dev/null 2>&1 || die "无效的 Git 分支名称：$BRANCH"
  acquire_lock
  ensure_docker

  if [[ -d "$INSTALL_DIR/.git" ]]; then
    existing_repository=true
    DEPLOY_DIR="$INSTALL_DIR/deploy"
    verify_existing_repository
    [[ -d "$DEPLOY_DIR" ]] || die "现有仓库缺少 deploy 目录。"
    update_repository
  else
    clone_repository
    DEPLOY_DIR="$INSTALL_DIR/deploy"
  fi

  [[ -d "$DEPLOY_DIR" ]] || die "仓库缺少 deploy 目录。"
  initialize_config
  deploy_application

  if [[ "$existing_repository" == true ]]; then
    log "代码和容器已更新到最新版本。"
  fi
  print_result
}

main "$@"
