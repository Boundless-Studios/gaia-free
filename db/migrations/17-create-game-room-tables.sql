-- Migration: Create game room tables and columns
-- Date: 2025-11-16
-- Description: Adds tables and columns for game room functionality including:
--   - room_seats table for seat management (DM + player seats)
--   - Game room state columns in campaign_sessions
--   - Seat association in websocket_connections
--   - Supporting indexes and views

-- Create room_seats table
CREATE TABLE IF NOT EXISTS public.room_seats (
    seat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id VARCHAR(255) NOT NULL
        REFERENCES public.campaign_sessions(session_id) ON DELETE CASCADE,
    seat_type VARCHAR(20) NOT NULL,
    slot_index SMALLINT,
    character_id VARCHAR(255),
    owner_user_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_room_seats_campaign_type_slot UNIQUE(campaign_id, seat_type, slot_index)
);

-- Add game room columns to campaign_sessions
ALTER TABLE public.campaign_sessions
    ADD COLUMN IF NOT EXISTS max_player_seats SMALLINT;

ALTER TABLE public.campaign_sessions
    ADD COLUMN IF NOT EXISTS dm_joined_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE public.campaign_sessions
    ADD COLUMN IF NOT EXISTS dm_connection_id UUID
        REFERENCES public.websocket_connections(connection_id) ON DELETE SET NULL;

ALTER TABLE public.campaign_sessions
    ADD COLUMN IF NOT EXISTS room_status VARCHAR(20) DEFAULT 'waiting_for_dm';

ALTER TABLE public.campaign_sessions
    ADD COLUMN IF NOT EXISTS campaign_status VARCHAR(20) DEFAULT 'setup';

ALTER TABLE public.campaign_sessions
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE;

-- Add seat_id to websocket_connections
ALTER TABLE public.websocket_connections
    ADD COLUMN IF NOT EXISTS seat_id UUID
        REFERENCES public.room_seats(seat_id) ON DELETE SET NULL;

-- Backfill room-related fields for existing campaigns
-- Note: DEFAULT values only apply to NEW rows inserted after ALTER TABLE
-- For existing rows, we need to UPDATE NULL values explicitly

-- Set room_status for existing campaigns (all need DM to reconnect)
UPDATE public.campaign_sessions
SET room_status = 'waiting_for_dm'
WHERE room_status IS NULL;

-- Set campaign_status for existing campaigns from files
-- These are active campaigns that existed before room functionality was added
-- New campaigns created via API will get DEFAULT 'setup' from column definition
UPDATE public.campaign_sessions
SET campaign_status = 'active'
WHERE campaign_status IS NULL;

-- Note: max_player_seats intentionally left NULL for existing campaigns
-- The startup script (scripts/startup/initialize_campaign_rooms.py) will set this
-- dynamically based on per-campaign metadata, allowing varying player counts

-- Create indexes for room_seats
CREATE INDEX IF NOT EXISTS idx_room_seats_campaign
    ON public.room_seats(campaign_id);

CREATE INDEX IF NOT EXISTS idx_room_seats_owner
    ON public.room_seats(owner_user_id);

-- Partial index for claimed player seats (performance optimization)
CREATE INDEX IF NOT EXISTS idx_room_seats_claimed_players
    ON public.room_seats(campaign_id)
    WHERE seat_type = 'player' AND owner_user_id IS NOT NULL;

