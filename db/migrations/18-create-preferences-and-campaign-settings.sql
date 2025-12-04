-- Migration: Create user preferences and campaign settings tables
-- Date: 2025-12-02
-- Description: Creates tables for DM preferences, player preferences, and campaign settings
-- These tables track user-specific and campaign-specific configuration

-- DM Preferences table (per-user settings for dungeon masters)
CREATE TABLE IF NOT EXISTS game.dm_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,

    -- Model configuration
    preferred_dm_model VARCHAR(100),
    preferred_npc_model VARCHAR(100),
    preferred_combat_model VARCHAR(100),

    -- UI/Display preferences
    show_dice_rolls BOOLEAN DEFAULT true,
    auto_generate_portraits BOOLEAN DEFAULT true,
    narration_style VARCHAR(50) DEFAULT 'balanced',

    -- Gameplay preferences
    default_difficulty VARCHAR(50) DEFAULT 'medium',
    enable_critical_success BOOLEAN DEFAULT true,
    enable_critical_failure BOOLEAN DEFAULT true,

    -- Metadata
    preferences_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- One preferences record per user
    CONSTRAINT uq_dm_preferences_user UNIQUE (user_id)
);

-- Player Preferences table (per-user settings for players)
CREATE TABLE IF NOT EXISTS game.player_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,

    -- Display preferences
    theme VARCHAR(50) DEFAULT 'dark',
    font_size VARCHAR(20) DEFAULT 'medium',
    show_animations BOOLEAN DEFAULT true,

    -- Audio preferences
    enable_audio BOOLEAN DEFAULT true,
    audio_volume INTEGER DEFAULT 80 CHECK (audio_volume >= 0 AND audio_volume <= 100),
    enable_background_music BOOLEAN DEFAULT true,
    enable_sound_effects BOOLEAN DEFAULT true,

    -- Notification preferences
    enable_turn_notifications BOOLEAN DEFAULT true,
    enable_combat_notifications BOOLEAN DEFAULT true,

    -- Metadata
    preferences_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- One preferences record per user
    CONSTRAINT uq_player_preferences_user UNIQUE (user_id)
);

-- Campaign Settings table (per-campaign configuration)
CREATE TABLE IF NOT EXISTS game.campaign_settings (
    settings_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES game.campaigns(campaign_id) ON DELETE CASCADE,

    -- Campaign style and tone
    tone VARCHAR(50) DEFAULT 'balanced',
    pace VARCHAR(50) DEFAULT 'medium',
    difficulty VARCHAR(50) DEFAULT 'medium',

    -- Player configuration
    max_players INTEGER DEFAULT 6,
    min_players INTEGER DEFAULT 1,
    allow_pvp BOOLEAN DEFAULT false,

    -- Model configuration for this campaign
    dm_model VARCHAR(100),
    npc_model VARCHAR(100),
    combat_model VARCHAR(100),
    narration_model VARCHAR(100),

    -- Gameplay rules
    allow_homebrew BOOLEAN DEFAULT false,
    use_milestone_leveling BOOLEAN DEFAULT true,
    starting_level INTEGER DEFAULT 1,
    max_level INTEGER DEFAULT 20,

    -- Session settings
    session_length_minutes INTEGER DEFAULT 180,
    breaks_enabled BOOLEAN DEFAULT true,

    -- Metadata
    settings_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- One settings record per campaign
    CONSTRAINT uq_campaign_settings_campaign UNIQUE (campaign_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS ix_dm_preferences_user ON game.dm_preferences(user_id);
CREATE INDEX IF NOT EXISTS ix_player_preferences_user ON game.player_preferences(user_id);
CREATE INDEX IF NOT EXISTS ix_campaign_settings_campaign ON game.campaign_settings(campaign_id);

-- Create update triggers for updated_at columns
CREATE TRIGGER update_dm_preferences_updated_at
    BEFORE UPDATE ON game.dm_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_player_preferences_updated_at
    BEFORE UPDATE ON game.player_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_campaign_settings_updated_at
    BEFORE UPDATE ON game.campaign_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to gaia user
GRANT ALL PRIVILEGES ON TABLE game.dm_preferences TO gaia;
GRANT ALL PRIVILEGES ON TABLE game.player_preferences TO gaia;
GRANT ALL PRIVILEGES ON TABLE game.campaign_settings TO gaia;

-- Add comments to document the tables
COMMENT ON TABLE game.dm_preferences IS 'Stores user-specific preferences for dungeon masters including model selection and gameplay settings';
COMMENT ON TABLE game.player_preferences IS 'Stores user-specific preferences for players including display and audio settings';
COMMENT ON TABLE game.campaign_settings IS 'Stores campaign-level settings including tone, pace, model configuration, and gameplay rules';

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Preferences and campaign settings tables created successfully';
    RAISE NOTICE 'Created: dm_preferences, player_preferences, campaign_settings';
END $$;
