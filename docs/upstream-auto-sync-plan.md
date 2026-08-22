# Nova 上游自动同步与自动合并方案

## 1. 目标

让 `sub2api-nova` 在上游 `Wei-Shaw/sub2api` 有新提交时，能够自动完成：

```text
检查上游更新
→ 生成同步分支
→ 应用上游差异
→ 检查 Nova 定制影响
→ 运行官方测试和 Nova 测试
→ 启动完整 Docker 环境验证
→ 创建同步 PR
→ 满足条件后自动合并
→ 构建并发布 GHCR 镜像
```

自动化的前提是：

- 不直接向 `main` 写入同步结果。
- 冲突、关键功能受影响或验证失败时自动停止。
- 只有所有验证通过且没有人工阻止标记时，才允许自动合并。
- 发布失败时保留上一版本，不删除可回滚镜像。

## 2. 当前约束

### 2.1 Nova 是完整 Fork

Nova 已经包含额度透支、品牌 UI、国产供应商、Grok、支付和部署脚本等定制，不能只按普通上游 Fork 的方式直接覆盖文件。

### 2.2 首次同步不能依赖普通 merge

当前 Nova 的 `main` 与最新 `upstream/main` 没有可用的共同 Git 祖先，不能把下面的命令作为首次同步方案：

```bash
git merge upstream/main
```

应使用最近一次成功融合的上游提交作为基线，生成“上游旧基线到新提交”的差异，再将差异以三方方式应用到 Nova 当前分支。首次落地时必须先校验基线树和关键文件，校验失败则人工建立新的基线。

## 3. 版本状态文件

新增：

```text
state/upstreams.json
```

示例：

```json
{
  "repository": "Wei-Shaw/sub2api",
  "branch": "main",
  "lastSuccessfulCommit": "<上次成功融合的上游提交>",
  "lastSuccessfulVersion": "0.1.179",
  "novaVersion": "0.1.179-nova.1",
  "lastSyncCommit": "<Nova 最近一次同步提交>",
  "lastSyncAt": "2026-08-22T00:00:00Z"
}
```

每次同步成功后才更新 `lastSuccessfulCommit`。同步冲突、测试失败或 Docker 验证失败时，不得更新成功基线。

版本来源统一为：

- `FORK_VERSION`：Nova 对外显示版本。
- `backend/cmd/server/VERSION`：兼容现有构建流程。
- `state/upstreams.json`：机器可读的上游基线。
- Docker 镜像完整 Git SHA：实际部署版本。

## 4. Nova 定制保护清单

新增：

```text
state/nova-customizations.json
```

初始清单至少包括：

```json
{
  "criticalPaths": [
    "backend/internal/service/openai_codex_quota_overdraft.go",
    "backend/internal/service/openai_codex_quota_overdraft_probe.go",
    "backend/internal/repository/account_repo_codex_overdraft.go",
    "frontend/src/views/HomeView.vue",
    "frontend/src/styles",
    "frontend/src/components",
    "frontend/src/stores",
    "deploy",
    "Dockerfile"
  ],
  "manualReviewPaths": [
    "backend/internal/service/billing_service.go",
    "backend/internal/service/account.go",
    "backend/internal/service/openai_gateway_service.go",
    "backend/internal/repository/migrations",
    "frontend/src/router",
    "frontend/src/api"
  ]
}
```

规则：

- `criticalPaths` 被上游修改时，自动同步 PR 必须暂停自动合并，添加 `nova-manual-review` 标签。
- `manualReviewPaths` 被修改时，允许创建 PR，但需要额外的 Nova 专属测试和人工确认。
- 上游删除 Nova 依赖文件、改变数据库迁移或修改 Docker 部署配置时，直接停止同步。
- 清单不是永久固定的，每新增一项 Nova 核心功能，就同时补充清单和测试。

## 5. 同步脚本

新增：

```text
scripts/sync_upstream.py
```

脚本职责：

1. 读取 `state/upstreams.json`。
2. 获取 `upstream/main` 最新提交和版本。
3. 比较旧基线与新提交，生成二进制安全的上游差异。
4. 从当前 `main` 创建同步分支：

   ```text
   sync/upstream-<短提交>-<日期>
   ```

5. 以三方方式应用上游差异。
6. 记录冲突文件和受影响的 Nova 定制路径。
7. 无冲突时更新版本文件和同步报告。
8. 运行基础静态检查。
9. 生成同步提交，供 GitHub Actions 创建 PR。

