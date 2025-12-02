## Player Seat Flow Implementation Plan

### Context
- We just enhanced `PlayerSessionModal` so invited players can review campaign summaries before joining.
- Next we must deliver the in-room player journey described in `docs/game-room-frontend-design.md`, covering seat selection, character creation/binding, and the reconnection path.
- The frontend already contains `RoomContext`, DM seat management, and reused base UI components (SeatCard, character creator pieces).

### Goals
1. Route all player sessions through `RoomContext` so they share the same live seat state as DMs.
2. Provide a dedicated `SeatSelectionModal` for players that uses room data plus the `room.seat_updated` events.
3. Allow players to assign characters to their claimed seats using the same character creation pipeline as the DM setup wizard.
4. Handle reconnect/vacate cases so existing seat owners bypass the modals and return to `PlayerView` seamlessly.

### Key Deliverables
1. **Player Seat State Hook**
   - Extend `RoomContext` to expose helpers like `getPlayerSeatForUser`, `occupySeat`, `releaseSeat`, and `assignCharacterToSeat`.
   - Track player-specific errors (409 seat conflicts, 401 auth) and surface friendly messages.

2. **SeatSelectionModal (Player)**
   - New component under `frontend/src/components/player/SeatSelectionModal.jsx`.
   - Renders available player seats using the existing `SeatCard`.
   - Handles optimistic seat reservation + refetch fallback.
   - Listens for `room.player_vacated` to boot users back into the modal when necessary.

3. **CharacterAssignmentModal**
   - New component reusing the DM character-creation form pieces (name metadata, portrait preview, visual customization).
   - Auto-opens when a player owns a seat that lacks `character_id`.
   - Persists form drafts to `localStorage` keyed by `(campaignId, seatId)`.
   - Calls `apiService.assignCharacterToSeat` on submit.

4. **PlayerPage Orchestration**
   - Wrap `PlayerPage` in `RoomProvider`.
   - Introduce a lightweight state machine: `{ needsSeat, needsCharacter, ready }`.
   - Show/Hide the new modals based on the derived state.
   - When `ready`, mount the existing `PlayerView`.

5. **PlayerVacated Handling**
   - When RoomContext reports `player_vacated` for the current user, clear cached seat info, show a modal explaining what happened, and reopen seat selection.

### Milestones
1. **Milestone A** – RoomContext integration + seat detection.
2. **Milestone B** – SeatSelection UI + API plumbing.
3. **Milestone C** – CharacterAssignment form reuse + persistence.
4. **Milestone D** – PlayerPage orchestration, reconnection, and vacate handling.

### Risks & Mitigations
- **WebSocket Desync**: Seat or character updates could arrive late. Mitigate by falling back to `fetchRoomState` whenever SeatSelection receives a 409 or `seat_id` mismatch.
- **Form Drift**: Character creator must match DM version. Share utilities/constants or import the same components directly.
- **Auth Race**: Ensure `apiService.getAccessToken` is ready before hitting `/rooms/*`. Keep RoomContext’s token readiness guard when invoking player seat methods.
