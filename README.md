# Sub2API Nova 部署指南

本项目使用 Docker Compose 从当前源码构建 Nova 镜像，并同时运行 Sub2API、PostgreSQL 和 Redis 三个容器。

## 部署要求

- Git
- Docker Engine 或 Docker Desktop
- Docker Compose v2
- 建议至少 2 核 CPU、4 GB 内存

## Linux 一键部署

在常见 Linux 服务器上执行：

```bash
curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh | sudo bash
```

脚本会自动完成：

- 安装缺少的基础依赖，并在需要时运行 Docker 官方安装脚本
- 首次部署时克隆源码并调用 `setup.sh` 生成安全配置
- 提示选择服务端口，直接回车默认使用 `8080`，并检查端口是否已被占用
- 重复运行时保留 `.env` 和全部持久化数据
- 更新前使用 `pg_dump` 备份 PostgreSQL
- 使用 `git merge --ff-only` 拉取 `main` 分支，拒绝覆盖本地源码修改
- 构建并启动 Sub2API、PostgreSQL 和 Redis
- 等待 `/health` 健康检查，失败时输出容器状态和应用日志

默认安装目录为 `/opt/sub2api-nova`。再次执行同一条命令即可更新。

向脚本传递参数：

```bash
curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh | \
  sudo bash -s -- --dir /srv/sub2api-nova --branch main
```

查看全部参数：

```bash
curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh | sudo bash -s -- --help
```

更新备份保存在 `deploy/backups/<时间>/database.sql.gz`。数据库备份包含敏感业务数据，应限制访问并定期转移到独立存储。

## 从零部署

以下步骤适用于希望手工控制 Git、配置和 Docker Compose 命令的场景。

### 1. 获取源码

```bash
git clone https://github.com/JuZiool/sub2api-nova.git
cd sub2api-nova/deploy
```

### 2. 初始化配置

推荐在 Linux、macOS、Git Bash 或 WSL 中运行交互式初始化脚本：

```bash
chmod +x setup.sh
./setup.sh
```

脚本会：

- 根据 `.env.example` 创建 `.env`
- 提示选择服务端口；直接回车使用 `8080`，端口已被占用时要求重新输入
- 自动生成 PostgreSQL、Redis、JWT 和 TOTP 密钥
- 提示输入管理员邮箱和初始密码
- 通过 Yes/No 选择是否开启 Codex 额度透支
- 创建 `data`、`postgres_data` 和 `redis_data` 持久化目录
- 将 `.env` 权限设置为仅当前用户可读写

管理员初始密码不限制位数，但不能为空，需要输入两次确认。密码不能包含单引号字符。

查看脚本参数：

```bash
./setup.sh --help
```

如果不使用脚本，可以手动创建配置。

Linux 或 macOS：

```bash
cp .env.example .env
mkdir -p data postgres_data redis_data
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Force data, postgres_data, redis_data
```

编辑 `.env`，至少配置以下内容：

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

不要将 `.env` 提交到 Git 仓库，也不要向他人公开其中的密码和密钥。

### 3. 构建并启动

在 `deploy` 目录执行。

Linux、macOS、Git Bash 或 WSL：

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

必须同时加载两个 Compose 文件：

- `docker-compose.local.yml`：定义应用、PostgreSQL、Redis、端口和数据目录
- `docker-compose.nova.yml`：从当前 Nova 源码构建 `sub2api-nova:local` 镜像

首次构建需要下载基础镜像和依赖，耗时取决于网络环境。

### 4. 检查部署

查看三个容器的状态：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml ps
```

健康检查：

```bash
curl http://localhost:8080/health
```

正常响应：

```json
{"status":"ok"}
```

浏览器访问：

```text
http://服务器地址:8080
```

使用 `.env` 中的 `ADMIN_EMAIL` 和 `ADMIN_PASSWORD` 登录。管理员创建后，修改 `.env` 不会更新数据库中的管理员账号或密码。

## 常用命令

以下命令均在 `deploy` 目录执行。

查看状态：

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

停止服务并保留容器和数据：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml stop
```

重新启动已停止的服务：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml start
```

停止并删除容器，但保留持久化数据：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml down
```

重新构建并启动：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml up -d --build
```

## 更新部署

先停止服务并备份数据，然后在项目根目录执行：

```bash
git pull origin main
cd deploy
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml up -d --build
```

Nova 已移除后台内置版本更新检测，源码更新需要手动执行。

## 备份与迁移

持久化数据位于：

```text
deploy/data/           应用数据和日志
deploy/postgres_data/  PostgreSQL 数据
deploy/redis_data/     Redis 数据
deploy/backups/        一键更新前生成的 PostgreSQL 逻辑备份
```

备份或迁移前先停止服务：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml stop
```

最稳妥的方式是完整打包整个 `sub2api-nova` 项目目录，这会同时保存源码、Dockerfile、Compose 配置、`.env` 和全部持久化数据。

恢复时将项目解压到目标机器，进入 `deploy` 目录，再执行构建启动命令。备份包包含数据库和密钥，应加密保存并限制访问。

不要在 PostgreSQL 仍有写入时直接复制 `postgres_data`。跨 PostgreSQL 大版本迁移时，应使用 PostgreSQL 逻辑备份和恢复，而不是直接复制数据目录。

## 生产环境建议

- 使用 Nginx、Caddy 等反向代理提供 HTTPS
- 通过本机反向代理访问时，将 `BIND_HOST` 设置为 `127.0.0.1`
- 不要将 PostgreSQL 和 Redis 端口暴露到公网
- 仅开放 SSH、HTTP 和 HTTPS 等必要端口
- 定期备份整个项目，并实际验证恢复流程
- 数据库、Redis、JWT 和 TOTP 应使用不同的随机密码或密钥

## 常见问题

### 启动时报 `POSTGRES_PASSWORD is required`

确认 `deploy/.env` 已创建，且 `POSTGRES_PASSWORD` 不是空值或示例占位值。

### 页面无法访问

检查容器状态和应用日志：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml ps
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml logs --tail=200 sub2api
```

同时确认 `SERVER_PORT` 未被占用，服务器防火墙允许访问该端口。

### 修改 `.env` 后没有生效

重新创建容器：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.nova.yml up -d --force-recreate
```

涉及源码或 Dockerfile 修改时，额外添加 `--build`。

### 如何关闭额度透支

在 `.env` 中设置：

```dotenv
GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED=false
```

然后重新创建应用容器使配置生效。
