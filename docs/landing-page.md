# Landing Page Redesign - Implementation Plan

## Executive Summary

Transform the home route from auto-loading the last campaign into a welcome screen with role-based navigation. Users explicitly choose their role (DM or Player) and select a session, making the session ID part of the URL structure.

## Current Architecture (As-Is)

### Routing Structure
- **`/`** - Auto-loads last campaign, shows DM view (App.jsx)
- **`/player`** - Shows player view (PlayerPage.jsx)
- **`/login`** - Auth0 login (production only)
- **`/callback`** - Auth0 callback (production only)
- **`/auth-error`** - Authentication error page

### Current Campaign Loading Flow
1. App.jsx mounts at `/`
2. After 1 second delay, `autoLoadLastCampaign()` executes
3. Checks `localStorage.lastCampaignId`
4. If not found, fetches campaign list and loads newest by `created_at`
5. Calls `handleSelectCampaign(campaignId)` to load campaign data
6. Both DM and Player views share `currentCampaignId` via localStorage
7. Cross-tab synchronization via storage events

### Current State Management
- **Campaign ID Storage**: `localStorage.lastCampaignId`
- **State Hook**: `useCampaignOperations.js` manages selection/loading
- **API Service**: `apiService.loadSimpleCampaign(campaignId)` loads campaign
- **No Redux**: Uses React hooks + context pattern
- **WebSocket**: Per-campaign connections using session ID in query params

### Current URL Schema Issues
- ❌ Session ID not in URL path
- ❌ Refreshing page may load different campaign if localStorage changes
- ❌ Can't share direct links to specific campaigns
- ❌ Back/forward browser navigation doesn't work for campaign switching
- ❌ No way to open multiple campaigns in different tabs intentionally

## Target Architecture (To-Be)

### New Routing Structure
```
/                           → Landing page (new WelcomePage component)
/:sessionId/dm              → DM view for specific campaign
/:sessionId/player          → Player view for specific campaign
/login                      → Auth0 login (production, unchanged)
/callback                   → Auth0 callback (production, unchanged)
/auth-error                 → Auth error page (unchanged)
```

### Landing Page UI (WelcomePage.jsx)

#### Layout
```
┌─────────────────────────────────────┐
│                                     │
│         [Fable Table Logo]          │
│                                     │
│      Choose Your Journey:           │
│                                     │
│   ┌─────────────────────────┐      │
│   │   🎲 Dungeon Master      │      │
│   └─────────────────────────┘      │
│                                     │
│   ┌─────────────────────────┐      │
│   │   ⚔️  Adventurer         │      │
│   └─────────────────────────┘      │
│                                     │
└─────────────────────────────────────┘
```

#### Components Structure
```
WelcomePage.jsx
├── Logo placeholder (to be replaced with actual logo)
├── Title: "Choose Your Journey"
├── Button: "Dungeon Master" → opens CampaignManager (reused)
├── Button: "Adventurer" → opens PlayerSessionModal
└── Modals
    ├── CampaignManager.jsx (REUSED - existing component)
    │   ├── List of campaigns (sorted by last_played) ✓ already exists
    │   ├── "Load" button per campaign → modified to navigate to /:sessionId/dm
    │   └── "Create New" button ✓ already exists → opens CampaignSetup wizard
    │
    ├── CampaignSetup.jsx (REUSED - existing wizard modal)
    │   ├── Multi-step wizard for campaign creation ✓ already exists
    │   ├── Step 1: Campaign info (title, description, style, setting, etc.)
    │   ├── Step 2: Player count
    │   ├── Step 3: Character creation (pre-gen or custom)
    │   └── onComplete(campaignId) → modified to navigate to /:sessionId/dm
    │
    └── PlayerSessionModal.jsx (NEW)
        └── List of invited/joined sessions
            └── "Join Session" button per session
                → navigates to /:sessionId/player
```

### New Navigation Flow

#### DM Flow
1. User clicks "Dungeon Master" button
2. `CampaignManager` modal opens (reused existing component)
3. Fetches campaign list via `apiService.listCampaigns({ sortBy: 'last_played' })` ✓ already implemented
4. Shows campaigns with:
   - Campaign name
   - Last played timestamp
   - "Load" button (existing)
5. Shows "Create New" button (existing, for structured campaigns)
6. On Load: `navigate('/:sessionId/dm')` (modify existing behavior)
7. On Create New:
   - Opens `CampaignSetup` wizard modal ✓ existing component (multi-step wizard)
   - CampaignManager closes
   - User completes wizard (campaign info → player count → character creation)
   - Wizard calls `onComplete(campaignId)` with new campaign ID
   - `navigate('/:newSessionId/dm')` (modify existing onComplete behavior)

