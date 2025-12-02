-- Add email notification tracking for admin access request emails
-- This migration adds fields to track whether admin notification emails were sent
-- successfully, allowing us to identify and fix users stuck in pending approval state

-- Add admin notification tracking fields
ALTER TABLE auth.users
ADD COLUMN IF NOT EXISTS admin_notified_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS admin_notification_failed BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS admin_notification_error TEXT;

-- Create index for finding users who need admin notification
CREATE INDEX IF NOT EXISTS idx_users_pending_notification
ON auth.users(registration_status, is_active, admin_notified_at)
WHERE registration_status = 'completed' AND is_active = false AND admin_notified_at IS NULL;

-- Add comments explaining the fields
COMMENT ON COLUMN auth.users.admin_notified_at IS 'Timestamp when admin was notified about access request';
COMMENT ON COLUMN auth.users.admin_notification_failed IS 'Whether the last admin notification attempt failed';
COMMENT ON COLUMN auth.users.admin_notification_error IS 'Error message from last failed admin notification attempt';
