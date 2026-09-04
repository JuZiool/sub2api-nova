-- 238_channel_pricing_multipliers.sql
-- 修复:Nova 新装库缺少渠道服务层级倍率列
-- 原因:上游 fce90ecf8 同时引入代码引用与迁移 228;Nova 融合时迁移目录属保护路径,
--       上游新增迁移被过滤而同一提交的代码被吸收,导致 channel_repo_pricing.go
--       等引用的 fast_multiplier/flex_multiplier 等列在任何 Nova 迁移中都不存在。
-- 处理:以 Nova 编号重放上游 228 的幂等 SQL,补齐列与约束,不改动既有数据。
-- 验证:全新数据库跑完整迁移链后,渠道定价读/写 SQL 可用。

ALTER TABLE channel_model_pricing
    ADD COLUMN IF NOT EXISTS fast_multiplier NUMERIC(12,6),
    ADD COLUMN IF NOT EXISTS flex_multiplier NUMERIC(12,6);

ALTER TABLE channel_pricing_intervals
    ADD COLUMN IF NOT EXISTS input_multiplier NUMERIC(12,6),
    ADD COLUMN IF NOT EXISTS output_multiplier NUMERIC(12,6),
    ADD COLUMN IF NOT EXISTS cache_write_multiplier NUMERIC(12,6),
    ADD COLUMN IF NOT EXISTS cache_read_multiplier NUMERIC(12,6);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'channel_model_pricing_fast_multiplier_positive' AND conrelid = 'channel_model_pricing'::regclass) THEN
        ALTER TABLE channel_model_pricing
            ADD CONSTRAINT channel_model_pricing_fast_multiplier_positive
            CHECK (fast_multiplier IS NULL OR fast_multiplier > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'channel_model_pricing_flex_multiplier_positive' AND conrelid = 'channel_model_pricing'::regclass) THEN
        ALTER TABLE channel_model_pricing
            ADD CONSTRAINT channel_model_pricing_flex_multiplier_positive
            CHECK (flex_multiplier IS NULL OR flex_multiplier > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'channel_pricing_intervals_input_multiplier_positive' AND conrelid = 'channel_pricing_intervals'::regclass) THEN
        ALTER TABLE channel_pricing_intervals
            ADD CONSTRAINT channel_pricing_intervals_input_multiplier_positive
            CHECK (input_multiplier IS NULL OR input_multiplier > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'channel_pricing_intervals_output_multiplier_positive' AND conrelid = 'channel_pricing_intervals'::regclass) THEN
        ALTER TABLE channel_pricing_intervals
            ADD CONSTRAINT channel_pricing_intervals_output_multiplier_positive
            CHECK (output_multiplier IS NULL OR output_multiplier > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'channel_pricing_intervals_cache_write_multiplier_positive' AND conrelid = 'channel_pricing_intervals'::regclass) THEN
        ALTER TABLE channel_pricing_intervals
            ADD CONSTRAINT channel_pricing_intervals_cache_write_multiplier_positive
            CHECK (cache_write_multiplier IS NULL OR cache_write_multiplier > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'channel_pricing_intervals_cache_read_multiplier_positive' AND conrelid = 'channel_pricing_intervals'::regclass) THEN
        ALTER TABLE channel_pricing_intervals
            ADD CONSTRAINT channel_pricing_intervals_cache_read_multiplier_positive
            CHECK (cache_read_multiplier IS NULL OR cache_read_multiplier > 0);
    END IF;
END $$;

COMMENT ON COLUMN channel_model_pricing.fast_multiplier IS
    'Fast/priority service tier multiplier applied to the selected standard channel price';
COMMENT ON COLUMN channel_model_pricing.flex_multiplier IS
    'Flex service tier multiplier applied to the selected standard channel price';
COMMENT ON COLUMN channel_pricing_intervals.input_multiplier IS
    'Interval input multiplier applied to the channel base input price when input_price is NULL';
COMMENT ON COLUMN channel_pricing_intervals.output_multiplier IS
    'Interval output multiplier applied to the channel base output price when output_price is NULL';
COMMENT ON COLUMN channel_pricing_intervals.cache_write_multiplier IS
    'Interval cache-write multiplier applied to the channel base cache-write price when cache_write_price is NULL';
COMMENT ON COLUMN channel_pricing_intervals.cache_read_multiplier IS
    'Interval cache-read multiplier applied to the channel base cache-read price when cache_read_price is NULL';
