# Sub2API Nova

Sub2API Nova 是基于 Sub2API 二开版本继续开发的 AI API 网关。项目保留账号池、分组调度、用户与 API Key、计费配额、渠道监控等现有能力，并默认启用 Codex 额度透支调度功能。

本仓库采用本地源码 Docker 构建方式，部署时会生成 `sub2api-nova:local` 镜像，不依赖上游 Sub2API 应用镜像。

## 主要功能

- 统一管理 OpenAI、Anthropic、Gemini、Antigravity、Grok 等上游账号
- 通过分组控制平台、模型、倍率、配额和调度策略
- 为用户创建独立 API Key，并统计请求量、Token 与费用
- 支持 OpenAI、Anthropic 和 Gemini 常用兼容接口
- 支持账号健康检查、额度监控、自动暂停和故障切换
- 默认启用 Codex 5 小时/7 天额度透支探测与调度
- 提供管理员后台、用户后台、日志、监控和运营功能
- 使用 PostgreSQL 保存业务数据，Redis 提供缓存和调度状态

## 部署要求

开始前需要安装：

- Git
- Docker Engine 或 Docker Desktop
- Docker Compose v2

建议至少准备 2 核 CPU、4 GB 内存。正式运营时应根据账号数量、并发量和数据库规模提高配置。

## 从零部署

### 1. 获取源码

```bash
git clone https://github.com/JuZiool/sub2api-nova.git
cd sub2api-nova/deploy
```

### 2. 创建环境配置

推荐使用交互式初始化脚本。脚本会自动生成 PostgreSQL、Redis、JWT 和 TOTP 密钥，只要求手动输入管理员邮箱、管理员初始密码，并通过 Yes/No 选择是否开启 Codex 额度透支。

Linux、macOS、Git Bash 或 WSL：

```bash
chmod +x setup.sh
./setup.sh
```

脚本会完成以下操作：

- 根据 `.env.example` 生成 `.env`
- 自动生成 `POSTGRES_PASSWORD`
- 自动生成 `REDIS_PASSWORD`
- 自动生成 `JWT_SECRET`
- 自动生成 `TOTP_ENCRYPTION_KEY`
- 手动填写 `ADMIN_EMAIL` 和 `ADMIN_PASSWORD`
- 通过 Yes/No 配置 `GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED`
- 创建 `data`、`postgres_data` 和 `redis_data` 目录
- 将 `.env` 权限设置为仅当前用户可读写

如果 `.env` 已存在，脚本会先询问是否覆盖。也可以使用 `./setup.sh --help` 查看可用选项。

管理员初始密码不限制位数，但不能为空。为了使用 `.env` 的单引号字面量安全保存空格、`$`、`#`、双引号和反斜杠，密码不能包含单引号字符。

需要手动创建配置时，Linux/macOS 执行：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

编辑 `deploy/.env`，首次部署至少检查以下配置：

```dotenv
BIND_HOST=0.0.0.0
SERVER_PORT=8080
TZ=Asia/Shanghai

POSTGRES_USER=sub2api
POSTGRES_PASSWORD=<数据库随机强密码>
POSTGRES_DB=sub2api

REDIS_PASSWORD=<Redis随机强密码>

ADMIN_EMAIL=<管理员邮箱>
ADMIN_PASSWORD=<管理员初始密码>

JWT_SECRET=<64位随机密钥>
TOTP_ENCRYPTION_KEY=<64位随机密钥>

GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED=true
```

可以使用 OpenSSL 生成随机值：

```bash
openssl rand -hex 24
openssl rand -hex 32
```

每个密码和密钥都应使用不同的随机值。不要把 `deploy/.env` 提交到 Git 仓库。

### 3. 创建数据目录

使用 `setup.sh` 时会自动创建数据目录，可以跳过本步骤。手动配置 `.env` 时执行以下命令。

Linux/macOS：

```bash
mkdir -p data postgres_data redis_data
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force data, postgres_data, redis_data
```

### 4. 构建并启动

在 `deploy` 目录执行：

```bash
docker compose --env-file .env \
  -f docker-compose.local.yml \
  -f docker-compose.nova.yml \
  up -d --build
```

Windows PowerShell：

```powershell
docker compose --env-file .env `
  -f docker-compose.local.yml `
  -f docker-compose.nova.yml `
  up -d --build
```

必须同时使用这两个 Compose 文件：

- `docker-compose.local.yml`：定义应用、PostgreSQL、Redis、端口和数据目录
- `docker-compose.nova.yml`：覆盖应用镜像并从当前 Nova 源码构建

如果只使用 `docker-compose.local.yml`，Compose 会使用上游镜像，不会包含 Nova 的源码修改。

### 5. 检查运行状态

```bash
docker compose --env-file .env \
  -f docker-compose.local.yml \
  -f docker-compose.nova.yml \
  ps
