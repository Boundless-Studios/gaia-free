-- Migration: Rename STREAMING status to GENERATING
-- Created: 2025-11-09
-- Description: Updates status enum value from 'streaming' to 'generating' to better reflect that this status means "audio generation in progress", not "ready to stream"
--
-- This migration:
-- - Updates existing records with status='streaming' to status='generating'
-- - Updates table comments to reflect the new status name
-- - Maintains backward compatibility by checking for existing values

-- Update audio_playback_requests table (case-insensitive to handle both lowercase and uppercase)
UPDATE audio_playback_requests
SET status = 'GENERATING'
WHERE UPPER(status) = 'STREAMING';

-- Update audio_chunks table (if any chunks have streaming status)
UPDATE audio_chunks
SET status = 'GENERATING'
WHERE UPPER(status) = 'STREAMING';

-- Update table comment to reflect new status name
COMMENT ON TABLE audio_playback_requests IS 'Tracks client audio playback requests with submission order. Lifecycle: PENDING -> GENERATING -> COMPLETED (when all chunks played)';

-- Update status column comment
COMMENT ON COLUMN audio_playback_requests.status IS 'Playback status: PENDING, GENERATING, PLAYING, COMPLETED, PLAYED, FAILED';

-- Report results
DO $$
DECLARE
    requests_updated INT;
    chunks_updated INT;
BEGIN
    -- Count updated requests
    SELECT COUNT(*) INTO requests_updated
    FROM audio_playback_requests
    WHERE UPPER(status) = 'GENERATING';

    -- Count updated chunks
    SELECT COUNT(*) INTO chunks_updated
    FROM audio_chunks
    WHERE UPPER(status) = 'GENERATING';

    RAISE NOTICE 'Migration complete: % requests and % chunks now use status=GENERATING', requests_updated, chunks_updated;
END $$;
