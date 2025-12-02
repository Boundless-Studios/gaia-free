-- Initialize Gaia Database Schema
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Create schemas
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS game;
CREATE SCHEMA IF NOT EXISTS audit;

-- Set default search path
ALTER DATABASE gaia SET search_path TO public, auth, game;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Auth Schema Tables
-- Users table
CREATE TABLE IF NOT EXISTS auth.users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE,
    display_name VARCHAR(255),
    avatar_url TEXT,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    user_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- OAuth providers table (Auth0 integration)
CREATE TABLE IF NOT EXISTS auth.oauth_accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_account_id VARCHAR(255) NOT NULL,
    -- Note: access_token and refresh_token removed - Auth0 handles token management
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, provider_account_id)
);

-- Sessions table removed - Auth0 handles all session management

-- Access control table
CREATE TABLE IF NOT EXISTS auth.access_control (
    access_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    permission_level VARCHAR(20) NOT NULL CHECK (permission_level IN ('read', 'write', 'admin')),
    granted_by UUID REFERENCES auth.users(user_id),
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id, resource_type, resource_id)
);

-- Game Schema Tables
-- Campaigns table
CREATE TABLE IF NOT EXISTS game.campaigns (
    campaign_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(user_id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    settings JSONB DEFAULT '{}',
    state JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_played TIMESTAMP WITH TIME ZONE
);

-- Campaign participants
CREATE TABLE IF NOT EXISTS game.campaign_participants (
    participant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES game.campaigns(campaign_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(user_id),
    role VARCHAR(50) DEFAULT 'player',
    character_data JSONB DEFAULT '{}',
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, user_id)
);

-- Chat history
CREATE TABLE IF NOT EXISTS game.chat_history (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES game.campaigns(campaign_id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(user_id),
    message_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Audit Schema Tables
-- Audit log for security events
CREATE TABLE IF NOT EXISTS audit.security_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(user_id),
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON auth.users(username);
CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user ON auth.oauth_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_accounts_provider ON auth.oauth_accounts(provider, provider_account_id);
-- Sessions indexes removed - Auth0 handles all session management
CREATE INDEX IF NOT EXISTS idx_access_control_user ON auth.access_control(user_id);
CREATE INDEX IF NOT EXISTS idx_access_control_resource ON auth.access_control(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_owner ON game.campaigns(owner_id);
CREATE INDEX IF NOT EXISTS idx_campaign_participants_campaign ON game.campaign_participants(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_participants_user ON game.campaign_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_campaign ON game.chat_history(campaign_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON game.chat_history(created_at);
CREATE INDEX IF NOT EXISTS idx_security_events_user ON audit.security_events(user_id);
CREATE INDEX IF NOT EXISTS idx_security_events_created ON audit.security_events(created_at);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON audit.security_events(event_type);

-- Create update trigger for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_auth_users_updated_at BEFORE UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_auth_oauth_accounts_updated_at BEFORE UPDATE ON auth.oauth_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_game_campaigns_updated_at BEFORE UPDATE ON game.campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to the gaia user
GRANT ALL PRIVILEGES ON SCHEMA auth TO gaia;
GRANT ALL PRIVILEGES ON SCHEMA game TO gaia;
GRANT ALL PRIVILEGES ON SCHEMA audit TO gaia;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA auth TO gaia;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA game TO gaia;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA audit TO gaia;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA auth TO gaia;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA game TO gaia;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA audit TO gaia;