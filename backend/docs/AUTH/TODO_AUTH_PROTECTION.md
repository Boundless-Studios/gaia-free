# TODO: Authentication Protection for Main API Endpoints

**Priority: HIGH**  
**Created: 2025-08-28**  
**Updated: 2025-09-01**

## Issue
The OAuth2 authentication system is fully implemented and secure, but most API endpoints are NOT protected by authentication. This means anyone can access campaigns, chat, image generation, and other features without logging in.

## Current State

### ✅ Protected Endpoints (with auth requirements)

#### Auth Module (`/api/auth/*`)
- `/api/auth/me` - Requires `CurrentUser`
- `/api/auth/logout` - Requires `CurrentUser`  
- `/api/auth/admin/users` - Requires `AdminUser`
- `/api/auth/admin/users/{id}` - Requires `AdminUser` (PUT/DELETE)
- `/api/auth/admin/whitelist` - Requires `AdminUser` (GET/POST/DELETE)

#### Public Auth Endpoints (must remain public)
- `/api/auth/providers` - List OAuth providers
- `/api/auth/login/{provider}` - OAuth login initiation
- `/api/auth/callback/{provider}` - OAuth callbacks
- `/api/auth/refresh` - Token refresh

### ❌ UNPROTECTED ENDPOINTS (need protection)

#### Campaign Management (`/api/campaigns/*`)
- `GET /api/campaigns` - List all campaigns
- `POST /api/campaigns` - Create new campaign
- `GET /api/campaigns/{campaign_id}` - Get campaign details
- `POST /api/campaigns/{campaign_id}/save` - Save campaign state
- `DELETE /api/campaigns/{campaign_id}` - Delete campaign
- `PATCH /api/campaigns/{campaign_id}` - Update campaign
- `POST /api/campaigns/import` - Import campaign data
- `GET /api/campaigns/{campaign_id}/structured-data` - Get structured data
- `GET /api/campaigns/{campaign_id}/structured-data/summary` - Get summary
- `GET /api/campaigns/{campaign_id}/files` - List campaign files
- `POST /api/campaigns/generate` - Generate campaign content
- `POST /api/campaigns/initialize` - Initialize campaign

#### Chat/Game Session (`/api/chat/*`)
- `POST /api/chat` - Main chat endpoint
- `POST /api/campaigns/new` - Create new campaign via chat
- `POST /api/campaigns/add-context` - Add context to campaign
- `POST /api/chat/compat` - Compatibility chat endpoint

#### Structured/Simple Campaigns
- `GET /api/structured-campaigns/{campaign_id}` - Get structured campaign
- `GET /api/simple-campaigns/{campaign_id}` - Get simple campaign
- `GET /api/simple-campaigns` - List simple campaigns

#### Image Generation (`/api/images/*`)
- `POST /api/images/generate` - Generate images (GPU/API intensive)
- `POST /api/generate-image` - Legacy image generation endpoint
- `GET /api/images` - List generated images
- `GET /api/images/{filename}` - Get specific image

#### Text-to-Speech (`/api/tts/*`)
- `POST /api/tts/synthesize` - Generate speech (API intensive)
- `GET /api/tts/auto/status` - Auto-TTS status
- `POST /api/tts/auto/toggle` - Toggle auto-TTS
- `POST /api/tts/auto/voice/{voice}` - Set TTS voice
- `POST /api/tts/auto/speed/{speed}` - Set TTS speed
- `GET /api/tts/queue/status` - Queue status
- `POST /api/tts/queue/clear` - Clear queue
- `POST /api/tts/queue/stop` - Stop playback

#### Character Management
- `POST /api/characters/generate` - Generate character
- `GET /api/characters/voices` - Get character voices

#### Internal/Debug Endpoints (`/api/internal/*`)
- `POST /api/internal/analyze-scene` - Scene analysis
- `GET /api/internal/scene-analyzer/status` - Analyzer status
- `POST /api/internal/test-individual-analyzer` - Test analyzer
- `GET /api/internal/debug/last-analysis` - Last analysis debug
- `POST /api/internal/run-campaign` - Run campaign
- `POST /api/internal/test-turn` - Test turn
- `GET /api/internal/health` - Internal health check
- `GET /api/internal/campaign/{campaign_id}/context` - Get context
- `POST /api/internal/campaign/{campaign_id}/summarize` - Summarize
- `POST /api/internal/campaign/{campaign_id}/analyze-current-scene` - Analyze scene
- `GET /api/internal/campaign/{campaign_id}/current-status` - Current status
- `POST /api/internal/campaign/{campaign_id}/generate-complete-summary` - Full summary

### ℹ️ Public/Config Endpoints (can remain public)
- `GET /api/health` - Health check
- `POST /api/test` - Test endpoint
- `GET /api/tts/voices` - List available voices
- `GET /api/tts/availability` - TTS provider availability
- `GET /api/tts/providers` - List TTS providers
- `GET /api/image-models` - List image models
- `POST /api/image-models/switch` - Switch image model

