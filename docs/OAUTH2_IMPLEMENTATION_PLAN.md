# OAuth2 Authentication Implementation Plan

## Overview
This document outlines the implementation of OAuth2 authentication for the Gaia D&D platform. The system will provide secure authentication, user management, and access control.

## Architecture Overview

### Components

#### 1. Backend Authentication Service
- **Location**: `backend/src/core/auth/`
- **Components**:
  - OAuth2 provider integration (Google, GitHub, Discord)
  - JWT token management
  - User session management
  - Access control middleware
  - User management API

#### 2. Database Schema
- **Users Table**:
  - user_id (UUID, primary key)
  - email (unique)
  - username
  - display_name
  - avatar_url
  - created_at
  - updated_at
  - last_login
  - is_active
  - is_admin
  - metadata (JSONB)

- **OAuth2 Accounts Table**:
  - account_id (UUID, primary key)
  - user_id (foreign key)
  - provider (google/github/discord)
  - provider_account_id
  - access_token (encrypted)
  - refresh_token (encrypted)
  - expires_at
  - created_at
  - updated_at

- **Sessions Table**:
  - session_id (UUID, primary key)
  - user_id (foreign key)
  - token_hash
  - expires_at
  - ip_address
  - user_agent
  - created_at
  - last_activity

- **Access Control Table**:
  - access_id (UUID, primary key)
  - user_id (foreign key)
  - resource_type (campaign/character/etc)
  - resource_id
  - permission_level (read/write/admin)
  - granted_by
  - granted_at

#### 3. Frontend Authentication Flow
- **Landing Page**: `/` - Public landing with login options
- **Login Page**: `/login` - OAuth2 provider selection
- **Main App**: `/app` - Protected application (current functionality)
- **Admin Panel**: `/admin` - User management interface

## Implementation Steps

### Phase 1: Backend Foundation

#### 1.1 Install Dependencies
```python
# Additional requirements.txt entries
authlib==1.3.0  # OAuth2 client library
python-jose[cryptography]==3.3.0  # JWT handling
passlib[bcrypt]==1.7.4  # Password hashing
sqlalchemy==2.0.23  # ORM for database
alembic==1.13.1  # Database migrations
asyncpg==0.29.0  # PostgreSQL async driver
redis==5.0.1  # Session storage
```

#### 1.2 Database Setup
- PostgreSQL for user data persistence
- Redis for session caching
- Alembic for schema migrations

#### 1.3 Core Authentication Module
```python
# backend/src/core/auth/__init__.py
# backend/src/core/auth/oauth2_providers.py
# backend/src/core/auth/jwt_handler.py
# backend/src/core/auth/user_manager.py
# backend/src/core/auth/middleware.py
# backend/src/core/auth/models.py
```

### Phase 2: OAuth2 Provider Integration

#### 2.1 Google OAuth2
- Client ID and Secret configuration
- Scopes: email, profile
- Callback URL: `/api/auth/callback/google`

#### 2.2 GitHub OAuth2
- OAuth App registration
- Scopes: user:email, read:user
- Callback URL: `/api/auth/callback/github`

#### 2.3 Discord OAuth2
- Application setup in Discord Developer Portal
- Scopes: identify, email
- Callback URL: `/api/auth/callback/discord`

### Phase 3: API Endpoints

#### Authentication Endpoints
- `GET /api/auth/providers` - List available OAuth2 providers
- `GET /api/auth/login/{provider}` - Initiate OAuth2 flow
- `GET /api/auth/callback/{provider}` - OAuth2 callback handler
- `POST /api/auth/refresh` - Refresh JWT token
- `POST /api/auth/logout` - Logout and invalidate session
- `GET /api/auth/me` - Get current user info

#### User Management Endpoints (Admin)
- `GET /api/admin/users` - List all users
- `GET /api/admin/users/{user_id}` - Get user details
- `PUT /api/admin/users/{user_id}` - Update user
- `DELETE /api/admin/users/{user_id}` - Deactivate user
- `POST /api/admin/users/{user_id}/permissions` - Grant permissions
- `DELETE /api/admin/users/{user_id}/permissions` - Revoke permissions

### Phase 4: Frontend Implementation

#### 4.1 Landing Page Component
```jsx
// frontend/src/pages/Landing.jsx
// Public landing page with login CTA
```

#### 4.2 Login Page Component
```jsx
// frontend/src/pages/Login.jsx
// OAuth2 provider selection
```

#### 4.3 Authentication Context
```jsx
// frontend/src/contexts/AuthContext.jsx
// Global authentication state management
```

#### 4.4 Protected Route Component
```jsx
// frontend/src/components/ProtectedRoute.jsx
// Route protection wrapper
```

