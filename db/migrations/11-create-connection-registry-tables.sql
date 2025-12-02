-- Migration: Create WebSocket connection registry tables
-- Created: 2025-11-09
-- Description: Adds tables for connection-scoped playback state tracking
--
-- This migration implements connection-scoped audio tracking to separate:
-- 1. Generation lifecycle - backend creating audio chunks
-- 2. Connection lifecycle - client WebSocket being alive
-- 3. Playback lifecycle - client actually playing audio
--
-- Key benefits:
-- - Independent playback state per connection (not per session)
-- - Resume support via connection tokens
-- - Track what each client has received/played
-- - Handle reconnections gracefully

-- Create WebSocket connections table
CREATE TABLE IF NOT EXISTS websocket_connections (
    connection_id UUID PRIMARY KEY,
    connection_token VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    user_email VARCHAR(255),
    connection_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'connected',
    connected_at TIMESTAMP WITH TIME ZONE NOT NULL,
    disconnected_at TIMESTAMP WITH TIME ZONE,
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    origin VARCHAR(512),
    user_agent VARCHAR(512),
    client_ip VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create connection playback state table
CREATE TABLE IF NOT EXISTS connection_playback_states (
    playback_state_id UUID PRIMARY KEY,
    connection_id UUID NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    request_id VARCHAR(255) NOT NULL,
    sequence_number INTEGER NOT NULL,
    sent_to_client BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by_client BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    played_by_client BOOLEAN NOT NULL DEFAULT FALSE,
    played_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_connection_playback_connection
        FOREIGN KEY (connection_id)
        REFERENCES websocket_connections (connection_id)
        ON DELETE CASCADE
);

-- Create indexes for efficient querying

-- Connection lookups
CREATE INDEX IF NOT EXISTS ix_ws_connections_session
    ON websocket_connections (session_id, connected_at);

CREATE INDEX IF NOT EXISTS ix_ws_connections_token
    ON websocket_connections (connection_token);

CREATE INDEX IF NOT EXISTS ix_ws_connections_user
    ON websocket_connections (user_id, connected_at);

CREATE INDEX IF NOT EXISTS ix_ws_connections_status
    ON websocket_connections (status, disconnected_at);

-- Playback state lookups
CREATE INDEX IF NOT EXISTS ix_conn_playback_connection
    ON connection_playback_states (connection_id, sequence_number);

CREATE INDEX IF NOT EXISTS ix_conn_playback_chunk
    ON connection_playback_states (chunk_id);

CREATE INDEX IF NOT EXISTS ix_conn_playback_request
    ON connection_playback_states (request_id, connection_id);

-- Add comments for documentation
COMMENT ON TABLE websocket_connections IS 'Tracks individual WebSocket connection instances with lifecycle state';
COMMENT ON TABLE connection_playback_states IS 'Tracks per-connection audio playback state (sent/acknowledged/played)';

COMMENT ON COLUMN websocket_connections.connection_id IS 'Unique identifier for this connection instance';
COMMENT ON COLUMN websocket_connections.connection_token IS 'Client-stored token to resume playback on reconnect';
COMMENT ON COLUMN websocket_connections.session_id IS 'Campaign/session this connection belongs to';
COMMENT ON COLUMN websocket_connections.connection_type IS 'Connection role: player or dm';
COMMENT ON COLUMN websocket_connections.status IS 'Connection status: connected, disconnected, failed, superseded';

COMMENT ON COLUMN connection_playback_states.sent_to_client IS 'Whether chunk was sent via WebSocket';
COMMENT ON COLUMN connection_playback_states.acknowledged_by_client IS 'Whether client confirmed receipt';
COMMENT ON COLUMN connection_playback_states.played_by_client IS 'Whether client reported playback complete';
COMMENT ON COLUMN connection_playback_states.sequence_number IS 'Playback order for this specific connection';
