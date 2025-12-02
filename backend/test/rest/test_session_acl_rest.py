"""REST-level ACL tests for session-guarded endpoints.

These tests mount a tiny FastAPI app with a guarded route that reuses
the session access guard from the main API module, but without starting
the full application (no DB or orchestrator needed).
"""

import os
from dataclasses import dataclass

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from gaia_private.session.session_registry import SessionRegistry
from gaia.api.app import _enforce_session_access


@dataclass
class DummyUser:
    user_id: str | None = None
    email: str | None = None


def get_user_from_headers():
    """Extract a minimal user from headers (for testing)."""
    # These header names are only for tests
    from fastapi import Request

    def _dep(req: Request) -> DummyUser:
        return DummyUser(
            user_id=req.headers.get("X-User-Id"),
            email=req.headers.get("X-User-Email"),
        )

    return _dep


def build_test_app(tmp_path) -> TestClient:
    # Ensure the registry operates without DB and with a temp storage root
    os.environ["SESSION_REGISTRY_DISABLE_DB"] = "1"
    os.environ["CAMPAIGN_STORAGE_PATH"] = str(tmp_path)

    app = FastAPI()
    app.state.session_registry = SessionRegistry()

    @app.get("/guard/{session_id}")
    def guarded(session_id: str, user: DummyUser = Depends(get_user_from_headers())):
        # Reuse the guard from main API
        try:
            _enforce_session_access(app.state.session_registry, session_id, user)
        except HTTPException as exc:  # just bubble up
            raise exc
        return {"ok": True, "session_id": session_id}

    return TestClient(app)


@pytest.fixture()
def client(tmp_path):
    return build_test_app(tmp_path)


def test_guard_allows_when_no_claims(client):
    # No claims recorded for session -> guard allows even without auth
    r = client.get("/guard/session-uno")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_guard_blocks_unauthorized_user(client):
    # Register a session with an owner
    reg: SessionRegistry = client.app.state.session_registry
    reg.register_session("session-alpha", owner_user_id="owner-1", title="Alpha")

    # Unauthenticated request should be 401
    r = client.get("/guard/session-alpha")
    assert r.status_code == 401

    # Wrong user should be 403
    r2 = client.get(
        "/guard/session-alpha",
        headers={"X-User-Id": "hacker", "X-User-Email": "hacker@example.com"},
    )
    assert r2.status_code == 403


def test_guard_allows_owner_and_member(client):
    reg: SessionRegistry = client.app.state.session_registry
    session_id = "session-bravo"
    reg.register_session(session_id, owner_user_id="owner-2", title="Bravo", owner_email="owner@example.com")

    # Owner access
    r_owner = client.get(
        f"/guard/{session_id}",
        headers={"X-User-Id": "owner-2", "X-User-Email": "owner@example.com"},
    )
    assert r_owner.status_code == 200

    # Add a member via touch_session (by user_id)
    reg.touch_session(session_id, user_id="member-9", user_email="member9@example.com")
    r_member = client.get(
        f"/guard/{session_id}",
        headers={"X-User-Id": "member-9", "X-User-Email": "member9@example.com"},
    )
    assert r_member.status_code == 200

    # Add a member via email-only
    reg.touch_session(session_id, user_id=None, user_email="member-only@example.com")
    r_member_email = client.get(
        f"/guard/{session_id}",
        headers={"X-User-Email": "member-only@example.com"},
    )
    assert r_member_email.status_code == 200