-- Create room_state_summary view for efficient room queries
CREATE OR REPLACE VIEW public.room_state_summary AS
WITH seat_counts AS (
    SELECT
        campaign_id,
        COUNT(seat_id) FILTER (
            WHERE seat_type = 'player' AND owner_user_id IS NOT NULL
        ) AS filled_player_seats
    FROM public.room_seats
    GROUP BY campaign_id
),
connected_members AS (
    SELECT DISTINCT session_id, user_id
    FROM public.websocket_connections
    WHERE status = 'connected' AND user_id IS NOT NULL
),
invite_rollup AS (
    SELECT
        m.session_id,
        jsonb_agg(
            jsonb_build_object(
                'user_id', m.user_id,
                'email', m.email,
                'display_name', COALESCE(m.email, m.user_id),
                'status',
                    CASE
                        WHEN rs.seat_id IS NOT NULL THEN 'seated'
                        WHEN m.user_id IS NOT NULL THEN 'accepted'
                        ELSE 'invited'
                    END,
                'seat_id', rs.seat_id,
                'seat_slot_index', rs.slot_index,
                'joined_at', m.joined_at,
                'is_online', (cm.user_id IS NOT NULL)
            )
            ORDER BY m.joined_at
        ) AS invited_players
    FROM public.campaign_session_members m
    LEFT JOIN public.room_seats rs
        ON rs.campaign_id = m.session_id
        AND rs.owner_user_id = m.user_id
        AND rs.seat_type = 'player'
    LEFT JOIN connected_members cm
        ON cm.session_id = m.session_id
        AND cm.user_id = m.user_id
    WHERE m.email IS NOT NULL
    GROUP BY m.session_id
)
SELECT
    cs.session_id AS campaign_id,
    cs.max_player_seats,
    cs.room_status,
    cs.owner_user_id,
    cs.owner_email,
    COALESCE(sc.filled_player_seats, 0) AS filled_player_seats,
    COALESCE(ir.invited_players, '[]'::jsonb) AS invited_players
FROM public.campaign_sessions cs
LEFT JOIN seat_counts sc ON sc.campaign_id = cs.session_id
LEFT JOIN invite_rollup ir ON ir.session_id = cs.session_id;

-- Create update trigger for room_seats
CREATE TRIGGER update_room_seats_updated_at
    BEFORE UPDATE ON public.room_seats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to gaia user
GRANT ALL PRIVILEGES ON TABLE public.room_seats TO gaia;
GRANT SELECT ON public.room_state_summary TO gaia;

-- Add comments to document the tables
COMMENT ON TABLE public.room_seats IS 'Seat definitions for game rooms. Characters are immutably bound to seats; ownership can transfer between sessions.';
COMMENT ON COLUMN public.room_seats.seat_type IS 'Seat type: dm or player';
COMMENT ON COLUMN public.room_seats.slot_index IS '0-based index for player seats, NULL for DM seat';
COMMENT ON COLUMN public.room_seats.character_id IS 'Character bound to this seat (immutable after creation)';
COMMENT ON COLUMN public.room_seats.owner_user_id IS 'Current owner of this seat (mutable - can change between sessions)';

COMMENT ON COLUMN public.campaign_sessions.max_player_seats IS 'Maximum number of player seats for this campaign (e.g., 4)';
COMMENT ON COLUMN public.campaign_sessions.dm_joined_at IS 'Timestamp when DM first joined the room';
COMMENT ON COLUMN public.campaign_sessions.dm_connection_id IS 'Current active DM connection (enforces single DM presence)';
COMMENT ON COLUMN public.campaign_sessions.room_status IS 'Room state: waiting_for_dm, waiting_for_players, ready, in_progress';
COMMENT ON COLUMN public.campaign_sessions.campaign_status IS 'Campaign lifecycle: setup, active, paused, completed';
COMMENT ON COLUMN public.campaign_sessions.started_at IS 'Timestamp when campaign was first started';

COMMENT ON COLUMN public.websocket_connections.seat_id IS 'Seat occupied by this connection (determines character access)';

COMMENT ON VIEW public.room_state_summary IS 'Aggregated view of room state showing filled vs total seats per campaign';

-- Log migration completion
DO $$
DECLARE
    backfilled_status INTEGER;
BEGIN
    -- Count how many campaigns were backfilled
    SELECT COUNT(*) INTO backfilled_status
    FROM public.campaign_sessions
    WHERE room_status IS NOT NULL OR campaign_status IS NOT NULL;

    RAISE NOTICE 'Game room tables and columns created successfully';
    RAISE NOTICE 'Created: room_seats table, room_state_summary view';
    RAISE NOTICE 'Extended: campaign_sessions, websocket_connections';
    RAISE NOTICE 'Backfilled status fields for % existing campaigns', backfilled_status;
    RAISE NOTICE 'Seats will be created by startup script based on per-campaign metadata';
END $$;
