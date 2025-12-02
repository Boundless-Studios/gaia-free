# Public Landing Page Implementation Plan

## Goal
Make the landing page (/) publicly accessible. Only require login when users click "Dungeon Master" or "Adventurer" buttons.

## Current State
- Landing page requires authentication (wrapped in ProtectedRoute)
- Clicking either button immediately shows modals (no auth check)
- Whitelist checking happens at route level (ProtectedRoute component)

## Target State
- Landing page is public (no ProtectedRoute)
- Clicking buttons checks authentication:
  - If authenticated AND authorized → show modal
  - If not authenticated → trigger login, save intent, return after login
  - If authenticated but NOT authorized → show RegistrationFlow
- After login, automatically open the intended modal

## Implementation Changes

### 1. AppWithAuth0.jsx (Line 302-309)

**Current:**
```javascript
<Route
  path="/"
  element={
    <ProtectedRoute>
      <WelcomePage />
    </ProtectedRoute>
  }
/>
```

**New:**
```javascript
<Route
  path="/"
  element={<WelcomePage />}
/>
```

**Rationale:** Remove ProtectedRoute to make landing page publicly accessible.

---

### 2. WelcomePage.jsx (Complete Rewrite of Button Handlers)

**Add Auth Hook Import:**
```javascript
import { useAuth } from '../contexts/Auth0Context.jsx';
```

**Add Auth State:**
```javascript
const WelcomePage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Add auth context
  const { isAuthenticated, loading, user, login } = useAuth();

  // ... existing state ...

  // Add registration status tracking
  const [checkingAuthorization, setCheckingAuthorization] = useState(false);
  const [showRegistration, setShowRegistration] = useState(false);
```

**Update Button Handlers:**
```javascript
// Handler for "Dungeon Master" button
const handleDungeonMasterClick = async () => {
  // If not authenticated, trigger login with intent
  if (!isAuthenticated) {
    // Save intent in URL params (will be preserved through Auth0 redirect)
    login({
      appState: {
        returnTo: '/?intent=dm'
      }
    });
    return;
  }

  // If authenticated, check authorization before opening modal
  const authorized = await checkUserAuthorization();
  if (!authorized) {
    return; // checkUserAuthorization will handle showing registration flow
  }

  // User is authenticated and authorized, open modal
  setShowCampaignManager(true);
};

// Handler for "Adventurer" button
const handleAdventurerClick = async () => {
  // If not authenticated, trigger login with intent
  if (!isAuthenticated) {
    login({
      appState: {
        returnTo: '/?intent=player'
      }
    });
    return;
  }

  // If authenticated, check authorization before opening modal
  const authorized = await checkUserAuthorization();
  if (!authorized) {
    return;
  }

  // User is authenticated and authorized, open modal
  setShowPlayerSessionModal(true);
};
```

**Add Authorization Check:**
```javascript
// Check if user is authorized (whitelist check)
const checkUserAuthorization = async () => {
  if (!user) return false;

  setCheckingAuthorization(true);

  try {
    const response = await fetch('/api/auth/registration-status', {
      headers: {
        Authorization: `Bearer ${await getAccessTokenSilently()}`,
      },
    });

    if (response.ok) {
      const status = await response.json();

      // If pending or not authorized, show registration flow
      if (status.registration_status === 'pending' || !status.is_authorized) {
        setShowRegistration(true);
        return false;
      }

      return true; // Authorized
    } else if (response.status === 403) {
      setShowRegistration(true);
      return false;
    }

    // If we can't check, assume authorized (fallback)
    return true;
  } catch (error) {
    console.error('Error checking authorization:', error);
    return true; // Assume authorized on error
  } finally {
    setCheckingAuthorization(false);
  }
};
```

**Handle Post-Login Intent:**
```javascript
// Handle intent after login (check URL params)
useEffect(() => {
  const handleIntent = async () => {
    const intent = searchParams.get('intent');

    if (intent && isAuthenticated && !loading) {
      // Clear intent from URL
      searchParams.delete('intent');
      setSearchParams(searchParams, { replace: true });

      // Check authorization before opening modal
      const authorized = await checkUserAuthorization();
      if (!authorized) {
        return;
      }

      // Open the intended modal
      if (intent === 'dm') {
        setShowCampaignManager(true);
      } else if (intent === 'player') {
        setShowPlayerSessionModal(true);
      }
    }
  };

  handleIntent();
}, [searchParams, isAuthenticated, loading]);
```

