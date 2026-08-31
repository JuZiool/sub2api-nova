# Sub2API Nova 部署指南

项目使用 Docker Compose 运行 `sub2api`、PostgreSQL 和 Redis。服务器直接使用 GitHub Container Registry 的预构建镜像，不需要克隆源码，也不需要在服务器编译。

## 一键安装

先进入准备存放部署文件的目录：

```bash
mkdir -p /opt/sub2api-nova
cd /opt/sub2api-nova
curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh | bash
```

脚本会显示菜单：

```text
1) 全新安装
2) 迁移后安装
3) 镜像升级
```

如果 Docker 已经由 iStoreOS 管理器安装，可以加上：

```bash
curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh \
  | bash -s -- --no-install-docker
```

## 三种模式

### 1. 全新安装

选择 `1` 后填写端口、管理员邮箱和密码。脚本会创建：

- `.env`
- `data/`
- `postgres_data/`
- `redis_data/`
- Compose 配置文件

然后拉取 `ghcr.io/juziool/sub2api-nova:latest` 并启动三个容器。数据库、Redis、JWT 和 TOTP 密钥会自动生成。

### 2. 迁移后安装

把旧服务器部署目录复制到新服务器，进入该目录执行安装脚本并选择 `2`。脚本会保留已有 `.env` 和所有数据，只补齐缺少的运行文件并启动服务。

使用逻辑备份迁移时，旧服务器停止服务后保存：

```text
.env
data/
数据库备份.sql.gz
```

新服务器安装完成后，在管理后台上传并恢复 `.sql.gz`。跨 PostgreSQL 版本迁移优先使用逻辑备份，不要直接复制正在运行的 `postgres_data/`。

如果完整复制了 `postgres_data/`，则不需要再导入 `.sql.gz`，两种方式二选一。

### 3. 镜像升级

在当前部署目录执行安装脚本并选择 `3`：

```bash
cd /opt/sub2api-nova
bash install.sh --mode 3
```

脚本只拉取新镜像并重建 `sub2api`，不会覆盖 `.env`、`data/`、`postgres_data/` 或 `redis_data/`。

如果服务器上的脚本版本较旧，或不想依赖服务器上的 Git 工作区，可以直接使用 GitHub 在线脚本升级现有部署：

```bash
cd /opt/sub2api-nova && curl -fsSL https://raw.githubusercontent.com/JuZiool/sub2api-nova/main/deploy/install.sh | bash -s -- --mode 3
```

在线脚本只会拉取镜像并重建应用容器，保留现有 `.env`、`data/`、`postgres_data/` 和 `redis_data/`。

默认使用 `latest`，也可以固定镜像 tag 或 digest：

```bash
SUB2API_IMAGE=ghcr.io/juziool/sub2api-nova:sha-完整提交号 \
  bash install.sh --mode 3
```

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

# 镜像升级
bash install.sh --mode 3

# 回滚到上一次成功更新前的镜像
bash update.sh --rollback
```

健康检查：

```bash
curl http://127.0.0.1:8080/health
```

浏览器访问：`http://服务器IP:8080`。

## 文件和安全

当前目录就是部署根目录，安装脚本不会覆盖已有配置或数据：

```text
.env                       运行配置、密码和密钥
.env.example               配置模板
docker-compose.local.yml   三个服务定义
docker-compose.ghcr.yml    GHCR 镜像覆盖配置
install.sh                 三模式安装脚本
update.sh                  镜像更新和回滚脚本
data/                      应用配置、日志和本地文件
postgres_data/              PostgreSQL 数据
redis_data/                 Redis 数据
```

`.env` 应限制为管理员可读。PostgreSQL `5432` 和 Redis `6379` 只在 Compose 内部网络使用，不要映射到公网。生产环境建议使用 Nginx 或 Caddy 提供 HTTPS。

如果修改了 `.env`，重新创建应用容器：

```bash
docker compose --env-file .env -f docker-compose.local.yml -f docker-compose.ghcr.yml up -d --force-recreate
```

## 环境要求

- Docker Engine
- Docker Compose v2
- root 权限
- 建议至少 2 核 CPU、4 GB 内存
- iStoreOS 用户请先在 Docker 管理器中安装并启动 Docker/Compose