#### Player Flow
1. User clicks "Adventurer" button
2. `PlayerSessionModal` opens
3. Fetches sessions list (needs new API endpoint or filter existing)
   - Option A: Filter `listCampaigns()` for campaigns where user is a player
   - Option B: New endpoint `/api/player-sessions`
4. Shows sessions with:
   - Campaign name
   - DM name/owner
   - "Join" button
5. On Join: `navigate('/:sessionId/player')`

### URL-Based Session Management

#### DM View Changes (App.jsx)
**Current:**
```javascript
// Auto-loads from localStorage
useEffect(() => {
  const timer = setTimeout(autoLoadLastCampaign, 1000);
  return () => clearTimeout(timer);
}, [autoLoadLastCampaign]);
```

**New:**
```javascript
// Get sessionId from URL params
const { sessionId } = useParams();

useEffect(() => {
  if (sessionId) {
    handleSelectCampaign(sessionId);
  }
}, [sessionId]);
```

#### Player View Changes (PlayerPage.jsx)
**Current:**
```javascript
// Gets sessionId from localStorage
const [currentCampaignId, setCurrentCampaignId] = useState(() => {
  return localStorage.getItem('lastCampaignId');
});
```

**New:**
```javascript
// Get sessionId from URL params
const { sessionId } = useParams();

useEffect(() => {
  if (sessionId) {
    setCurrentCampaignId(sessionId);
    loadCampaignData(sessionId);
  }
}, [sessionId]);
```

#### Benefits of URL-Based Approach
✅ Shareable links to specific campaigns
✅ Browser back/forward works correctly
✅ Refresh maintains correct campaign
✅ Multiple campaigns in different tabs
✅ Clearer separation between DM and player roles
✅ No race conditions with localStorage sync
✅ Better for bookmarking specific sessions

### localStorage Usage After Changes

**Keep using localStorage for:**
- User preferences (theme, audio settings, etc.)
- Auth tokens (Auth0)
- Cached data for performance
- Most recently used campaign ID (for modal sorting/highlighting)

**Stop using localStorage for:**
- ❌ Determining which campaign is currently active
- ❌ Cross-tab campaign synchronization (URL handles this)
- ❌ Auto-loading campaigns on app startup

### Backward Compatibility & Migration

#### Handling Old URLs
Users may have bookmarks or links to `/` or `/player`. We need graceful fallback:

**Option A: Redirect to Landing**
```javascript
// In AppWithAuth0.jsx routes
<Route path="/" element={<WelcomePage />} />
<Route path="/player" element={<Navigate to="/" replace />} />
```

**Option B: Auto-Load with Redirect**
```javascript
// In AppWithAuth0.jsx routes
<Route path="/" element={<LegacyRouteHandler />} />

// LegacyRouteHandler component
function LegacyRouteHandler() {
  const navigate = useNavigate();

  useEffect(() => {
    const lastCampaignId = localStorage.getItem('lastCampaignId');
    if (lastCampaignId) {
      navigate(`/${lastCampaignId}/dm`, { replace: true });
    } else {
      navigate('/welcome', { replace: true });
    }
  }, []);

  return <LoadingSpinner />;
}
```

**Recommendation**: Use Option A (redirect to landing). Forces users to explicitly choose role and session, avoiding confusion.

#### Invite Token Handling
Currently, invite tokens work via query params: `/?invite=<token>` or `/player?invite=<token>`

**New approach:**
- Landing page accepts `/?invite=<token>`
- Shows "You've been invited to join a session!" message
- Auto-opens Player modal or auto-navigates to `/:sessionId/player` after token validation
- Alternative: New route `/invite/:token` that processes and redirects

## Implementation Plan

### Phase 1: Create New Components (Non-Breaking)
**Goal**: Build landing page and player modal without touching existing routes

#### Tasks
1. **Create `WelcomePage.jsx`**
   - Location: `/frontend/src/components/WelcomePage.jsx`
   - Simple layout with logo placeholder, title, two buttons
   - No API calls yet, just UI structure
   - Use existing styling patterns from `App.jsx` / `PlayerPage.jsx`
   - Renders `CampaignManager` (existing) when "Dungeon Master" clicked
   - Renders `PlayerSessionModal` (new) when "Adventurer" clicked

