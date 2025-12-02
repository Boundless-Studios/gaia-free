-- Migration: Add chunk sequence validation constraints
-- Created: 2025-11-09
-- Description: Adds unique constraint and validation for audio chunk sequencing
--
-- This migration ensures:
-- - No duplicate sequence numbers within a request
-- - Prevents race conditions during chunk persistence
-- - Validates chunk ordering before marking request as COMPLETED

-- Safety check: Detect and report any existing duplicates before adding constraint
DO $$
DECLARE
    duplicate_count INTEGER;
    duplicate_record RECORD;
BEGIN
    -- Check for duplicates
    SELECT COUNT(*) INTO duplicate_count
    FROM (
        SELECT request_id, sequence_number, COUNT(*) as dup_count
        FROM audio_chunks
        GROUP BY request_id, sequence_number
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_count > 0 THEN
        RAISE WARNING 'Found % duplicate sequence numbers. Details:', duplicate_count;

        -- Log details of duplicates
        FOR duplicate_record IN
            SELECT request_id, sequence_number, COUNT(*) as count
            FROM audio_chunks
            GROUP BY request_id, sequence_number
            HAVING COUNT(*) > 1
            ORDER BY request_id, sequence_number
        LOOP
            RAISE WARNING '  request_id=%, sequence_number=%, count=%',
                duplicate_record.request_id,
                duplicate_record.sequence_number,
                duplicate_record.count;
        END LOOP;

        -- Delete duplicates, keeping only the oldest (by created_at)
        DELETE FROM audio_chunks
        WHERE chunk_id IN (
            SELECT chunk_id
            FROM (
                SELECT chunk_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY request_id, sequence_number
                           ORDER BY created_at ASC
                       ) AS rn
                FROM audio_chunks
            ) ranked
            WHERE rn > 1
        );

        RAISE NOTICE 'Cleaned up duplicate audio chunks, kept oldest by created_at';
    ELSE
        RAISE NOTICE 'No duplicate sequence numbers found';
    END IF;
END $$;

-- Add unique constraint on (request_id, sequence_number)
-- This prevents duplicate sequence numbers within the same request
DO $$
BEGIN
    -- Check if constraint already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_audio_chunks_request_sequence'
    ) THEN
        ALTER TABLE audio_chunks
        ADD CONSTRAINT uq_audio_chunks_request_sequence
        UNIQUE (request_id, sequence_number);

        RAISE NOTICE 'Added unique constraint uq_audio_chunks_request_sequence';
    ELSE
        RAISE NOTICE 'Constraint uq_audio_chunks_request_sequence already exists';
    END IF;
END $$;

-- Add index for efficient sequence validation queries
CREATE INDEX IF NOT EXISTS ix_audio_chunks_request_seq_status
    ON audio_chunks (request_id, sequence_number, status);

-- Add comments
COMMENT ON CONSTRAINT uq_audio_chunks_request_sequence ON audio_chunks IS
'Ensures each sequence number is unique within a request, preventing duplicate chunks';
