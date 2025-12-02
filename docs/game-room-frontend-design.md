# Game Room System - Frontend Design

## Overview

This document defines the user experience, architecture, and design patterns for the Game Room frontend. The backend provides complete room/seat management APIs, WebSocket events, and database models. The frontend must now deliver intuitive interfaces for both DMs and Players.

### Goals

- **For DMs**: Room management, seat monitoring, player invites, campaign starting
- **For Players**: Seat selection, character creation, session discovery, reconnection handling
- **Real-time**: All users see updates instantly via WebSocket events
- **Resilient**: Handle disconnections, race conditions, and edge cases gracefully

---

## State Management Architecture

### Centralized Room State

We'll use React Context to manage a global `roomState` object - the single source of truth for each campaign room.

**TypeScript Interface:**

```typescript
interface RoomState {
  // Room metadata
  campaignId: string;
  ownerId: string;
  maxPlayerSeats: number;
  roomStatus: 'waiting_for_dm' | 'active' | 'paused';
  campaignStatus: 'setup' | 'active' | 'completed';
  dmJoinedAt: string | null;

  // Seats
  seats: Seat[];

  // Invited players
  invitedPlayers: Array<{
    userId: string;
    email: string;
  }>;
}

interface Seat {
  seatId: string;
  slotIndex: number | null;  // null for DM seat, 0-7 for player seats
  seatType: 'dm' | 'player';

  // Ownership
  ownerUserId: string | null;
  ownerDisplayName: string | null;
  ownerEmail: string | null;

  // Character
  characterId: string | null;
  characterName: string | null;
  characterAvatarUrl: string | null;

  // Derived state
  status: 'available' | 'claimed' | 'occupied';
  online: boolean;
}
```

**Derived Getters (computed from seats):**

```typescript
const playerSeats = seats.filter(s => s.seatType === 'player');
const dmSeat = seats.find(s => s.seatType === 'dm');
const isDMSeated = dmSeat?.ownerUserId !== null;
const filledSeats = seats.filter(s => s.ownerUserId !== null).length;
const seatsWithCharacters = seats.filter(s => s.characterId !== null).length;
const canStartCampaign = isDMSeated && seatsWithCharacters > 0;
```

### WebSocket Event Handling

A single persistent WebSocket connection per user listens for events and updates the central roomState.

**Event Behaviors:**

- **`room.dm_joined`**: Set `roomStatus` to `'active'`, update DM seat to online
- **`room.dm_left`**: Set `roomStatus` to `'waiting_for_dm'`, update DM seat to offline
- **`room.seat_updated`**: Merge-patch the updated seat into the seats array (optimistic update)
- **`room.player_vacated`**: If current user is `previous_owner`, show notification modal and reset to seat selection
- **`room.campaign_started`**: Set `campaignStatus` to `'active'`, hide setup UI, show game interface

**Update Strategy:**
- Use **merge patch** for seat updates (only update changed seat, not full refetch)
- Fall back to full refetch if seat ID mismatch detected
- Optimistic UI updates for seat operations (revert on error)

---

## Component Hierarchy

