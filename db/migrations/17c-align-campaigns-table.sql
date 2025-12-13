-- Migration: Align campaigns table with external IDs
-- Date: 2025-12-13
-- Description: Add external_campaign_id/environment columns to game.campaigns,
--              relax owner/name constraints, and ensure indexes match models.

-- Add new columns if missing
ALTER TABLE IF EXISTS game.campaigns
    ADD COLUMN IF NOT EXISTS external_campaign_id VARCHAR(255);

ALTER TABLE IF EXISTS game.campaigns
    ADD COLUMN IF NOT EXISTS environment VARCHAR(50);

-- Backfill new columns for existing rows
UPDATE game.campaigns
SET external_campaign_id = COALESCE(external_campaign_id, campaign_id::text);

UPDATE game.campaigns
SET environment = COALESCE(environment, 'prod');

-- Allow nullable name/owner_id to match current models
ALTER TABLE IF EXISTS game.campaigns
    ALTER COLUMN name DROP NOT NULL;

-- Drop old FK on owner_id and make it optional text
DO $$
DECLARE
    fk_name text;
BEGIN
    SELECT tc.constraint_name INTO fk_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    WHERE tc.table_schema = 'game'
        AND tc.table_name = 'campaigns'
        AND tc.constraint_type = 'FOREIGN KEY'
        AND kcu.column_name = 'owner_id'
    LIMIT 1;

    IF fk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE game.campaigns DROP CONSTRAINT %I', fk_name);
    END IF;
END $$;

ALTER TABLE IF EXISTS game.campaigns
    ALTER COLUMN owner_id DROP NOT NULL;

ALTER TABLE IF EXISTS game.campaigns
    ALTER COLUMN owner_id TYPE VARCHAR(255) USING owner_id::text;

-- Ensure is_active has a default and is non-null
UPDATE game.campaigns
SET is_active = true
WHERE is_active IS NULL;

ALTER TABLE IF EXISTS game.campaigns
    ALTER COLUMN is_active SET NOT NULL,
    ALTER COLUMN is_active SET DEFAULT true;

-- Enforce NOT NULL on new columns after backfill
ALTER TABLE IF EXISTS game.campaigns
    ALTER COLUMN external_campaign_id SET NOT NULL,
    ALTER COLUMN environment SET NOT NULL;

-- Add unique constraint for external_campaign_id if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_external_campaign_id'
          AND conrelid = 'game.campaigns'::regclass
    ) THEN
        ALTER TABLE game.campaigns
            ADD CONSTRAINT uq_external_campaign_id UNIQUE(external_campaign_id);
    END IF;
END $$;

-- Ensure supporting indexes exist
CREATE INDEX IF NOT EXISTS idx_campaigns_external_id ON game.campaigns(external_campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_environment ON game.campaigns(environment);
CREATE INDEX IF NOT EXISTS idx_campaigns_owner ON game.campaigns(owner_id) WHERE owner_id IS NOT NULL;

-- Ensure updated_at trigger exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'update_game_campaigns_updated_at'
          AND tgrelid = 'game.campaigns'::regclass
    ) THEN
        CREATE TRIGGER update_game_campaigns_updated_at
            BEFORE UPDATE ON game.campaigns
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Aligned game.campaigns with external_campaign_id/environment columns and relaxed owner/name constraints';
END $$;
