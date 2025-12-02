# Scene Music Integration Proposal

## Purpose
Deliver adaptive background music that plays concurrently with narration and SFX during tabletop scenes. Music should respond to narrative tone, stream reliably to clients, and never block or delay dialogue playback.

## Goals
- Stream a continuous music layer in parallel with the existing speech queue.
- Automatically select or generate track prompts based on real-time scene state.
- Use ElevenLabs music generation with guardrails for latency, caching, and reuse.
- Provide session hosts with lightweight controls (start/refresh/mute) without exposing extra steps to players.
- Maintain compatibility with current websocket infrastructure and deployment flows.

## Non-Goals
- Mixing music cues into the TTS/audio queue.
- Replacing or refactoring existing narration agents.
- Delivering highly granular adaptive scoring (per action/turn beat).

## Experience Overview
- When a scene resolves, the orchestrator requests a mood prompt (e.g., “tense strings with tribal percussion”).
- ElevenLabs renders the track; the backend publishes a `music` websocket event containing playback metadata and a signed stream URL.
- Frontend MusicManager preloads and plays the track via a dedicated audio node while narration continues through the existing queue.
- Hosts can mute/update music; players receive read-only state (volume, track title, duration).

## System Architecture
| Component | Responsibilities |
| --- | --- |
| Music Prompt Agent | Analyze `SceneInfo`, combat/emotion markers, and DM hints to craft a concise ElevenLabs prompt. |
| ElevenLabs Music Client | Wrap API auth, prompt submission, polling, asset caching, and fallback selection. |
| Music Orchestration Hook | Invoke agent/client post-scene update, persist metadata, and broadcast websocket events. |
| Music Websocket Channel | Deliver `start`, `progress`, `stop`, and `error` messages plus signed URLs to clients. |
| Frontend MusicManager | Manage websocket subscription, buffering, playback, crossfades, and UI state. |

### Data Flow
1. Scene update completes (`scene_integration.py` / `scene_updater.py`).
2. Music hook gathers context and calls `MusicPromptAgent`.
3. Prompt is sent to `ElevenLabsMusicClient`; result cached (object storage + metadata store).
4. Music metadata saved via `campaign_object_store` and broadcast as `music:start`.
5. Frontend MusicManager downloads/streams audio, plays via Web Audio API.
6. Updates (loop, replace, stop) propagate via dedicated websocket messages.

## Backend Workstream
- **MusicPromptAgent (`backend/src/game/dnd_agents/tools/music_prompt_agent.py`)**  
  - Inputs: `SceneInfo`, emotional tone, combat status, DM-imposed tags.  
  - Output: Prompt text + optional style tags (tempo, instrumentation).  
  - Reuse scene analyzers for sentiment classification; add tests covering combat/non-combat.

- **ElevenLabsMusicClient (`backend/src/core/audio/elevenlabs_music_client.py`)**  
  - Handles auth headers, prompt submission, async polling for asset readiness.  
  - Supports config for duration (e.g., 2–4 min), looping toggles, instrument filters.  
  - Implements retry backoff and fallback to cached track if generation fails.

- **Music Orchestration Integration**  
  - Extend `scene_integration.py` and `scene_updater.py` to enqueue music generation after narration payload is committed.  
  - Track per-scene music state in session storage (`campaign_object_store.py`) for reuse when players reconnect.  
  - Emit domain events (e.g., `MusicTrackGenerated`) for observability.

- **Websocket Delivery**  
  - Add `music_channel.py` under `backend/src/api/websocket/`.  
  - Use shared auth/session verification, but segregate message types (`music:start|update|stop|error`).  
  - Reuse `campaign_broadcaster.py` infrastructure while keeping transport distinct from narration queue.

- **Config & Feature Flag**  
  - Introduce `MUSIC_FEATURE_ENABLED` and ElevenLabs keys in `config/cloudrun.*.env`.  
  - Document setup steps in `docs/SETUP.md`.  
  - Add rate-limiting + per-session concurrency guard (max active generations to respect ElevenLabs quotas).

- **Persistence & Caching**  
  - Store generated assets in object storage (existing campaign storage bucket).  
  - Persist metadata (prompt, tone, track_id, signed URL expiry) alongside scene records.

## Frontend Workstream
- **MusicManager Hook (`frontend/src/state/audio/musicManager.ts`)**  
  - Establish websocket connection to `music-channel`.  
  - Manage audio element or Web Audio node, buffer streaming content, and maintain playback state in context.  
  - Handle reconnection logic, resume playback on network hiccups, and expose status to components.

- **Parallel Audio Layering**  
  - Instantiate hidden `<audio>` element or `AudioBufferSourceNode` independent of `audioQueueContext`.  
  - Implement crossfade or volume ramping when replacing tracks.  
  - Respect global mute/volume settings while keeping narration control separately adjustable.

- **UI Updates**  
  - Player view: display track title, mood tag, duration, minimal controls (mute toggle).  
  - Host tools: add “Refresh music” / “Stop music” actions in `PlayerPage.jsx` or admin panel.  
  - Surface errors or fallback states unobtrusively (e.g., toast if generation fails).

- **Offline & Caching**  
  - Cache signed URLs in IndexedDB (with expiry) to avoid re-downloading on short reconnections.  
  - Ensure cleanup when leaving campaign to prevent orphaned audio.

## Infrastructure & Deployment
- Update Docker/Cloud Run manifests to include new env vars and optional storage mounts for caching.  
- Expand secrets management for ElevenLabs music key (SOPS/GCP Secret Manager).  
- Confirm bandwidth/cost impact; add monitoring (e.g., log event counters, track generation latency).

## Testing Strategy
- **Backend**  
  - Unit: prompt agent sentiment mapping, ElevenLabs client error handling, websocket broadcaster payloads.  
  - Integration: end-to-end scene update triggering music event (mock external API).  
  - Load: ensure multiple simultaneous sessions obey rate limits.

- **Frontend**  
  - Unit: MusicManager state transitions, reconnection handling, volume controls.  
  - Integration (Vitest/Cypress): verify narration queue continues while music plays, and UI reacts to start/stop events.  
  - Accessibility: confirm background music respects user mute preferences.

## Rollout Plan
1. Behind feature flag in staging; manual QA across combat and exploration scenes.  
2. Limited beta with trusted campaigns, monitoring generation latency and websocket stability.  
3. Iterate on prompt heuristics, add manual override library if generation quality varies.  
4. Gradual production enablement once telemetry confirms reliability and cost envelope.

## Risks & Mitigations
- **Generation latency** → Pre-cache tracks for predictable scene types; show loading state on frontend.  
- **Quota exhaustion** → Apply per-session caps; reuse cached assets when possible.  
- **Client bandwidth** → Offer lower-bitrate fallback; allow players to opt out.  
- **Sync drift** → Use timestamps in websocket payloads so clients align playback start times.

## Open Questions
- Do we need artist/genre constraints to fit brand guidelines?  
- Should music persist across scene transitions until replaced, or fade out automatically on scene end?  
- How much manual override should hosts have (custom prompt entry, track library)?  
- What telemetry dashboards are required for post-launch monitoring?

## Next Steps
1. Finalize websocket payload contract and signed URL strategy.  
2. Confirm ElevenLabs licensing & cost assumptions for continuous background usage.  
3. Prototype MusicManager hook with mocked websocket events to validate concurrency with narration.  
4. Schedule backend task implementation order (prompt agent → client → orchestration → channel).
