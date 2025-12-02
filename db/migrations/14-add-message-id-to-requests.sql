-- Migration: Add message_id to audio_playback_requests
-- Created: 2025-11-09
-- Description: Adds message_id column to link playback requests to their source messages
--
-- This migration:
-- - Adds nullable message_id column to audio_playback_requests table
-- - Creates index for efficient message-based queries
-- - Updates table comment to document the new relationship
--
-- Note: message_id is stored as VARCHAR since messages are not in a dedicated DB table
--       Once messages move to DB, this can be converted to a proper FK with CASCADE

-- Add message_id column (nullable for backward compatibility with existing records)
ALTER TABLE audio_playback_requests
ADD COLUMN IF NOT EXISTS message_id VARCHAR(255);

-- Create index for message-based lookups
CREATE INDEX IF NOT EXISTS ix_audio_playback_requests_message
    ON audio_playback_requests (message_id)
    WHERE message_id IS NOT NULL;

-- Update table comment to document message relationship
COMMENT ON TABLE audio_playback_requests IS 'Tracks client audio playback requests with submission order. Linked to source messages via message_id. Lifecycle: PENDING -> GENERATING -> COMPLETED (when all chunks played)';

COMMENT ON COLUMN audio_playback_requests.message_id IS 'Reference to the source message that triggered this playback request. Used for auditing and cleanup.';

-- Report results
DO $$
DECLARE
    total_requests INT;
    requests_with_message INT;
BEGIN
    SELECT COUNT(*) INTO total_requests FROM audio_playback_requests;
    SELECT COUNT(*) INTO requests_with_message FROM audio_playback_requests WHERE message_id IS NOT NULL;

    RAISE NOTICE 'Migration complete: message_id column added. Total requests: %, with message_id: %', total_requests, requests_with_message;
END $$;
