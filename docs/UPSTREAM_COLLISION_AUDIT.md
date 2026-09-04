# Nova 上游碰撞审计报告(2026-09-04)

> 纯只读分析,用于回答"Nova 定制做薄"的第一张地图:哪些上游文件最值得翻修。

## 1. 方法与数据窗口

- Nova 侧:本地 `HEAD`(43fbda6ad)与 `upstream/main`(b1748c4ea,基线 5097b3145)的差异。
- 上游侧:upstream/main 近 90 天非合并提交对每个文件的改动次数(作为"上游未来还会继续改这些文件"的代理指标)。
- 碰撞分 = 上游改动次数 × Nova 差异行数(±),只统计上游改动 ≥ 5 次且 Nova 也有差异的文件。
- 差异性质通过抽样 `git diff` 判定,标注为结论而非猜测。

## 2. 关键结论

1. Nova 与上游总差异 865 文件(M 613 / A 95 / D 155 / R 2),其中 **613 个"改写上游文件"里,近 90 天被上游高频(≥5 次)改动且 Nova 也改过的约 45 个**,真正的"高碰撞深改写"只有 10 个左右。
2. 抽样 `billing_service.go`、`openai_gateway_passthrough.go` 发现:**相当比例的差异是格式漂移噪音**(gofmt 对齐、注释挪动、空行增删、别名调用改写)和"上游新增字段/函数而 Nova 未同步",并非 Nova 语义定制。例如 passthrough 的大段 diff 是注释位置移动与 `c.Set` 直调替换。
3. 因此"做薄"的对象不是 613 个文件,而是**少数真实语义碰撞文件**;其余大部分差异可通过工具自动吸收(格式归一)或选择"锁定不跟"。

## 3. 碰撞热力图(Top 40)

| 上游次数 | Nova + | Nova - | 文件 | 初步性质 |
| --- | --- | --- | --- | --- |
| 69 | 95 | 827 | README.md | Nova 品牌重写(净差异多因上游新增文档 Nova 未跟)→ 锁定 |
| 100 | 109 | 293 | backend/internal/handler/openai_gateway_handler.go | 需复核:Nova 透传/Codex 内嵌 |
| 45 | 0 | 743 | README_JA.md | Nova 删除/未同步 → 锁定 |
| 42 | 0 | 787 | README_CN.md | 同上 |
| 69 | 163 | 268 | backend/internal/service/openai_gateway_passthrough.go | 混合:格式漂移 + Codex 身份注入调用 → 收敛 |
| 44 | 232 | 350 | frontend/src/views/admin/GroupsView.vue | Nova 分组/倍率定制前端 → 收敛或锁定 |
| 55 | 186 | 255 | backend/internal/service/billing_service.go | 混合:字段各加各的 + Nova 常量 + 格式漂移 → 需逐段核对 |
| 49 | 69 | 141 | backend/internal/service/openai_gateway_response_handling.go | 上游高频演进,Nova 差异中等 → 跟随为主 |
| 32 | 155 | 114 | backend/internal/service/billing_service_test.go | 测试侧定制 → 跟随上游结构 |
| 64 | 24 | 83 | backend/internal/service/openai_gateway_forward.go | 上游高频,Nova 差异小 → 跟随 |
| 43 | 139 | 13 | deploy/config.example.yaml | Nova 配置项 → 独立 overlay 化 |
| 66 | 8 | 78 | backend/internal/service/openai_gateway_grok.go | Nova 差异小 → 跟随 |
| 37 | 86 | 60 | backend/internal/service/openai_gateway_usage.go | 需复核(用量/透支交集) |
| 67 | 63 | 11 | frontend/src/types/index.ts | Nova 类型扩展 → 尽量上移 |
| 51 | 48 | 47 | backend/internal/service/gateway_service.go | 跟随 |
| 44 | 103 | 5 | frontend/src/i18n/.../settings.ts(中英) | Nova 文案 → 以覆盖文件方式解耦 |
| 36 | 73 | 57 | backend/internal/server/routes/gateway.go | 跟随 + Nova 路由保留 |
| 41 | 19 | 62 | backend/internal/service/openai_gateway_chat_completions.go | 跟随 |
| 36 | 64 | 22 | backend/internal/service/openai_ws_http_bridge.go | Nova WS 定制(Nova 独有文件语义) |
| 40 | 63 | 11 | backend/internal/handler/gateway_handler.go | 需复核 |
| 74 | 12 | 13 | backend/internal/service/openai_gateway_service.go | **上游 90 天改 74 次但 Nova 差异仅 ~25 行** → 说明 Nova 挂载做得不错,继续维持 |
| 43 | 3 | 12 | backend/internal/service/account.go | Nova 差异极小 → 跟随 |

