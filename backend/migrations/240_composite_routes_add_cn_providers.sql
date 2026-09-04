-- 240_composite_routes_add_cn_providers.sql
-- 同步上游策略：放开 Composite 模型路由的国产平台目标（对应上游 227，被融合过滤遗漏）
-- 与 HTTP 层 oneof 校验（group_handler.go）与前端选项同步放开，默认不产生任何路由变更
-- 幂等：先删旧约束再重建，可重复执行

ALTER TABLE composite_model_routes
    DROP CONSTRAINT IF EXISTS composite_model_routes_target_platform_check;

ALTER TABLE composite_model_routes
    ADD CONSTRAINT composite_model_routes_target_platform_check
    CHECK (target_platform IN ('anthropic', 'openai', 'gemini', 'antigravity', 'grok',
                               'kimi', 'zhipu', 'deepseek'));
