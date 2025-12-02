# Game Room System - Revised Implementation Plan
## Table of Contents

1. [Background & Goals](#1-background--goals)
2. [Current State](#2-current-state)
3. [Desired State & Features](#3-desired-state--features)
4. [User Flows](#4-user-flows)
5. [Data Model](#5-data-model)
6. [Migrations](#6-migrations)
7. [Backend Architecture](#7-backend-architecture)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Development Phases](#9-development-phases)
10. [Testing Strategy](#10-testing-strategy)

refer to game-room-revised-migration.md for sections 5 and 6
refer to game-room-revised-code.md for sections 7 and 8

In this document:
1. [Background & Goals](#1-background--goals)
2. [Current State](#2-current-state)
3. [Desired State & Features](#3-desired-state--features)
4. [User Flows](#4-user-flows)
9. [Development Phases](#9-development-phases)
10. [Testing Strategy](#10-testing-strategy)

---

## 1. Background & Goals

### Overview

The game room system transforms Gaia from single-DM sessions into structured multiplayer campaigns with:
- **Persistent seat assignments** - Players claim seats that persist across sessions
- **Character-to-seat binding** - Characters belong to seats, allowing player rotation
- **DM-driven sessions** - Only campaign owners can run sessions
- **Invite-only participation** - DMs invite specific friends to join

### Key Principles

1. **Seat-based architecture** - Characters are bound to seats, not players
2. **Character rotation** - Different players can occupy the same seat (and character) across sessions **via DM vacate only**
3. **Two-step claiming** - Select seat (reserve) → Create character (bind)
4. **Invite-only model** - Small groups of friends, no race conditions
5. **DM-controlled seats** - Only DM can vacate occupied seats; players cannot take over each other's seats directly

### Design Constraints

- **Production-ready** - Safe migrations for existing databases
- **Multi-environment** - Works for dev, staging, production
- **Feature-flagged** - Can be disabled via `ENABLE_GAME_ROOMS=false`
- **Backward compatible** - Existing campaigns continue working
- **No observers** - Entire observer concept deferred to future

---

## 2. Current State

### What EXISTS ✅

**Backend:**
- `CampaignSession`, `CampaignSessionMember`, `CampaignSessionInvite` tables (session ownership + invites)
- `WebSocketConnection` model tracking individual connections (player/dm type, heartbeats)
- `CampaignBroadcaster` enforcing single active DM connection
- `CharacterManager` creating characters with string-based IDs
- REST API for session creation/sharing, invite consumption, connected player tracking

**Frontend:**
- DM view at `/:sessionId/dm` (GameDashboard.jsx)
- Player view at `/:sessionId/player` (PlayerPage.jsx)
- `CampaignSetup.jsx` wizard with character slots system (1-8 players, optional pre-creation)
- `PlayerSessionModal.jsx` listing joinable campaigns
- `WelcomePage.jsx` with DM/Adventurer options + Auth0 login

### What is MISSING ❌

- **No seat tables** - `room_seats` table doesn't exist
- **No room state** - Campaign sessions lack seat configuration columns
- **No seat APIs** - `/api/v2/rooms/*` routes don't exist
- **No seat-to-character binding** - Characters not permanently assigned to seats
- **No DM ownership validation** - CampaignBroadcaster doesn't validate DM user_id
- **No seat-aware WebSocket events** - No `room.seat_updated`, `room.dm_joined`, `room.dm_left`
- **No seat UI components** - SeatSelectionModal, RoomStatusPanel, RoomManagementDrawer don't exist
- **No persistent seat management** - CampaignSetup slots only used during wizard

---

## 3. Desired State & Features

### Core Features

#### 3.1 Seat Management

**DM Flow:**
- DM creates campaign, selects player count (1-8 seats)
- DM can see which seats are occupied, by whom, and their online status
- DM can vacate any player seat, freeing it for others
- DM must occupy DM seat to advance campaign (controls are disabled otherwise)
- DM can invite specific players to campaign

**Player Flow:**
- Invited player opens campaign, sees seat grid
- Player **selects available seat** → seat reserved for them (owner_user_id set)
- Player **creates character** → character bound to seat (character_id set, immutable)
- Player can **claim seat with existing character** → occupy seat and play as that character
- Player disconnects → seat remains theirs (shows offline)
- Player reconnects → auto-occupies their seat

**Character Rotation:**
- Characters belong to **seats**, not players
- Seat 1 has character "Gaius"
- Session 1: Bob occupies Seat 1, plays as Gaius
- Session 2: Bob doesn't join, Alice occupies Seat 1, plays as Gaius
- Character persists on seat across different players

#### 3.2 DM Presence Enforcement

- Campaign only advances when DM occupies DM seat
- DM view shows "Join as DM" button if not seated
- Player actions are rejected server-side if DM not present (chat endpoint, turn advancement, suggestion queue)
- `CampaignBroadcaster` refuses DM socket connections unless `user_id == campaign.owner_user_id`
- WebSocket broadcasts DM join/leave events so both clients and backend checks stay in sync

#### 3.3 Invite-Only Model

- Only players in `campaign_session_members` can occupy seats
- DM generates invite links for specific people
- No anonymous access, no race conditions (small trusted groups)

#### 3.4 Vacate = Seat Reset

- DM can vacate any seat (clears `owner_user_id`)
- Character remains on seat (available for next player)
- Not a ban - vacated player can immediately rejoin and pick a seat
- No reason tracking (friends playing together)

#### 3.5 Session Discovery (Pre-Join Status)

- Player lobby (PlayerSessionModal) shows **seat counts and DM online state** before launching the room
- API supplies `filledSeats`, `maxSeats`, and `room_status` per campaign
- Users with a claimed seat see “Resume as {Character}” instead of generic “Join”
- If the room is full (all seats have owners), discovery surfaces that state so players avoid loading a locked room

---

## 4. User Flows

### 4.1 DM Creates Campaign

```
1. DM opens CampaignSetup wizard
2. DM selects player count (e.g., 4 seats)
3. DM optionally pre-creates characters for some/all seats
4. DM clicks "Create Campaign"

Backend:
- Creates campaign JSON
- Sets campaign_sessions.max_player_seats = 4
- Creates 1 DM seat (seat_type='dm', slot_index=NULL)
- Creates 4 player seats (seat_type='player', slot_index=0..3)
- If pre-created characters exist:
  - Sets room_seats.character_id for each slot
  - Leaves owner_user_id = NULL (available for claiming)

Result:
- DM lands on GameDashboard
- Sees "Join as DM" button
- Sees 4 empty seats (or seats with pre-created characters)
```

### 4.2 DM Invites Players

```
1. DM clicks "Invite Players" in RoomManagementDrawer
2. DM enters emails: alice@example.com, bob@example.com, carol@example.com, dave@example.com
3. Backend creates campaign_session_members rows
4. Backend generates invite link
5. DM shares link with friends

Result:
- 4 players receive invite links
- Each link contains campaign_id + invite token
- Player lobby card now shows "0/4 seats filled • ⚪ Waiting for DM"
```

### 4.3 Player Checks Seat Availability

```
1. Player opens Welcome page and PlayerSessionModal
2. Modal calls GET /api/v2/rooms/{campaign_id}/summary for each campaign
3. Card shows:
   - Seat usage: "1 / 4 seats" (claimed owners)
   - DM status: "● DM Online" if room_status='active'
   - Resume CTA if player already occupies a seat
4. If room is full, CTA shows "Room Full" and the player cannot launch PlayerPage
```

Result:
- Players know whether they can join before loading the heavy Player view
- Returning users jump straight to their seat using the Resume CTA

### 4.4 Player Joins & Selects Seat

```
1. Player Alice clicks invite link
2. Authenticates via Auth0
3. Backend validates:
   - Alice is in campaign_session_members
   - Invite is valid
4. Redirects to PlayerPage

Frontend:
- Fetches GET /api/v2/rooms/{campaign_id}
- Shows SeatSelectionModal with seat grid:

  ┌─────────────────────┐
  │ Seat 1: Available   │  ← Empty seat, no character
  │ [Select Seat]       │
  └─────────────────────┘

  ┌─────────────────────┐
  │ Seat 2: Gaius       │  ← Has character, no owner
  │ Available           │
  │ [Occupy Seat]       │
  └─────────────────────┘

  ┌─────────────────────┐
  │ Seat 3: Thalia      │  ← Bob playing, online
  │ (Bob) ● Online      │
  │ [Unavailable]       │
  └─────────────────────┘

  ┌─────────────────────┐
  │ Seat 4: Reserved    │  ← Carol claimed, creating character
  │ by Carol            │
  │ [Unavailable]       │
  └─────────────────────┘

5. Alice clicks "Occupy Seat 2" (has character "Gaius")

Backend:
- POST /api/v2/rooms/{campaign_id}/seats/{seat_2}/occupy
- Sets room_seats[seat_2].owner_user_id = "alice_456"
- Broadcasts room.seat_updated WebSocket event

Result:
- Alice now occupies Seat 2
- SeatSelectionModal disables other seat buttons for Alice until she explicitly clicks "Switch Seat" (which releases Seat 2 first), ensuring a player can only hold one seat at a time
- Alice will play as the existing character "Gaius"
- Other players see "Seat 2: Gaius (Alice) ● Online"
```

### 4.5 Player Creates New Character

```
1. Player Dave clicks "Select Seat 1" (empty seat)

Backend:
- POST /api/v2/rooms/{campaign_id}/seats/{seat_1}/occupy
- Sets room_seats[seat_1].owner_user_id = "dave_789"
- Broadcasts room.seat_updated

Frontend:
- Other players see "Seat 1: Reserved by Dave"
- Dave sees CharacterAssignmentModal

2. Dave fills character creation form:
   - Name: Ragnar
   - Race: Dwarf
   - Class: Cleric
   - Background: Acolyte
   - Appearance: Scarred face, grey beard
   - Personality: Gruff but loyal

3. Dave clicks "Create Character"

Backend:
- POST /api/v2/rooms/{campaign_id}/seats/{seat_1}/assign-character
- **Authorization**: Validates requester is seat owner OR campaign DM ✓
- Creates character via CharacterManager
- Sets room_seats[seat_1].character_id = "char_ragnar" (immutable!)
- Broadcasts room.seat_updated

Result:
- Seat 1 now has character "Ragnar" owned by Dave
- Other players see "Seat 1: Ragnar (Dave) ● Online"
- Character "Ragnar" is permanently bound to Seat 1
```

### 4.6 Player Disconnects & Reconnects

```
1. Alice (playing Gaius in Seat 2) closes browser

Backend:
- WebSocket disconnect event
- Updates websocket_connections.status = 'disconnected'
- room_seats[seat_2].owner_user_id remains "alice_456" (persists!)

Frontend (other players):
- See "Seat 2: Gaius (Alice) ○ Offline"

2. Alice reopens browser, navigates to campaign

Backend:
- GET /api/v2/rooms/{campaign_id}
- Finds seat where owner_user_id = "alice_456"
- Returns Seat 2 (her seat)

Frontend:
- PlayerPage auto-connects to Seat 2
- No seat selection modal (already has seat)
- Opens WebSocket connection

Backend:
- Creates websocket_connections row
- Sets seat_id = seat_2, connection_type = 'player'

Result:
- Alice back in Seat 2 playing as Gaius
- Other players see "Seat 2: Gaius (Alice) ● Online"
```

### 4.7 Character Rotation Between Sessions

```
Session 1:
- Bob occupies Seat 3, character "Thalia" exists
- room_seats[seat_3]: owner_user_id="bob_123", character_id="char_thalia"
- Campaign runs, Bob plays as Thalia

Session 2 (next week):
- Bob doesn't join
- Seat shows "Seat 3: Thalia (Bob) ○ Offline"

Alice wants to play Thalia:
**IMPORTANT: Only DM can vacate seats. Players cannot take over occupied seats directly.**

1. DM vacates Seat 3 (to allow character rotation)

Backend (DM vacates):
- POST /api/v2/rooms/{campaign_id}/seats/{seat_3}/vacate
- Validates: requester is campaign owner (DM) ✓
- Stores previous_owner = "bob_123"
- Sets room_seats[seat_3].owner_user_id = null
- character_id remains "char_thalia" (character persists!)
- Broadcasts room.seat_updated with previous_owner

2. Alice clicks "Occupy Seat 3" (now vacant)

Backend (Alice occupies):
- POST /api/v2/rooms/{campaign_id}/seats/{seat_3}/occupy
- Validates: Alice is invited player ✓
- Validates: Seat is vacant (owner_user_id = null) ✓
- Sets room_seats[seat_3].owner_user_id = "alice_456"
- character_id remains "char_thalia" (unchanged!)
- Broadcasts room.seat_updated

Result:
- Alice now occupies Seat 3
- Alice plays as Thalia this session
- Other players see "Seat 3: Thalia (Alice) ● Online"
- Campaign continues with Thalia (now controlled by Alice)

Session 3:
- Bob returns, sees Seat 3 occupied by Alice
- Bob picks different available seat
- OR: DM vacates Seat 3 again, Bob reclaims it and plays as Thalia
```

### 4.8 DM Vacates Seat (Vacate)

```
1. DM opens RoomManagementDrawer
2. DM sees seat table:

| Seat | Character | Player | Status  | Actions |
|------|-----------|--------|---------|---------|
| 1    | Ragnar    | Dave   | Online  | [Vacate]|
| 2    | Gaius     | Alice  | Online  | [Vacate]|
| 3    | Thalia    | Bob    | Offline | [Vacate]|
| 4    | (empty)   | -      | Avail.  | -       |

3. DM clicks "Vacate" on Seat 2 (Alice)

Backend:
- POST /api/v2/rooms/{campaign_id}/seats/{seat_2}/vacate
- Captures previous owner_user_id before clearing
- Sets room_seats[seat_2].owner_user_id = NULL
- character_id remains "char_gaius" (unchanged!)
- Closes Alice's WebSocket connection
- Broadcasts room.seat_updated + room.player_vacated { seat_id, previous_owner }

Frontend (Alice):
- Sees "You have been removed from your seat" modal (driven by `room.player_vacated` event payload)
- Redirected to seat selection

Frontend (Others):
- See "Seat 2: Gaius - Available"

Result:
- Seat 2 freed, character "Gaius" still exists on seat
- Any invited player can now occupy Seat 2 and play as Gaius
- Alice can pick a different available seat
```

### 4.9 DM Joins DM Seat

```
1. DM opens GameDashboard
2. Sees DMAbsenceBanner: "⚠️ You must occupy the DM seat to run the game"
3. All controls disabled (chat input, turn advancement, dice roller)
4. DM clicks "Join as DM" button

Backend:
- POST /api/v2/rooms/{campaign_id}/seats/{dm_seat_id}/occupy
- Validates user_id == campaign_sessions.owner_user_id
- Sets campaign_sessions.dm_joined_at = now()
- Sets campaign_sessions.dm_connection_id = connection_id
- Sets campaign_sessions.room_status = 'active'
- Broadcasts room.dm_joined

Frontend:
- DMAbsenceBanner disappears
- Controls enabled (room management only)
- Players see "DM Online" status

Result:
- DM is seated and can manage the room
- DM can see "Start Campaign" button (if seats filled)
- Game controls still disabled until campaign starts
```

### 4.10 DM Starts Campaign

**Prerequisite:** Minimum seats must have characters assigned (configurable, default 1)

```
1. DM is seated, sees GameDashboard
2. Sees seat status panel showing which seats have characters
3. Once minimum seats filled with characters, "Start Campaign" button becomes enabled
4. DM clicks "Start Campaign" (minimum gate = ≥1 seat with character; DM decides when party is ready even if not full)

Backend:
- POST /api/v2/rooms/{campaign_id}/start
- Validates:
  - User is campaign owner
  - DM is seated (dm_connection_id exists)
  - Minimum seats have characters (default: at least 1 player seat)
- Loads campaign metadata (title, description, setting, theme, NPCs, quests) saved during campaign creation
- Loads all character data from room_seats
- Builds initial prompt with campaign metadata + characters
- Triggers first turn generation asynchronously (non-blocking)
  - Orchestrator sends initial prompt to DM agent
  - LLM generates opening narrative with full context
  - Opening scene, dynamic NPCs, and world state created by LLM
  - Result broadcast via WebSocket when ready
- Sets campaign_sessions.campaign_status = 'active'
- Sets campaign_sessions.started_at = now()
- Broadcasts room.campaign_started event

Frontend (DM):
- "Start Campaign" button disappears
- Loading spinner shows "Generating campaign..."
- Once complete, initial narrative displays
- Game controls become fully active
- Turn advancement enabled
- Chat/action processing enabled

Frontend (Players):
- See "Campaign starting..." notification
- Initial narrative displays when ready
- Action input becomes available
- Game begins

Result:
- Campaign content generated with actual player-created characters
- Initial scene, NPCs, and world state created
- Game is ready for first turn
- All players can see narrative and take actions
```

**Key Architectural Change:**

Campaign metadata and character creation are fully decoupled:
- **Step 1 (DM creates campaign)**: Save campaign metadata (title, description, setting, theme, NPCs, quests) - no characters needed
- **Step 2 (Players join)**: Players create characters in their seats independently
- **Step 3 (DM starts)**: Build initial prompt from saved metadata + characters → LLM generates opening narrative

This allows:
- Players control their own character creation
- DM doesn't pre-create characters in wizard (optional)
- Campaign metadata defined before characters exist
- LLM generates opening narrative with full context (campaign + characters)
- Supports character rotation (different players, same campaign)
- Characters can be added/changed before campaign starts
- Uses existing campaign generation flow (no new generators needed)

---

## 9. Development Phases

### Phase 0: Schema & Infrastructure (Week 1-2)

**Goal:** Database foundation without breaking existing functionality

**Backend:**
- [ ] Create migration 16 (tables + columns)
- [ ] Create migration 17 (backfill script with --dry-run)
- [ ] Extend `session_models.py` with `RoomSeat` model
- [ ] Update `SessionRegistry._init_db()` bootstrap
- [ ] Create `RoomService` with all methods
- [ ] Add `ENABLE_GAME_ROOMS` feature flag
- [ ] Unit tests for `RoomService`

**Testing:**
- [ ] Run migrations on dev database
- [ ] Verify backfill creates correct seats
- [ ] Verify existing campaigns unaffected

**Deliverable:** Database schema ready, feature flagged off

---

### Phase 1: DM Presence & Seat APIs (Week 3-4)

**Goal:** DM must occupy seat, basic seat operations, campaign generation decoupled

**Backend:**
- [ ] Create `room_routes.py` with 7 endpoints (including `/start`)
- [ ] Mount routes in `main.py`
- [ ] Update `CampaignBroadcaster`:
  - [ ] `connect_dm()` - validate ownership, set room_status
  - [ ] `disconnect_dm()` - clear room_status
  - [ ] Broadcast `room.dm_joined`, `room.dm_left`, `room.campaign_started`
- [ ] Update `CampaignService`:
  - [ ] Implement `start_campaign_from_seats()` - loads campaign metadata + characters
  - [ ] Build initial prompt with both campaign_info and characters
  - [ ] Trigger first turn generation (uses existing orchestrator flow)
- [ ] Update `create_campaign()`:
  - [ ] Persist world_settings (campaign metadata) during campaign creation
  - [ ] Support pre-generated or custom campaign metadata (theme, NPCs, quests)

**Frontend:**
- [ ] Add `roomApi` to apiService.js (including `startCampaign()`)
- [ ] Create `DMAbsenceBanner.jsx`
- [ ] Update `GameDashboard.jsx`:
  - [ ] Show banner if DM not seated
  - [ ] Conditional rendering based on `campaign_status`
  - [ ] "Join as DM" button
  - [ ] "Start Campaign" button with seat status display
  - [ ] Loading state during campaign generation

**Testing:**
- [ ] DM can't advance game without seating
- [ ] DM joins → room controls enabled
- [ ] Campaign wizard creates structure only (no content)
- [ ] "Start Campaign" button disabled until seats filled
- [ ] "Start Campaign" triggers content generation
- [ ] Player sees DM status updates

**Deliverable:** DM gating + campaign generation decoupling functional

---

### Phase 2: Player Seats & Character Creation (Week 5-7)

**Goal:** Players can claim seats, create characters, character rotation works

**Backend:**
- [ ] Extend `occupy_seat()` for player seats
- [ ] Implement `assign_character_to_seat()` with CharacterManager integration
- [ ] Broadcast `room.seat_updated` on all seat changes
- [ ] Update `connect_player()` to find user's seat

**Frontend:**
- [ ] Create `SeatSelectionModal.jsx`
- [ ] Create `CharacterAssignmentModal.jsx`
- [ ] Update `PlayerPage.jsx`:
  - [ ] Show seat selection if no seat
  - [ ] Show character creation if no character
  - [ ] Load character from seat
- [ ] Create `RoomStatusPanel.jsx` (DM dashboard)
- [ ] Create `RoomManagementDrawer.jsx` (DM seat management)
- [ ] Subscribe to WebSocket events in both views
- [ ] Update `PlayerSessionModal.jsx` with seat counts + DM status (uses `/summary`)

**Testing:**
- [ ] Player selects seat → reserved
- [ ] Player creates character → bound to seat
- [ ] Player disconnects → seat stays theirs
- [ ] Different player occupies seat with character (rotation)
- [ ] DM vacates player → seat freed

**Deliverable:** Full seat system functional

---

### Phase 3: Polish & QA (Week 8-9)

**Goal:** Production-ready, tested, documented

**Backend:**
- [ ] Integration tests for seat lifecycle
- [ ] Load test (4 players + DM, concurrent seat changes)
- [ ] Security audit (authorization checks)
- [ ] Error handling improvements

**Frontend:**
- [ ] UI polish (loading states, error messages)
- [ ] Optimistic updates for seat actions
- [ ] Keyboard navigation
- [ ] Accessibility audit

**Documentation:**
- [ ] Manual test plan (`docs/manual_testing_game_rooms.md`)
- [ ] API documentation
- [ ] User guide for DMs

**Deployment:**
- [ ] Run migrations on staging
- [ ] Test with real campaigns
- [ ] Enable `ENABLE_GAME_ROOMS=true` on production
- [ ] Monitor metrics

**Deliverable:** Feature shipped to production

---

## 10. Testing Strategy

### 10.1 Unit Tests

**File:** `backend/test/core/session/test_room_service.py`

```python
def test_create_room():
    """Test room creation creates seats."""
    service = RoomService(db)
    service.create_room("campaign_123", "dm_user", max_player_seats=4)

    seats = db.query(RoomSeat).filter_by(campaign_id="campaign_123").all()
    assert len(seats) == 5  # 1 DM + 4 player
    assert seats[0].seat_type == 'dm'

def test_occupy_seat():
    """Test seat occupation."""
    seat = create_test_seat()
    service.occupy_seat(seat.seat_id, "player_123")

    updated = db.query(RoomSeat).get(seat.seat_id)
    assert updated.owner_user_id == "player_123"

def test_character_rotation():
    """Test different players can occupy same seat."""
    seat = create_test_seat(character_id="char_gaius", owner_user_id="bob")

    # Alice occupies Bob's seat
    service.occupy_seat(seat.seat_id, "alice")

    updated = db.query(RoomSeat).get(seat.seat_id)
    assert updated.owner_user_id == "alice"
    assert updated.character_id == "char_gaius"  # Character unchanged

def test_character_immutability():
    """Test character_id cannot be changed once set."""
    seat = create_test_seat(character_id="char_gaius")

    with pytest.raises(ValueError):
        service.assign_character_to_seat(seat.seat_id, {"name": "Ragnar"})
```

### 10.2 Integration Tests

**File:** `backend/test/integration/test_room_flow.py`

```python
def test_full_player_flow():
    """Test complete player journey."""
    # Setup
    campaign = create_test_campaign()
    invite_player(campaign.session_id, "alice@example.com")

    # Player joins
    client = TestClient(app)
    state = client.get(f"/api/v2/rooms/{campaign.session_id}").json()
    assert len(state['seats']) == 5

    # Player occupies seat
    seat_1 = state['seats'][1]  # First player seat
    client.post(f"/api/v2/rooms/{campaign.session_id}/seats/{seat_1['seat_id']}/occupy")

    # Player creates character
    client.post(
        f"/api/v2/rooms/{campaign.session_id}/seats/{seat_1['seat_id']}/assign-character",
        json={"character_data": {"name": "Gaius", "race": "Human", "class": "Warrior"}}
    )

    # Verify state
    state = client.get(f"/api/v2/rooms/{campaign.session_id}").json()
    seat_1 = next(s for s in state['seats'] if s['slot_index'] == 0)
    assert seat_1['character_name'] == "Gaius"
    assert seat_1['owner_user_id'] == "alice_123"
```

### 10.3 Manual Test Plan

**File:** `docs/manual_testing_game_rooms.md`

```markdown
# Game Room Manual Test Plan

## Test 1: DM Creates Campaign
1. Login as DM
2. Click "Create New Campaign"
3. Set player count to 4
4. Create campaign
5. ✓ Verify 4 empty seats visible
6. ✓ Verify "Join as DM" button shown
7. ✓ Verify controls disabled

## Test 2: DM Joins DM Seat
1. Click "Join as DM"
2. ✓ Verify banner disappears
3. ✓ Verify controls enabled
4. ✓ Verify "DM Online" status

## Test 3: Player Claims Seat
1. Login as Player (different user)
2. Click invite link
3. ✓ Verify seat selection modal shown
4. Click "Select Seat 1"
5. ✓ Verify character creation modal shown
6. Fill form, submit
7. ✓ Verify character created
8. ✓ Verify DM sees "Seat 1: [Character] (Player) ● Online"

## Test 4: Character Rotation
1. Player 1 creates character "Gaius" on Seat 1
2. Player 1 disconnects
3. Player 2 clicks "Occupy Seat 1"
4. ✓ Verify Player 2 now plays as Gaius
5. ✓ Verify DM sees "Seat 1: Gaius (Player 2) ● Online"

## Test 5: DM Vacates Player Seat
1. DM opens Room Management
2. DM clicks "Vacate" on Seat 1
3. ✓ Verify player vacated
4. ✓ Verify Seat 1 shows "Gaius - Available"
5. ✓ Verify character still exists on seat
```