(完整明细含上游频率 ≥5 的全部文件,见分析时的临时数据。)

## 4. 建议的翻修优先级

### P0:真实高频语义碰撞(值得做薄)
1. `openai_gateway_passthrough.go` — 先剥离格式漂移;Codex 身份注入等 Nova 调用收敛为独立 hook 文件,上游文件只留 1~2 个调用点。
2. `billing_service.go` — 与上游逐段对账:上游新增字段照单全收,Nova 独有逻辑(倍率、长上下文常量)收敛到独立计价器/注册表。
3. `frontend/src/views/admin/GroupsView.vue` — 若为 Nova 独有交互,改为独立路由页 + 注册入口,不整体改写上游页面。
4. `frontend/src/types/index.ts` 与 i18n — Nova 增量用独立覆盖文件/增量 locale 合并,别改上游基础文件(或仅追加尾部)。
5. `backend/ent/*` 与 `usagelog_create/update.go` 等生成代码 — 审计确认后一律停止手改;需要扩展字段走独立 ent schema/扩展表。

### P1:锁定不跟(避免无谓翻修)
- `README*.md`:Nova 品牌重写,接受与上游永久分叉,同步时整文件保留 Nova 版。
- Nova 独有测试文件与格式噪音:由融合脚本在应用上游补丁后统一跑 `gofmt`/`goimports`,消除漂移类伪冲突。

### P2:维持现状(本就健康)
- `openai_gateway_service.go`(74 次上游改动但 Nova 差异小)、`account.go`:说明现有"薄挂载"模式有效,作为后续新定制的样板。

## 5. 后续动作建议

1. 对 P0 的 5 个文件逐一产出"差异定性报告"(哪些行是 Nova 语义、哪些是漂移、哪些是上游净增)。
2. 融合脚本增加"格式归一化"步骤,把漂移类差异从冲突统计中剔除。
3. 将本报告中的锁定清单并入 `state/nova-customizations.json` 的路径策略,使自动融合遇到锁定路径时直接保留 Nova 版本并记录。

## 6. 深度定性结果(2026-09-04,五区域全量分析)

五个区域逐一只读定性后,结论与最初的 P0 清单有重要修正——**多数区域"不改造"或"小幅收敛"才是正确动作**:

