# Database Schema Synchronization

**Date**: 2025-10-12
**Status**: Complete

## Summary

Synchronized local development database schema with GCP Cloud SQL production database.

## Changes Made

### 1. Local Database Cleanup
- ✅ Removed unused `auth.sessions` table (Auth0 handles session management)
- ✅ Result: Local DB now has 10 tables matching production requirements

### 2. Migration Scripts Created

#### [04-create-session-registry-tables.sql](../db/migrations/04-create-session-registry-tables.sql)
Creates session management tables:
- `public.campaign_sessions` - Primary session metadata
- `public.campaign_session_members` - Session membership tracking
- `public.campaign_session_invites` - Invite token management

**Tables actively used by**:
- [session_models.py](../backend/src/core/session/session_models.py) - SQLAlchemy models
- [session_registry.py](../backend/src/core/session/session_registry.py) - Session management logic

### 3. Current Schema State

#### Local Database (10 tables)
```
audit.security_events
auth.access_control
auth.oauth_accounts
auth.users
game.campaign_participants
game.campaigns
game.chat_history
public.campaign_session_invites
public.campaign_session_members
public.campaign_sessions
```

#### GCP Cloud SQL (Target: 10 tables)
After migration:
- Same 10 tables as local
- Removes: `auth.sessions` (unused, Auth0 handles sessions)
- Adds: 3 `public.campaign_session*` tables

## OAuth Token Columns Analysis

**Question**: Are `access_token` and `refresh_token` columns needed in `auth.oauth_accounts`?

**Answer**: No - Intentionally removed
- See [models.py:126](../auth/src/models.py#L126):
  ```python
  # Note: access_token and refresh_token removed - Auth0 handles token management
  ```
- Auth0 manages all OAuth token lifecycle
- Migration [02-auth0-cleanup-migration.sql](../db/migrations/02-auth0-cleanup-migration.sql) explicitly drops these columns

## Applying Migration to GCP

### Option 1: Manual Application (Recommended for first time)
```bash
# From your local machine with gcloud access
gcloud sql connect gaia-prod-db --user=gaia --database=gaia

# Then paste the contents of 04-create-session-registry-tables.sql
```

### Option 2: Automated Script
```bash
# Run from backend container with secrets loaded
docker exec gaia-backend-gpu bash /home/gaia/scripts/apply-gcp-migrations.sh
```

### Option 3: Cloud Run Startup
The init-db scripts run automatically when connecting to a new database, so deploying to Cloud Run will apply them.

## Verification

After migration, verify schemas match:

```bash
# Local
docker exec gaia-postgres psql -U gaia -d gaia -c \
  "SELECT schemaname, tablename FROM pg_tables
   WHERE schemaname IN ('audit', 'auth', 'game', 'public')
   ORDER BY schemaname, tablename;"

# GCP (requires connection)
# Should show same 10 tables
```

## Next Steps

1. ✅ Local database cleaned up (removed unused tables)
2. ⏳ Apply migration 04 to GCP Cloud SQL
3. ⏳ Verify both databases have identical schemas
4. ⏳ Test backend connection to GCP Cloud SQL with new tables
5. ⏳ Deploy backend to Cloud Run

## Files Modified/Created

### Created
- `db/migrations/04-create-session-registry-tables.sql` - Session tables migration
- `backend/scripts/apply-gcp-migrations.sh` - GCP migration helper script
- `docs/database-schema-sync.md` - This document

### Modified
- Local database: Dropped `auth.sessions` table

## Notes

- All session management tables use `VARCHAR(255)` for IDs to support string-based session identifiers
- Multi-use invite tokens supported via `multi_use`, `max_uses`, and `uses` columns
- All tables have proper indexes for query performance
- Triggers automatically update `updated_at` timestamps
- Foreign key constraints with `ON DELETE CASCADE` for cleanup
