# Campaign Storage Re-Architecture Plan

## Why Revisit Storage
- `SimpleCampaignManager` is responsible for directory creation, history persistence, and character management; every subsystem reaches directly into the filesystem, making ownership checks and backend swaps hard.
- Session state lives in globals (`Orchestrator`, campaign manager, character caches). Rehydrating a session in a new process requires bespoke bootstrapping with no metadata source of truth.
- Storage paths (`campaigns/<env>/campaign_* - Name/...`) conflate runtime IDs with human readable names and legacy artifacts. There is no link between filesystem state and authenticated users.
- WebSockets, REST requests, and background jobs all assume a single active campaign; concurrency, sharing, and audits are brittle.

## Target Architecture
1. **Session Metadata**
   - Persist `session_id`, `owner_user_id`, `storage_prefix`, members, timestamps, and lifecycle flags in Postgres.
   - All entry points (REST, WS, background jobs) resolve sessions through metadata first; unauthorized requests are rejected.

2. **Storage Abstraction**
   - Introduce `CampaignStorage` interface (read/write history, structured data, media) with implementations for local disk and GCS/S3.
   - `SimpleCampaignManager` becomes a thin adapter around this interface; business logic references storage through dependency injection.

3. **Session Runtime**
   - `SessionManager` maintains an in-memory cache of `SessionContext = {session_id, orchestrator, lock, last_accessed}`.
   - Hydration path: metadata lookup → storage prefix resolution → orchestrator boot with injected storage + character providers.
   - Background idle-pruner removes inactive contexts; restarts rehydrate on demand.

4. **Filesystem Layout**
   - `campaign_storage/<env>/users/<user_id>/sessions/<session_id>/{logs,data,media}` for owned content.
   - Shared sessions optionally mount under `campaign_storage/<env>/shared/<session_id>` with ACL entries for members.
   - Media (images/audio) co-located under each session root to simplify clean-up.

5. **API / WebSocket Updates**
   - REST endpoints create/read sessions via metadata, enforcing ownership or membership on each request.
   - WebSocket URLs require `session_id`; connection upgrade verifies membership before joining the broadcast group.
   - Sharing flow issues invite tokens, persists hashed tokens, and populates `campaign_session_members`.

## Migration Strategy
1. Schema migration for `campaign_sessions` and `campaign_session_members` tables; add indexes on `owner_user_id` and `updated_at`.
2. Write a migration job:
   - Scan `campaigns/<env>/campaign_*` directories.
   - Determine owner (from registry, Auth0 logs, or manual mapping file).
   - Move content into user-scoped directories; update metadata rows with new `storage_prefix`.
   - Produce a reconciliation report for ambiguous sessions.
3. Provide read-only shim that maps legacy paths to metadata until migration completes; log shim usage for follow-up.

## Testing & Tooling
- Unit tests for metadata DAO, storage adapters, and ACL guards.
- Integration tests that spin up two users, share a session, and confirm isolation across REST + WebSocket flows.
- CLI/Cloud Run job to run `prune_idle(ttl)` and to reconcile metadata vs filesystem.
- Observability: emit structured logs for lock contention, storage latency, and session lifecycle events.

## Rollout Sequence
1. Land metadata schema + DAO; build storage abstraction with existing filesystem backend.
2. Refactor `SessionManager` and orchestrator to rely on metadata + storage interfaces.
3. Update API + WebSocket layers to enforce access control through metadata.
4. Introduce new filesystem layout and run migration in staging, then production.
5. Remove legacy path assumptions and finalize documentation/runbooks.
