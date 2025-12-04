-- Migration: Drop scenes campaign_id FK constraint
-- Created: 2025-12-04
-- Description: Removes the foreign key constraint on campaign_id since campaigns
--              are not stored in the database yet (they use filesystem storage).
--              This allows scenes to be created before campaigns are migrated to DB.

-- Drop the FK constraint if it exists
ALTER TABLE game.scenes DROP CONSTRAINT IF EXISTS scenes_campaign_id_fkey;

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Dropped scenes_campaign_id_fkey constraint (if it existed)';
    RAISE NOTICE 'Scenes can now be created without requiring a campaign record in the database';
END $$;
