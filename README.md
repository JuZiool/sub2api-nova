# Sub2API Nova 部署指南

Sub2API Nova 使用 Docker Compose 运行应用、PostgreSQL 和 Redis。服务器直接拉取 GitHub Container Registry（GHCR）的预构建镜像，不需要克隆源码，也不需要在服务器编译。

## 快速安装

在新服务器执行：

```bash
sudo mkdir -p /opt/sub2api-nova
cd /opt/sub2api-nova
curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh | sudo bash
```

安装脚本会显示菜单：

```text
1) 全新安装
2) 迁移后安装
3) 镜像升级
```

选择 `1` 后按提示填写服务端口、管理员邮箱和管理员密码。脚本会自动生成 `.env`、数据库密码、Redis 密码、JWT 密钥和 TOTP 密钥，然后拉取镜像并启动服务。

脚本要求 root 权限；如果当前已经是 root，可以去掉命令中的 `sudo`。

## 在线升级

### 推荐：使用本地更新脚本

进入现有部署目录执行：

```bash
cd /opt/sub2api-nova
sudo bash update.sh
```

`update.sh` 会拉取新镜像、重建应用容器并执行健康检查。升级失败时会尝试自动恢复旧镜像，并记录部署状态。

手动回滚到上一次成功更新前的镜像：

```bash
sudo bash update.sh --rollback
```

### 服务器直接使用在线安装脚本

可以，不需要先拉取源码。在线脚本适合服务器上的脚本较旧，或需要补齐部署文件的情况：

```bash
cd /opt/sub2api-nova
curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh \
  | sudo bash -s -- --mode 3
```

模式 `3` 要求当前目录已有 `.env`，只升级应用镜像，保留以下配置和数据：

```text
.env
data/
postgres_data/
redis_data/
```

也支持在旧版 Git 仓库根目录执行。脚本会自动识别其中的 `deploy/.env`，并在目标目录补齐 Compose 和更新脚本。找不到 `.env` 时会直接退出，不会创建新配置或数据目录。

默认镜像为 `ghcr.io/juziool/sub2api-nova:latest`。需要固定版本时，可指定提交 SHA 对应的镜像 tag：

```bash
sudo env SUB2API_IMAGE=ghcr.io/juziool/sub2api-nova:sha-完整提交号 \
  bash update.sh
```

日常更新建议使用 `update.sh`，这样会记录回滚状态；在线 `install.sh --mode 3` 主要用于无源码升级和刷新部署脚本。

## 迁移到新服务器

### 完整目录迁移

先停止旧服务器服务，再复制整个部署目录中的配置和数据：

```text
.env
data/
postgres_data/
redis_data/
```

复制到新服务器后，在该目录执行安装脚本并选择模式 `2`：

```bash
curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh \
  | sudo bash -s -- --mode 2
```

模式 `2` 会保留已有 `.env` 和持久化数据，只补齐运行文件并启动服务。

### 使用逻辑备份迁移

跨 PostgreSQL 版本时，优先使用逻辑备份。旧服务器停止服务后保存 `.env`、`data/` 和数据库备份（例如 `.sql.gz`），新服务器使用模式 `2` 完成部署后，再在管理后台恢复数据库备份。

不要直接复制正在运行中的 `postgres_data/`。完整复制 `postgres_data/` 和恢复 `.sql.gz` 是两种互斥方案，选择其中一种即可。

## 常用命令

以下命令在部署目录执行：

```bash
# 查看状态
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml ps

# 查看应用日志
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml logs -f sub2api

# 停止服务但保留数据
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml stop

# 启动服务
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml start

# 镜像升级（推荐）
sudo bash update.sh

# 回滚到上一次成功更新前的镜像
sudo bash update.sh --rollback
```

健康检查：

```bash
curl http://127.0.0.1:8080/health
```

浏览器访问：`http://服务器IP:8080`。如果修改了 `SERVER_PORT`，请替换为实际端口。

修改 `.env` 后，需要重新创建容器使配置生效：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml up -d --force-recreate
```

## 文件和安全

当前目录就是部署根目录。模式 `2` 和 `3` 不会覆盖已有配置或数据：

```text
.env                       运行配置、密码和密钥
.env.example               配置模板
docker-compose.local.yml   PostgreSQL、Redis 和应用基础配置
docker-compose.ghcr.yml    GHCR 镜像覆盖配置
install.sh                 安装、迁移和在线升级脚本
update.sh                  镜像更新和回滚脚本
data/                      应用配置、日志和本地文件
postgres_data/              PostgreSQL 数据
redis_data/                 Redis 数据
```

注意：

- `.env` 包含密码和密钥，只允许管理员读取，不要提交到 Git 或公开分享。
- PostgreSQL `5432` 和 Redis `6379` 只在 Compose 内部网络使用，不要映射到公网。
- 生产环境建议使用 Nginx 或 Caddy 提供 HTTPS，并限制管理端访问来源。
- 定期备份 `.env`、`data/` 和数据库；密钥变化可能导致登录会话或二次验证失效。

## 环境要求

- Docker Engine
- Docker Compose v2（脚本也兼容 `docker-compose`）
- `flock`（`update.sh` 用于防止并发更新）
- 安装脚本需要 root 权限
- 建议至少 2 核 CPU、4 GB 内存