```
App
├── WelcomePage
│   ├── DMCampaignModal (enhanced with room status)
│   └── PlayerSessionModal (enhanced with seat counts)
│
├── GameDashboard (DM View)
│   ├── DMAbsenceBanner (when DM not seated)
│   ├── RoomManagementButton
│   ├── RoomManagementDrawer
│   │   ├── SeatGrid
│   │   ├── SeatFilters (All/Available/Occupied/Offline)
│   │   ├── InvitePlayersSection
│   │   └── StartCampaignButton
│   ├── TurnView
│   ├── CombatStatusView
│   └── PlayerAndTurnList
│
├── PlayerPage (Player View)
│   ├── SeatSelectionModal
│   │   └── SeatCard (multiple)
│   ├── CharacterAssignmentModal
│   ├── PlayerVacatedModal
│   └── PlayerView
│       ├── StreamingNarrativeView
│       └── ChatInterface
│
└── CampaignSetup (Wizard)
    ├── CampaignBasicsStep
    ├── PlayerConfigurationStep (just select seat count)
    ├── WorldBuildingStep (optional)
    ├── OptionalCharacterPreCreationStep (optional)
    └── ReviewStep

---

## Welcome Page Adventurer Flow

When a player lands on the WelcomePage they pick between **DM** and **Adventurer** roles. Clicking **Adventurer** opens the `PlayerSessionModal`, which now renders a full list of joinable sessions pulled from the backend `room_sessions_view`. The modal uses the same layout on desktop and mobile (sheet on smaller screens) so the entry point into the player experience is predictable.

### Data Requirements

The modal issues `GET /api/room-sessions?role=adventurer` which is backed by the `room_sessions_view`. We only show sessions the user has been invited to plus any public sessions they can access. Each item is normalized into a `PlayerSessionSummary` object so the UI can remain presentation-only:

```typescript
interface PlayerSessionSummary {
  sessionId: string;
  campaignName: string;
  campaignStatus: 'setup' | 'active' | 'completed';
  dmOnline: boolean;              // derived from dm seat online flag
  filledSeats: number;            // count of seats with ownerUserId
  maxSeats: number;               // max player seats for campaign
  lastPlayedAt: string | null;    // optional "Last played" badge
  invitationType: 'direct' | 'open';
  resumeCharacterName?: string;   // if this user already owns a seat
}
```

### Session List UX

- Sessions are grouped by **Invited Sessions** (direct invites) and **Other Joinable Sessions** (public ones where `filledSeats < maxSeats`).
- Each card shows:
  - Campaign name + status pill (`campaignStatus`).
  - DM presence indicator (`● DM Online` / `○ DM Offline` rendered from `dmOnline`).
  - Seat fill summary using `filledSeats/maxSeats` (e.g., `2 / 4 seats`).
  - Optional `Resume as {resumeCharacterName}` CTA if `resumeCharacterName` exists, otherwise `Join` / `Preview` CTA.
  - "Last played X ago" string formatted from `lastPlayedAt`.
- Filter tabs (Joinable / Waiting for DM / Full) run client-side using `campaignStatus`, `dmOnline`, and seat counts so the player can quickly find an available table.
- Whenever the modal opens we refresh the summaries and subscribe to room summary WebSocket events so seat counts and DM presence stay in sync without requiring the player to back out and re-open the modal.
```

---

## Component Design Patterns

### Seat Component - 5 States

The `Seat` component renders differently based on seat state:

**State 1: Available (Empty)**
- Conditions: `ownerUserId === null`, `characterId === null`
- Display: "Seat X: Available", "[Select Seat]" button

**State 2: Available (With Character)**
- Conditions: `ownerUserId === null`, `characterId !== null`
- Display: Character avatar, "Seat X: {characterName}", "Available", "[Occupy Seat]" button

**State 3: Reserved (Creating Character)**
- Conditions: `ownerUserId !== null`, `characterId === null`
- Display: "Seat X: Reserved by {playerName}", spinner badge "Creating..."

**State 4: Occupied (Online)**
- Conditions: `ownerUserId !== null`, `characterId !== null`, `online === true`
- Display: Character avatar, "Seat X: {characterName}", "({playerName}) ● Online"

**State 5: Occupied (Offline)**
- Conditions: `ownerUserId !== null`, `characterId !== null`, `online === false`
- Display: Grayscale avatar, "Seat X: {characterName}", "({playerName}) ○ Offline"

### Enhanced Features

**DM Features:**
- **Players Waiting Alert**: Campaign cards show pulsing "🚨 X Players Waiting!" badge when `roomStatus === 'waiting_for_dm'` and `filledSeats > 0`
- **Seat Filters**: Filter chips (All/Available/Occupied/Offline) in Room Management Drawer
- **Quick Copy Invite Link**: One-click clipboard copy of campaign invite URL
- **Smart Sorting**: Campaign list prioritizes "players waiting" campaigns