**Add Loading State for Auth Check:**
```javascript
// Show loading spinner while checking authorization
{checkingAuthorization && (
  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
    <div className="bg-gaia-light rounded-lg p-6">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gaia-accent mx-auto"></div>
      <p className="text-white mt-4">Checking access...</p>
    </div>
  </div>
)}
```

**Add Registration Flow:**
```javascript
// Show registration flow if needed
{showRegistration && (
  <RegistrationFlow
    onComplete={() => {
      setShowRegistration(false);
      // After registration, they can try the action again
    }}
  />
)}
```

---

### 3. Auth0Context.jsx (No changes needed)

The existing `useAuth()` hook already supports:
- ✅ `isAuthenticated` - boolean
- ✅ `loading` - boolean
- ✅ `user` - user object (or null)
- ✅ `login(options)` - trigger login with returnTo
- ✅ `getAccessTokenSilently()` - get token for API calls

---

## Benefits

✅ **Public Landing Page** - SEO friendly, sharable, no login wall
✅ **Progressive Authentication** - Only require login when needed
✅ **Intent Preservation** - User's choice (DM/Player) is remembered through login
✅ **Whitelist Enforcement** - Still checks authorization before granting access
✅ **Smooth UX** - No jarring redirects, clear loading states
✅ **Backward Compatible** - Dev mode (no Auth0) continues to work

---

## Testing Checklist

### Dev Mode (no Auth0)
- [ ] Visit `/` - see landing page
- [ ] Click "Dungeon Master" - modal opens immediately
- [ ] Click "Adventurer" - modal opens immediately

### Production Mode (Auth0)

**Unauthenticated User:**
- [ ] Visit `/` - see landing page (no login prompt)
- [ ] Click "Dungeon Master" - redirected to Auth0 login
- [ ] After login - returned to `/`, DM modal auto-opens
- [ ] Click "Adventurer" - redirected to Auth0 login
- [ ] After login - returned to `/`, Player modal auto-opens

**Authenticated + Whitelisted User:**
- [ ] Visit `/` - see landing page
- [ ] Click "Dungeon Master" - modal opens immediately
- [ ] Click "Adventurer" - modal opens immediately

**Authenticated but NOT Whitelisted:**
- [ ] Visit `/` - see landing page
- [ ] Click "Dungeon Master" - see RegistrationFlow
- [ ] Complete registration - can now open modals
- [ ] Click "Adventurer" - see RegistrationFlow if still pending

**Edge Cases:**
- [ ] Visit `/?intent=dm` while logged in - DM modal auto-opens
- [ ] Visit `/?intent=player` while logged in - Player modal auto-opens
- [ ] Visit `/?intent=dm` while logged out - redirected to login, then modal opens
- [ ] Invalid intent value - ignored gracefully

---

## Security Considerations

🔒 **No Security Regression:**
- Landing page is public, but contains no sensitive data
- All modals require authentication (checked before opening)
- Campaign/session routes still protected with ProtectedRoute
- Whitelist checking still enforced via registration status API
- API endpoints remain protected (backend auth unchanged)

🔒 **Attack Vectors Mitigated:**
- Unauthorized users cannot access campaigns (routes protected)
- Whitelist bypass prevented (checked before modal opening)
- Token theft ineffective (backend verifies all API calls)

---

## Rollback Plan

If issues arise:
1. Revert AppWithAuth0.jsx - restore ProtectedRoute on `/` route
2. Revert WelcomePage.jsx - remove auth check logic
3. System returns to previous behavior (login required for landing page)

---

## Open Questions

1. **Should we add a "Sign In" button to the landing page header?**
   - Pro: Allows users to pre-authenticate before clicking DM/Player
   - Con: Might confuse users (why sign in if I haven't chosen a role?)

2. **Should we show user info in header if already logged in?**
   - Pro: User sees they're logged in
   - Con: Might be confusing on a "public" landing page

3. **Should invite tokens (`?invite=xyz`) work for unauthenticated users?**
   - Currently: Invite token processing requires auth (WelcomePage calls API)
   - Option: Save invite token, trigger login, process after auth

---

## Next Steps

1. Review this plan with team
2. Implement changes in order (AppWithAuth0 → WelcomePage)
3. Test in dev mode (no Auth0)
4. Test in staging with Auth0 enabled
5. Deploy to production
