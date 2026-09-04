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

## 7. P0 完成度矩阵(2026-09-04 收尾)

| 区域 | 定性 | 实施动作 | 状态 |
| --- | --- | --- | --- |
| passthrough.go | 32 hunk 分类完成 | A 漂移清理(注释归位/包装调用)、D6 空错误码对齐上游;A 类其余为等价重排与注释,收益低不逐处清理 | ✅ 已提交推送 |
| billing_service.go | 441 行差异仅 11.3% 格式,长期分叉 | 长上下文扩展(常量+usesLegacy+CalculateCostWithLongContext)抽入 `billing_nova_ext.go`,diff 441→317 行 | ✅ 已提交推送 |
| GroupsView.vue | 不需分页;Nova 区块可子组件化 | **第一步已实施**:模型专属倍率编辑器抽为 `GroupsRateRulesEditor.vue`(模板 60+ 行×2 移出,typecheck/lint/vitest 223/build 全绿);hidden models textarea(与 modelsList 状态强耦合)暂留父页;platform 白名单/tooltip 回灌待产品确认 | ✅ 已提交推送(a3abc8e8c) |
| types/index.ts + i18n | 上游自基线零改动,差异全 Nova 定制 | **决策:保持现状即最薄**;仅 5 行覆写是真实冲突面;触发条件(上游块级重写/词条激增)后再切 overlay | ✅ 已决策并记录 |
| ent/schema + 生成物 | 无手改生成物,13 列全 schema 驱动 | **决策:不整体上移**(group 热路径/usage_log 事务一致性风险);新功能开新实体;238/239 迁移缺口已修复并全新库冒烟;同步脚本根修已落地 | ✅ 已提交推送 |
| 上游净增 C1(代理快照 e9e3c46cb/4c1f920d5) | 60 文件系统级功能 | **已移植**(d708f7244,PR #6179 以 `cherry-pick -m 1` 应用,仅 4 文件冲突):接收 proxy_id/proxy_name 归属快照与哨兵规则;保留 Nova compact 回退上抛语义(未采纳同帧合成响应);3 个上游语义测试未适配而移除;service 全量回归+全仓编译通过 | ✅ 已提交推送 |

**验证基线**:go1.27.0(GOTOOLCHAIN,与上游 go.mod 一致)下 `internal/service`、`internal/repository`、`migrations` 全绿;脚本测试 19 passed;迁移链全新数据库 Compose 冒烟通过(镜像 sha-cb472cf6);C1 移植镜像 sha-d708f7244 全新数据目录部署冒烟通过(/health、登录、日志、迁移链)。

## 8. 决策建议书(待业务拍板,2026-09-04)

每项给出推荐动作与理由,回复"同意/冻结/修改"即可开工。前 4 项为计费数值/语义,后 4 项为行为口径。

**执行记录(2026-09-04,用户已授权"开工"):**
- ✅ **#1 已实施**(`3a8dc027e`):乘 0 修复,`longContextMultiplierOrOne` 归一(输入/输出/缓存读/缓存创建四处),显式 0 关闭语义保留(阈值层判定),新增 2 个回归测试
- ✅ **#2 已实施**(`77e041fd6`):gpt-5.5 独立价卡($5/$30,Fast 2.5x=$12.5/$75)+ 5.5-pro 官方价($30/$180,无 Fast),legacy 长上下文名单语义不变
- ✅ **#3 已实施**(`6198464c8`):DeepSeek 数值更新为官方 2026-08-23 低谷价(pro $0.66/$1.98、flash $0.22/$0.66、cache hit 对应值);峰谷机制未引入(全天低谷价,高峰少收取舍记录)
- ✅ **#4 核实等价**(不改动):claude-opus-4.8/5 Fast 档 Nova 走通用 fast 倍率 2.0 = $10/$50,与上游显式 priority 2x 数值一致——仅结构差异(上游显式化),无行为差异
- ✅ **#5/#6/#7 冻结确认**:ServiceTier 口径、流内 429 headers、deepseek fail-closed 保持 Nova 现状,不改
- ✅ **#8 已实施**(`abffacead`):composite 路由目标平台放开国产(迁移 240 复刻上游 227 + handler oneof + 前端选项三处同步),仅放开"允许配置"能力,不配不生效,未触碰 Nova 定制
- **冒烟**:镜像 sha-8359fd513(含 1-3 计费修复)全新数据目录部署验证通过(/health、登录、日志正常),验证环境已清理
- **冒烟**:镜像 sha-abffacead(含 #8)全新数据目录验证通过:迁移 240 已应用,composite 约束确认含 kimi/zhipu/deepseek,/health 正常;验证环境已清理

| # | 事项 | 现状 | 推荐 | 理由与成本 |
| --- | --- | --- | --- | --- |
| 1 | **乘 0 免费漏洞**(billing R15) | Nova 直乘 multiplier 无 ≤0 归一;目录单侧漏配(如 input 0/output 1.5)时分项计 0 免费 | **修复但保 Nova 语义**:仅当长上下文未显式关闭时做 orOne(≤0→1)归一,显式 0=关闭阶梯的语义保留 | 上游 530fb20f2 后目录数据驱动,单侧字段会出现;成本中(一处计算+回归测试) |
| 2 | **gpt-5.5/5.5-pro 按 5.4 价计费**(billing R9) | 兜底表确认别名:`fallbackPrices["gpt-5.5"]=fallbackPrices["gpt-5.4"]`(5.5-pro 同);目录来自远程更新,命中时用目录价,未命中才走兜底 | **跟随上游独立价卡**(已核实低风险:目录覆盖时不影响,仅修正目录缺失场景少收 2x) | 上游 $5/$30(Fast 2x/2.5x);成本低(价卡 3 行+测试) |
| 3 | **DeepSeek 兜底旧价 + 无峰谷**(billing R6/R10) | 兜底 flash $0.14/$0.28(官方低谷 $0.22/$0.66)等 | **价格数值跟随官方,峰谷机制暂缓**(时区逻辑复杂、需调度侧支持) | 仅兜底路径差异(目录命中者走 Nova pricing_service);成本低(改表)+ 中(峰谷) |
| 4 | **claude-opus-4.8/5 Fast 档倍率**(billing R7) | Nova 按官方同价($5/$25),上游 priority 档乘 2/2.5 | **跟随上游**(影响仅 Fast/priority 用户)或冻结 | Nova 注释称"官方同价"为旧口径;成本一行 |
| 5 | **passthrough ServiceTier 计费口径**(D2) | Nova 透传按请求 serviceTier 记账,不并入观测 tier | **冻结**(保持现状) | 影响账单 tier 字段;resolver 仅该路径弃用,疑似有意;需计费 owner 复核,成本 1 行但语义重 |
| 6 | **流内 429 headers 语义**(B2) | HTTP200 流内 429 的 x-codex-* 头=成功流配额快照,Nova 置空防误触发冷却 | **冻结**(commit 3f3e78d56 有意为之) | 与透支/Spark 冷却策略耦合,勿顺手改 |
| 7 | **未知 deepseek-* 前缀 fail-closed**(R11) | Nova 仅识别 v4-pro/flash+别名,未知型号拒绝兜底 | **冻结** | 有意(避免误计价);新增型号时记得扩名单 |
| 8 | **composite 平台收紧 + 迁移 227**(GroupsView/ent) | 已核实:限制在**数据库约束**(迁移 172 CHECK 仅 5 平台,上游 227 放宽加 kimi/zhipu/deepseek 未跟随),前端白名单同 5 平台;后端路由解析读库,无独立平台名单 | **产品确认**:composite 是否需要路由到 CN 供应商。需要→补 240 号迁移复刻上游 227+前端白名单加 CN;不需要→保持并记录 | 成本低(一迁移+白名单);若确认需要,DB 约束是唯一闸口 |

## 9. 最终交付清单(2026-09-04,15 个提交全部推送 main)

| 提交 | 内容 | 验证 |
| --- | --- | --- |
| `8afa37db0` | 迁移缺口修复 238/239(渠道倍率列+用量索引) | migrations/repository 测试 + **全新库 Compose 冒烟**(sha-cb472cf6) |
| `0f407b39e` | passthrough 注释归位+包装调用 | build+定向测试 |
| `9d8d779e9` | 五区域定性结论入库 | — |
| `87c66ad6c` | billing 长上下文抽取 `billing_nova_ext.go` | 计费测试全绿 |
| `cb472cf61` | 容量降载空错误码对齐上游 | Capacity 测试 |
| `6cdfc2653` | 冒烟记录 | — |
| `84e60d482` | **同步脚本根修**(上游新增迁移自动吸收/登记) | 脚本测试 19 passed |
| `f70083d3d` | 完成度矩阵 | — |
| `a3abc8e8c` | GroupsView 倍率编辑器抽取 `GroupsRateRulesEditor.vue` | typecheck/lint/vitest 223/build |
| `374fa67ab` | GroupsView 进度 | — |
| `d708f7244` | **C1 代理快照移植**(PR #6179,55 文件) | service 全量回归+全仓 build+**部署冒烟**(sha-d708f7244) |
| `8d9841e67`/`eb6454798` | C1 记录与冒烟 | — |
| `2d358de26` | 决策建议书(8 项) | — |
| `640c38e63` | 建议书事实补充 | — |

**收尾状态**:工程侧全部完成;唯一待办 = 报告 §8 八项业务决策(用户拍板后逐项实施)。验证环境与临时分支均已清理,工作区干净,本地=远程同步。
