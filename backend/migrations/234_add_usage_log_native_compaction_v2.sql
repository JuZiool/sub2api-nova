-- 记录 OpenAI 原生 remote compaction v2 的运行时识别结果。
-- 默认 false，保证已经存在的 usage_logs 历史行与旧应用读取兼容。
ALTER TABLE usage_logs
    ADD COLUMN IF NOT EXISTS native_compaction_v2 BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN usage_logs.native_compaction_v2 IS
    'True only when the request was identified at runtime as native OpenAI remote compaction v2';
