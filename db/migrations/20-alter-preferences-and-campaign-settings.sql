-- Migration: Alter user preferences and campaign settings tables
-- Date: 2025-12-13
-- Description: Updates preference tables to add auto-generation settings and remove unused fields

-- ============================================================================
-- DM Preferences: Add new auto-generation columns, remove narration_style
-- ============================================================================

-- Add new columns
ALTER TABLE game.dm_preferences
    ADD COLUMN IF NOT EXISTS auto_scene_image_generation BOOLEAN DEFAULT true,
    ADD COLUMN IF NOT EXISTS auto_audio_playback BOOLEAN DEFAULT true;

-- Remove narration_style column
ALTER TABLE game.dm_preferences
    DROP COLUMN IF EXISTS narration_style;

-- ============================================================================
-- Player Preferences: Remove display preferences (theme, font_size, animations)
-- ============================================================================

ALTER TABLE game.player_preferences
    DROP COLUMN IF EXISTS theme,
    DROP COLUMN IF EXISTS font_size,
    DROP COLUMN IF EXISTS show_animations;

-- ============================================================================
-- Campaign Settings: Remove leveling rules and session settings
-- ============================================================================

ALTER TABLE game.campaign_settings
    DROP COLUMN IF EXISTS allow_homebrew,
    DROP COLUMN IF EXISTS use_milestone_leveling,
    DROP COLUMN IF EXISTS starting_level,
    DROP COLUMN IF EXISTS max_level,
    DROP COLUMN IF EXISTS session_length_minutes,
    DROP COLUMN IF EXISTS breaks_enabled;

-- ============================================================================
-- Update table comments
-- ============================================================================

COMMENT ON TABLE game.dm_preferences IS 'Stores user-specific preferences for dungeon masters including model selection, auto-generation settings, and gameplay preferences';
COMMENT ON TABLE game.player_preferences IS 'Stores user-specific preferences for players including audio and notification settings';
COMMENT ON TABLE game.campaign_settings IS 'Stores campaign-level settings including tone, pace, difficulty, player configuration, and model selection';

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Preferences and campaign settings tables altered successfully';
    RAISE NOTICE 'DM Preferences: Added auto_scene_image_generation, auto_audio_playback; Removed narration_style';
    RAISE NOTICE 'Player Preferences: Removed theme, font_size, show_animations';
    RAISE NOTICE 'Campaign Settings: Removed leveling and session settings';
END $$;
