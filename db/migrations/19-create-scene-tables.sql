-- Migration: Create scene storage tables
-- Created: 2025-12-02
-- Description: Adds tables for storing scenes and scene-entity associations in the database
--              Supports soft deletes and generic entity associations (characters, items, quests, etc.)

-- Create scenes table
CREATE TABLE IF NOT EXISTS game.scenes (
    scene_id VARCHAR(255) PRIMARY KEY,
    -- No FK constraint - campaigns aren't in database yet (stored in filesystem)
    campaign_id UUID NOT NULL,

    -- Immutable creation fields
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    scene_type VARCHAR(50) NOT NULL,  -- combat, exploration, social, puzzle

    -- Narrative and objectives (stored as JSONB arrays)
    objectives JSONB DEFAULT '[]'::jsonb NOT NULL,

    -- Mutable tracking fields (arrays of strings)
    outcomes JSONB DEFAULT '[]'::jsonb NOT NULL,
    duration_turns INTEGER DEFAULT 0 NOT NULL,

    -- Turn order (array of entity_ids)
    turn_order JSONB DEFAULT '[]'::jsonb NOT NULL,
    current_turn_index INTEGER DEFAULT 0 NOT NULL,
    in_combat BOOLEAN DEFAULT false NOT NULL,
    combat_data JSONB,

    -- Scene metadata (named scene_metadata to avoid SQLAlchemy reserved 'metadata')
    scene_metadata JSONB DEFAULT '{}'::jsonb NOT NULL,

    -- Soft delete support
    is_deleted BOOLEAN DEFAULT false NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    scene_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE
);

-- Create scene entities association table (generic entity tracking)
CREATE TABLE IF NOT EXISTS game.scene_entities (
    scene_entity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scene_id VARCHAR(255) NOT NULL REFERENCES game.scenes(scene_id) ON DELETE CASCADE,
    entity_id VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,  -- 'character', 'item', 'object', 'quest', 'location', etc.

    -- Presence tracking (for entities that can join/leave)
    is_present BOOLEAN DEFAULT true NOT NULL,
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE,

    -- Role in scene (optional, primarily for characters)
    role VARCHAR(50),  -- 'player', 'dm_controlled_npc', 'enemy', 'ally', etc.

    -- Entity metadata (named entity_metadata to avoid SQLAlchemy reserved 'metadata')
    entity_metadata JSONB DEFAULT '{}'::jsonb NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Ensure unique entity per scene
    CONSTRAINT uq_scene_entity UNIQUE(scene_id, entity_id, entity_type)
);

-- Create indexes for scenes table
CREATE INDEX IF NOT EXISTS idx_scenes_campaign ON game.scenes(campaign_id);
CREATE INDEX IF NOT EXISTS idx_scenes_scene_type ON game.scenes(scene_type);
CREATE INDEX IF NOT EXISTS idx_scenes_timestamp ON game.scenes(scene_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_scenes_campaign_timestamp ON game.scenes(campaign_id, scene_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_scenes_is_deleted ON game.scenes(is_deleted);
CREATE INDEX IF NOT EXISTS idx_scenes_campaign_active ON game.scenes(campaign_id, is_deleted) WHERE is_deleted = false;

-- Create indexes for scene_entities table
CREATE INDEX IF NOT EXISTS idx_scene_entities_scene ON game.scene_entities(scene_id);
CREATE INDEX IF NOT EXISTS idx_scene_entities_entity ON game.scene_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_scene_entities_entity_type ON game.scene_entities(entity_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_scene_entities_type ON game.scene_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_scene_entities_presence ON game.scene_entities(scene_id, is_present);
CREATE INDEX IF NOT EXISTS idx_scene_entities_role ON game.scene_entities(role) WHERE role IS NOT NULL;

-- Create GIN indexes for JSONB columns (fast array/object searches)
CREATE INDEX IF NOT EXISTS idx_scenes_objectives_gin ON game.scenes USING GIN (objectives);
CREATE INDEX IF NOT EXISTS idx_scenes_turn_order_gin ON game.scenes USING GIN (turn_order);
CREATE INDEX IF NOT EXISTS idx_scenes_metadata_gin ON game.scenes USING GIN (scene_metadata);
CREATE INDEX IF NOT EXISTS idx_scene_entities_metadata_gin ON game.scene_entities USING GIN (entity_metadata);

-- Create update triggers for updated_at columns
CREATE TRIGGER update_game_scenes_updated_at
    BEFORE UPDATE ON game.scenes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_game_scene_entities_updated_at
    BEFORE UPDATE ON game.scene_entities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to gaia user
GRANT ALL PRIVILEGES ON TABLE game.scenes TO gaia;
GRANT ALL PRIVILEGES ON TABLE game.scene_entities TO gaia;

-- Add comments to document the tables
COMMENT ON TABLE game.scenes IS 'Stores scene metadata and state. Scenes represent distinct narrative moments or encounters in a campaign.';
COMMENT ON TABLE game.scene_entities IS 'Generic association table linking scenes to entities (characters, items, quests, objects, etc.). Future-proof for when entities are stored in database.';

COMMENT ON COLUMN game.scenes.scene_id IS 'Unique scene identifier, format: scene_{number:03d}_{timestamp}';
COMMENT ON COLUMN game.scenes.scene_type IS 'Type of scene: combat, exploration, social, puzzle';
COMMENT ON COLUMN game.scenes.turn_order IS 'Array of entity_ids representing initiative/turn order';
COMMENT ON COLUMN game.scenes.is_deleted IS 'Soft delete flag - scenes are never hard deleted';
COMMENT ON COLUMN game.scenes.deleted_at IS 'Timestamp when scene was soft deleted';

COMMENT ON COLUMN game.scene_entities.entity_type IS 'Type of entity: character, item, object, quest, location, etc.';
COMMENT ON COLUMN game.scene_entities.is_present IS 'Whether entity is currently present in the scene';
COMMENT ON COLUMN game.scene_entities.role IS 'Role in scene (primarily for characters): player, dm_controlled_npc, enemy, ally, etc.';

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Scene storage tables created successfully';
    RAISE NOTICE 'Created tables: game.scenes, game.scene_entities';
    RAISE NOTICE 'Scene storage supports soft deletes and generic entity associations';
END $$;
