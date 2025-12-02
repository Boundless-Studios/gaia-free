-- Create prompt schema for versioned agent prompts
-- This migration adds support for managing agent prompts through the admin UI

-- Create prompt schema
CREATE SCHEMA IF NOT EXISTS prompt;

-- Grant permissions to gaia user
GRANT ALL PRIVILEGES ON SCHEMA prompt TO gaia;

-- Create prompts table
CREATE TABLE IF NOT EXISTS prompt.prompts (
    prompt_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Agent identification
    agent_type VARCHAR(100) NOT NULL,
    prompt_key VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,

    -- Versioning
    version_number INTEGER NOT NULL,
    parent_prompt_id UUID REFERENCES prompt.prompts(prompt_id),

    -- Content
    prompt_text TEXT NOT NULL,
    description TEXT,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT false,

    -- Audit
    created_by UUID NOT NULL REFERENCES auth.users(user_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Constraints
    CONSTRAINT uq_agent_key_version UNIQUE (agent_type, prompt_key, version_number)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_prompts_agent_type ON prompt.prompts(agent_type);
CREATE INDEX IF NOT EXISTS idx_prompts_prompt_key ON prompt.prompts(prompt_key);
CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompt.prompts(category);
CREATE INDEX IF NOT EXISTS idx_prompts_is_active ON prompt.prompts(is_active);
CREATE INDEX IF NOT EXISTS idx_prompts_agent_active ON prompt.prompts(agent_type, prompt_key, is_active);
CREATE INDEX IF NOT EXISTS idx_prompts_created_by ON prompt.prompts(created_by);
CREATE INDEX IF NOT EXISTS idx_prompts_parent ON prompt.prompts(parent_prompt_id);

-- Create trigger for updated_at
CREATE TRIGGER update_prompt_prompts_updated_at BEFORE UPDATE ON prompt.prompts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant table permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA prompt TO gaia;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA prompt TO gaia;

-- Comments for documentation
COMMENT ON SCHEMA prompt IS 'Schema for versioned agent prompts';
COMMENT ON TABLE prompt.prompts IS 'Versioned agent prompts with activation tracking';
COMMENT ON COLUMN prompt.prompts.agent_type IS 'Type of agent (e.g., streaming_dm, scene_agent)';
COMMENT ON COLUMN prompt.prompts.prompt_key IS 'Specific prompt within agent (e.g., system_prompt, metadata_prompt)';
COMMENT ON COLUMN prompt.prompts.category IS 'Category for UI grouping (e.g., dm_runner, scene_agent, analyzer)';
COMMENT ON COLUMN prompt.prompts.version_number IS 'Sequential version number (1, 2, 3, ...)';
COMMENT ON COLUMN prompt.prompts.parent_prompt_id IS 'Reference to previous version (optional)';
COMMENT ON COLUMN prompt.prompts.prompt_text IS 'The actual prompt text (supports f-string syntax)';
COMMENT ON COLUMN prompt.prompts.is_active IS 'True if this is the currently deployed version';