2. **Modify `CampaignManager.jsx`** (Existing Component)
   - Add `mode` prop: `'select'` (default, current behavior) or `'navigate'` (new behavior for landing page)
   - Add `onRequestNewCampaign` callback prop (optional, for triggering CampaignSetup wizard)
   - When `mode='navigate'`:
     - Import `useNavigate` from `react-router-dom`
     - On "Load" button click:
       - Call `navigate('/${sessionId}/dm')` instead of `onCampaignSelect(sessionId)`
       - Close modal after navigation
     - On "Create New" button click:
       - **Hide existing inline form** (lines ~369-405 with showCreateForm state)
       - Show "Create New Campaign" button instead (only when `mode='navigate'`)
       - If `onRequestNewCampaign` callback provided, call it (opens CampaignSetup wizard)
       - Implementation:
         ```javascript
         {!showSimple && mode === 'navigate' && (
           <Button onClick={onRequestNewCampaign} variant="primary">
             ✨ Create New Campaign
           </Button>
         )}
         {!showSimple && mode !== 'navigate' && (
           <Button onClick={() => setShowCreateForm(true)} variant="primary">
             Create New
           </Button>
         )}
         ```
   - When `mode='select'` (default):
     - Keep existing behavior: inline form, `onCampaignSelect` callback
     - Maintains backward compatibility during transition
   - Close modal after navigation

3. **Update `WelcomePage.jsx` to manage modals**
   - Manage state for `CampaignManager`, `CampaignSetup`, and `PlayerSessionModal`
   - Pass `onRequestNewCampaign` callback to CampaignManager
   - When callback fired, close CampaignManager and open CampaignSetup
   - CampaignSetup's `onComplete(campaignId)` navigates to `/:sessionId/dm`

4. **Create `PlayerSessionModal.jsx`** (NEW - no existing component found)
   - **Validation**: No existing player session selector exists (verified 2025-11-01)
   - **Current behavior**: Players load from localStorage, no UI to view/select sessions
   - Location: `/frontend/src/components/PlayerSessionModal.jsx`
   - **API Call**: Use `apiService.listSimpleCampaigns({ ownedOnly: false })`
     - Returns all campaigns user has access to (owned OR member)
     - No client-side filtering needed - show all accessible campaigns
   - Display session list with:
     - Campaign name
     - DM name/owner (from `owner_email` field)
     - Last played time (if available)
     - "Join Session" button per campaign
   - Handle navigation to `/:sessionId/player` on Join click
   - Similar styling to CampaignManager (reuse Modal, Card, Button components)
   - Import and use `useNavigate` from `react-router-dom`

5. **Test Components in Isolation**
   - Temporarily add route `/welcome` → `WelcomePage`
   - Verify CampaignManager opens with `mode='navigate'`
   - Verify "Create New" button opens CampaignSetup wizard
   - Verify CampaignSetup wizard completes and returns campaign ID
   - Verify PlayerSessionModal opens/closes correctly
   - Verify navigation buttons work (will fail until routes updated)

### Phase 2: Update Routing Structure
**Goal**: Add new routes without removing old ones (parallel operation)

#### Tasks
1. **Update `AppWithAuth0.jsx` Routes**
   - Add new routes:
     ```javascript
     <Route path="/welcome" element={<WelcomePage />} />
     <Route path="/:sessionId/dm" element={<ProtectedRoute><App /></ProtectedRoute>} />
     <Route path="/:sessionId/player" element={<ProtectedRoute><PlayerPage /></ProtectedRoute>} />
     ```
   - Keep existing `/` and `/player` routes temporarily

2. **Test New Routes Work**
   - Manually navigate to `/welcome`
   - Manually navigate to `/<valid-session-id>/dm`
   - Manually navigate to `/<valid-session-id>/player`
   - Verify all routes load correctly

### Phase 3: Update DM View to Use URL Session ID
**Goal**: Make DM view work with `/:sessionId/dm` route

