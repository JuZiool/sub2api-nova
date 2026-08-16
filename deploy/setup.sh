#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="${SCRIPT_DIR}/.env.example"
OUTPUT_FILE="${SCRIPT_DIR}/.env"
FORCE=false

usage() {
  cat <<'EOF'
用法：./setup.sh [选项]

选项：
  --force          覆盖已存在的环境配置，不再询问
  --output <路径>  将配置写入指定文件，默认写入 deploy/.env
  -h, --help       显示帮助
EOF
}

while (($# > 0)); do
  case "$1" in
    --force)
      FORCE=true
      shift
      ;;
    --output)
      if (($# < 2)); then
        echo "错误：--output 需要提供文件路径。" >&2
        exit 1
      fi
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "错误：未知选项 $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$TEMPLATE_FILE" ]]; then
  echo "错误：找不到环境配置模板 $TEMPLATE_FILE" >&2
  exit 1
fi

if [[ "$OUTPUT_FILE" != /* ]]; then
  OUTPUT_FILE="${SCRIPT_DIR}/${OUTPUT_FILE}"
fi

if [[ -e "$OUTPUT_FILE" && "$FORCE" != true ]]; then
  read -r -p "配置文件 ${OUTPUT_FILE} 已存在，是否覆盖？[y/N]: " overwrite
  case "${overwrite,,}" in
    y | yes) ;;
    *)
      echo "已取消，原配置未修改。"
      exit 0
      ;;
  esac
fi

generate_hex() {
  local bytes="$1"

  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
    return
  fi

  if [[ -r /dev/urandom ]] && command -v od >/dev/null 2>&1; then
    od -An -N "$bytes" -tx1 /dev/urandom | tr -d ' \n'
    return
  fi

  echo "错误：无法生成安全随机值，请安装 openssl。" >&2
  exit 1
}

dotenv_single_quote() {
  printf "'%s'" "$1"
}

prompt_admin_email() {
  local value

  while true; do
    read -r -p "管理员邮箱: " value
    if [[ "$value" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
      ADMIN_EMAIL="$value"
      return
    fi
    echo "请输入有效的管理员邮箱。" >&2
  done
}

prompt_admin_password() {
  local value confirm

  while true; do
    read -r -s -p "管理员初始密码: " value
    printf '\n'

    if [[ -z "$value" ]]; then
      echo "管理员初始密码不能为空。" >&2
      continue
    fi

    case "$value" in
      *"'"*)
        echo "管理员初始密码不能包含单引号字符。" >&2
        continue
        ;;
    esac

    read -r -s -p "再次输入管理员初始密码: " confirm
    printf '\n'
    if [[ "$value" != "$confirm" ]]; then
      echo "两次输入的密码不一致。" >&2
      continue
    fi

    ADMIN_PASSWORD="$value"
    return
  done
}

prompt_overdraft() {
  local answer

  while true; do
    read -r -p "是否启用 Codex 额度透支功能？[Y/n]: " answer
    case "${answer,,}" in
      "" | y | yes)
        OVERDRAFT_ENABLED=true
        return
        ;;
      n | no)
        OVERDRAFT_ENABLED=false
        return
        ;;
      *)
        echo "请输入 Yes 或 No。" >&2
        ;;
    esac
  done
}

echo "Sub2API Nova 环境配置初始化"
echo

prompt_admin_email
prompt_admin_password
prompt_overdraft

POSTGRES_PASSWORD="$(generate_hex 24)"
REDIS_PASSWORD="$(generate_hex 24)"
JWT_SECRET="$(generate_hex 32)"
TOTP_ENCRYPTION_KEY="$(generate_hex 32)"

mkdir -p "$(dirname -- "$OUTPUT_FILE")"
TEMP_FILE="$(mktemp "${OUTPUT_FILE}.tmp.XXXXXX")"
trap 'rm -f -- "$TEMP_FILE"' EXIT

ADMIN_PASSWORD_ENV="$(dotenv_single_quote "$ADMIN_PASSWORD")"

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  case "$line" in
    POSTGRES_PASSWORD=*) printf 'POSTGRES_PASSWORD=%s\n' "$POSTGRES_PASSWORD" ;;
    REDIS_PASSWORD=*) printf 'REDIS_PASSWORD=%s\n' "$REDIS_PASSWORD" ;;
    ADMIN_EMAIL=*) printf 'ADMIN_EMAIL=%s\n' "$ADMIN_EMAIL" ;;
    ADMIN_PASSWORD=*) printf 'ADMIN_PASSWORD=%s\n' "$ADMIN_PASSWORD_ENV" ;;
    JWT_SECRET=*) printf 'JWT_SECRET=%s\n' "$JWT_SECRET" ;;
    TOTP_ENCRYPTION_KEY=*) printf 'TOTP_ENCRYPTION_KEY=%s\n' "$TOTP_ENCRYPTION_KEY" ;;
    GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED=*)
      printf 'GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED=%s\n' "$OVERDRAFT_ENABLED"
      ;;
    *) printf '%s\n' "$line" ;;
  esac
done <"$TEMPLATE_FILE" >"$TEMP_FILE"

chmod 600 "$TEMP_FILE"
mv -f -- "$TEMP_FILE" "$OUTPUT_FILE"
trap - EXIT

mkdir -p "${SCRIPT_DIR}/data" "${SCRIPT_DIR}/postgres_data" "${SCRIPT_DIR}/redis_data"

echo
echo "配置已生成：$OUTPUT_FILE"
echo "数据库、Redis、JWT 和 TOTP 密钥已自动随机生成。"
echo "Codex 额度透支：$OVERDRAFT_ENABLED"
echo
echo "启动命令："
echo "docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml up -d --build"
