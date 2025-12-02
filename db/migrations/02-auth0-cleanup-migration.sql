-- Migration: Clean up legacy authentication tables and columns after Auth0 migration
-- Date: 2025-09-03
-- Description: Removes unused session management and token storage now handled by Auth0

-- Drop sessions table (Auth0 handles all session management)
DROP TABLE IF EXISTS auth.sessions CASCADE;

-- Remove unused token columns from oauth_accounts table (Auth0 manages tokens)
ALTER TABLE auth.oauth_accounts 
DROP COLUMN IF EXISTS access_token,
DROP COLUMN IF EXISTS refresh_token;

-- Drop refresh_tokens table if it exists (from earlier schemas)
DROP TABLE IF EXISTS auth.refresh_tokens CASCADE;

-- Add comment to oauth_accounts table explaining Auth0 integration
COMMENT ON TABLE auth.oauth_accounts IS 'Links local users to Auth0 accounts. Token management handled by Auth0.';
COMMENT ON COLUMN auth.oauth_accounts.provider IS 'Authentication provider (should be "auth0" for all new records)';
COMMENT ON COLUMN auth.oauth_accounts.provider_account_id IS 'Auth0 user ID (e.g., "auth0|123456")';

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Auth0 cleanup migration completed successfully';
    RAISE NOTICE 'Removed: sessions table, refresh_tokens table, token columns from oauth_accounts';
END $$;