#### Tasks
1. **Update `App.jsx`**
   - Import `useParams` from `react-router-dom`
   - Get `sessionId` from URL: `const { sessionId } = useParams();`
   - Replace auto-load logic:
     ```javascript
     // OLD:
     useEffect(() => {
       const timer = setTimeout(autoLoadLastCampaign, 1000);
       return () => clearTimeout(timer);
     }, [autoLoadLastCampaign]);

     // NEW:
     useEffect(() => {
       if (sessionId) {
         handleSelectCampaign(sessionId)
           .catch(error => {
             console.error('Failed to load campaign:', error);
             // Handle different error types
             if (error.message?.includes('404') || error.message?.includes('not found')) {
               setError('Campaign not found. It may have been deleted.');
             } else if (error.message?.includes('403') || error.message?.includes('unauthorized')) {
               setError('You do not have access to this campaign.');
             } else {
               setError('Failed to load campaign. Please try again.');
             }
           });
       }
     }, [sessionId]);
     ```
   - **Update WebSocket connection**: Change `useDMWebSocket` to use sessionId from URL
     ```javascript
     const { webSocketRef: dmWebSocketRef } = useDMWebSocket({
       campaignId: sessionId,  // ← Changed from currentCampaignId to sessionId
       getAccessTokenSilently,
       // ... other props
     });
     ```
   - Add error display UI when campaign fails to load:
     ```javascript
     {error && !currentCampaignId && (
       <div className="flex items-center justify-center min-h-[60vh]">
         <div className="text-center bg-gaia-light rounded-lg p-8 max-w-md">
           <h2 className="text-xl font-bold text-red-400 mb-4">⚠️ Error</h2>
           <p className="text-white mb-6">{error}</p>
           <Link
             to="/"
             className="px-6 py-3 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors font-bold"
           >
             🏠 Return to Campaign Lobby
           </Link>
         </div>
       </div>
     )}
     ```
   - Keep localStorage write for "last used" tracking (optional)
   - Remove localStorage read for determining active campaign

2. **Update `useCampaignOperations.js`**
   - Keep `handleSelectCampaign()` function (still needed)
   - Remove or deprecate `autoLoadLastCampaign()` function
   - Ensure `handleSelectCampaign` properly throws errors for invalid campaign IDs

3. **Test DM View**
   - Navigate to `/:sessionId/dm` with valid session ID → loads correctly
   - Navigate to invalid session ID → shows error page with "Return to Campaign Lobby"
   - Test unauthorized campaign → shows access denied error
   - Test switching between campaigns by changing URL → WebSocket reconnects
   - Verify error state clears when navigating to valid campaign

### Phase 4: Update Player View to Use URL Session ID
**Goal**: Make player view work with `/:sessionId/player` route

#### Tasks
1. **Update `PlayerPage.jsx`**
   - Import `useParams` from `react-router-dom`
   - Get `sessionId` from URL: `const { sessionId } = useParams();`
   - Replace localStorage-based initialization:
     ```javascript
     // OLD:
     const initialSessionId = localStorage.getItem('lastCampaignId');
     const [currentCampaignId, setCurrentCampaignId] = useState(initialSessionId);

     // NEW:
     const { sessionId } = useParams();
     const [currentCampaignId, setCurrentCampaignId] = useState(sessionId);

     useEffect(() => {
       if (sessionId) {
         setCurrentCampaignId(sessionId);
         loadCampaignData(sessionId)
           .catch(error => {
             console.error('Failed to load campaign:', error);
             // Handle different error types
             if (error.message?.includes('404') || error.message?.includes('not found')) {
               setError('Campaign not found. It may have been deleted.');
             } else if (error.message?.includes('403') || error.message?.includes('unauthorized')) {
               setError('You do not have access to this campaign.');
             } else {
               setError('Failed to load campaign. Please try again.');
             }
           });
       } else {
         setError('No campaign ID provided in URL');
       }
     }, [sessionId]);
     ```
   - Remove storage event listener (lines ~436-464, no longer needed for cross-tab sync)
   - Update error display to include "Return to Campaign Lobby" link:
     ```javascript
     {error && (
       <div className="bg-gaia-error text-white px-4 py-3 mx-4 rounded-md font-bold mt-4">
         <p className="mb-2">Error: {error}</p>
         <Link
           to="/"
           className="text-sm underline hover:text-gray-200"
         >
           🏠 Return to Campaign Lobby
         </Link>
       </div>
     )}
     ```

2. **Update WebSocket Connection**
   - **WebSocket already uses session ID** in connection URL (line ~1090+)
   - Ensure it uses `sessionId` from URL params instead of `currentCampaignId` state
   - WebSocket query params: `?session_id={sessionId}` (ensure sessionId is from URL)

3. **Test Player View**
   - Navigate to `/:sessionId/player` with valid session ID → loads correctly
   - Navigate to invalid session ID → shows error with "Return to Campaign Lobby"
   - Navigate to unauthorized campaign → shows access denied error
   - Test character sheet displays correctly
   - Test WebSocket messages work (reconnects when URL changes)
   - Verify storage event listener removed (no more cross-tab syncing)

