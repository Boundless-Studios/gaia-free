-- Migration: Create session registry tables
-- Date: 2025-10-12
-- Description: Creates tables for campaign session management, members, and invites
-- These tables track session ownership, membership, and sharing capabilities

-- Campaign Sessions table (primary session metadata)
CREATE TABLE IF NOT EXISTS public.campaign_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    owner_user_id VARCHAR(255),
    owner_email VARCHAR(255),
    normalized_owner_email VARCHAR(255),
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Campaign Session Members table (tracks who has access to each session)
CREATE TABLE IF NOT EXISTS public.campaign_session_members (
    member_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL REFERENCES public.campaign_sessions(session_id) ON DELETE CASCADE,
    user_id VARCHAR(255),
    email VARCHAR(255),
    normalized_email VARCHAR(255),
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_session_member_user UNIQUE (session_id, user_id),
    CONSTRAINT uq_session_member_email UNIQUE (session_id, normalized_email)
);

-- Campaign Session Invites table (for sharing sessions via invite links)
CREATE TABLE IF NOT EXISTS public.campaign_session_invites (
    invite_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL REFERENCES public.campaign_sessions(session_id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    created_by_user_id VARCHAR(255),
    created_by_email VARCHAR(255),
    normalized_created_by_email VARCHAR(255),
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    multi_use BOOLEAN DEFAULT false,
    max_uses INTEGER,
    uses INTEGER DEFAULT 0,
    CONSTRAINT uq_session_invite_token UNIQUE (token)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS ix_campaign_sessions_owner_user_id ON public.campaign_sessions(owner_user_id);
CREATE INDEX IF NOT EXISTS ix_campaign_sessions_owner_email ON public.campaign_sessions(owner_email);
CREATE INDEX IF NOT EXISTS ix_campaign_sessions_normalized_owner_email ON public.campaign_sessions(normalized_owner_email);
CREATE INDEX IF NOT EXISTS ix_campaign_sessions_last_accessed_at ON public.campaign_sessions(last_accessed_at);

CREATE INDEX IF NOT EXISTS ix_campaign_session_members_session ON public.campaign_session_members(session_id);
CREATE INDEX IF NOT EXISTS ix_campaign_session_members_normalized_email ON public.campaign_session_members(normalized_email);

CREATE INDEX IF NOT EXISTS ix_campaign_session_invites_session ON public.campaign_session_invites(session_id);
CREATE INDEX IF NOT EXISTS ix_campaign_session_invites_expires_at ON public.campaign_session_invites(expires_at);

-- Create update triggers for updated_at columns
CREATE TRIGGER update_campaign_sessions_updated_at
    BEFORE UPDATE ON public.campaign_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_campaign_session_members_updated_at
    BEFORE UPDATE ON public.campaign_session_members
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_campaign_session_invites_updated_at
    BEFORE UPDATE ON public.campaign_session_invites
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to gaia user
GRANT ALL PRIVILEGES ON TABLE public.campaign_sessions TO gaia;
GRANT ALL PRIVILEGES ON TABLE public.campaign_session_members TO gaia;
GRANT ALL PRIVILEGES ON TABLE public.campaign_session_invites TO gaia;

-- Add comments to document the tables
COMMENT ON TABLE public.campaign_sessions IS 'Stores metadata for campaign sessions including ownership and access tracking';
COMMENT ON TABLE public.campaign_session_members IS 'Tracks which users/emails have access to each campaign session';
COMMENT ON TABLE public.campaign_session_invites IS 'Stores invite tokens for sharing campaign sessions with others';

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Session registry tables created successfully';
    RAISE NOTICE 'Created: campaign_sessions, campaign_session_members, campaign_session_invites';
END $$;
