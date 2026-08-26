ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS model_rate_multipliers JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS rate_config_version BIGINT NOT NULL DEFAULT 1;

UPDATE groups
SET model_rate_multipliers = '[]'::jsonb
WHERE model_rate_multipliers IS NULL OR jsonb_typeof(model_rate_multipliers) <> 'array';

UPDATE groups
SET rate_config_version = 1
WHERE rate_config_version IS NULL OR rate_config_version < 1;

COMMENT ON COLUMN groups.model_rate_multipliers IS
    'Ordered user billing multiplier rules matched against the client-requested model';
COMMENT ON COLUMN groups.rate_config_version IS
    'Monotonic version for group billing configuration and request-rate snapshots';