建议输出：

```text
artifacts/upstream-sync-report.md
```

报告至少包含：

- 上游旧提交和新提交。
- 上游版本变化。
- 变更文件统计。
- 冲突文件。
- 受影响的 `criticalPaths` 和 `manualReviewPaths`。
- 需要执行的额外测试。
- 自动合并判定结果。

伪代码：

```text
old = state.lastSuccessfulCommit
new = upstream/main

if old == new:
    exit("没有上游更新")

create sync branch from Nova main
generate upstream diff old..new
apply diff with three-way strategy

if conflicts:
    report and stop

check changed paths against customization manifest
update version and report
commit sync result
create PR
```

## 6. GitHub Actions 工作流

### 6.1 上游检查和创建 PR

新增：

```text
.github/workflows/upstream-sync.yml
```

触发方式：

- 每天定时运行一次。
- 支持 `workflow_dispatch` 手动运行。
- 允许手动指定上游提交，方便重试和回归验证。

工作流职责：

1. 检出完整历史。
2. 拉取 `upstream/main`。
3. 运行 `scripts/sync_upstream.py`。
4. 没有更新时正常结束。
5. 有冲突时创建失败报告，不创建可合并 PR。
6. 无冲突时推送 `sync/*` 分支。
7. 创建或更新一个同步 PR。
8. 根据影响范围添加标签：
   - `upstream-sync`
   - `nova-manual-review`
   - `nova-critical-change`

该工作流不直接修改 `main`。

### 6.2 PR 验证

新增或完善：

```text
.github/workflows/pr-validation.yml
```

验证分为四层：

#### 第一层：文件和静态检查

```bash
git diff --check
```

检查版本文件、状态文件和同步报告格式是否正确。

#### 第二层：后端验证

```bash
cd backend
gofmt -l .
go test ./...
golangci-lint run ./...
```

#### 第三层：前端验证

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm lint:check
pnpm typecheck
pnpm test:run
pnpm build
```

#### 第四层：Docker 验证

使用 Nova 现有 Compose 配置：

```bash
cd deploy
docker compose --env-file .env \
  -f docker-compose.local.yml \
  -f docker-compose.nova.yml \
  config --quiet

docker compose --env-file .env \
  -f docker-compose.local.yml \
  -f docker-compose.nova.yml \
  build sub2api
