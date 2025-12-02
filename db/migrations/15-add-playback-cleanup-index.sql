-- Migration: Add index for playback state cleanup operations
-- Created: 2025-11-14
-- Description: Adds missing index on created_at for efficient cleanup of old playback states
--
-- Background:
-- The connection_playback_states table tracks per-connection audio playback state.
-- Cleanup operations need to efficiently query by created_at to prune old records.
-- Without this index, cleanup queries result in full table scans.
--
-- Performance impact:
-- - Cleanup queries will use index scan instead of sequential scan
-- - Enables efficient time-based partitioning/archival in the future
-- - Minimal overhead on insert (single column, timestamp type)

-- Add index for cleanup operations (prune old playback states)
CREATE INDEX IF NOT EXISTS ix_conn_playback_created
    ON connection_playback_states (created_at);

-- Add comment for documentation
COMMENT ON INDEX ix_conn_playback_created IS 'Efficient cleanup of old playback states by creation timestamp';