| 区域 | 定性结论 | 推荐动作 |
| --- | --- | --- |
| `openai_gateway_passthrough.go` | 32 hunk;A 漂移 ≈90 行、B Nova 语义 8 项、C 上游净增 3 项(唯一真上游新功能 e9e3c46cb 代理快照)、D 7 项(3 疑似误删、4 有意改写) | A 类清理(已做两处)+ C1 代理快照整体跟随 + B/D 语义收敛为 hook 文件;ServiceTier(D2)、429 headers(B2)涉及计费/透支口径,**冻结待拍板** |
| `billing_service.go` | 441 行差异仅 11.3% 纯格式;**差异是两次融合"保留 Nova 侧"形成的长期分叉,非近期上游移动**;B 必留符号 ≈120 行可搬 `billing_nova_ext.go` | 低风险项抽取独立文件;DeepSeek 峰谷(R6)、gpt-5.5 价卡(R9)、opus Fast 档(R7)、DeepSeek 价数值(R10)、fail-closed(R11)、policy 体系(R16)均为**有意覆盖,需业务确认**;R13 疑似历史遗留待核对;乘 0 免费漏洞(R15)建议修 |
| `GroupsView.vue` | 远未到"整页分叉":差异 = 12 处 tooltip 重构(占删除行 60%)+ 4 组 Nova 独立区块 + 3 组平台收紧;路由零改动 | 抽独立子组件 `GroupsNovaExtras.vue`,冲突 49→2~8 hunk;`platforms.ts` 整文件删除是高危架构选择(建议恢复+派生覆盖);tooltip 重构可回灌 |
| `types/index.ts` + i18n settings | 上游自基线起**零改动**,差异 100% Nova 定制;无重排噪音 | **保持现状即最薄**(直改两文件,真实冲突面仅 5 行覆写);暂不做 nova.ts 外移/overlay;触发条件:上游开始块级重写或 Nova 词条新增频率上升 |
| ent/schema + 生成物 | **无手改生成物**(全部 schema 驱动,证据链完整);Nova 定制 = 3 个上游实体追加 13 列 | 不整体上移(usage_log 中档、group 热路径**不建议拆表**);今后新功能开新实体;存量靠 regen+gofmt 吸收;⚠️ 迁移缺口 228/227(见下) |

### 6.1 已落地修复(融合机制 bug)

上游提交同时含代码与迁移时,Nova 融合脚本把"上游新增迁移"(保护路径)过滤掉、却吸收同提交的代码 → 代码引用不存在的列/索引。已修复:
- 迁移 `238_channel_pricing_multipliers.sql`:重放上游 228(渠道倍率列+约束),`channel_repo_pricing.go` 等 SQL 不再缺列
- 迁移 `239_add_usage_log_effective_model_indexes_notx.sql`:重放上游 226(usage_logs 两个有效模型索引,CONCURRENTLY)
- 待办:`227_composite_routes_add_cn_providers.sql`(约束放宽)是否补齐需产品确认(Nova 前端已收紧 composite 平台到 5 个)
- 根修:同步脚本对"上游新增迁移"应从"直接过滤"改为"登记+人工放行",防止再次重演

**全新数据库冒烟验证(2026-09-04,镜像 sha-cb472cf6)**:空数据目录启动 Compose(独立 project/端口 18081),完整迁移链执行成功:
`schema_migrations` 含 238/239;`channel_model_pricing.fast_multiplier/flex_multiplier` 列存在;
`usage_logs` 两个 effective 索引存在;`/health` ok;管理员登录成功;验证后容器与临时目录已清理。

### 6.2 待业务拍板清单(不自动实施)

1. `billing_service.go` R15 乘 0 免费漏洞(建议跟随上游 orOne 归一化,或数据校验双侧 >0)
2. gpt-5.5/5.5-pro 按 gpt-5.4 价计费(上游独立价卡,差异 2~2.5x)——收入影响
3. DeepSeek 兜底价旧数值 + 无峰谷(R6/R10)——官方 2026-08-23 已降价/峰谷
4. claude-opus-4.8/5 Fast 档倍率(R7)
5. passthrough ServiceTier 计费口径(D2)与 429 headers 语义(B2)
6. 未知 deepseek-* 前缀 fail-closed(R11)是否放宽
7. `platforms.ts` 删除是否回退为"恢复上游+派生覆盖"
8. composite 平台收紧(v-if 白名单)是否为产品决策

### 6.3 收敛目标

- `billing_service.go`:441 行 diff → ≈30 行归档补丁(独立文件 ≈120 行 + 2-4 行字段/映射 + 2-3 钩子)
- `passthrough.go`:32 hunk → 少量调用点 + 1 个 Nova hooks 文件
- `GroupsView.vue`:49 hunk → 2~8 hunk
- 融合脚本:加 gofmt 归一化步骤,漂移类伪冲突不再计入统计
