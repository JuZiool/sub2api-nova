-- 239_add_usage_log_effective_model_indexes_notx.sql
-- 修复:Nova 新装库缺少 usage_logs 有效模型查询索引
-- 原因:同 238——上游迁移 226 的两个索引文件属"上游新增迁移",被 Nova 融合保护过滤,
--       而使用这些索引的查询代码(usage_log 列表/导出按有效模型过滤)已被吸收。
-- 处理:以 Nova 编号重放上游 226 的幂等非事务迁移(CONCURRENTLY 不能在事务内执行,
--       文件必须保留 _notx.sql 后缀)。
-- 验证:全新数据库跑完整迁移链后,索引存在且查询计划可用。

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usage_logs_effective_requested_model_created
    ON usage_logs (
        (COALESCE(NULLIF(BTRIM(requested_model), ''), model)),
        created_at DESC,
        id DESC
    );

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usage_logs_effective_upstream_model_created
    ON usage_logs (
        (COALESCE(NULLIF(BTRIM(upstream_model), ''), model)),
        created_at DESC,
        id DESC
    );