### Phase 5: Handle Invite Tokens
**Goal**: Support invite links in new URL structure

#### Tasks
1. **Update Invite Flow in `WelcomePage.jsx`**
   - Import `useSearchParams` and `useNavigate` from `react-router-dom`
   - Add state for invite processing: `const [inviteError, setInviteError] = useState(null)`
   - Detect invite token on component mount:
     ```javascript
     import { useSearchParams, useNavigate } from 'react-router-dom';

     function WelcomePage() {
       const [searchParams] = useSearchParams();
       const navigate = useNavigate();
       const [inviteError, setInviteError] = useState(null);
       const [processingInvite, setProcessingInvite] = useState(false);

       useEffect(() => {
         const inviteToken = searchParams.get('invite');
         if (inviteToken) {
           handleInviteToken(inviteToken);
         }
       }, [searchParams]);

       const handleInviteToken = async (token) => {
         try {
           setProcessingInvite(true);
           setInviteError(null);
           const response = await apiService.joinSessionByInvite(token);
           if (response.session_id) {
             // Auto-navigate to player view with session ID
             navigate(`/${response.session_id}/player`, { replace: true });
           } else {
             throw new Error('Invite did not return a session ID');
           }
         } catch (error) {
           console.error('Failed to process invite:', error);
           setInviteError(error.message || 'Invalid or expired invite link');
           setProcessingInvite(false);
         }
       };

       // ... rest of component
     }
     ```
   - Show loading indicator while processing invite: "Processing invite..."
   - Show error message if invite fails with option to continue to landing page
   - Remove invite token from URL after processing (success or failure)

2. **Update Backend API (if needed)**
   - Verify `/api/join-session-invite` returns `session_id` field
   - Verify it handles already-joined sessions gracefully (returns session_id)
   - No changes expected - just validation

3. **Test Invite Flow**
   - Generate invite link from DM view (existing "Share" button)
   - Open invite link in new browser/incognito: `/?invite=<token>`
   - Verify landing page shows "Processing invite..." message
   - Verify auto-join and redirect to `/:sessionId/player`
   - Test invalid/expired token shows error message
   - Test already-joined invite (should still work)

### Phase 6: Switch Root Route to Landing Page & Remove Header Buttons
**Goal**: Make `/` route show welcome page instead of auto-loading campaign, and remove header campaign management buttons

#### Tasks
1. **Update `AppWithAuth0.jsx` Routes**
   - Change `/` route from `<App />` to `<WelcomePage />`
   - Remove `/welcome` route (no longer needed)
   - Keep `/:sessionId/dm` and `/:sessionId/player` routes
   - Add fallback for old `/player` route:
     ```javascript
     <Route path="/player" element={<Navigate to="/" replace />} />
     ```

2. **Remove Campaign Header Buttons & Add Campaign Lobby Button in `App.jsx`**
   - Remove "📋 Campaigns" button (lines ~917-919)
   - Remove "🎲 New Campaign" button (lines ~920-922)
   - **Add "🏠 Campaign Lobby" button** in their place:
     ```javascript
     <Link
       to="/"
       className="px-3 py-1 bg-purple-500 text-white rounded text-xs hover:bg-purple-600 transition-colors font-medium"
     >
       🏠 Campaign Lobby
     </Link>
     ```
   - Remove `showCampaignList` state and related handlers
   - Remove `showCampaignSetup` state and related handlers
   - Keep CampaignManager and CampaignSetup components for now (can remove later if unused)
   - **Rationale**: Campaign Lobby button allows DMs to switch campaigns by returning to landing page

3. **Remove Legacy Auto-Load Code**
   - Remove `autoLoadLastCampaign()` function from `useCampaignOperations.js`
   - Remove auto-load useEffect from `App.jsx`
   - Clean up localStorage.lastCampaignId reads (keep writes for "last used" tracking)

4. **Test Full User Journey**
   - Navigate to `/` → should show welcome page
   - Click "Dungeon Master" → CampaignManager modal opens with campaign list
   - Click "Load" → navigates to `/:sessionId/dm` and loads campaign
   - Verify header no longer has "Campaigns" or "New Campaign" buttons
   - Click "Start New" (in CampaignManager) → creates campaign and navigates to `/:newSessionId/dm`
   - Navigate to `/` again → click "Adventurer" → PlayerSessionModal opens
   - Click "Join" → navigates to `/:sessionId/player` and loads campaign

### Phase 7: Add Logo and Polish UI
**Goal**: Final visual polish with branding

