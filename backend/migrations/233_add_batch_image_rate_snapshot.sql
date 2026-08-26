ALTER TABLE IF EXISTS batch_image_jobs
  ADD COLUMN IF NOT EXISTS pricing_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS rate_resolution_snapshot JSONB;

COMMENT ON COLUMN batch_image_jobs.pricing_at IS
  'Pricing instant captured when the batch image job was created';
COMMENT ON COLUMN batch_image_jobs.rate_resolution_snapshot IS
  'Complete immutable user-side model-rate resolution captured at job creation';
