---
title: Add Proper ACL Management For Images
labels: enhancement, security, backend, frontend
assignees: 
---

## Summary

Add session-aware ACL for image media while keeping a smooth dev UX. Ensure images are private to session members in production and still load in browsers where `<img>` cannot attach Authorization headers.

## Current Behavior

- Public listing: `/api/images` returns recent image metadata with `path: "/api/images/<filename>"` and no ACL checks. See backend/src/api/main.py:722.
- Public fetch: `/api/images/{filename}` serves files from `IMAGE_STORAGE_PATH`. See backend/src/api/main.py:978.
- ACL route: `/api/media/{session_id}/{media_type}/{filename}` enforces `_enforce_session_access` and resolves via metadata. See backend/src/api/main.py:1313.
- Frontend gallery constructs URLs; now prefers server-provided paths and falls back to session media only when needed. See frontend/src/components/ImageGalleryWithPolling.jsx:20 and frontend/src/services/apiService.js:303.

## Problems

- `<img>` requests can’t attach Authorization headers; they rely on cookies. Without cookie-based auth, `/api/media/...` returns 401/403 and images fail to load.
- Public `/api/images` bypasses ACLs, which is undesirable in production for private campaigns.
- No signed-URL flow for safe embedding when cookies aren’t present.
- Cookie-based auth not wired for images by default; tokens aren’t set as HttpOnly cookies on login.

## Goals

- Enforce session ACLs for media fetches in production.
- Keep a dev mode where images “just work.”
- Support both cookie-protected and signed, short-lived URLs.

## Proposed Approach

1) Cookie-based media ACLs (baseline)

- Ensure login sets HttpOnly cookies (`access_token`, `refresh_token`) using `set_auth_cookies` or `create_redirect_with_cookies`.
  - auth/src/cookies.py:21
  - auth/src/middleware.py:55 (cookie read fallback exists)
- With cookies present, `<img src="/api/media/{session_id}/images/{filename}">` authenticates automatically.
- Frontend continues to prefer server-provided `/api/images/...` in dev; in prod use `/api/media/...` when cookies exist.

2) Signed media URLs (for embed without cookies)

- Add a HMAC-signed token endpoint to mint short-lived URLs:
  - `POST /api/media/{session_id}/sign` → `{ url: "/api/media/{session_id}/{type}/{filename}?token=...&exp=...", expires_at }`
- Implement `MEDIA_SIGNING_KEY` and `MEDIA_TOKEN_TTL_SECONDS` envs.
- Extend `/api/media/...` to accept `token` query; verify signature, `exp`, `session_id`, `filename`, `type`.
- Frontend: when cookies are unavailable, request signed URL via XHR (with Authorization or existing cookie), then set `<img src>` to the signed URL.

3) Lock down and deprecate public `/api/images`

- Add `MEDIA_PUBLIC_ENABLED` (default false in prod) to disable `/api/images` or return placeholders.
- Add `MEDIA_DEV_ALLOW_PUBLIC` (default true) for local development.

## API Changes

- New: `POST /api/media/{session_id}/sign` body `{ filename, media_type }` → `{ url, expires_at }`.
- Extend: `/api/media/{session_id}/{media_type}/{filename}` to accept `token` query for signed access.
- Config:
  - `MEDIA_AUTH_STRATEGY` = `public | cookie | signed | cookie+signed`
  - `MEDIA_SIGNING_KEY`, `MEDIA_TOKEN_TTL_SECONDS` (e.g., 120)
  - `MEDIA_PUBLIC_ENABLED` (prod default: false), `MEDIA_DEV_ALLOW_PUBLIC` (dev default: true)
  - `COOKIE_DOMAIN`, `COOKIE_SAMESITE`, `COOKIE_SECURE` for cookies

## Frontend Changes

- Gallery/media URL selection:
  - If `MEDIA_AUTH_STRATEGY=cookie` and cookies present → use `/api/media/{session_id}/images/{filename}`.
  - Else if `...=signed` → request a signed URL and set `<img src>` to it.
  - Else (dev/public) → fallback to `/api/images/{filename}`.
- Set `<meta name="referrer" content="no-referrer">` to reduce token leak risk for signed URLs.
- Relevant code:
  - frontend/src/components/ImageGalleryWithPolling.jsx:20
  - frontend/src/services/apiService.js:303
  - frontend/src/App.jsx:516

## Backwards Compatibility

- Keep `/api/images` enabled when `MEDIA_PUBLIC_ENABLED=true` (default in dev).
- Existing metadata and gallery continue to work; new logic prefers safer routes when available.

## Security Considerations

- Cookies: HttpOnly, Secure, `SameSite=None` for cross-site or `Lax` for same-site.
- Signed URLs: short TTL (60–300s), HMAC with server secret, validate all claims.
- Response headers: `Referrer-Policy: no-referrer`, `Cache-Control` tuned (`private, max-age=<short>` or `no-store`).
- Consider 404 instead of 403 for unauthorized media to reduce existence leakage.

## Open Questions

- Fully disable `/api/images` in production or allow a whitelist of public campaigns?
- What TTL is acceptable for signed URLs (e.g., 60–300 seconds)?
- Should we pivot to object storage (S3/GCS) and use presigned URLs instead of proxying?

## Acceptance Criteria

- With cookies set, `<img>` loads from `/api/media/...` for members; unauthenticated gets 401 and non-members 403.
- Without cookies, UI can fetch a signed URL and `<img>` loads successfully within TTL.
- Dev mode: images load via `/api/images` when `MEDIA_DEV_ALLOW_PUBLIC=true`.
- Tests cover: owner, member by email, unauthenticated, non-member, signed URL path, TTL expiry, tampered token.

## Test Plan

- Unit: token generation/verification util (happy/expired/tampered).
- REST: extend `backend/test/rest/test_media_proxy_acl.py` with signed URL cases; keep existing 401/403 assertions.
- E2E: browser loads images with cookies; browser loads images with signed URLs when no cookies.

## Rollout

1. Implement cookie login/callback to set cookies; add env flags; keep `/api/images` enabled.
2. Implement signing endpoint and token verification; add frontend fallback.
3. Disable public `/api/images` in production via env; monitor logs; remove legacy path later if desired.

## Code Pointers

- Media routes: `backend/src/api/main.py:1313`
- Public image route: `backend/src/api/main.py:978`
- Recent images listing: `backend/src/api/main.py:722`
- Auth cookies: `auth/src/cookies.py:21`
- Optional auth (cookie support): `auth/src/middleware.py:245`
- Image metadata manager: `backend/src/core/image/image_metadata.py:141`
- Frontend gallery: `frontend/src/components/ImageGalleryWithPolling.jsx:20`
- Frontend API: `frontend/src/services/apiService.js:303`
- App image handling: `frontend/src/App.jsx:516`

## Tasks

- [ ] Add `MEDIA_AUTH_STRATEGY`, `MEDIA_SIGNING_KEY`, related env handling
- [ ] Implement `POST /api/media/{session_id}/sign` and token verification in `/api/media/...`
- [ ] Update login/callback to set cookies via `set_auth_cookies`
- [ ] Frontend: use cookie route when available; fallback to signed URLs; dev → public
- [ ] Add security headers and caching policy
- [ ] Update docs and examples; add `Referrer-Policy: no-referrer`
- [ ] Expand tests (REST + unit) for signed URLs and cookie flows

