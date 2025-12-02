-- Add user registration fields for EULA acceptance and registration flow
-- This migration adds fields to track user registration status, EULA acceptance,
-- and email opt-in preferences

-- Add registration status field (defaults to 'pending' for new users)
ALTER TABLE auth.users
ADD COLUMN IF NOT EXISTS registration_status VARCHAR(20) NOT NULL DEFAULT 'pending'
CHECK (registration_status IN ('pending', 'completed'));

-- Add EULA acceptance tracking
ALTER TABLE auth.users
ADD COLUMN IF NOT EXISTS eula_accepted_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS eula_version_accepted VARCHAR(50);

-- Add email opt-in preferences
ALTER TABLE auth.users
ADD COLUMN IF NOT EXISTS registration_email_opt_in BOOLEAN DEFAULT false;

-- Add registration completion timestamp
ALTER TABLE auth.users
ADD COLUMN IF NOT EXISTS registration_completed_at TIMESTAMP WITH TIME ZONE;

-- Create index for registration status queries
CREATE INDEX IF NOT EXISTS idx_users_registration_status ON auth.users(registration_status);

-- Update existing users to have completed registration status
-- (Existing users should not be blocked by the new registration flow)
UPDATE auth.users
SET registration_status = 'completed',
    registration_completed_at = created_at
WHERE registration_status = 'pending' AND created_at < NOW();

-- Add comment explaining the fields
COMMENT ON COLUMN auth.users.registration_status IS 'Registration flow status: pending (needs to accept EULA) or completed';
COMMENT ON COLUMN auth.users.eula_accepted_at IS 'Timestamp when user accepted the EULA';
COMMENT ON COLUMN auth.users.eula_version_accepted IS 'Version of EULA that was accepted (e.g., "1.0", "2023-10-01")';
COMMENT ON COLUMN auth.users.registration_email_opt_in IS 'Whether user opted in to receive registration and update emails';
COMMENT ON COLUMN auth.users.registration_completed_at IS 'Timestamp when user completed the registration flow';
