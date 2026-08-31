-- Restrict a specific user's access to public groups only when explicitly enabled.
-- The false default preserves all existing public-group access decisions.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS restrict_public_groups BOOLEAN NOT NULL DEFAULT false;