**Player Features:**
- **Filter Tabs**: "Joinable Now", "Waiting for DM", "Full Rooms" tabs in session modal
- **Resume CTA**: Button changes to "Resume as {CharacterName}" if player already has seat
- **Switch Seat**: Players can release current seat and pick a different one
- **Draft Restoration**: localStorage persists character form, shows "Draft restored!" on reload
- **Enhanced Error Handling**: 409 conflicts auto-refresh seat grid, 401/403 redirect to lobby

**Performance Optimizations:**
- **Room Summary Caching**: 30s TTL cache for `/summary` endpoint to avoid refetch storms
- **Optimistic Updates**: Seat occupation shows "Reserved by..." immediately (revert on error)
- **Merge Patch Strategy**: Only update changed seats, not full state refetch

---

## User Journey: DM Creates Campaign & Starts Session

**Step 1: Campaign Creation**

DM opens CampaignSetup wizard:
1. Enters campaign basics (name, description, setting, theme)
2. Selects number of player seats (1-8)
3. Optionally adds world details (NPCs, quests, locations)
4. Optionally pre-creates sample characters for some seats
5. Clicks "Create"

Backend creates:
- `campaign_sessions` row
- 1 DM seat (type='dm', owner=null)
- N player seats (type='player', slot_index=0..N-1, owner=null)
- Optional: Characters (if pre-created, assigned to seats but owner=null)

**Step 2: DM Lands on GameDashboard**

GameDashboard loads and checks if DM is seated:
- **Not seated**: Shows DMAbsenceBanner with "⚠️ You must occupy the DM seat to run the game"
- Game controls are grayed out and disabled
- "Join as DM" button is prominent
- RoomStatusPanel shows all player seats (empty initially)

**Step 3: Players Join**

While DM waits:
- **Player A** joins, sees SeatSelectionModal, selects Seat 1
- SeatSelectionModal closes, CharacterAssignmentModal opens
- Player A creates "Gaius" and a profile photo and submits
- DM's RoomStatusPanel updates in real-time: Seat 1 now shows "Gaius (Player A) ● Online" along with the character profile photo

- **Player B** joins, selects Seat 2 (which had a pre-created character)
- No character creation needed, immediately enters game
- DM's panel updates: Seat 2 shows pre-created character with Player B as owner

**Step 4: DM Joins Seat**

DM clicks "Join as DM":
- API call to `/seats/{dm_seat_id}/occupy`
- DMAbsenceBanner disappears
- RoomManagementButton becomes enabled
- "Start Campaign" button appears (enabled because `seatsWithCharacters >= 1`)

**Step 5: DM Starts Campaign**

DM clicks "Start Campaign":
- Loading overlay: "Starting Campaign... Generating the opening narrative with your characters. This may take a minute."
- Backend generates opening turn via LLM
- `room.campaign_started` WebSocket event fires
- RoomStatusPanel hides
- Main game UI appears with narrative visible
- this game can no longer support new seats being occupied once its been started. so once the game leaves the setup state and transitions to active we cannot accept new seats/characters
 
**Step 6: Campaign Active**

All players see the opening narrative:
- "The sun sets over Phandalin as you arrive. Gaius, the stalwart fighter, and Thalia, the wise wizard, stand at the inn entrance..."
- Players can now take actions via chat
- DM can advance turns and manage game

---

## User Journey: Player Joins & Reconnects

**Step 1: Session Discovery (Welcome → Adventurer)**

Player lands on WelcomePage and clicks **Adventurer**, which opens PlayerSessionModal populated with `PlayerSessionSummary` objects from `room_sessions_view`:
- Sees campaign card: "The Lost Mines of Phandelver"
- Status badges: campaign status pill ("Setup"), DM presence indicator ("● DM Online"), seat counts rendered as "3 / 4 seats"
- "Last played: Yesterday"
- Because the user was invited, the card shows `Join` (or `Resume as {Character}` if applicable)

**Step 2: Seat Selection**

