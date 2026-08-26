-- Persist the exact group model-rate decision used for each billed request.
-- All fields stay nullable so historical logs remain valid and distinguishable.
ALTER TABLE IF EXISTS usage_logs
  ADD COLUMN IF NOT EXISTS pricing_group_id BIGINT,
  ADD COLUMN IF NOT EXISTS rate_match_model VARCHAR(200),
  ADD COLUMN IF NOT EXISTS rate_rule_source VARCHAR(40),
  ADD COLUMN IF NOT EXISTS rate_rule_key VARCHAR(200),
  ADD COLUMN IF NOT EXISTS rate_config_version BIGINT,
  ADD COLUMN IF NOT EXISTS rate_base_multiplier DECIMAL(10,4),
  ADD COLUMN IF NOT EXISTS rate_token_multiplier DECIMAL(10,4),
  ADD COLUMN IF NOT EXISTS rate_image_multiplier DECIMAL(10,4),
  ADD COLUMN IF NOT EXISTS rate_video_multiplier DECIMAL(10,4);

CREATE INDEX IF NOT EXISTS idx_usage_logs_pricing_group_created
  ON usage_logs(pricing_group_id, created_at DESC);

COMMENT ON COLUMN usage_logs.pricing_group_id IS 'Authenticated pricing-owner group for model-rate audit';
COMMENT ON COLUMN usage_logs.rate_match_model IS 'Trimmed client-requested model used to match the rate rule';
COMMENT ON COLUMN usage_logs.rate_rule_source IS 'user_group_override, model_exact, model_prefix, or group_default';
COMMENT ON COLUMN usage_logs.rate_rule_key IS 'Matched exact/prefix rule; empty for fallback sources';
COMMENT ON COLUMN usage_logs.rate_config_version IS 'groups.rate_config_version captured for the billed request';