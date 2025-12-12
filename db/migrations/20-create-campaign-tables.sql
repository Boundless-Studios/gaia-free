-- Migration: Create campaign storage tables
-- Created: 2025-12-12
-- Description: Adds tables for campaigns, campaign state, and turn events
--              Supports turn persistence, event logging, and future campaign migration

-- Create campaigns table (core fact table)
CREATE TABLE IF NOT EXISTS game.campaigns (
    campaign_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_campaign_id VARCHAR(255) NOT NULL,
    environment VARCHAR(50) NOT NULL,
    name VARCHAR(255),
    description TEXT,
    owner_id VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_external_campaign_id UNIQUE(external_campaign_id)
);

-- Create campaign_state table (turn/session state)
CREATE TABLE IF NOT EXISTS game.campaign_state (
    state_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES game.campaigns(campaign_id) ON DELETE CASCADE,
    current_turn INTEGER NOT NULL DEFAULT 0,
    last_turn_started_at TIMESTAMP WITH TIME ZONE,
    last_turn_completed_at TIMESTAMP WITH TIME ZONE,
    active_turn JSONB,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_campaign_state UNIQUE(campaign_id)
);

-- Create turn_events table (lightweight event log)
CREATE TABLE IF NOT EXISTS game.turn_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES game.campaigns(campaign_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    event_index INTEGER NOT NULL DEFAULT 0,
    type VARCHAR(50) NOT NULL,
    role VARCHAR(50) NOT NULL,
    content JSONB,
    event_metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create indexes for campaigns table
CREATE INDEX IF NOT EXISTS idx_campaigns_external_id ON game.campaigns(external_campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_environment ON game.campaigns(environment);
CREATE INDEX IF NOT EXISTS idx_campaigns_owner ON game.campaigns(owner_id) WHERE owner_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_campaigns_active ON game.campaigns(is_active) WHERE is_active = true;

-- Create indexes for campaign_state table
CREATE INDEX IF NOT EXISTS idx_campaign_state_campaign ON game.campaign_state(campaign_id);

-- Create indexes for turn_events table
CREATE INDEX IF NOT EXISTS idx_turn_events_campaign_turn ON game.turn_events(campaign_id, turn_number, event_index);
CREATE INDEX IF NOT EXISTS idx_turn_events_campaign_created ON game.turn_events(campaign_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_turn_events_type ON game.turn_events(type);
CREATE INDEX IF NOT EXISTS idx_turn_events_role ON game.turn_events(role);

-- Create GIN indexes for JSONB columns (fast object searches)
CREATE INDEX IF NOT EXISTS idx_turn_events_content_gin ON game.turn_events USING GIN (content);
CREATE INDEX IF NOT EXISTS idx_turn_events_metadata_gin ON game.turn_events USING GIN (event_metadata);
CREATE INDEX IF NOT EXISTS idx_campaign_state_active_turn_gin ON game.campaign_state USING GIN (active_turn);

-- Create update triggers for updated_at columns
CREATE TRIGGER update_game_campaigns_updated_at
    BEFORE UPDATE ON game.campaigns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_game_campaign_state_updated_at
    BEFORE UPDATE ON game.campaign_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to gaia user
GRANT ALL PRIVILEGES ON TABLE game.campaigns TO gaia;
GRANT ALL PRIVILEGES ON TABLE game.campaign_state TO gaia;
GRANT ALL PRIVILEGES ON TABLE game.turn_events TO gaia;

-- Add comments to document the tables
COMMENT ON TABLE game.campaigns IS 'Core campaign fact table. Links filesystem campaign_id to database UUID.';
COMMENT ON TABLE game.campaign_state IS 'Tracks turn state and processing status for each campaign. One row per campaign.';
COMMENT ON TABLE game.turn_events IS 'Lightweight event log for turn inputs and responses. Used for chat history on refresh.';

COMMENT ON COLUMN game.campaigns.external_campaign_id IS 'Filesystem campaign identifier (e.g., "ilya", "demo_campaign")';
COMMENT ON COLUMN game.campaigns.environment IS 'Environment: dev, staging, prod (no default - must be explicit)';
COMMENT ON COLUMN game.campaigns.is_active IS 'Soft active/inactive flag for campaign management';

COMMENT ON COLUMN game.campaign_state.current_turn IS 'Current turn number (monotonically increasing)';
COMMENT ON COLUMN game.campaign_state.active_turn IS 'In-flight turn: {turn_number, input_payload, is_processing}';
COMMENT ON COLUMN game.campaign_state.version IS 'Optimistic concurrency version for safe updates';

COMMENT ON COLUMN game.turn_events.event_index IS 'Ordering within a turn (0, 1, 2...)';
COMMENT ON COLUMN game.turn_events.type IS 'Event type: player_input, dm_input, turn_input, assistant, system';
COMMENT ON COLUMN game.turn_events.role IS 'Actor role: player, dm, assistant, system';
COMMENT ON COLUMN game.turn_events.content IS 'Structured JSONB content (varies by type)';

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Campaign tables created successfully';
    RAISE NOTICE 'Created tables: game.campaigns, game.campaign_state, game.turn_events';
    RAISE NOTICE 'Turn events support: player_input, dm_input, turn_input, assistant, system';
END $$;