PlayerPage mounts, checks if player has a seat:
- No seat found, shows SeatSelectionModal
- Modal displays 4 seat cards:
  - Seat 1: "Gaius (Alice) ● Online" - [Occupied]
  - Seat 2: "Thalia (Bob) ● Online" - [Occupied]
  - Seat 3: "Ragnar (Carol) ● Online" - [Occupied]
  - Seat 4: "Empty" - [Select Seat]
- Player clicks "Select Seat" on Seat 4

**Step 3: Character Creation**

API call to `/seats/{seat_4_id}/occupy` succeeds:
- SeatSelectionModal closes
- CharacterAssignmentModal opens
- Player creates "Elara" (Elf Ranger):
  - Name, Race, Class, Background
  - Appearance description
  - Personality traits
- Form auto-saves to localStorage on every field change
- Player submits, API call to `/seats/{seat_4_id}/assign-character`

**Step 4: Enter Game**

Character created successfully:
- CharacterAssignmentModal closes
- PlayerView loads with character data
- Shows "Waiting for DM to start campaign..."
- Other players visible: "Gaius (Alice), Thalia (Bob), Ragnar (Carol)"

**Step 5: Disconnection**

Player closes browser:
- WebSocket disconnects
- Seat 4 updates: `online` changes to `false`
- Other players see Seat 4 as "Elara (Player) ○ Offline"
- Character and seat ownership persist in database

**Step 6: Reconnection**

Player returns, opens PlayerSessionModal:
- Campaign card now shows: "Resume as Elara" button
- Clicks "Resume as Elara"
- PlayerPage mounts, finds existing seat
- No modals shown, immediately loads PlayerView
- Player is back in the game

---

## User Journey: Character Rotation

**Scenario**: Bob originally played Thalia, but can't attend next session. DM wants Alice to play Thalia instead.

**Step 1: Bob Offline**

After previous session:
- Bob disconnects
- Seat 2: "Thalia (Bob) ○ Offline"

**Step 2: DM Vacates Seat**

Next session starts, Bob doesn't join:
- DM opens RoomManagementDrawer
- Sees Seat 2: "Thalia (Bob) ○ Offline" with [Vacate] button
- DM clicks [Vacate]
- API call to `/seats/{seat_2_id}/vacate` with `notify_user: true`
- Seat 2 updates: `ownerUserId` becomes null, `characterId` remains set
- Seat 2 now: "Thalia (Available)" - character persists, no owner

**Step 3: Alice Switches Seats**

Alice currently in Seat 1 (Gaius):
- Alice wants to play Thalia
- Opens SeatSelectionModal (via "Switch Seat" button)
- Sees Seat 2: "Thalia (Available)" with [Occupy Seat] button
- Clicks [Occupy Seat]
- API releases Seat 1, occupies Seat 2
- Seat 1: "Gaius (Available)" - character persists, no owner
- Seat 2: "Thalia (Alice) ● Online" - Alice now owns Thalia

**Step 4: Continue Game**

Campaign continues with Alice playing Thalia:
- All of Thalia's progress/inventory persists
- Alice sees Thalia's character sheet
- Other players see "Thalia (Alice) ● Online"

---

## Feature Requirements Summary

### DM Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Campaign Creation Wizard | Simplified to select seat count, no forced character creation | P0 |
| DM Absence Banner | Warning when DM not seated, controls disabled | P0 |
| Room Management Drawer | View all seats, vacate players, invite, start campaign | P0 |
| Players Waiting Alert | Highlight campaigns with players in lobby | P1 |
| Seat Filters | Filter by All/Available/Occupied/Offline | P1 |
| Quick Copy Invite Link | One-click clipboard copy | P2 |

### Player Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Session Discovery | Welcome→Adventurer modal backed by `room_sessions_view`, shows campaign status, DM online, and seat counts | P0 |
| Seat Selection | Visual grid of available/occupied seats | P0 |
| Character Creation | Form to create character for claimed seat | P0 |
| Auto-Reconnection | Resume game with existing seat/character | P0 |
| Filter Tabs | Joinable/Waiting/Full room filters | P1 |
| Switch Seat | Release current seat and pick another | P1 |
| Draft Restoration | localStorage persists character form progress | P2 |

