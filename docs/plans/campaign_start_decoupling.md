# Campaign Start Decoupling Plan

## Goals

- Support the “setup → start” lifecycle in [docs/game-room-revised.md](../game-room-revised.md) so that campaigns can be created/configured without immediately launching the DM agents.
- Allow DMs to pre-create characters (stored via `CharacterManager` and `room_seats.character_id`) or leave seats empty for players to fill later.
- Expose a clear API for the Room Management modal to transition a campaign from `setup` to `active`, kicking off LLM scene generation only when the DM clicks “Start Campaign”.
- Ensure the DM/player UIs never miss the opening scene streaming by relying on the existing WebSocket broadcaster once the campaign becomes active.

## Data Model Considerations

- The existing `campaign_sessions` columns are enough: `campaign_status`, `room_status`, `started_at`, and `max_player_seats` already exist (see `db/migrations/16-create-game-room-tables.sql`). We will:
  - Keep new campaigns in `campaign_status='setup'` and `room_status='waiting_for_players'` until start.
  - Set `campaign_status='active'`, `room_status='in_progress'`, and `started_at=NOW()` when the DM starts the campaign.
- No new columns are required. The initial prompt can be reconstructed at start time from the persisted world metadata (`world_settings` saved under campaign storage) plus the seat-bound characters.
- Characters:
  - Pre-created characters continue to be persisted through `CharacterManager` and bound to `room_seats.character_id` during wizard completion.
  - Empty seats remain with `character_id=NULL`; players can later call `/api/v2/rooms/{id}/seats/{seat_id}/assign-character` to write their PCs before the DM hits start.

## API / Service Updates

1. **Campaign creation (`CampaignService.initialize_campaign`)**
   - Set `campaign_status='setup'` and `room_status='waiting_for_players'` explicitly on the DB row (via `RoomService` or `CampaignSession` write).
   - Build the initial prompt context (world settings + characters) but do not run `_generate_first_turn_async`. Let the Room start endpoint recompute the prompt at activation time.
   - Skip `asyncio.create_task(...)`. The response returns `{initializing: False, campaign_status: 'setup'}` so the UI knows it is waiting on manual start.

2. **New “start campaign” endpoint**
   - Add `POST /api/v2/rooms/{campaign_id}/start` in `backend/src/api/routes/room.py`.
   - Flow:
     1. Require auth + DM ownership (reuse `_ensure_room_access` + DM check).
     2. Ensure DM seat occupied (optional: auto-occupy DM seat for owner if not already).
     3. Validate at least one seat has a character (via `room_seats.character_id` or `CharacterManager` lookup).
     4. Rebuild the initial prompt from `world_settings` + `RoomSeat` character payloads.
     5. Update `campaign_sessions` (`campaign_status='active'`, `room_status='in_progress'`, `started_at=NOW()`).
     6. Kick off `_generate_first_turn_async` (reuse helper by moving it to a shared service or call `CampaignService.start_campaign`).
     7. Broadcast `room.status_updated` + `campaign_update` events via `CampaignBroadcaster` so the DM UI refreshes instantly.
   - Return the active campaign metadata plus a `status: "starting"` indicator to show the DM that narration is being generated.

3. **Room state / summary**
   - `RoomService.get_room_state` already surfaces `campaign_status`, which is enough for the UI to show the “Start” CTA while in `setup`.
   - When `start_campaign` updates statuses, reuse `CampaignBroadcaster.broadcast_room_status` (add if missing) so connected clients refresh without polling.

## Frontend Touchpoints (high level)

- DM Room Management Drawer:
  - Show “Start Campaign” button when `campaign_status === 'setup'`.
  - Disable DM-only controls (run turn, compaction toggles, etc.) until the status flips to `active`.
  - After calling `/api/v2/rooms/{id}/start`, keep listening to websocket `campaign_update` events; the first update will carry the DM narrative generated from `_generate_first_turn_async`.
- Player lobby / player view:
  - Use `campaign_status` from `/api/v2/rooms/{id}/summary` to display “Setup” vs “Active”.
  - No changes needed for streaming since `CampaignBroadcaster` already routes all chunks from `StreamingDMRunner`.

## Execution Steps

1. **Backend refactor**
   - Modify `CampaignService.initialize_campaign` to skip LLM execution while persisting world metadata + characters.
   - Expose a helper `CampaignService.start_campaign(campaign_id)` to encapsulate the validation + `_generate_first_turn_async` call using `RoomSeat`/metadata context.
   - Add `/api/v2/rooms/{id}/start` route which calls the helper after DB validations.
   - Ensure status transitions broadcast to connected clients (extend `CampaignBroadcaster` if necessary).

2. **Frontend wiring (follow-up PR)**
   - Update Room Management modal to call the start endpoint and watch for the resulting status change / streaming events.

This plan keeps the DM-driven flows aligned with the documented Game Room user journeys, leverages the existing database schema, and introduces a small, focused API surface for kicking off campaigns once the room is ready.