#### 4.5 User Menu Component
```jsx
// frontend/src/components/UserMenu.jsx
// User profile dropdown with logout
```

### Phase 5: Middleware & Security

#### 5.1 Authentication Middleware
- JWT validation on all protected routes
- Token refresh logic
- Session expiry handling

#### 5.2 Authorization Middleware
- Role-based access control (RBAC)
- Resource-level permissions
- Admin access verification

#### 5.3 Security Measures
- HTTPS enforcement
- CORS configuration update
- Rate limiting on auth endpoints
- Token rotation
- Secure cookie settings
- CSRF protection

### Phase 6: Docker Configuration

#### 6.1 PostgreSQL Service
```yaml
# docker-compose.yml addition
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: gaia_auth
    POSTGRES_USER: gaia
    POSTGRES_PASSWORD: ${DB_PASSWORD}
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

#### 6.2 Redis Service
```yaml
# docker-compose.yml addition
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
```

### Phase 7: Testing

#### 7.1 Unit Tests
- OAuth2 flow tests
- JWT generation/validation tests
- User management tests
- Permission checking tests

#### 7.2 Integration Tests
- Full authentication flow
- Token refresh cycle
- Session management
- Multi-provider login

#### 7.3 E2E Tests
- Login flow with each provider
- Protected route access
- Admin functionality
- Logout and session cleanup

## Configuration

### Environment Variables
```bash
# OAuth2 Providers
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=

# JWT Configuration
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/gaia_auth
REDIS_URL=redis://localhost:6379/0

# Security
SESSION_SECRET_KEY=
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Migration Strategy

### Phase 1: Soft Launch
1. Deploy authentication system alongside existing app
2. Landing page accessible at root `/`
3. Existing app still accessible directly
4. Optional login for testing

### Phase 2: Beta Testing
1. Enable authentication for beta users
2. Collect feedback and fix issues
3. Monitor performance and security

### Phase 3: Full Rollout
1. Enforce authentication for all users
2. Migrate any existing user data
3. Remove direct app access
4. Monitor and support users

## Security Considerations

1. **Token Security**:
   - Use secure random JWT secrets
   - Short token expiration (1 hour)
   - Refresh tokens with longer expiry (7 days)
   - Secure, httpOnly cookies for tokens

2. **Database Security**:
   - Encrypt sensitive data (tokens)
   - Use parameterized queries
   - Regular security audits
   - Backup and recovery procedures

3. **API Security**:
   - Rate limiting on auth endpoints
   - CORS properly configured
   - Input validation and sanitization
   - Audit logging for admin actions

4. **Frontend Security**:
   - XSS prevention
   - CSRF tokens
   - Secure storage (no localStorage for tokens)
   - Content Security Policy headers

## Performance Considerations

1. **Caching Strategy**:
   - Redis for session data
   - JWT claims caching
   - User profile caching

2. **Database Optimization**:
   - Indexed columns for queries
   - Connection pooling
   - Query optimization

3. **Frontend Optimization**:
   - Lazy loading for auth components
   - Optimistic UI updates
   - Token refresh preemptively

## Monitoring & Logging

1. **Authentication Events**:
   - Login attempts (success/failure)
   - Token generation/refresh
   - Logout events
   - Permission changes

2. **Security Events**:
   - Failed authentication attempts
   - Suspicious activity detection
   - Admin actions audit trail

3. **Performance Metrics**:
   - Authentication response times
   - Database query performance
   - Session count and duration

## Rollback Plan

If issues arise during deployment:

1. **Feature Flag**: Disable auth requirement via environment variable
2. **Database Rollback**: Alembic migration rollback commands ready
3. **Quick Revert**: Git tags for pre-auth versions
4. **Communication**: User notification system for updates

## Success Criteria

1. **Functional Requirements**:
   - Users can login with at least one OAuth2 provider
   - Sessions persist across browser refreshes
   - Proper access control enforcement
   - Admin can manage user access

2. **Performance Requirements**:
   - Login completion < 3 seconds
   - Token refresh < 500ms
   - No degradation of existing functionality

3. **Security Requirements**:
   - No plain text password storage
   - All auth endpoints use HTTPS
   - Proper token expiration and refresh
   - Audit trail for security events

## Timeline

- **Week 1**: Backend foundation and database setup
- **Week 2**: OAuth2 provider integration
- **Week 3**: Frontend implementation
- **Week 4**: Testing and security hardening
- **Week 5**: Documentation and deployment preparation
- **Week 6**: Staged rollout and monitoring

## Next Steps

1. Review and approve this plan
2. Set up OAuth2 applications with providers
3. Begin implementation starting with backend foundation
4. Regular testing throughout development
5. Security review before deployment