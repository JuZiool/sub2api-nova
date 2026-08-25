# Nova 手动上游接入批次记录

## 批次信息

- Nova 分支：`upstream/manual-first-batch`
- 批次提交：`75b9824ee8c5f1640beedcfc6c6813593a0d9f4b`
- 本批次补充验证提交：`aa6183220`
- 上游基线：`d45135d87df16d48637f04ccd245727bc955ba54`（`0.1.179`）
- 说明：本批次是选择性移植，不推进 `state/upstreams.json` 的完整成功基线。

## 移植清单

| 类别 | 上游来源 | Nova 调整 |
| --- | --- | --- |
| P0 DOMPurify | `4a1da29509a6cf388ee26c58ec6185bee0cd8676` | 升级 `dompurify` 到 `3.4.14`，增加旧版本 override，并同步锁文件。 |
| P1 IPv6 代理 | `ee62dfbaf1d9623682df2593e4231f1d377efa5e` | 批量代理解析接受带方括号的 IPv6，内部存储去除方括号；保留裸 IPv6 拒绝规则。 |
| P1 用户并发 | `5dfad32b8779cdff4008db929061bfaed3acceed` | 用户编辑表单允许整数 `0`，并明确 `0` 表示不限；后端已有非负校验和无限并发语义。 |
| P1 账号优先级 | `616df479e8dce259b262255db628385fe1199721` | 账号列表默认显示优先级列，保留已有列偏好迁移逻辑。 |
| P1 运维详情返回 | `cfecc8d113053f58ec93897b95eaec92a410249a` | 错误详情可返回错误列表或请求列表，并保留筛选、分页和时间范围。 |
| P1 Compose 透传 | Nova 本地修复 | 补齐 `GATEWAY_*` 参数透传、默认值和 WebSocket HTTP 回滚开关；新增透传一致性测试。 |

## 验证记录

- Python 同步脚本测试：14 项通过。
- 前端 lint、typecheck、Vitest：通过；Vitest 共 1686 项测试通过。
- 前端生产构建：通过。
- Go：`go test ./...` 通过。
- Go lint：使用 CI 同版本 `golangci-lint v2.13.1` 在 LF 临时 checkout 中执行，`golangci-lint run ./...` 结果为 `0 issues`。
- Compose 配置及网关环境变量透传测试：通过。
- Nova Compose 镜像构建：通过。
- 独立新数据卷启动、`/health` 和 `scripts/nova_smoke.py`：通过。

原有 `deploy/.env` 数据卷因历史迁移 `224_channel_monitor_mode_v2_default.sql` 校验值与当前文件不一致，不能作为干净部署验证环境；验证过程未删除或修改该数据卷。