#### Tasks
1. **Add Logo Asset**
   - User will provide logo file
   - Place in `/frontend/public/` or `/frontend/src/assets/`
   - Update `WelcomePage.jsx` to use actual logo

2. **Styling Polish**
   - Match existing app theme (dark mode support)
   - Responsive design for mobile
   - Button hover states, animations
   - Modal transitions

3. **Accessibility**
   - Keyboard navigation
   - ARIA labels
   - Focus management in modals

### Phase 8: Testing & Validation
**Goal**: Comprehensive testing before deployment

#### Tasks
1. **Unit Tests**
   - Test WelcomePage renders correctly
   - Test modals open/close
   - Test navigation functions

2. **Integration Tests**
   - Test full DM flow (landing → modal → campaign)
   - Test full Player flow (landing → modal → session)
   - Test invite token flow
   - Test URL-based campaign loading

3. **E2E Tests**
   - Test in both development and production mode (with Auth0)
   - Test browser back/forward navigation
   - Test refresh on campaign page
   - Test multiple tabs with different campaigns

4. **Docker Testing**
   - Build frontend in Docker: `docker exec gaia-frontend-dev npm run build`
   - Restart containers: `docker restart gaia-frontend-dev gaia-backend-dev`
   - Test full flow in containerized environment

### Phase 9: Deployment
**Goal**: Deploy to staging, test, then production

#### Tasks
1. **Deploy to Staging**
   - Run `./scripts/deploy_staging.sh --local`
   - Test all flows in staging environment
   - Verify Auth0 integration works

2. **Monitor & Fix Issues**
   - Check Cloud Run logs for errors
   - Test with real users if possible
   - Fix any deployment-specific issues

3. **Deploy to Production**
   - Run `./scripts/deploy_production.sh --local`
   - Monitor deployment health checks
   - Verify production functionality

4. **Create PR and Commit**
   - Test all changes thoroughly
   - Create descriptive commit message
   - Create PR with summary of changes
   - Reference this plan document in PR description

## Technical Considerations

### API Changes Needed

#### Potential New Endpoints
1. **`GET /api/player-sessions`** - List sessions where user is a player (not DM)
   - Alternative: Use existing `listCampaigns()` with a filter parameter
   - Backend: Filter campaigns by player user ID

2. **Session ID Validation**
   - `GET /api/campaigns/:sessionId/exists` - Check if session exists
   - Used to show 404 page if URL session ID is invalid

#### Modified Endpoints
- Ensure all campaign endpoints accept session ID in path (likely already done)
- Ensure invite token endpoint returns session ID in response

### Error Handling

#### Invalid Session ID in URL
- Show error page: "Campaign not found"
- Provide "Return to Home" button → navigates to `/`

#### Unauthorized Access
- User tries to access session they're not part of
- Show error: "You don't have access to this campaign"
- Provide "Return to Home" button

#### Session Loading Failures
- API call to `loadSimpleCampaign()` fails
- Show error message with retry button
- Option to return to landing page

### WebSocket Considerations

Both DM and Player views use WebSocket connections:
- **DM**: `/ws/campaign/dm` with session ID in query params or message
- **Player**: `/ws/campaign/player?session_id={id}`

#### Changes Needed
- Ensure WebSocket connections use URL session ID
- Handle reconnection if session ID changes (user navigates to different campaign)
- Close old WebSocket when component unmounts

### State Management

#### Current State Hooks (Keep Using)
- `useCampaignState.js` - Per-session structured data
- `useCampaignMessages.js` - Per-session messages
- `useCampaignOperations.js` - Campaign selection/loading logic
- `useStreamingState.js` - Per-session streaming state

#### Changes to State Hooks
- Remove dependency on localStorage for active campaign
- Add URL-based initialization
- Keep multi-session support (already supports multiple session IDs)

### Browser History & Navigation

#### Back/Forward Behavior
- User navigates from Campaign A to Campaign B
- Browser back button returns to Campaign A
- React Router handles URL changes
- useEffect detects new session ID and loads correct campaign

#### Refresh Behavior
- User refreshes page on `/:sessionId/dm`
- App reloads, React Router parses session ID from URL
- useEffect loads campaign from session ID
- No localStorage needed

### Multi-Tab Behavior

#### Current (localStorage sync)
- User opens Campaign A in Tab 1
- User opens same app in Tab 2
- Tab 2 auto-syncs to Campaign A via storage events
- Confusing if user wants different campaigns in different tabs

