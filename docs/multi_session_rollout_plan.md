# Gaia Multi-Session Rollout (Cloud Run)

## Constraints & Goals
- Run a single containerized backend on Google Cloud Run (spot instances enabled) via the `deploy-cloudrun` GitHub Actions workflow.
- Rely on remote services (LLM, image, audio) for heavy compute; no GPU on the container.
- Give every visitor an isolated, optionally shareable campaign session with zero cross-talk.
- Keep the existing FastAPI/React stack; no Colyseus adoption.

---

## 1. Backend Changes *(status: close to complete)*

### 1.1 Session Contexts
- ✅ Create `SessionManager` (`backend/src/core/session/session_manager.py`) that maps `session_id -> SessionContext`.
- ✅ `SessionContext` encapsulates:
  - `ConversationHistoryManager`
  - `CampaignRunner` (+ `TurnManager`, `SceneIntegration`, `CombatStateManager`)
  - `CharacterManager`
  - `asyncio.Lock` to serialize turns
- ✅ Provide helpers: `get_or_create`, `touch`, `release`, `prune_idle(ttl_minutes)`.
- ✅ Add background pruning trigger (`prune_idle`) via an internal scheduler in app lifespan (configurable TTL + interval).

### 1.2 Persistence Layout
- ✅ Update `SessionStorage` + `SimpleCampaignManager` to resolve new layout at `campaign_storage/<session_id>/...` with legacy fallbacks; json `metadata.json` persisted per session.
- ✅ Add migration script (`backend/scripts/migrate_session_storage.py`) to remap legacy folders -> session-scoped directories and seed Postgres; produces optional JSON reports for audits.
  - Usage: `python backend/scripts/migrate_session_storage.py --dry-run` to preview, drop `--dry-run` to execute; `--output` writes a JSON report.
- Store media under `campaign_storage/<session_id>/media/{images,audio}`.
- Ensure all file writes stay within the writable mount that Cloud Run provides (e.g., /tmp or Cloud Storage bucket).

### 1.3 Session API & Sharing
- `/api/campaigns/new` returns a UUID `session_id`; frontend stores it immediately.
- ✅ Introduced `SessionRegistry` (local metadata store) capturing owner + members per session, now persisted in Postgres tables (`campaign_sessions`, `campaign_session_members`, `campaign_session_invites`) while mirroring to JSON for legacy compatibility.
- ✅ Endpoints:
  - `POST /api/sessions/share` → create one-time invite token (currently persisted in SessionRegistry; DB migration pending).
  - `POST /api/sessions/join` → validate token, add current user to members, and consume invite.
- Middleware or endpoint guards validate session ownership/membership before loading context.

### 1.4 Orchestrator Integration
- ✅ Orchestrator uses `SessionManager.get_or_create(session_id)` for each request, acquires the session lock, hydrates history/characters from storage when cold, processes the turn, persists back, releases lock.
- ✅ Persist structured data after each assistant reply for future resumes and UI refreshes.
- ✅ Tool persistence hooks now persist scenes to the active campaign (no more fallback to `default`).

### 1.5 Realtime Updates
- ✅ Refactor `CampaignBroadcaster` to keep `Dict[str, List[ConnectionInfo]]` keyed by session id.
- ✅ Require `session_id` query param on `/ws/campaign/player`; reject if unauthorized.
- ✅ Broadcast events only to matching session connections.

---

## 2. Frontend Changes
- On load, call `/api/campaigns/new` (unless resuming saved `session_id`); store id in localStorage.
- Pass `session_id` with every chat/context request and include it when opening WebSockets (`/ws/campaign/player?session_id=...`).
- ✅ Provide a “Share Session” UI that calls the backend invite endpoint, renders a shareable link, and copies it to the clipboard.
- ✅ Update state management to keep per-session data (messages, structured responses, images) isolated.
- ✅ Fix campaign header/list to show campaign names (not raw IDs) by wiring names from `/api/simple-campaigns` and registry metadata.

---

