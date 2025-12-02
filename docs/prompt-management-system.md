# Agent Prompt Management System

## Overview

The Agent Prompt Management System allows system administrators to manage and version agent prompts through a web UI, with database-backed storage, versioning, and hot-reloading capabilities.

## Features

- **Versioned Prompts**: Create multiple versions of each prompt with descriptions
- **Hot Reloading**: Activate/deactivate versions without code deployments
- **Fallback Safety**: Agents automatically fall back to hardcoded prompts if database is unavailable
- **Admin-Only Access**: Protected by super admin authentication
- **Testing Interface**: Test prompts with sample inputs before activation
- **New Prompt Creation**: Start brand-new agent_type + prompt_key combinations directly from the UI
- **Caching**: In-memory caching for performance

## Architecture

### Database Schema

**Table**: `prompt.prompts`

| Column | Type | Description |
|--------|------|-------------|
| prompt_id | UUID | Primary key |
| agent_type | VARCHAR(100) | Agent identifier (e.g., 'streaming_dm') |
| prompt_key | VARCHAR(100) | Specific prompt within agent (e.g., 'unified_streaming') |
| category | VARCHAR(50) | UI grouping category (e.g., 'dm_runner') |
| version_number | INTEGER | Sequential version number |
| parent_prompt_id | UUID | Reference to previous version (optional) |
| prompt_text | TEXT | The actual prompt content |
| description | TEXT | Description of changes in this version |
| is_active | BOOLEAN | Only one active version per (agent_type, prompt_key) |
| created_by | UUID | User who created this version |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

### Backend Components

1. **PromptService** (`backend/src/core/prompts/prompt_service.py`)
   - Loads prompts from database
   - In-memory caching for performance
   - Fallback support for resilience

2. **API Endpoints** (`backend/src/api/prompts_endpoints.py`)
   - `GET /api/admin/prompts/summary` - List all prompts
   - `GET /api/admin/prompts/versions/{agent_type}/{prompt_key}` - Get all versions
   - `POST /api/admin/prompts/` - Create a brand new prompt or a new version
   - `POST /api/admin/prompts/{prompt_id}/activate` - Activate a version
   - `POST /api/admin/prompts/{prompt_id}/test` - Test a prompt
   - `DELETE /api/admin/prompts/{prompt_id}` - Delete inactive version

3. **Model** (`prompts/src/models.py`)
   - SQLAlchemy ORM model for `prompt.prompts` table

### Frontend Components

**Prompt Manager UI** (`frontend/src/components/admin/PromptManager.jsx`)
- Three-column layout:
  - **Prompt List**: Browse all available prompts
  - **Version History**: View versions for selected prompt
  - **Editor**: Create new versions or test existing ones
- Accessible at `/admin/prompts`

## Usage

### Initial Setup

1. **Apply Migration**

```bash
# Migration runs automatically on next postgres container start
# Or manually apply:
docker exec gaia-postgres psql -U gaia -d gaia -f /docker-entrypoint-initdb.d/11-create-prompt-schema.sql
```

2. **Seed Database**

```bash
# Import all prompts using SQL migration script
./backend/src/core/prompts/run_migration.sh
```

### Managing Prompts via UI

1. Navigate to `/admin/prompts` (requires super admin access)
2. Select a prompt from the left panel
3. View version history in the center panel
4. Click "New Version" to create a new prompt version
5. Edit the prompt text and add a description
6. Test the prompt with sample input (optional)
7. Save as new version (creates inactive version)
8. Activate the version when ready to deploy

### Creating a brand new prompt

1. Click the **➕ Create** button in the left-hand column to launch the creation modal.
2. Provide the required metadata: Agent Type, Prompt Key, optional Category, optional Description, and the initial Prompt Text.
3. Submit the form to create version 1 of the new prompt. The modal closes, the new prompt appears in the list, and its first version loads in the editor for further edits or testing.
4. Activate the version once you're ready to make it live for agents.

### Current Supported Agents

**Streaming DM** (`agent_type: streaming_dm`, `category: dm_runner`)
- `core_persona` - Shared DM personality and guidelines
- `unified_streaming` - Two-paragraph streaming narrative prompt
- `metadata_generation` - Background metadata generation

## How It Works

### Agent Integration

Agents load prompts using this pattern:

```python
from backend.src.core.prompts import PromptService
from db.src import get_async_db

# Load prompt with fallback
async with get_async_db() as db:
    prompt_service = PromptService(db)
    prompt_text = await prompt_service.get_prompt_with_fallback(
        agent_type="streaming_dm",
        prompt_key="unified_streaming",
        fallback=HARDCODED_PROMPT  # Fallback if DB unavailable
    )
```

### Caching

- Prompts are cached in-memory after first load
- Cache is invalidated when a new version is activated
- Cache key: `{agent_type}:{prompt_key}`

