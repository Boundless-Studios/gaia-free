# Client-Side Audio Playback Specification

## Goals & Constraints
- Move DM narration playback from the server host to the player’s browser.
- Reuse existing remote TTS providers (OpenAI / ElevenLabs / F5) via asynchronous generation.
- Store audio artifacts per session in Cloud Storage so Cloud Run remains stateless.
- Support multiple simultaneous sessions without cross-talk; each browser controls its own queue.
- Maintain accessibility (visible controls, keyboard operation) and graceful degradation (text-only fallback).

---

## 1. Backend Updates

### 1.1 Audio Generation Flow
1. `auto_tts_service.generate_audio(text, session_id)` accepts `return_artifact: bool = True`.
2. Delegates to `tts_service.synthesize_speech` with `play=False` and new parameter `persist=True`.
3. `tts_service` writes the audio file to a temporary path, uploads it to `gs://<campaign-bucket>/<session_id>/media/audio/<uuid>.mp3`, and deletes the temp file.
4. Return payload:
   ```python
   {
     "success": True,
     "url": "<signed_url_or_public_path>",
     "mime_type": "audio/mpeg",
     "duration_sec": <float>,
     "size_bytes": <int>,
     "created_at": "<iso8601>"
   }
   ```

### 1.2 API Schema Changes
- Extend `StructuredGameData` (backend/src/api/schemas/chat.py) with optional `audio` field containing the payload above.
- Ensure `/api/chat`, `/api/campaigns/new` responses surface `audio`.
- Update OpenAPI docs (FastAPI auto-generated) to reflect new field.

### 1.3 Security & Expiration
- Use signed URLs with short TTL (e.g., 15 minutes) generated via GCS SignedURL API.
- Add `/api/media/audio/<session_id>/<file>` proxy endpoint if signed URLs are undesirable; enforce membership checks.
- Implement cleanup job (`scripts/prune_audio_artifacts.py`) to remove audio older than 24 hours to control storage costs.

### 1.4 Observability
- Log generation latency, upload success/failure, and returned URL.
- Emit counter metrics (if available) for `tts_requests_total`, `tts_failures_total`.

---

## 2. Frontend Architecture

### 2.1 Audio Queue Provider
- Create `AudioQueueProvider` (React context) under `frontend/src/context/audioQueueContext.jsx`.
- Responsibilities:
  - Maintain queue per session (`{ sessionId: AudioTrack[] }`).
  - Auto-play next track when current finishes.
  - Expose controls: `enqueue(track)`, `play()`, `pause()`, `skip()`, `mute(toggle)`, `clear(sessionId)`.
  - Persist mute preference in localStorage (`gaiaAudioMuted`).

### 2.2 Integration Points
- `apiService.transformResponse` maps backend `audio` payload into an `AudioTrack` object:
  ```js
  { id, sessionId, url, mimeType, durationSec, createdAt }
  ```
- `App.jsx` (or message handling layer) calls `audioQueue.enqueue(track)` when a DM response contains audio.
- Update `PlayerView` to consume queue state and show:
  - Now playing (title defaults to “DM narration” with timestamp)
  - Progress bar (use `<audio>` element events)
  - Controls (play/pause, skip, mute, volume slider)

### 2.3 Accessibility & UX
- Ensure controls are keyboard focusable and have ARIA labels.
- Visual indicator in chat timeline when an audio clip is associated with a message (play icon).
- Handle user-gesture requirement: first interaction displays “Enable audio” button if autoplay blocked.
- Retry logic for failed fetch with exponential backoff (max 3 attempts); fall back to text-only message and toast.

### 2.4 Error Handling
- If audio URL returns 403/404, remove from queue and display toast “Audio unavailable”.
- Handle `<audio>` `onerror` by skipping to next track.
- Allow user to clear queue manually.

---

## 3. Testing Plan

### 3.1 Backend
- Unit tests for `auto_tts_service` verifying returned payload, upload call, and error path.
- Integration test (pytest + moto/gcsfuse mock) for `/api/chat` ensuring `audio` appears in JSON and signed URL is valid.

### 3.2 Frontend
- Jest/RTL tests:
  - AudioQueueProvider enqueue/play/pause logic (mock `HTMLAudioElement`).
  - UI component renders controls and responds to state changes.
- Cypress/Playwright E2E:
  - Mock backend to return audio payload, confirm browser plays clip and controls respond.
  - Two sessions open simultaneously; ensure queues are independent.

### 3.3 Manual
- Verify audio plays on Chrome, Firefox, Safari (desktop + mobile).
- Confirm mute persists across reloads.
- Validate signed URL expiration: clip should fail after TTL.

---

## 4. Rollout Steps
1. Implement backend changes with client audio enabled by default (retain `GAIA_AUDIO_DISABLED` escape hatch for smoke-testing).
2. Ship updated API schema + tests.
3. Build frontend AudioQueueProvider, integrate into chat flow.
4. Enable feature flag in staging; run automated + manual checks.
5. Toggle flag for production deployment once validated.
6. Monitor logs and storage usage; adjust cleanup cadence if needed.

---

## 5. Open Questions
- Desired audio format (mp3 vs. ogg) for best browser compatibility? Default to mp3 unless provider requires otherwise.
- Should we allow players to download clips? If yes, expose download button with signed URL.
- Do we need to cache audio metadata for session resume, or fetch anew each time? (Current assumption: fetch on first render; queue only live messages.)

---

**Owner:** `@you`  
**Related Tasks:** Multi-session rollout, Cloud Run deployment  
**Status:** Draft – ready for implementation planning.
