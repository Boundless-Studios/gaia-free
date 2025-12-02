# User Identifier Reference

This doc summarizes every identity representation in Gaia, what it looks like, who emits it, and which layers should use it.

## Canonical GAIA UUID (`auth.users.user_id`)

* **Format:** standard UUID v4 (e.g., `30d5da74-e283-42d7-9492-2448c1228076`).
* **Source of truth:** `auth.users`. Created when a user is provisioned (either manually or via Auth0 auto-provision).
* **Where it’s stored:**
  * `campaign_sessions.owner_user_id`
  * `room_seats.owner_user_id`
  * `campaign_session_members.user_id`
  * `websocket_connections.user_id`
  * Every REST/WebSocket auth dependency (`current_user.user_id`, `RoomProvider currentUserId`, etc.).
* **Usage:** This is the only identifier we compare in code. All authorization decisions, seat ownership checks, and frontend “is this me?” logic rely on this UUID.

## Auth0 Subject (`sub`)

* **Format:** Auth0-specific identifiers (e.g., `auth0|65f5ef0dbcb5837a74487ca9`).
* **Source:** JWT tokens issued by Auth0.
* **Where it’s used:** `oauth_accounts.provider_account_id`; optionally mirrored in API payloads via `owner_identity.auth0_user_id` for auditing.
* **When to use:** Only for correlating Gaia activity back to Auth0 logs. Never compare or store this in primary tables once the GAIA UUID is known.

## Email Address

* **Format:** standard email string (e.g., `user1@example.com`). Often normalized (lower-case).
* **Purpose:** Display text, invite flow, fallback contact info.
* **Current fields:** `campaign_sessions.owner_email/normalized_owner_email`, `campaign_session_members.email/normalized_email`, `websocket_connections.user_email`, room API payloads (`owner_email`, `invited_players[*].email`).
* **Guidance:** Use email only for invitations and UI display. All equality checks must rely on the GAIA UUID. We can reduce duplication (e.g., drop `owner_email` and `websocket_connections.user_email`) once every record has a GAIA `user_id` and the frontend can fetch profile info on demand.

## WebSocket Identity Flow

1. Client connects to `/ws/campaign/{player|dm}` with an Auth0 token.
2. `ws_helpers.authenticate_ws_user*` verifies the token and resolves it to the GAIA UUID + email.
3. `connect_player` / `connect_dm` pass that GAIA ID into `connection_registry.create_connection`, and later updates push the seat ID.
4. `RoomService` marks a seat “online” when `room_seats.owner_user_id` matches a connected `websocket_connections.user_id`.

If the token is missing on connect, the socket is accepted but `room.dm_joined` events and registry rows won’t have an owner until the `auth` message arrives—ensure clients send the `auth` payload immediately, and consider rejecting unauthenticated sockets in production.

## Frontend Identity Flow

* At startup, the frontend calls `/api/auth0/verify`. Response contains `user_id` (GAIA UUID), `email`, etc.
* We store that in `Auth0Context`, and pass `user.user_id` down to contexts like `RoomProvider currentUserId`.
* Room APIs now return `owner_identity.gaia_user_id`, `owner_identity.auth0_user_id`, and `owner_identity.normalized_email`; comparisons such as `currentUserIsOwner` or `isDMSeated` should use `*.gaia_user_id`.

## Canonical Rules

1. **All comparisons use GAIA UUIDs.** Store them everywhere (`owner_user_id`, `websocket_connections.user_id`, etc.) and keep them in sync.
2. **Auth0 subject is informational.** Keep it only when bridging back to Auth0 or logging.
3. **Emails are display-only.** Use them for invites and UI labels, but do not rely on them for identity checks.
4. **WebSocket registry must persist GAIA IDs.** Ensure the backend can reach Postgres so `connection_registry` writes `user_id`, `user_email`, and `seat_id`.
5. **Frontend relies on `/api/auth0/verify`.** That endpoint returns the GAIA UUID; no need to parse Auth0 tokens client-side for identity.

Following these rules ensures every layer (auth, REST, WebSocket, frontend) shares the same canonical notion of “who is this user?” while minimizing redundant email storage.
