-- Insert default data for Gaia database
-- This script runs after schema creation

-- Create a default admin user (for development only - remove in production)
-- Password will be set via OAuth, this is just a placeholder
INSERT INTO auth.users (email, username, display_name, is_admin, user_metadata)
VALUES
    ('admin@gaia.local', 'admin', 'System Administrator', true,
     '{"role": "admin", "created_by": "system"}'),
    ('user@example.com', 'danielrosenthal', 'Example User', false,
     '{"role": "user", "added_by": "admin"}')
ON CONFLICT (email) DO NOTHING;

-- Add some default access control rules templates
-- These can be used as templates for actual permissions
INSERT INTO auth.access_control (
    user_id, 
    resource_type, 
    resource_id, 
    permission_level,
    granted_by
)
SELECT 
    user_id,
    'system',
    'global',
    'admin',
    user_id
FROM auth.users 
WHERE email = 'admin@gaia.local'
ON CONFLICT DO NOTHING;

-- Log the initialization
INSERT INTO audit.security_events (
    event_type,
    event_data,
    success
)
VALUES (
    'system.initialized',
    '{"message": "Database initialized successfully", "version": "1.0.0"}',
    true
);