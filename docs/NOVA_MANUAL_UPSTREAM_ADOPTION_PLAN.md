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

## 7. 已完成的历史首批

首个手动批次已经独立记录在 `docs/NOVA_MANUAL_UPSTREAM_BATCH_20260824.md`。其中的
DOMPurify、IPv6 代理、并发数、账户优先级和运维详情变更均为选择性移植，不代表完整
上游基线推进。

## 8. v0.1.184 专项选择性合并方案

### 8.1 审计结论

- 完整成功基线：`7634e3c23b5b9afc588c37b170820f63f1d41bbb`（`0.1.183`）。
- 审计目标：`200602b41bf97c706f8c28fdc9df97ef5ece1aa9`（`0.1.184`）。
- 上游范围包含 173 个提交（101 个非合并提交）和 343 个变更路径。
- 当前安全分支 `merge/upstream-200602b41-guardrails` 的只读三方预检为 `blocked`：
  37 个真实冲突、7 个缺失 index 路径、0 个保护路径删除。

不得执行 `git merge upstream/main`、整批 `cherry-pick`，也不得为了消除冲突而恢复 Nova
已经删除的文件。冲突只是提醒必须按功能切片，不应被作为一次性人工解冲突的待办。

本轮已经安全接入但不推进完整基线的提交为：

- `a7f6e0d13`：结构化只读预检报告。
- `2921f286d`：Nova 迁移 `234`、`235` 的用量遥测存储契约。
- `1af555501`：请求推理强度和原生压缩遥测，仅记录元数据。

### 8.2 Nova 不可破坏边界

1. 不改动 Codex 透支的探测、暂停、恢复和调度：`openai_codex_quota_overdraft*`、`account_repo_codex_overdraft*`。
2. 不改动国产供应商的余额、额度、轮询和扣费：`cn_provider_balance_*`、`cn_provider_quota_*`。
3. 不直接覆盖实际计费、模型倍率、渠道定价、Nova 费率审计或模型价格 JSON。
4. 不改写支付路由、订单状态机、回调验签或现有支付前端。
5. 冻结品牌前端：`frontend/src/components`、`stores`、`router`、`styles`、`HomeView.vue`、Nova 图标和首页文案。
6. 冻结部署与版本：`deploy`、`Dockerfile`、`FORK_VERSION`、`backend/cmd/server/VERSION`。
7. 迁移只可追加唯一编号，不能复用上游的 `231_*` 文件名或修改已执行迁移。
8. 选择性移植期间不更新 `state/upstreams.json` 或 `.nova-upstream-provenance.json`，不宣称已完整同步到 `0.1.184`。

默认关闭的新增能力必须在关闭时与当前版本保持同一业务结果；新增适配器不得自动轮询、参与调度或成为计费输入。

### 8.3 分批顺序

#### A. 公开分组限制，默认关闭

- 上游来源：`b56c61ecc`。
- 新增 `236_add_user_restrict_public_groups.sql`，字段为 `users.restrict_public_groups BOOLEAN NOT NULL DEFAULT false`。
- 贯通 Ent、用户仓储、管理员 DTO、API Key 鉴权缓存和 `User.CanBindGroup`。
- 开关为 `false` 时，所有既有用户仍可绑定所有公开分组；专属分组仍只按 `AllowedGroups` 判断。仅当开关为 `true` 时，公开分组也必须在 `AllowedGroups` 内。
- 第一阶段不接入模型广场过滤，不改 `UserAllowedGroupsModal.vue`，不改用户端展示。
- 准入：默认用户、既有授权列表、受限用户、专属分组、已绑定 API Key 的请求鉴权缓存均有回归测试。
- 建议提交：`功能：支持按用户限制公开分组访问（默认关闭）`。

#### B. 无计费副作用的协议兼容

- 上游来源：`3c5553e25`、`901a77cfb`、`b1737cc84`、`50ba14629`。
- 分别处理合成 Responses 的 `created_at`、Anthropic 工具调用 thinking、混合内置工具和多模态客户端工具输出。
- 每个协议方向单独提交，只改转换器和 wire fixture；不得改账号选择、余额判断、倍率、用量扣费或 Gateway 路由。
- 准入：HTTP 和流式 fixture 覆盖；普通 Chat、Responses 透传和既有 Codex 请求的输出保持不变。

#### C. 流式与 WebSocket 可靠性，逐项验证