### Safety Features

1. **Fallback**: If database is unavailable, agents use hardcoded prompts
2. **Only One Active**: Constraint ensures only one active version per prompt
3. **Versioning**: All changes create new versions (no destructive edits)
4. **Audit Trail**: Every version tracks creator and timestamps

## Adding New Agents

To add prompt management for a new agent:

1. **Identify prompts in code**

```python
# Example: backend/src/game/scene_agents/dialog_agent.py
DIALOG_PROMPT = """Your dialog prompt here..."""
```

2. **Seed database**

```python
# backend/scripts/seed_my_agent_prompts.py
prompts = [
    {
        "agent_type": "scene_agent",
        "prompt_key": "dialog_prompt",
        "category": "scene_agent",
        "prompt_text": DIALOG_PROMPT,
        "description": "Initial version from code",
    }
]
# ... create Prompt objects and save to DB
```

3. **Modify agent to load from database**

```python
# In agent's as_openai_agent() or similar method
async with get_async_db() as db:
    prompt_service = PromptService(db)
    instructions = await prompt_service.get_prompt_with_fallback(
        agent_type="scene_agent",
        prompt_key="dialog_prompt",
        fallback=DIALOG_PROMPT
    )
```

## API Examples

### List all prompts

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/prompts/summary
```

### Create new version

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "streaming_dm",
    "prompt_key": "unified_streaming",
    "category": "dm_runner",
    "prompt_text": "Updated prompt text here...",
    "description": "Improved narrative flow"
  }' \
  http://localhost:8000/api/admin/prompts/
```

### Activate version

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/prompts/{prompt_id}/activate
```

### Test prompt

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "test_input": "The player opens the mysterious door..."
  }' \
  http://localhost:8000/api/admin/prompts/{prompt_id}/test
```

## Security

- **Super Admin Only**: Only emails in `SUPER_ADMIN_EMAILS` can access endpoints
- **Auth0 Protected**: All endpoints require valid Auth0 token
- **Active Version Lock**: Cannot delete active prompts
- **Audit Trail**: All changes tracked with creator and timestamps

## Performance

- **Caching**: First load from DB, subsequent loads from cache
- **Invalidation**: Cache cleared on version activation
- **Connection Pooling**: Reuses database connections
- **Async/Await**: Non-blocking database operations

## Future Enhancements

- [ ] A/B testing support (multiple active versions)
- [ ] Approval workflow (require second admin to approve production deploys)
- [ ] Diff viewer in UI (compare versions side-by-side)
- [ ] Rollback history (track deployments with auto-rollback)
- [ ] Environment support (dev/staging/prod versions)
- [ ] Bulk import/export (JSON/YAML prompt configs)
- [ ] Performance metrics (track prompt effectiveness)

## Troubleshooting

### Agents not using new prompts

1. Check if version is activated: `SELECT * FROM prompt.prompts WHERE is_active = true`
2. Clear cache: Restart backend service or call activation endpoint again
3. Check logs for database connection errors

### Migration not applied

```bash
# Check if schema exists
docker exec gaia-postgres psql -U gaia -d gaia -c "\dn"

# Manually apply migration
docker exec gaia-postgres psql -U gaia -d gaia -f /docker-entrypoint-initdb.d/11-create-prompt-schema.sql
```

### UI not accessible

- Verify you're logged in as super admin email
- Check browser console for errors
- Verify backend is running: `curl http://localhost:8000/api/health`

## Files Created/Modified

### New Files

- `prompts/src/models.py` - Prompt ORM model
- `prompts/src/__init__.py` - Module exports
- `backend/src/core/prompts/prompt_service.py` - Prompt loading service
- `backend/src/core/prompts/__init__.py` - Service exports
- `backend/src/api/prompts_endpoints.py` - REST API endpoints
- `backend/src/core/prompts/run_migration.sh` - SQL-based prompt import tool
- `backend/src/core/prompts/sql/` - SQL prompt files organized by category
- `frontend/src/components/admin/PromptManager.jsx` - Admin UI
- `db/migrations/11-create-prompt-schema.sql` - Database migration
- `backend/scripts/init-db/11-create-prompt-schema.sql` - Init script copy

### Modified Files

- `backend/src/api/main.py` - Registered prompts router
- `frontend/src/AppWithAuth0.jsx` - Added `/admin/prompts` route
- `backend/src/game/dnd_agents/streaming_dungeon_master.py` - Added `instructions_override` parameter
- `backend/src/game/dnd_agents/streaming_dm_orchestrator.py` - Integrated PromptService

## Support

For issues or questions:
1. Check backend logs: `docker logs gaia-backend-dev`
2. Check database: `docker exec gaia-postgres psql -U gaia -d gaia`
3. Review this documentation
4. Contact system administrators
