-- Migration: Create audio playback persistence tables
-- Created: 2025-11-06
-- Description: Adds tables for tracking audio playback state with submission order

-- Create audio playback requests table
CREATE TABLE IF NOT EXISTS audio_playback_requests (
    request_id UUID PRIMARY KEY,
    campaign_id VARCHAR(255) NOT NULL,
    playback_group VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    total_chunks INTEGER,
    text TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create audio chunks table
CREATE TABLE IF NOT EXISTS audio_chunks (
    chunk_id UUID PRIMARY KEY,
    request_id UUID NOT NULL,
    campaign_id VARCHAR(255) NOT NULL,
    artifact_id VARCHAR(255) NOT NULL,
    url VARCHAR(1024) NOT NULL,
    sequence_number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    mime_type VARCHAR(100) NOT NULL DEFAULT 'audio/mpeg',
    size_bytes INTEGER NOT NULL,
    duration_sec DOUBLE PRECISION,
    storage_path VARCHAR(1024) NOT NULL,
    bucket VARCHAR(255),
    played_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_audio_chunks_request
        FOREIGN KEY (request_id)
        REFERENCES audio_playback_requests (request_id)
        ON DELETE CASCADE
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS ix_audio_playback_requests_campaign
    ON audio_playback_requests (campaign_id, requested_at);

CREATE INDEX IF NOT EXISTS ix_audio_playback_requests_status
    ON audio_playback_requests (campaign_id, status);

CREATE INDEX IF NOT EXISTS ix_audio_playback_requests_campaign_id
    ON audio_playback_requests (campaign_id);

CREATE INDEX IF NOT EXISTS ix_audio_chunks_campaign
    ON audio_chunks (campaign_id, created_at);

CREATE INDEX IF NOT EXISTS ix_audio_chunks_request
    ON audio_chunks (request_id, sequence_number);

CREATE INDEX IF NOT EXISTS ix_audio_chunks_status
    ON audio_chunks (campaign_id, status);

CREATE INDEX IF NOT EXISTS ix_audio_chunks_campaign_id
    ON audio_chunks (campaign_id);

-- Add comments for documentation
COMMENT ON TABLE audio_playback_requests IS 'Tracks client audio playback requests with submission order. Lifecycle: PENDING -> STREAMING -> COMPLETED (when all chunks played)';
COMMENT ON TABLE audio_chunks IS 'Tracks individual audio chunks within a playback request';

COMMENT ON COLUMN audio_playback_requests.playback_group IS 'Group identifier: narrative, response, etc.';
COMMENT ON COLUMN audio_playback_requests.status IS 'Playback status: PENDING, STREAMING, PLAYING, COMPLETED, PLAYED, FAILED';
COMMENT ON COLUMN audio_playback_requests.requested_at IS 'Timestamp used for submission ordering across all campaigns';
COMMENT ON COLUMN audio_playback_requests.total_chunks IS 'Total number of chunks expected in this request (set when generation completes)';
COMMENT ON COLUMN audio_playback_requests.text IS 'Full text that was converted to audio';

COMMENT ON COLUMN audio_chunks.sequence_number IS 'Order within the parent request (0-indexed)';
COMMENT ON COLUMN audio_chunks.artifact_id IS 'Reference to audio artifact store';
COMMENT ON COLUMN audio_chunks.url IS 'Proxy URL for client playback';
COMMENT ON COLUMN audio_chunks.storage_path IS 'GCS or local file path';
COMMENT ON COLUMN audio_chunks.bucket IS 'GCS bucket name if cloud storage is used';
