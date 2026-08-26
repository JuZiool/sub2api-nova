#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

readonly DEFAULT_IMAGE="ghcr.io/juziool/sub2api-nova:latest"
readonly DEFAULT_HEALTH_TIMEOUT=180
readonly RAW_BASE_URL="${SUB2API_RAW_BASE_URL:-https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy}"

DEPLOY_DIR="${SUB2API_DEPLOY_DIR:-$(pwd -P)}"
HEALTH_TIMEOUT="${SUB2API_HEALTH_TIMEOUT:-$DEFAULT_HEALTH_TIMEOUT}"
DOCKER_INSTALL_ENABLED=true
MODE=""
COMPOSE_MODE=""
COMPOSE_COMMAND_LABEL="docker compose"
LOCK_FILE=""
TEMP_FILES=()

log() { printf '[Sub2API] %s\n' "$*"; }
warn() { printf '[Sub2API] 警告：%s\n' "$*" >&2; }
die() { printf '[Sub2API] 错误：%s\n' "$*" >&2; exit 1; }
cleanup() { local file; for file in "${TEMP_FILES[@]}"; do rm -f -- "$file"; done; }
trap cleanup EXIT

usage() {
  cat <<'EOF'
Sub2API Nova GHCR 镜像部署脚本

用法：
  cd /目标目录
  curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh | bash

启动菜单：
  1  全新安装：生成 .env、创建数据目录、拉取镜像并启动
  2  迁移后安装：保留已有 .env 和数据，补齐文件并启动
  3  镜像升级：保留配置和数据，只拉取镜像并重建应用

选项：
  --dir <路径>          指定部署目录，默认当前目录
  --mode <1|2|3>        跳过菜单，直接选择模式
  --health-timeout <秒> 健康检查超时，默认 180
  --no-install-docker   Docker/Compose 缺失时不自动安装
  -h, --help            显示帮助

环境变量：
  SUB2API_DEPLOY_DIR       默认部署目录
  SUB2API_IMAGE            覆盖镜像 tag 或 digest
  SUB2API_HEALTH_TIMEOUT   健康检查超时秒数
  SUB2API_RAW_BASE_URL     部署文件下载地址（维护者测试用）
EOF
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --dir)
        (($# >= 2)) || die "--dir 需要提供路径。"
        DEPLOY_DIR="$2"
        shift 2
        ;;
      --mode)
        (($# >= 2)) || die "--mode 需要提供 1、2 或 3。"
        MODE="$2"
        shift 2
        ;;
      --health-timeout)
        (($# >= 2)) || die "--health-timeout 需要提供秒数。"
        HEALTH_TIMEOUT="$2"
        shift 2
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

require_root() { ((EUID == 0)) || die "请使用 root 权限运行安装脚本。"; }

validate_settings() {
  [[ "$DEPLOY_DIR" == /* ]] || die "部署目录必须是绝对路径：$DEPLOY_DIR"
  [[ "$DEPLOY_DIR" != "/" ]] || die "部署目录不能是根目录。"
  [[ "$HEALTH_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die "健康检查超时必须是正整数。"
  [[ -z "$MODE" || "$MODE" =~ ^[123]$ ]] || die "模式必须是 1、2 或 3。"
}

choose_mode() {
  [[ -n "$MODE" ]] && return 0
  if [[ -t 0 ]]; then
    read -r -p $'\n请选择操作：\n  1) 全新安装\n  2) 迁移后安装\n  3) 镜像升级\n请输入 1、2 或 3 [1]: ' MODE
  elif [[ -c /dev/tty ]]; then
    read -r -p $'\n请选择操作：\n  1) 全新安装\n  2) 迁移后安装\n  3) 镜像升级\n请输入 1、2 或 3 [1]: ' MODE </dev/tty
  else
    MODE=1
    warn "未检测到交互式终端，默认使用全新安装。"
  fi
  MODE="${MODE:-1}"
  [[ "$MODE" =~ ^[123]$ ]] || die "模式必须是 1、2 或 3。"
}

detect_platform() {
  local os_id="unknown" os_name="unknown Linux"
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    os_id="${ID:-unknown}"
    os_name="${NAME:-unknown Linux}"
  fi
  if [[ "$os_id" == "openwrt" ]]; then
    log "检测平台：${os_name}（iStoreOS/OpenWrt）"
  else
    log "检测平台：$os_name（$os_id）"
  fi
}

package_manager() {
  if command -v opkg >/dev/null 2>&1; then printf 'opkg';
  elif command -v apt-get >/dev/null 2>&1; then printf 'apt-get';
  elif command -v apk >/dev/null 2>&1; then printf 'apk';
  elif command -v dnf >/dev/null 2>&1; then printf 'dnf';
  elif command -v yum >/dev/null 2>&1; then printf 'yum';
  else printf ''; fi
}

install_package() {
  local manager
  manager="$(package_manager)"
  case "$manager" in
    opkg) opkg update >/dev/null 2>&1 || true; opkg install "$1" ;;
    apt-get) DEBIAN_FRONTEND=noninteractive apt-get update >/dev/null 2>&1 || true; DEBIAN_FRONTEND=noninteractive apt-get install -y "$1" ;;
    apk) apk add --no-cache "$1" ;;
    dnf) dnf install -y "$1" ;;
    yum) yum install -y "$1" ;;
    *) return 1 ;;
  esac
}

ensure_base_dependencies() {
  local command_name package_name
  for command_name in curl openssl flock sed tail tr; do
    command -v "$command_name" >/dev/null 2>&1 && continue
    case "$command_name:$(package_manager)" in
      openssl:opkg) package_name="openssl-util" ;;
      flock:opkg) package_name="util-linux-flock" ;;
      *) package_name="$command_name" ;;
    esac
    install_package "$package_name" || die "缺少必要命令 $command_name，请手动安装后重试。"
  done
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

start_docker() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  log "启动 Docker 服务。"
  if [[ -x /etc/init.d/dockerd ]]; then
    /etc/init.d/dockerd enable >/dev/null 2>&1 || true
    /etc/init.d/dockerd start
  elif [[ -x /etc/init.d/docker ]]; then
    /etc/init.d/docker enable >/dev/null 2>&1 || true
    /etc/init.d/docker start
  elif command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now docker
  elif command -v service >/dev/null 2>&1; then
    service docker start
  else
    die "无法自动启动 Docker 服务，请手动启动后重试。"
  fi

  local attempt
  for attempt in {1..15}; do
    docker info >/dev/null 2>&1 && return 0
    sleep 2
  done
  die "Docker 服务未正常运行。"
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    [[ "$DOCKER_INSTALL_ENABLED" == true ]] || die "未检测到 Docker，请先在 iStoreOS Docker 管理器中安装。"
    if [[ "$(package_manager)" == "opkg" ]]; then
      install_package docker || install_package dockerd || die "无法通过 opkg 安装 Docker，请使用 iStoreOS Docker 管理器。"
    else
      install_package docker || install_package docker.io || true
    fi
  fi
  command -v docker >/dev/null 2>&1 || die "未安装 Docker，请先安装并启动 Docker。"
  if ! detect_docker_compose; then
    [[ "$DOCKER_INSTALL_ENABLED" == true ]] || die "未检测到 Docker Compose，请先安装 Compose v2。"
    case "$(package_manager)" in
      opkg) install_package docker-compose || install_package docker-cli-compose || install_package docker-compose-v2 || true ;;
      apt-get) install_package docker-compose-plugin || install_package docker-compose-v2 || install_package docker-compose || true ;;
      *) install_package docker-compose || true ;;
    esac
    detect_docker_compose || die "未检测到 Docker Compose（支持 docker compose 或 docker-compose）。"
  fi
  start_docker
}

compose() {
  (
    cd -- "$DEPLOY_DIR"
    docker_compose --env-file .env \
      -f docker-compose.local.yml \
      -f docker-compose.ghcr.yml \
      "$@"
  )
}

prepare_file() {
  local name="$1" target="$DEPLOY_DIR/$1" temp
  [[ -f "$target" ]] && return 0
  temp="$(mktemp "$DEPLOY_DIR/.${name}.XXXXXX")"
  TEMP_FILES+=("$temp")
  log "下载 $name"
  curl --proto '=https' --tlsv1.2 -fsSL "$RAW_BASE_URL/$name" -o "$temp" || die "无法下载 $name。"
  mv -f -- "$temp" "$target"
  chmod 644 "$target"
}

prepare_runtime_files() {
  mkdir -p -- "$DEPLOY_DIR" || die "无法创建部署目录：$DEPLOY_DIR"
  [[ -w "$DEPLOY_DIR" ]] || die "部署目录不可写：$DEPLOY_DIR"
  prepare_file docker-compose.local.yml
  prepare_file docker-compose.ghcr.yml
  prepare_file install.sh
  prepare_file update.sh
  [[ "$MODE" == 1 ]] && prepare_file .env.example && prepare_file setup.sh
  chmod 755 "$DEPLOY_DIR/setup.sh" "$DEPLOY_DIR/update.sh" 2>/dev/null || true
  mkdir -p "$DEPLOY_DIR/data" "$DEPLOY_DIR/postgres_data" "$DEPLOY_DIR/redis_data"
}

has_persistent_data() {
  [[ -n "$(find "$DEPLOY_DIR/data" "$DEPLOY_DIR/postgres_data" "$DEPLOY_DIR/redis_data" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]
}

initialize_fresh() {
  [[ ! -e "$DEPLOY_DIR/.env" ]] || die "当前目录已有 .env，不适合全新安装；请选择模式 2 或 3。"
  if has_persistent_data; then
    die "当前目录已有持久化数据，不适合全新安装；请选择模式 2 或 3。"
  fi
  [[ -r /dev/tty ]] || die "全新安装需要交互式终端来填写管理员账号和密码。"
  log "开始生成 .env。"
  (cd "$DEPLOY_DIR" && bash ./setup.sh --no-start </dev/tty)
}

require_migration_config() {
  [[ -f "$DEPLOY_DIR/.env" ]] || die "迁移安装要求当前目录已有 .env。"
  log "保留已有 .env 和持久化数据。"
}

require_upgrade_config() {
  [[ -f "$DEPLOY_DIR/.env" ]] || die "镜像升级要求当前目录已有 .env。"
  log "保留已有 .env 和持久化数据，仅升级应用镜像。"
}

read_env_value() {
  local key="$1" fallback="$2" value=""
  value="$(sed -n "s/^${key}=//p" "$DEPLOY_DIR/.env" | tail -n 1 | tr -d '\r')"
  value="${value#\"}"; value="${value%\"}"; value="${value#\'}"; value="${value%\'}"
  printf '%s' "${value:-$fallback}"
}

wait_for_application() {
  local port="$(read_env_value SERVER_PORT 8080)" deadline=$((SECONDS + HEALTH_TIMEOUT))
  local container_id health
  log "等待服务健康检查：http://127.0.0.1:${port}/health"
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
  die "服务未在 ${HEALTH_TIMEOUT} 秒内通过健康检查。"
}

deploy_application() {
  export SUB2API_IMAGE="${SUB2API_IMAGE:-$DEFAULT_IMAGE}"
  log "拉取预构建镜像：$SUB2API_IMAGE"
  compose config --quiet
  compose pull sub2api || die "GHCR 镜像拉取失败，请检查网络或设置 SUB2API_IMAGE。"
  compose up -d --remove-orphans
  wait_for_application
}

upgrade_application() {
  export SUB2API_IMAGE="${SUB2API_IMAGE:-$(read_env_value SUB2API_IMAGE "$DEFAULT_IMAGE")}"
  log "升级应用镜像：$SUB2API_IMAGE"
  compose config --quiet
  compose pull sub2api || die "镜像拉取失败。"
  compose up -d --force-recreate --remove-orphans sub2api
  wait_for_application
}

main() {
  parse_args "$@"
  require_root
  validate_settings
  choose_mode
  detect_platform
  ensure_base_dependencies
  mkdir -p -- "$DEPLOY_DIR"
  LOCK_FILE="$DEPLOY_DIR/.sub2api-install.lock"
  exec 9>"$LOCK_FILE"
  flock -n 9 || die "另一个安装或升级任务正在运行。"
  ensure_docker
  prepare_runtime_files

  case "$MODE" in
    1) initialize_fresh; deploy_application ;;
    2) require_migration_config; deploy_application ;;
    3) require_upgrade_config; upgrade_application ;;
  esac

  printf '\n'
  log "操作完成（模式 $MODE）"
  log "部署目录：$DEPLOY_DIR"
  log "访问地址：http://服务器IP:$(read_env_value SERVER_PORT 8080)"
  log "查看状态：cd $DEPLOY_DIR && $COMPOSE_COMMAND_LABEL --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml ps"
}

main "$@"
