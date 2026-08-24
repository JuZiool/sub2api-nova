# Nova 上游手动接入与维护方案

## 1. 当前状态

- Nova 已暂停 GitHub 上游自动同步、自动合并和自动成功基线记录。
- 当前主线通过 PR 维护，`main` 保持为稳定分支。
- 上游更新由维护者人工评估、选择性移植、验证后提交。
- 本方案不采用上游整批覆盖，也不直接执行 `git merge upstream/main`。

## 2. 维护原则

1. `main` 只保留经过验证的代码，不在主线上直接试改。
2. 每次上游接入使用独立分支和 PR。
3. 上游变更按功能拆分，优先移植安全修复和低风险修复。
4. Nova 的配额、计费、支付、品牌前端和部署定制优先级高于上游同名实现。
5. 每个功能尽量形成独立提交，便于审查、回滚和后续追踪。
6. 上游基线只记录已经确认被完整吸收的版本；选择性移植不推进完整基线。

## 3. 上游变更分级

### P0：安全和依赖

- DOMPurify 升级到 `3.4.14`。
- 更新前端锁文件，并通过依赖审计和前端构建验证。

### P1：低风险功能

- 支持带方括号的 IPv6 代理地址。
- 用户并发数 `0` 表示不限。
- 账户列表默认显示优先级。
- 运维错误详情返回列表并保留筛选条件。
- 将网关参数透传修复适配到 Nova 现有 Compose 文件。

### P2：需要人工融合

- `fast/priority` 按上游实际响应档位计费。
- 渠道时间段定价的工作日规则。
- OpenAI Responses、工具调用、Grok 和 WebSocket 兼容性修复。

这些内容会触碰 Nova 的计费、配额或 Gateway 定制，必须逐文件比较并连同回归测试移植。

### P3：暂缓评估

- 完整插件系统。

插件系统涉及运行时、插件包格式、管理后台、协议代码和数据库迁移 `229/230`。除非产品明确需要插件生态，否则不纳入普通上游更新批次。

## 4. 每次手动接入流程

### 4.1 建立安全基线

```bash
git switch main
git pull --ff-only origin main
git tag nova-before-upstream-YYYYMMDD
git status --short
```

工作区必须干净。缓存文件、构建产物和临时报告不得提交。

### 4.2 获取并盘点上游变化

```bash
git fetch upstream main
git switch -c upstream/manual-YYYYMMDD
git diff --stat <上次上游基线> upstream/main
git diff --name-status <上次上游基线> upstream/main
```

重点检查以下 Nova 定制路径：

- `backend/internal/service` 中的配额、计费和 Gateway 代码。
- `backend/internal/payment`。
- `backend/migrations`。
- `frontend/src/components`、`frontend/src/stores`、`frontend/src/router`。
- `deploy`、`Dockerfile`、版本文件。

### 4.3 选择性移植

按 P0 → P1 → P2 的顺序处理。每项变更都要：

- 阅读上游提交和测试。
- 对照 Nova 当前实现手动修改。
- 保留 Nova 的业务规则和配置命名。
- 新增或移植对应回归测试。
- 记录来源提交 SHA 和实际调整内容。

不直接复制上游已被 Nova 删除的部署文件，也不覆盖 Nova 的关键定制目录。

### 4.4 本地验证

后端至少执行：

```bash
cd backend
go test ./...
golangci-lint run ./...
```

前端至少执行：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm lint:check
pnpm typecheck
pnpm test:run
pnpm build
```

部署至少执行：

```bash
docker compose -f deploy/docker-compose.local.yml config
```

并完成 Nova Docker Compose 启动、健康检查和基础请求冒烟测试。

### 4.5 提交和合并

1. `git diff --check`。
2. 按功能拆分提交，例如：
   - `fix(frontend): 升级 DOMPurify 安全版本`
   - `fix(proxy): 支持批量代理 IPv6 地址`
3. 推送功能分支。
4. 创建 PR，填写上游来源、Nova 特殊处理和验证结果。
5. 通过必需检查后合并到 `main`。

## 5. 基线记录规则

- 只移植单个修复或部分功能时，不更新 `state/upstreams.json` 的完整上游基线。
- 完整吸收某个上游版本并完成回归验证后，才更新：
  - `lastSuccessfulCommit`
  - `lastSuccessfulVersion`
  - `lastSuccessfulNovaCommit`
  - `lastSyncAt`
- 基线更新应与对应合并提交放在同一个 PR 中，并说明未采纳的上游变更。

## 6. 回滚方案

- 优先回滚单个功能提交，不回滚整个 Nova 主线。
- 计费、配额、支付或 Gateway 出现异常时，立即回滚对应 PR。
- 数据库迁移前先备份，迁移失败时使用备份恢复。
- 保留每次接入前的 `nova-before-upstream-YYYYMMDD` 标签。
- 回滚后不得推进上游成功基线。

## 7. 首个执行批次

建议第一个手动批次只包含：

1. DOMPurify 安全升级。
2. IPv6 代理解析及测试。
3. 并发数 `0` 表示不限。
4. 账户优先级显示。
5. 运维错误详情返回列表。

计费、OpenAI Gateway 和插件系统分别建立后续 PR，避免一次变更同时影响多个核心业务域。