```

PR 验证工作流只使用只读权限，不向外部 PR 暴露发布凭据。

## 7. Nova 专属验证

官方测试通过不代表 Nova 功能正常，必须增加专属冒烟测试。

### 7.1 后端功能

至少验证：

- `GATEWAY_CODEX_QUOTA_OVERDRAFT_ENABLED` 开关。
- Codex 配额探测、透支调度和额度计算。
- 账户列表、账户状态和账户用量接口。
- Nova 新增的国产模型和供应商能力。
- Grok、OpenAI 等已有定制转发能力。
- 数据库迁移和 Redis 初始化。

### 7.2 前端功能

至少验证：

- Nova 品牌名称和 Logo。
- 首页加载和登录后跳转。
- 管理后台首页和账户列表。
- Token 使用排行榜。
- 深色模式切换和文字对比度。
- 手机端首页、后台看板和账户工具栏布局。
- 额度透支状态和用量展示。

### 7.3 Docker 集成冒烟

启动 PostgreSQL、Redis 和 Nova 后，执行：

```text
GET /health
管理员登录
获取系统配置
获取账户列表
获取模型列表
执行一条受控的网关请求
```

测试使用专用临时数据库和测试账户，不使用生产密钥，不连接真实上游账户。

## 8. 自动合并规则

同步 PR 只有同时满足以下条件才允许自动合并：

- 上游差异成功应用。
- 没有 Git 冲突。
- 没有 `nova-critical-change` 标签。
- 没有 `nova-manual-review` 标签，或人工已移除该标签。
- 所有必需的 GitHub Checks 通过。
- Nova 专属后端、前端和 Docker 冒烟测试通过。
- PR 分支基于最新 `main`。
- 没有人工添加 `no-auto-merge` 标签。

自动合并使用 GitHub 原生 Auto-merge 或：

```bash
gh pr merge <PR_NUMBER> --auto --squash
```

不允许同步工作流直接执行：

```bash
git push origin main --force
```

也不允许绕过分支保护规则。

## 9. 分支保护

`main` 必须启用：

- 必须通过 PR 合并。
- 必须通过全部必需检查。
- 禁止强制推送。
- 禁止删除分支。
- 至少保留一个管理员人工应急停止方式。
- 同步机器人只能创建分支和 PR，不能绕过检查直接写入 `main`。

自动合并使用单独的 GitHub App 或最小权限的机器人令牌，避免把仓库管理员令牌放进普通测试任务。

## 10. 合并后的发布和回滚

合并到 `main` 后继续使用现有 GHCR 发布工作流：

```text
main 合并提交
→ 构建 linux/amd64 和 linux/arm64 镜像
→ 推送 sha-完整提交标签
→ 更新 latest
```

发布前增加以下检查：

- 镜像构建成功。
- 容器启动成功。
- `/health` 通过。
- 数据库和 Redis 健康。
- 核心接口冒烟通过。

服务器更新继续使用 `deploy/update.sh`：

- 更新前保留旧镜像 ID，并创建带上一稳定提交的本地回滚标签。
- 新容器健康检查失败时自动尝试恢复旧镜像。
- 更新成功后写入被忽略的 `deploy/.deploy-state.json`，记录状态、提交、镜像、镜像 ID 和回滚标签。
- 输出容器状态和最近日志。
- `bash deploy/update.sh --rollback` 只切换应用镜像，不修改 Git 或数据库。

回滚方式：

```bash
bash deploy/update.sh --rollback
```

生产环境不允许直接回滚数据库迁移；涉及不可逆迁移时，必须先提供向前兼容方案和备份恢复方案。

## 11. 分阶段实施

### 阶段一：建立基线和验证

目标：先确保 Nova 的功能可以被自动验证。

内容：

- 确认最近一次成功融合的上游提交。
- 新增 `state/upstreams.json`。
- 新增 Nova 定制保护清单。
- 整理 Nova 专属后端、前端和 Docker 冒烟测试。
- 增加 PR 验证工作流。
- 配置 `main` 分支保护。

验收：

- 手动 PR 可以完整跑完所有检查。
- Docker 能启动三个服务。
- Nova 核心页面和接口通过冒烟测试。

### 阶段二：自动生成同步 PR

目标：上游有更新时自动产生可审查的同步 PR。

内容：

- 实现 `scripts/sync_upstream.py`。
- 实现上游差异三方应用。
- 生成同步报告。
- 自动标记关键文件影响。
- 新增定时同步工作流。

验收：

- 无冲突更新能自动生成 PR。
- 有冲突更新能停止并报告。
- 状态文件只在验证成功后更新。

### 阶段三：条件自动合并

目标：低风险上游更新自动合并。

内容：

- 配置必需检查。
- 配置 GitHub Auto-merge。
- 无关键文件影响时允许自动合并。
- 关键文件、数据库迁移和部署文件变更时自动暂停。

验收：

- 普通上游更新可自动完成同步、测试和合并。
- Nova 核心功能变化会等待人工确认。
- 任何测试失败都不会合并。

### 阶段四：合并后发布和回滚

目标：合并后的镜像可验证、可回滚。

内容：

- 发布工作流增加镜像启动冒烟测试。
- 记录最后稳定提交和镜像标签。
- 完善 `deploy/update.sh` 的失败保留和回滚输出。
- 定期验证数据库备份恢复流程。

## 12. 自动合并决策表

| 情况 | 自动创建 PR | 自动合并 | 处理方式 |
| --- | --- | --- | --- |
| 上游无更新 | 否 | 否 | 正常结束 |
| 无冲突、只改普通文件、全部测试通过 | 是 | 是 | 自动合并并发布 |
| 修改 Nova 普通定制文件 | 是 | 否 | 标记人工审核 |
| 修改额度透支、认证、支付、迁移或 Docker | 是 | 否 | 强制人工审核 |
| 存在冲突 | 可生成报告 | 否 | 人工解决冲突 |
| 测试或构建失败 | 是 | 否 | 修复后重新运行 |
| 发布后健康检查失败 | 已合并 | 否 | 保留旧镜像并回滚 |

## 13. 最终目标

最终系统应满足：

```text
普通上游更新：自动同步、自动验证、自动合并、自动发布
Nova 核心功能受影响：自动暂停，人工确认
发生冲突或测试失败：自动停止
发布后启动失败：保留旧版本并可回滚
```

核心原则是：**自动化负责重复工作，验证负责保护 Nova，人工只处理真正的冲突和高风险变更。**
