# Player Message Sender Metadata

## Context
- The DM dashboard currently renders chat history with only `role` and message text.
- Player labels in the streaming panel depend on the *current* turn info or unreliable client metadata.
- When turns advance (or fallback metadata is missing) labels drift and show `PLAYER` or the wrong character.
- Frontend heuristics add complexity, break on history reloads, and require constant patching.

## Goals
- Persist authoritative details about who submitted each user message.
- Eliminate frontend guesswork; the UI should simply render the stored name.
- Support richer presentation (avatars, filtering, auditing) as a follow-on.
- Maintain backward compatibility for existing clients while enabling migration.

## Proposed Schema Additions
Extend the stored message shape with a canonical `sender` object alongside existing fields (`message_id`, `role`, `content`, `timestamp`, etc.).

```jsonc
{
  "message_id": "msg_123",
  "role": "user",
  "content": "Test the ancestral memory effect on yourself",
  "timestamp": "2025-11-02T00:02:57.711856Z",
  "sender": {
    "type": "player",                // player | dm | system
    "character_id": "pc:grasha_ironhide",
    "display_name": "Grasha Ironhide",
    "player_id": "user_42",          // optional: human account identifier
    "avatar_url": null               // optional: future UI enrichment
  },
  "metadata": { ... }                // unchanged
}
```

### Storage
- If messages persist as JSON blobs (e.g., S3 or JSONB), embed `sender` directly.
- For relational storage, add columns mirroring the `sender` attributes (`sender_type`, `sender_character_id`, `sender_display_name`, `sender_player_id`, etc.) so they can be indexed.

## Write Path Updates
1. **Resolve sender once** when the backend receives a player action (websocket or REST):
   - Derive the active character via session state, explicit request payload, or authenticated context.
   - Populate `sender.type`, `sender.character_id`, `sender.display_name`, and optionally `sender.player_id`.
2. Persist the enriched message and include `sender` in any websocket/event payloads that echo the submission.
3. For DM-authored messages, set `sender.type = "dm"` and provide the appropriate display name (e.g., `"DM"` or the orchestrator persona).

## Read Path / API Changes
- All message fetch endpoints (e.g., `GET /campaigns/{id}/messages`, websocket history refresh) should return the new `sender` object.
- Keep the existing `role` field for backward compatibility; newer clients read `sender.display_name`.
- Document the field in API specs (`chat.py` schemas, OpenAPI if present).

## Migration Strategy
1. **Schema prep**: run DB migrations or update storage templates so new fields are allowed but nullable.
2. **Backfill (optional but recommended)**:
   - Replay recent messages, inferring `sender` from stored metadata or turn history when possible.
   - For older entries where we cannot recover a character name, leave `sender` null—frontend will fall back to `"Player"`.
3. **Feature flag rollout**:
   - Gate the change so both old/new clients function during deployment.
   - Once frontend release that consumes `sender` is live, remove heuristics and rely solely on backend data.

## Frontend Impact
- Simplify `StreamingNarrativeView` and related hooks: render `message.sender.display_name` if present, otherwise fallback to the legacy logic.
- Drop the current dependency on `turn_info` for chat labels.
- Future enhancements (avatars, filtering by character) become trivial because the data is authoritative.

## Open Questions
1. Do we need to store both the *character* and the *human player* (for shared-character scenarios)?
2. Should `sender` also capture locale, voice preference, or other personalization fields for later UI use?
3. Do we expose `sender` in analytics/telemetry pipelines, and if so, how do we scrub PII?
4. How far back do we attempt to backfill historical campaigns, and is that worth the effort?

## Next Steps
1. Align on naming (`sender` vs. `actor`) and confirm the required attributes.
2. Implement backend changes: schema migration, write-path enrichment, API return fields.
3. Ship a frontend update consuming `sender`.
4. Remove temporary client-side heuristics once the new data is fully deployed.