#### New (URL-based)
- Tab 1: `/:sessionA/dm`
- Tab 2: `/:sessionB/dm`
- Each tab maintains its own session independently
- No cross-tab interference
- Better for DMs managing multiple campaigns

## Migration & Rollback Plan

### User Experience During Transition
- Existing users may have old URLs bookmarked
- Old `/` route redirects to `/welcome` (landing page)
- Old `/player` route redirects to `/welcome`
- Users will need to re-select their campaigns once
- Invite links will need to be regenerated (if URL structure changes)

### Rollback Strategy
If issues arise post-deployment:
1. Revert commit with routing changes
2. Restore old `App.jsx` with auto-load logic
3. Restore old route structure (`/` → DM view, `/player` → Player view)
4. Re-deploy previous version

### Feature Flag Approach (Optional)
Add feature flag to toggle between old and new landing page:
```javascript
const USE_NEW_LANDING = process.env.REACT_APP_NEW_LANDING === 'true';

<Route path="/" element={USE_NEW_LANDING ? <WelcomePage /> : <App />} />
```

This allows:
- Gradual rollout (enable for subset of users)
- A/B testing
- Easy rollback via environment variable

## File Change Summary

### New Files to Create
```
frontend/src/components/WelcomePage.jsx              # Landing page
frontend/src/components/PlayerSessionModal.jsx       # Player session selector modal
frontend/src/components/WelcomePage.css              # Styling for landing page (optional)
docs/landing-page.md                                 # This plan document ✓ created
```

### Files to Modify
```
frontend/src/AppWithAuth0.jsx                        # Update route configuration
frontend/src/App.jsx                                 # Use URL params for session ID, remove header buttons
frontend/src/components/CampaignManager.jsx          # Add navigation mode, onRequestNewCampaign callback
frontend/src/components/CampaignSetup.jsx            # Modify onComplete to navigate to /:sessionId/dm
frontend/src/components/player/PlayerPage.jsx        # Use URL params for session ID
frontend/src/hooks/useCampaignOperations.js          # Remove/deprecate auto-load logic
frontend/src/services/apiService.js                  # Potentially add new endpoints
```

### Files to Potentially Delete (Optional - Phase 9)
```
# After confirming new flow works and header buttons are removed:
# Consider removing auto-load logic entirely from useCampaignOperations.js
# CampaignSetup.jsx will be KEPT and REUSED for campaign creation wizard
```

## Success Criteria

### Functional Requirements
✅ Landing page displays with logo and two buttons
✅ Dungeon Master button opens modal with campaign list
✅ Player button opens modal with session list
✅ Resume campaign navigates to `/:sessionId/dm` and loads correctly
✅ Start new campaign creates campaign and navigates to `/:newSessionId/dm`
✅ Join session navigates to `/:sessionId/player` and loads correctly
✅ URL refresh maintains correct campaign
✅ Browser back/forward works correctly
✅ Invite tokens still work with new URL structure
✅ Invalid session IDs show error page
✅ All existing features work (chat, combat, images, audio, etc.)

### Non-Functional Requirements
✅ No performance regression in campaign loading
✅ Responsive design works on mobile
✅ Accessible via keyboard navigation
✅ Compatible with Auth0 in production
✅ Works in Docker development environment
✅ Works in deployed staging/production environments

### User Experience Goals
✅ Clear separation between DM and Player roles
✅ Explicit campaign selection (no auto-loading confusion)
✅ Shareable campaign URLs
✅ Ability to open multiple campaigns in different tabs
✅ Smooth transition from current flow

## Timeline Estimate

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1 | Create/modify components (WelcomePage, CampaignManager, PlayerSessionModal) | 2-3 hours |
| Phase 2 | Update routing structure | 1 hour |
| Phase 3 | Update DM view (URL params) | 2 hours |
| Phase 4 | Update Player view (URL params) | 2 hours |
| Phase 5 | Handle invite tokens | 1 hour |
| Phase 6 | Switch root route & remove header buttons | 1-2 hours |
| Phase 7 | Add logo & polish UI | 2-3 hours |
| Phase 8 | Testing & validation | 3-4 hours |
| Phase 9 | Deployment | 1-2 hours |
| **Total** | | **15-21 hours** |

## Open Questions & Decisions Needed

1. **Logo Asset**
   - User will provide logo later
   - What format? (SVG preferred for scalability)
   - What dimensions?

2. **Player Session List API**
   - Create new endpoint `/api/player-sessions`?
   - Or filter existing `listCampaigns()` with `playerOnly` parameter?
   - **Recommendation**: Use existing endpoint with filter for simplicity

