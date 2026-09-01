-- 保存客户端在策略改写和模型族映射前请求的推理强度。
-- 保持 NULL 默认值，避免改写已存在的大型 usage_logs 表；NULL 兼容历史记录。
ALTER TABLE usage_logs
    ADD COLUMN IF NOT EXISTS requested_reasoning_effort VARCHAR(20);