```

健康检查：

```bash
curl http://localhost:8080/health
```

正常响应：

```json
{"status":"ok"}
```

### 6. 登录后台

浏览器访问：

```text
http://服务器地址:8080
```

使用 `.env` 中首次启动前设置的 `ADMIN_EMAIL` 和 `ADMIN_PASSWORD` 登录。

管理员账号创建完成后，再修改 `.env` 中的管理员邮箱或密码不会自动更新数据库中的账号。后续密码应在后台个人设置中修改。

## 首次使用流程

建议按照以下顺序完成后台配置：

1. 登录管理员后台，检查站点名称、API 地址和基础安全设置。
2. 在“分组管理”中创建分组，选择目标平台并设置可用模型、倍率和配额。
3. 在“账号管理”中添加对应平台的 OAuth、Setup Token、API Key 或上游账号。
4. 将账号分配到相应分组，并确认账号状态和额度检测正常。
5. 创建用户，或直接为管理员/用户生成 API Key。
6. 在客户端中填写 Nova 的 API 地址和生成的 API Key。
7. 使用模型列表或简单请求验证调度和计费是否正常。

API Key 是否能调用某个平台，取决于它绑定的分组以及分组中的账号、模型和平台配置。

## 客户端接入

假设服务地址为 `https://api.example.com`，API Key 为后台生成的 `sk-...`。

### OpenAI 兼容接口

Base URL：

```text
https://api.example.com/v1
```

常用接口：

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /v1/models`
- `POST /v1/embeddings`
- `POST /v1/images/generations`

Chat Completions 示例：

```bash
curl https://api.example.com/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<MODEL_NAME>",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

Responses 示例：

```bash
curl https://api.example.com/v1/responses \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<MODEL_NAME>",
    "input": "你好"
  }'
```

### Anthropic 兼容接口

```text
POST https://api.example.com/v1/messages
```

客户端使用 API Key 认证，模型和账号由 API Key 所属分组决定。

### Gemini 原生兼容接口

```text
GET  https://api.example.com/v1beta/models
POST https://api.example.com/v1beta/models/<MODEL>:generateContent
```

不同客户端对 Base URL 是否需要包含 `/v1` 的处理不同。通常 OpenAI SDK 填写 `https://api.example.com/v1`，直接请求接口时按上面的完整路径使用。

## Codex 额度透支

Nova 部署覆盖文件默认设置：

```dotenv
GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED=true
```

开启后，当 Codex 账号的 5 小时或 7 天额度窗口达到 100% 时，系统可以执行真实探测并参与透支调度。后台额度面板会显示透支状态、探测时间和预计恢复时间。

该能力需要先正确添加 OpenAI/Codex 账号，并将账号加入对应分组。若需要恢复上游默认调度行为，可在 `.env` 中设置：

```dotenv
GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED=false
```

修改后重新执行 Compose 启动命令使配置生效。

## 常用运维命令

以下命令均在 `deploy` 目录执行。

查看服务：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml ps
```

查看应用日志：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml logs -f sub2api
```

查看全部日志：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml logs -f
```

重启服务：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml restart
```

停止服务但保留数据：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml down
```

修改源码后重新构建：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml up -d --build
```

## 更新项目

Nova 已移除后台内置版本更新检测。更新源码时手动执行：

```bash
git pull origin main
cd deploy
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml up -d --build
```

更新前建议先备份 `deploy` 目录中的持久化数据。

## 数据与备份

本地目录部署使用以下持久化目录：

```text
deploy/data/           应用数据和日志
deploy/postgres_data/  PostgreSQL 数据
deploy/redis_data/     Redis 数据
```

迁移或备份前先停止服务：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml down
```

随后备份整个 `deploy` 目录，至少应保存 `.env`、`data`、`postgres_data` 和 `redis_data`。`.env` 含有敏感信息，备份文件应加密保存。

不要在仍有数据库写入时直接复制 `postgres_data`。正式环境建议配合 PostgreSQL 逻辑备份或后台备份功能使用。

## 生产环境建议

- 使用 Nginx、Caddy 或其他反向代理提供 HTTPS。
- 通过反向代理访问时，将 `BIND_HOST` 设置为 `127.0.0.1`。
- 不要将 PostgreSQL 和 Redis 端口直接暴露到公网。
- 为数据库、Redis、JWT 和 TOTP 使用不同的随机密钥。
- 定期备份数据库，并实际验证恢复流程。
- 使用防火墙仅开放 SSH、HTTP 和 HTTPS 等必要端口。
- 根据机器内存调整 PostgreSQL 和连接池参数，避免照搬高配置参数。

## 常见问题

### 启动时报 `POSTGRES_PASSWORD is required`

确认 `deploy/.env` 已创建，并且 `POSTGRES_PASSWORD` 不是空值或示例占位值。

### 页面无法访问

检查容器状态和日志：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml ps
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml logs --tail=200 sub2api
```

同时确认 `SERVER_PORT` 未被占用，服务器防火墙允许访问该端口。

### 修改管理员密码后无法使用新密码

`ADMIN_PASSWORD` 只用于首次初始化管理员账号。系统已经初始化后，应登录后台修改密码。

### 修改 `.env` 后没有生效

执行以下命令重新创建应用容器：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml up -d --force-recreate
```

涉及源码或 Dockerfile 的修改需要额外添加 `--build`。

### 如何关闭额度透支

在 `.env` 中设置：

```dotenv
GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED=false
```

然后重新创建应用容器。

## 项目目录

```text
backend/                    Go 后端与网关服务
frontend/                   Vue 3 管理端和用户端
deploy/                     Docker Compose、环境配置和持久化数据目录
deploy/setup.sh             交互式环境配置初始化脚本
docs/                       法律文本及项目文档
Dockerfile                  Nova 本地源码多阶段构建文件
FORK_VERSION                当前 Nova 源码版本
```

## 许可证

本项目沿用仓库中的 [LICENSE](LICENSE)。使用、修改和分发前请阅读许可证内容，并遵守上游项目及相关服务平台的使用条款。