3. **Invite Token URL Structure**
   - Keep query param `?invite=<token>`?
   - Or create dedicated route `/invite/:token`?
   - **Recommendation**: Keep query param, handle in landing page

4. **Legacy URL Handling**
   - Redirect `/` and `/player` to landing page?
   - Or try to preserve last campaign and auto-redirect?
   - **Recommendation**: Redirect to landing page (forces explicit selection)

5. **Feature Flag**
   - Should we use a feature flag for gradual rollout?
   - Or deploy all at once?
   - **Recommendation**: Deploy all at once after thorough testing in staging

6. **localStorage Cleanup**
   - Keep `lastCampaignId` for "highlight last used campaign" in modal?
   - Or completely remove all localStorage campaign tracking?
   - **Recommendation**: Keep for UX enhancement (highlight last used)

## Next Steps

1. **Review this plan** with the user
2. **Get approval** on approach and UI design
3. **Begin Phase 1** - Create new components
4. **Iterate** through phases, testing thoroughly at each step
5. **Deploy to staging** for final validation
6. **Deploy to production** after user acceptance

---

**Document Version**: 1.2
**Created**: 2025-11-01
**Last Updated**: 2025-11-01
**Author**: Claude Code
**Status**: Ready for Implementation - All gaps addressed

## Changelog

### v1.2 (2025-11-01) - Critical Gap Fixes
Comprehensive review completed (see `docs/landing-page-review.md`). All 6 critical gaps addressed:

- **GAP 1 - Campaign Switching UX**: Added "🏠 Campaign Lobby" button to DM header (Phase 6)
  - Allows DMs to return to landing page to switch campaigns
  - Replaces removed "Campaigns" and "New Campaign" buttons

- **GAP 2 - Player Session API**: Specified exact API call for PlayerSessionModal (Phase 1)
  - Use `listSimpleCampaigns({ ownedOnly: false })` to show all accessible campaigns
  - No client-side filtering needed

- **GAP 3 - Invite Token Flow**: Added complete implementation details (Phase 5)
  - WelcomePage detects `?invite=token` query param
  - Auto-processes invite and navigates to player view
  - Includes error handling and loading states
  - Full code example provided

- **GAP 4 - Error Handling**: Added error handling to DM and Player views (Phases 3 & 4)
  - Handle 404 (campaign not found) and 403 (unauthorized) errors
  - Display error UI with "Return to Campaign Lobby" link
  - Proper error catching in useEffect hooks

- **GAP 5 - Inline Form Handling**: Clarified CampaignManager "Create New" behavior (Phase 1)
  - Hide inline form when `mode='navigate'`
  - Show "Create New Campaign" button that triggers wizard
  - Keep inline form when `mode='select'` for backward compatibility

- **GAP 6 - WebSocket Updates**: Made WebSocket session ID changes explicit (Phases 3 & 4)
  - Explicitly updated useDMWebSocket to use sessionId from URL params
  - Updated PlayerPage WebSocket connection to use URL sessionId
  - Clear documentation of WebSocket reconnection on URL changes

**Review Score**: 7.5/10 → 9.5/10 after fixes

### v1.1 (2025-11-01)
- **Reuse CampaignManager**: Changed approach to reuse existing `CampaignManager.jsx` instead of creating new `DMSessionModal.jsx`
- **Reuse CampaignSetup wizard**: "Create New" in CampaignManager opens existing `CampaignSetup.jsx` wizard modal
- **Add navigation mode**: `CampaignManager` will support `mode` prop for navigate vs select behavior
- **Add wizard callback**: `CampaignManager` gets `onRequestNewCampaign` prop to trigger CampaignSetup wizard
- **Remove header buttons**: Plan now includes removing "📋 Campaigns" and "🎲 New Campaign" buttons from DM view header
- **Simplify component structure**: Reduced number of new components from 3 to 1 (PlayerSessionModal only, reuse CampaignManager + CampaignSetup)
- **Validated player flow**: Confirmed no existing player session selector exists (PlayerPage uses localStorage only)
- **Updated file changes**: Removed DMSessionModal from new files, added CampaignManager and CampaignSetup to modified files
- **Updated Phase 1**: Modified to reflect CampaignManager modifications and wizard integration
- **Updated Phase 6**: Added task to remove header buttons from App.jsx
- **Updated DM Flow**: Clarified that "Create New" opens CampaignSetup wizard, not inline form

### v1.0 (2025-11-01)
- Initial plan created
