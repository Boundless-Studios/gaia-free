-- Migration: Create character storage tables
-- Created: 2025-12-13
-- Description: Adds tables for characters, campaign instances, NPCs, and user associations
--              Supports user ownership, campaign-specific state, and character sharing

-- Create character_profiles table (global character identity)
CREATE TABLE IF NOT EXISTS game.character_profiles (
    -- Primary key
    character_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- External identifier (for backward compatibility with filesystem character_id)
    external_character_id VARCHAR(255) NOT NULL UNIQUE,

    -- Ownership (NULL = system character)
    created_by_user_id VARCHAR(255),
    created_by_email VARCHAR(255),

    -- Core identity
    name VARCHAR(255) NOT NULL,
    race VARCHAR(100) NOT NULL DEFAULT 'human',
    character_class VARCHAR(100) NOT NULL DEFAULT 'adventurer',
    base_level INTEGER NOT NULL DEFAULT 1,
    character_type VARCHAR(50) NOT NULL DEFAULT 'player',  -- player, npc, creature

    -- Voice assignment
    voice_id VARCHAR(255),
    voice_settings JSONB DEFAULT '{}'::jsonb NOT NULL,
    voice_archetype VARCHAR(50),

    -- Visual representation (portraits)
    portrait_url TEXT,
    portrait_path TEXT,
    portrait_prompt TEXT,
    additional_images JSONB DEFAULT '[]'::jsonb NOT NULL,

    -- Visual metadata for portrait generation
    gender VARCHAR(50),
    age_category VARCHAR(50),
    build VARCHAR(50),
    height_description VARCHAR(100),
    facial_expression VARCHAR(100),
    facial_features TEXT,
    attire TEXT,
    primary_weapon VARCHAR(255),
    distinguishing_feature TEXT,
    background_setting TEXT,
    pose VARCHAR(100),

    -- Descriptions
    backstory TEXT DEFAULT '',
    description TEXT DEFAULT '',
    appearance TEXT DEFAULT '',
    visual_description TEXT DEFAULT '',
    personality_traits JSONB DEFAULT '[]'::jsonb NOT NULL,
    bonds JSONB DEFAULT '[]'::jsonb NOT NULL,
    flaws JSONB DEFAULT '[]'::jsonb NOT NULL,

    -- Base ability scores (can be overridden in campaign instances)
    strength INTEGER DEFAULT 10 NOT NULL,
    dexterity INTEGER DEFAULT 10 NOT NULL,
    constitution INTEGER DEFAULT 10 NOT NULL,
    intelligence INTEGER DEFAULT 10 NOT NULL,
    wisdom INTEGER DEFAULT 10 NOT NULL,
    charisma INTEGER DEFAULT 10 NOT NULL,

    -- Metadata
    total_interactions INTEGER DEFAULT 0 NOT NULL,
    first_created TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Soft delete support
    is_deleted BOOLEAN DEFAULT false NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create character_campaign_instances table (campaign-specific character state)
CREATE TABLE IF NOT EXISTS game.character_campaign_instances (
    -- Primary key
    instance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign keys
    character_id UUID NOT NULL REFERENCES game.character_profiles(character_id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES game.campaigns(campaign_id) ON DELETE CASCADE,

    -- Campaign-specific state
    current_level INTEGER NOT NULL,  -- Can differ from base_level
    hit_points_current INTEGER NOT NULL,
    hit_points_max INTEGER NOT NULL,
    armor_class INTEGER NOT NULL,

    -- Status and effects
    status VARCHAR(50) NOT NULL DEFAULT 'healthy',  -- healthy, injured, affected, unconscious, dead
    status_effects JSONB DEFAULT '[]'::jsonb NOT NULL,

    -- Inventory (dict of item objects)
    inventory JSONB DEFAULT '{}'::jsonb NOT NULL,

    -- Abilities (dict of ability objects)
    abilities JSONB DEFAULT '{}'::jsonb NOT NULL,

    -- Quests
    quests JSONB DEFAULT '[]'::jsonb NOT NULL,  -- Array of quest_ids

    -- Location
    location VARCHAR(500),

    -- Dialog history
    dialog_history JSONB DEFAULT '[]'::jsonb NOT NULL,

    -- Character role and capabilities (campaign-specific)
    character_role VARCHAR(50) NOT NULL DEFAULT 'player',
    capabilities INTEGER DEFAULT 0 NOT NULL,

    -- Combat-related fields
    action_points JSONB,
    combat_stats JSONB,
    initiative_modifier INTEGER DEFAULT 0 NOT NULL,
    hostile BOOLEAN,

    -- Tracking
    first_appearance TIMESTAMP WITH TIME ZONE,
    last_interaction TIMESTAMP WITH TIME ZONE,
    interaction_count INTEGER DEFAULT 0 NOT NULL,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT false NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Ensure one instance per character per campaign
    CONSTRAINT uq_character_campaign UNIQUE(character_id, campaign_id)
);

-- Create npc_profiles table (lightweight NPC records)
CREATE TABLE IF NOT EXISTS game.npc_profiles (
    -- Primary key
    npc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- External identifier (for backward compatibility)
    external_npc_id VARCHAR(255) NOT NULL UNIQUE,

    -- Ownership
    created_by_user_id VARCHAR(255) NOT NULL,
    created_by_email VARCHAR(255),

    -- Campaign association (NULL = reusable across campaigns)
    campaign_id UUID REFERENCES game.campaigns(campaign_id) ON DELETE SET NULL,

    -- Core NPC data
    display_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'npc_support',
    description TEXT DEFAULT '',
    tags JSONB DEFAULT '[]'::jsonb NOT NULL,
    relationships JSONB DEFAULT '{}'::jsonb NOT NULL,
    notes JSONB DEFAULT '[]'::jsonb NOT NULL,
    capabilities INTEGER DEFAULT 1 NOT NULL,  -- CharacterCapability.NARRATIVE

    -- Promotion tracking
    has_full_sheet BOOLEAN DEFAULT false NOT NULL,
    promoted_to_character_id UUID REFERENCES game.character_profiles(character_id) ON DELETE SET NULL,
    promoted_at TIMESTAMP WITH TIME ZONE,

    -- Additional metadata
    npc_metadata JSONB DEFAULT '{}'::jsonb NOT NULL,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT false NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create character_users table (character-user association for ownership and sharing)
CREATE TABLE IF NOT EXISTS game.character_users (
    -- Primary key
    association_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign keys
    character_id UUID NOT NULL REFERENCES game.character_profiles(character_id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),

    -- Access role
    role VARCHAR(50) NOT NULL DEFAULT 'owner',  -- owner, viewer, editor

    -- Access metadata
    granted_by_user_id VARCHAR(255),
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Ensure unique user per character
    CONSTRAINT uq_character_user UNIQUE(character_id, user_id)
);

-- Create indexes for character_profiles table
CREATE INDEX IF NOT EXISTS idx_character_profiles_external_id ON game.character_profiles(external_character_id);
CREATE INDEX IF NOT EXISTS idx_character_profiles_created_by ON game.character_profiles(created_by_user_id) WHERE created_by_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_character_profiles_type ON game.character_profiles(character_type);
CREATE INDEX IF NOT EXISTS idx_character_profiles_is_deleted ON game.character_profiles(is_deleted) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_character_profiles_name ON game.character_profiles(name);

-- Create indexes for character_campaign_instances table
CREATE INDEX IF NOT EXISTS idx_character_instances_character ON game.character_campaign_instances(character_id);
CREATE INDEX IF NOT EXISTS idx_character_instances_campaign ON game.character_campaign_instances(campaign_id);
CREATE INDEX IF NOT EXISTS idx_character_instances_is_deleted ON game.character_campaign_instances(is_deleted) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_character_instances_status ON game.character_campaign_instances(status);

-- Create indexes for npc_profiles table
CREATE INDEX IF NOT EXISTS idx_npc_profiles_external_id ON game.npc_profiles(external_npc_id);
CREATE INDEX IF NOT EXISTS idx_npc_profiles_created_by ON game.npc_profiles(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_npc_profiles_campaign ON game.npc_profiles(campaign_id) WHERE campaign_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_npc_profiles_promoted ON game.npc_profiles(promoted_to_character_id) WHERE promoted_to_character_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_npc_profiles_is_deleted ON game.npc_profiles(is_deleted) WHERE is_deleted = false;

-- Create indexes for character_users table
CREATE INDEX IF NOT EXISTS idx_character_users_character ON game.character_users(character_id);
CREATE INDEX IF NOT EXISTS idx_character_users_user ON game.character_users(user_id);
CREATE INDEX IF NOT EXISTS idx_character_users_role ON game.character_users(role);

-- Create GIN indexes for JSONB columns (fast array/object searches)
CREATE INDEX IF NOT EXISTS idx_character_profiles_personality_gin ON game.character_profiles USING GIN (personality_traits);
CREATE INDEX IF NOT EXISTS idx_character_profiles_bonds_gin ON game.character_profiles USING GIN (bonds);
CREATE INDEX IF NOT EXISTS idx_character_profiles_flaws_gin ON game.character_profiles USING GIN (flaws);
CREATE INDEX IF NOT EXISTS idx_character_instances_inventory_gin ON game.character_campaign_instances USING GIN (inventory);
CREATE INDEX IF NOT EXISTS idx_character_instances_abilities_gin ON game.character_campaign_instances USING GIN (abilities);
CREATE INDEX IF NOT EXISTS idx_character_instances_status_effects_gin ON game.character_campaign_instances USING GIN (status_effects);
CREATE INDEX IF NOT EXISTS idx_npc_profiles_tags_gin ON game.npc_profiles USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_npc_profiles_relationships_gin ON game.npc_profiles USING GIN (relationships);

-- Create update triggers for updated_at columns
CREATE TRIGGER update_game_character_profiles_updated_at
    BEFORE UPDATE ON game.character_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_game_character_campaign_instances_updated_at
    BEFORE UPDATE ON game.character_campaign_instances
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_game_npc_profiles_updated_at
    BEFORE UPDATE ON game.npc_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_game_character_users_updated_at
    BEFORE UPDATE ON game.character_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to gaia user
GRANT ALL PRIVILEGES ON TABLE game.character_profiles TO gaia;
GRANT ALL PRIVILEGES ON TABLE game.character_campaign_instances TO gaia;
GRANT ALL PRIVILEGES ON TABLE game.npc_profiles TO gaia;
GRANT ALL PRIVILEGES ON TABLE game.character_users TO gaia;

-- Add table comments
COMMENT ON TABLE game.character_profiles IS 'Global character identity with voice, portraits, and base attributes. User-owned or system characters.';
COMMENT ON TABLE game.character_campaign_instances IS 'Campaign-specific character state (HP, inventory, location). Multiple instances per character allowed.';
COMMENT ON TABLE game.npc_profiles IS 'Lightweight NPC records. Can be promoted to full CharacterProfile.';
COMMENT ON TABLE game.character_users IS 'Character-user association for ownership and sharing.';

-- Add column comments for character_profiles
COMMENT ON COLUMN game.character_profiles.character_id IS 'Database UUID primary key';
COMMENT ON COLUMN game.character_profiles.external_character_id IS 'Filesystem character identifier for backward compatibility';
COMMENT ON COLUMN game.character_profiles.created_by_user_id IS 'User who created this character (NULL = system character)';
COMMENT ON COLUMN game.character_profiles.character_type IS 'Type: player, npc, creature';
COMMENT ON COLUMN game.character_profiles.base_level IS 'Default level (campaigns can override in instances)';

-- Add column comments for character_campaign_instances
COMMENT ON COLUMN game.character_campaign_instances.instance_id IS 'Database UUID primary key for this instance';
COMMENT ON COLUMN game.character_campaign_instances.character_id IS 'Reference to global character profile';
COMMENT ON COLUMN game.character_campaign_instances.campaign_id IS 'Campaign this instance belongs to';
COMMENT ON COLUMN game.character_campaign_instances.current_level IS 'Character level in this campaign (can differ from base_level)';
COMMENT ON COLUMN game.character_campaign_instances.inventory IS 'Campaign-specific inventory (JSONB dict of items)';
COMMENT ON COLUMN game.character_campaign_instances.abilities IS 'Campaign-specific abilities (JSONB dict of abilities)';

-- Add column comments for npc_profiles
COMMENT ON COLUMN game.npc_profiles.npc_id IS 'Database UUID primary key';
COMMENT ON COLUMN game.npc_profiles.external_npc_id IS 'Filesystem NPC identifier for backward compatibility';
COMMENT ON COLUMN game.npc_profiles.campaign_id IS 'Campaign association (NULL = reusable across campaigns)';
COMMENT ON COLUMN game.npc_profiles.promoted_to_character_id IS 'Character profile if promoted from NPC';
COMMENT ON COLUMN game.npc_profiles.has_full_sheet IS 'Whether this NPC has been promoted to a full character sheet';

-- Add column comments for character_users
COMMENT ON COLUMN game.character_users.role IS 'Access level: owner, viewer, editor';
COMMENT ON COLUMN game.character_users.granted_by_user_id IS 'User who granted this access';

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Character storage tables created successfully';
    RAISE NOTICE 'Created tables: game.character_profiles, game.character_campaign_instances, game.npc_profiles, game.character_users';
    RAISE NOTICE 'Character storage supports user ownership, campaign-specific instances, and character sharing';
END $$;