### Shared Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Real-time Updates | WebSocket events for seat/room changes | P0 |
| Optimistic UI | Immediate feedback, revert on error | P1 |
| Enhanced Error Handling | 409 auto-refresh, 401/403 redirect | P1 |
| Merge Patch Updates | Only update changed seats, not full refetch | P1 |
| Room Summary Caching | 30s TTL to prevent refetch storms | P1 |

---

## Implementation Phases

### Phase 1: Core DM Experience (Week 1-2)

**Goal**: DM can create rooms, join seat, manage players, start campaigns

**Deliverables**:
- Simplified CampaignSetup wizard (seat count only)
- DMAbsenceBanner component
- RoomManagementDrawer with seat grid
- "Start Campaign" button with validation
- RoomContext provider with WebSocket integration
- DM can see room status in campaign list

### Phase 2: Core Player Experience (Week 3-4)

**Goal**: Players can join, select seats, create characters, reconnect

**Deliverables**:
- SeatSelectionModal with seat grid
- CharacterAssignmentModal with form
- Auto-load seat on reconnection
- PlayerVacatedModal for kicked players
- Players see seat counts before joining
- "Resume as {Character}" CTA

### Phase 3: Enhanced Features & Polish (Week 5-6)

**Goal**: Advanced features, optimizations, error handling

**Deliverables**:
- Room summary caching (30s TTL)
- Seat filters (All/Available/Occupied/Offline)
- Filter tabs (Joinable/Waiting/Full)
- "Players Waiting" highlighting with smart sort
- Switch Seat functionality
- localStorage draft restoration
- Enhanced error handling (409/401/403)
- Optimistic UI updates
- Merge patch WebSocket strategy

### Phase 4: Testing & Documentation (Week 7)

**Goal**: Production-ready, tested, documented

**Deliverables**:
- Unit tests for new components
- Integration tests for user flows
- Manual test plan execution
- Performance testing (8 concurrent players)
- WebSocket reconnection tests
- User guides (DM & Player)
- Accessibility audit
- Mobile responsive design

---

## Edge Cases & Error Handling

| Scenario | Behavior |
|----------|----------|
| Player refreshes during character creation | localStorage restores form, shows "Draft restored!" notification |
| Two players claim same seat simultaneously | Backend rejects second (409), frontend auto-refreshes seat grid |
| DM vacates seat while player creating character | Player receives `player_vacated` event, creation cancelled, seat freed |
| DM disconnects mid-campaign | `roomStatus` → `'waiting_for_dm'`, players see "DM Offline", can't take actions |
| Player reconnects after being vacated | SeatSelectionModal shows, player picks new seat |
| Unauthorized/expired invite | Frontend catches 401/403, redirects to lobby with error message |
| WebSocket seat update for unknown seat ID | Merge patch fails, falls back to full refetch |
| DM tries to start with 0 characters | Button disabled, tooltip: "At least one player seat must have a character" |
| Player tries to join full room | "Join" button disabled, shows "Room Full" |

---

## Design Principles

1. **Clarity**: Users always know their current state (seated/not seated, character created/not created)
2. **Resilience**: Handle disconnections, errors, race conditions gracefully
3. **Real-time**: All updates reflect immediately via WebSocket events
4. **Accessibility**: Keyboard navigation, ARIA labels, focus management
5. **Performance**: Optimize with caching, merge patches, optimistic updates
6. **Mobile-first**: Responsive design for seat grids and modals

---

## Summary

This design provides a complete user experience for the Game Room system:

- **Centralized state management** via RoomContext with TypeScript interfaces
- **Clear component hierarchy** with DM and Player experiences
- **Narrative user journeys** showing step-by-step flows
- **5-state Seat component** with explicit rendering logic
- **Enhanced features** (filters, caching, persistence, error handling)
- **4-phase implementation plan** with clear deliverables

All features integrate seamlessly with the backend APIs and WebSocket events documented in `game-room-revised.md`.