- 上游来源：`60756c0ca`、`b7ec3cdad`、`c83dced4b`、`d5a012463`、`7c616db07`；`f4e3eb1c5` 的安全策略识别最后单独审查。
- 先处理 Responses 预输出 keepalive；复用现有 `gateway.stream_keepalive_interval`，值为 `0` 时严格无行为变化。
- 其后依次处理客户端正常关闭归因、会话隔离和超大请求 HTTP bridge；每项独立提交。
- 保留 Nova 的 WebSocket 强制 HTTP、连接池、透支调度和错误审计策略。客户端取消不能被记为账号成功，真实上游故障也不能被弱化。
- 准入：HTTP/WS 双路径、断连、超时、长思考首包、会话抢占、超大请求、用量落库及 Codex 透支、模型级限流回归。

#### D. Gateway 传输容错，先默认关闭

- 上游来源：`44003d7f6` 的 Anthropic/Bedrock 传输错误转移与临时摘除逻辑。
- 先放在新的显式配置开关后，默认 `false`；关闭时保留当前 502、调度和账号状态写入。
- 仅在 staging 确认 DNS、TLS、代理认证、连接拒绝分类与 Nova 一致后，才对指定平台灰度开启；`context.Canceled` 永远不得触发换号或摘除。
- 准入：失败转移、临时摘除、耗尽响应、取消请求，以及国产供应商和 Codex 账号不受影响。

#### E. 供应商与额度能力，隔离适配器

- 上游来源：`c4e46c3be`（智谱 Team Coding Plan）、`30b29e51e`（Ollama Cloud 用量窗口）、`e652f6e20`（配额抓取缓存）及 Grok/Anthropic 协议修复。
- 不直接覆盖 Nova 的国产供应商余额与额度服务。每项先作为独立账号类型或只读探测适配器，默认关闭、无自动轮询、无调度参与、无计费输入。
- 准入：开关前后既有国产账号的请求数、余额、额度、账号状态和扣费记录完全相同；新适配器必须有独立 mock 与集成测试。

#### F. 支付修复，单供应商封闭验证

- 上游来源：`1e8745c88`（EasyPay 相对 `payurl/qrcode`）和 `02eee39dd`（所选币种展示）。
- 先只审查 EasyPay 后端：仅把以 `/` 开头的相对地址按实例 `apiBase` 解析；绝对 URL、深链和无前导斜杠二维码 token 原样保留。
- 支付页币种文案另开前端小批次，保持 Nova 布局、翻译和响应式规则。
- 准入：支付创建、二维码、跳转、回调验签、退款、失败重试和全部既有支付类型回归。

#### G. 计费、价格与倍率，只做影子校验

- 上游来源：`b5827cfd5`（DeepSeek 峰谷价）、`eb4237a2b`（带后缀模型渠道定价）、`3a9070359`、`50ad6e2e5`、`82105f260`（Codex tier 计费）。
- 不合并到实际扣费链路。先利用 Nova 费率审计离线比较当前和候选结果，输出差异、命中规则和影响订单，不改变用户余额或账单。
- 样本必须覆盖 Nova 自定义倍率、渠道价、国产供应商、Codex 透支、免费/优惠场景；产品确认差异后才能提交独立计费方案。
- 本轮不接入 `billing_service.go` 实际逻辑、模型价格 JSON、渠道倍率和结算前端。

#### H. Codex 模型目录、模型广场和大范围前端，继续冻结

- 上游来源：`22e1b8144`、`e471be730` 及后续 Codex catalog、模型广场和账户页改动。
- 该范围与 Nova Codex 透支、模型倍率、账号显示、品牌前端和路由重叠，本轮不接入。
- 后续必须先有独立设计，证明目录展示、模型路由和可用模型缓存不会改变 Nova 透支调度或既有 API Key 行为。

### 8.4 执行与发布闸门

1. 每批从当前安全分支建立单功能分支，先打 `nova-before-<batch>` 标签并确认工作区干净。
2. 阅读指定上游提交和测试，只手工移植必要语义；不复制上游迁移编号、前端大组件或部署文件。
3. 先增加 Nova 回归测试，再写最小实现；关闭状态必须验证与当前版本业务结果一致。
4. 每批独立中文提交，记录上游 SHA、Nova 保留差异和验证命令；Gateway、迁移、支付、计费不得混在同一提交。
5. 通过局部测试后执行 `git diff --check`、`go test ./...`、前端 `npm run lint:check`、`npm run typecheck`、`npm run test:run`、`npm run build`。
6. 涉及迁移或 Gateway 时，必须在全新数据目录执行 Nova Compose 构建、启动、`/health`、登录、既有 API Key、Codex 透支、国产供应商额度、支付模拟及新功能冒烟。
7. 任一核心契约失败，立即只回滚当前功能提交；追加迁移保留，功能开关回到关闭状态，不推进后续批次。

本专项方案的目标不是把分支伪装成完整 `0.1.184`，而是在不损害 Nova 特性的前提下逐项吸收可验证价值。只有未来覆盖所有未采纳变更、完成全量回归且产品确认版本语义一致后，才能单独评审版本号与上游成功基线更新。
