-- Switch the legacy V1 factory setting to the V2 passive-monitoring default.
-- This migration runs once; administrators can still select V1 explicitly afterwards.
UPDATE settings
SET value = 'v2', updated_at = NOW()
WHERE key = 'channel_monitor_mode'
  AND LOWER(TRIM(value)) = 'v1';
