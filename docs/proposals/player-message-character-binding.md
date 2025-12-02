# Player Message → Character Binding

## Problem
- Streaming UI knows which character is active when the player submits a message, but backend persistence ignores that context.
- Stored `chat_history.json` entries only keep `role=“user”`, so history replay, refreshes, and secondary consumers (summaries, TTS, etc.) lose the character association.
- Without a canonical character link, turn indicators break after reload and other systems can’t reason about per-character contributions.

## Goal
Persist and surface the active character for every user-authored message so that any playback (live stream, refresh, exported history) can display accurate speaker attribution.

## Functional Requirements
- Accept the active character (id + friendly name) on chat submission.
- Store the character metadata alongside the message in memory, on disk (`chat_history.json`), and in any API response/websocket payload that emits that message.
- Preserve backwards compatibility with existing histories (missing metadata defaults to `null` and does not crash).
- Expose the metadata through existing API schemas so the frontend can rely on it after refresh.

## High-Level Design
1. **Ingress**  
   - Extend `ChatRequest.metadata` (and compat paths) to accept a nested `player_character` object containing `character_id` and `character_name`.  
   - Validate and normalize that payload in `chat.py` before invoking the orchestrator.
2. **History Tracking**  
   - Update `HistoryManager.add_message` to store optional `character_id` / `character_name` fields for user messages.  
   - Ensure `_save_campaign_history` writes those fields to disk and that `load_campaign_history` leaves them intact.
3. **Streaming + Broadcast**  
   - Pass the character metadata into `run_turn` / streaming orchestrator so websocket events (`player_response_chunk`, etc.) and immediate API responses carry the same tags.
4. **Schema Surface**  
   - Add `character_id` / `character_name` to `ConversationMessage`, `UserInput`, and any other outward-facing schema that represents player messages.

## Implementation Plan
1. **Schema & Request Updates**
   - Update Pydantic models (`ChatRequest`, `ConversationMessage`, `UserInput`) to include optional character fields.  
   - Modify request handling in `chat.py` / `chat_compat` to extract the character payload and pass it through orchestration calls.
2. **History Manager Changes**
   - Alter the internal message representation to store a `metadata` dict (or explicit fields) and persist the new keys when saving history.  
   - Add defensive logic so histories missing the keys continue to load.
3. **Persistence & Storage**
   - Ensure `SimpleCampaignManager.save_campaign` writes and `load_campaign_history` retains the metadata.  
   - Verify mirrored object-store writes remain compatible.
4. **Streaming Propagation**
   - Thread the character metadata through `run_turn`, streaming DM orchestrator, and any broadcaster payloads that contain user messages.  
   - Confirm UI websocket consumers receive `character_name` during live streaming.
5. **Testing**
   - Add regression coverage that round-trips a message with character metadata through history save/load.  
   - Write unit/integration coverage for websocket payload inclusion if feasible.
6. **Backfill Strategy (Optional)**
   - Decide whether to backfill historic logs (e.g., inferring from `turn_info`) or leave them null.

## Risks & Mitigations
- **Legacy history parsing**: guard loads with `.get()` defaults and avoid assuming the new fields exist.  
- **Frontend contract drift**: coordinate on exact field names (`characterId` vs `character_id`) and maintain camelCase ↔ snake_case mapping as needed.  
- **Partial metadata**: handle the case where only one of ID/name is provided; fall back gracefully.

## Open Questions
1. Do we need to persist both character ID and display name, or is one canonical identifier sufficient?  
2. Should inference/backfill run for old histories, or is a null display acceptable for legacy turns?  
3. Are there downstream consumers (analytics, summarizers) that also need awareness of the new fields?