## 3. Infrastructure & Deployment
- Container build remains the existing Dockerfile; ensure the image reads remote provider keys from Cloud Run secrets.
- GitHub Actions pipeline:
  1. Run unit/integration tests
  2. Build & push image to Artifact Registry
  3. Deploy with `gcloud run deploy` (spot option, min instances = 0, max = 1)
  4. Run migration script via `gcloud run jobs execute` or a one-off execution step before traffic cut-over.
- Mount/write storage strategy:
  - Use Cloud Storage bucket for persistent campaign data via Workload Identity + GCS FUSE or signed URLs.
  - Keep transient files (e.g., temp JSON) in `/tmp` since Cloud Run provides ephemeral storage.
  - Media routing: keep `/api/images/{filename}` for compatibility; extend server to look up session media; plan `/api/media/{session_id}/{type}/{filename}` for future.
- Configure Cloud Run concurrency to 1–2 so the single instance doesn’t overcommit CPU while holding session locks.

---

## 4. Test & Verification

### 4.1 Automated
- ✅ **Backend unit**: SessionManager logic, ACL checks, storage helpers, Postgres-backed session registry.
- 🔄 **Backend integration** (pytest + httpx): new campaign → chat → share/join → concurrent turns; ensure isolated histories.
- **Frontend unit**: session handling hooks/contexts, share link UI.
- **E2E** (Playwright/Cypress against staging Cloud Run URL): two users, independent sessions, invite flow.

### 4.2 Manual Checklist
- ✅ Deploy to staging Cloud Run.
- ✅ Exercise two browsers (different Auth0 accounts): confirm no cross-talk in chat, combat, history; registry reflects both members.
- Validate invite link share.
- Confirm remote media (image/audio) paths resolve correctly.
- Verify Cloud Run logs show per-session lock acquisition/release, no auth errors.
+ ✅ Confirm Scene Creator persists scenes under the correct campaign directory (no stray `default` scenes).

---

## 5. Rollout Sequence
1. ✅ Implement SessionManager + persistence refactor behind feature flag.
2. ✅ Ship API auth checks & WebSocket isolation (session_id query param, registry tracking).
3. ✅ Update frontend session handling (WebSocket query param + session registry aware listings; show names in UI).
4. Run migration script, import legacy data into new layout.
5. Execute automated suite + manual checklist on staging Cloud Run.
6. Merge to main; GitHub Actions deploys to production Cloud Run.
7. Monitor metrics/logs; if stable, delete legacy storage paths.

---

## 6. Risks & Mitigations
- **Lock contention**: timeframe metrics; log waits >2s, consider queue metrics.
- **Storage latency (GCS)**: batch writes where possible; cache hot data in memory with TTL.
- **Spot eviction**: rely on Cloud Run automatic restart; ensure session contexts rehydrate correctly on cold start.
- **Remote API failures**: wrap providers with retries/backoffs; degrade gracefully to text-only responses.
- **Legacy path bleed**: Scene Creator fallback to `default` fixed; monitor for residual artifacts before deleting `default` directories.

---

## 7. Media Storage Roadmap
- Phase A (compatibility, implemented):
  - Persist image metadata under each session; keep binaries in `IMAGE_STORAGE_PATH` (outside repo).
  - `/api/images/{filename}` resolves via metadata to absolute path; `/api/media/{session_id}/...` proxies using metadata with ACLs.
- Phase B (metadata-only session mapping):
  - Do NOT store binaries under `campaign_storage/` to avoid repo growth.
  - Standardize providers to always write to `IMAGE_STORAGE_PATH`; session association lives only in metadata and URLs.
- Phase C (Cloud Run + GCS):
  - Point `IMAGE_STORAGE_PATH` to a GCS bucket mount or serve signed URLs.
  - Optional: background reconciliation for any stragglers; no session directory writes.

---

Owner: `@you`  
Pipeline: GitHub Actions `deploy-cloudrun`  
Last Updated: 2025-10-10  
Status: Updated – tracking implementation

---

**Owner:** `@you`  
**Pipeline:** GitHub Actions `deploy-cloudrun`  
**Last Updated:** {{DATE}}  
**Status:** Draft – ready for implementation & review.