## Authentication Dependencies Available

The codebase already imports the following auth dependencies in `main.py`:
```python
from auth.src.middleware import CurrentUser, ActiveUser, AdminUser, OptionalUser
```

However, these are NOT being used on most endpoints!

## Implementation Priority

### 🔴 Critical Priority (User Data & Security)
1. **Campaign endpoints** - Users' game data must be isolated
2. **Chat endpoints** - Game interactions tied to users
3. **Character generation** - User-created content

### 🟡 High Priority (Resource Intensive)
1. **Image generation** - GPU/API costs
2. **TTS synthesis** - API costs
3. **Internal campaign operations** - Should be admin-only

### 🟢 Medium Priority (Configuration)
1. **Auto-TTS controls** - User preferences
2. **Queue management** - User's audio queue

### ⚪ Low Priority (Read-Only Info)
1. **Voice lists** - Can remain public
2. **Model lists** - Can remain public
3. **Provider info** - Can remain public

## Required Changes

### Phase 1: Add Optional Authentication
First, add `OptionalUser` to track usage without breaking existing functionality:

```python
@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    current_user: OptionalUser = None
):
    if current_user:
        # Track authenticated usage
        logger.info(f"Authenticated chat from user: {current_user.email}")
    # Process request...
```

### Phase 2: Enforce Authentication
After testing, enforce authentication on sensitive endpoints:

```python
@app.post("/api/campaigns")
async def create_campaign(
    request: CreateCampaignRequest,
    current_user: CurrentUser  # Makes auth required
):
    # Campaign tied to authenticated user
    campaign.user_id = current_user.user_id
    # Only this user can access this campaign
```

### Phase 3: Add User Isolation
Ensure users can only access their own data:

```python
@app.get("/api/campaigns")
async def list_campaigns(
    current_user: CurrentUser,
    limit: int = 100
):
    # Filter campaigns by user
    campaigns = await get_user_campaigns(current_user.user_id, limit)
    return campaigns
```

### Phase 4: Admin-Only Internal Endpoints
Lock down internal/debug endpoints:

```python
@router.post("/internal/run-campaign")
async def run_campaign(
    request: RunCampaignRequest,
    admin_user: AdminUser  # Admin only
):
    # Only admins can run campaigns directly
```

## Database Schema Requirements

Campaigns and other user data need user_id fields:
```sql
ALTER TABLE campaigns ADD COLUMN user_id UUID REFERENCES auth.users(id);
ALTER TABLE generated_images ADD COLUMN user_id UUID REFERENCES auth.users(id);
ALTER TABLE characters ADD COLUMN user_id UUID REFERENCES auth.users(id);
```

## Testing Checklist

### Before Implementation
- [ ] OAuth2 provider configured and working
- [ ] Can complete full login flow
- [ ] Receive valid JWT tokens
- [ ] Can access protected auth endpoints
- [ ] Admin role enforcement works
- [ ] Token refresh works

### After Implementation
- [ ] Unauthenticated requests return 401
- [ ] Users can only access their own campaigns
- [ ] Admin users can access internal endpoints
- [ ] Token expiration handled gracefully
- [ ] Frontend handles auth redirects
- [ ] Resource limits per user enforced

## Security Considerations

1. **Session Management**: Campaigns must be tied to user sessions
2. **Data Isolation**: Users must only see their own data
3. **Rate Limiting**: Add per-user rate limits after auth
4. **Audit Logging**: Log all authenticated actions
5. **Resource Limits**: Set per-user limits for expensive operations
6. **CSRF Protection**: Ensure state parameter validation in OAuth
7. **Token Storage**: Move tokens from URLs to secure cookies

## Migration Strategy

1. **Add user_id columns** to existing tables (nullable initially)
2. **Deploy optional auth** to gather metrics
3. **Announce auth requirement** to users (grace period)
4. **Migrate existing data** to admin user or archive
5. **Enable required auth** progressively by endpoint priority
6. **Full enforcement** after migration complete

## Next Steps

1. ✅ Document all unprotected endpoints (this document)
2. ⚠️ Fix the auth middleware import issue (missing Header import)
3. ⚠️ Implement cookie-based token storage (security critical)
4. ⚠️ Add PKCE and state validation to OAuth flow
5. 🔜 Add user_id columns to database tables
6. 🔜 Start with OptionalUser on high-value endpoints
7. 🔜 Implement user data isolation
8. 🔜 Lock down internal endpoints to admin-only
9. 🔜 Full authentication enforcement

---

**Critical Security Note**: The current state leaves the entire application exposed. Any user can access any campaign, generate images, use TTS, and access internal debug endpoints without authentication. This must be addressed urgently.