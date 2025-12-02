"""Tests for share/join endpoints behavior (invites + expiry).

Implements a minimal FastAPI app that mirrors the production logic
using SessionRegistry, without starting the full backend.
"""

import os
from dataclasses import dataclass
from typing import Optional

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from gaia_private.session.session_registry import SessionRegistry


@dataclass
class DummyUser:
    user_id: Optional[str] = None
    email: Optional[str] = None


def user_dep():
    from fastapi import Request

    def _dep(req: Request) -> DummyUser:
        return DummyUser(
            user_id=req.headers.get("X-User-Id"),
            email=req.headers.get("X-User-Email"),
        )

    return _dep


def build_app(tmp_path) -> TestClient:
    # Isolate persistent roots and disable DB sync
    os.environ["CAMPAIGN_STORAGE_PATH"] = str(tmp_path)
    os.environ["SESSION_REGISTRY_DISABLE_DB"] = "1"

    app = FastAPI()
    registry = SessionRegistry()
    app.state.session_registry = registry

    @app.post("/api/sessions/share")
    def share(payload: dict, user: DummyUser = Depends(user_dep())):
        if not user.user_id and not user.email:
            raise HTTPException(status_code=401, detail="Authentication required")

        session_id = payload.get("session_id")
        regenerate = bool(payload.get("regenerate"))
        exp = payload.get("expires_in_minutes")
        multi_use = payload.get("multi_use", True)  # Default to True to mirror production
        max_uses = payload.get("max_uses")

        meta = registry.get_metadata(session_id)
        if not meta:
            # Mirror production: first sharer claims ownership if not recorded yet
            registry.register_session(session_id, owner_user_id=user.user_id, title=None, owner_email=user.email)
            meta = registry.get_metadata(session_id)

        # Only owner may share if owner set
        owner_id = meta.get("owner_user_id")
        owner_email = meta.get("owner_email")
        if (owner_id or owner_email) and not (
            (owner_id and owner_id == user.user_id) or (
                owner_email and user.email and owner_email.strip().lower() == user.email.strip().lower()
            )
        ):
            raise HTTPException(status_code=403, detail="Only the session owner can create invite links")

        if regenerate:
            registry.invalidate_invites(session_id)

        result = registry.create_invite_token(
            session_id,
            created_by=user.user_id,
            created_by_email=user.email,
            expires_in_minutes=exp,
            multi_use=multi_use,
            max_uses=max_uses,
        )
        return {"session_id": session_id, "invite_token": result["token"], "expires_at": result.get("expires_at")}

    @app.post("/api/sessions/join")
    def join(payload: dict, user: DummyUser = Depends(user_dep())):
        if not user.user_id and not user.email:
            raise HTTPException(status_code=401, detail="Authentication required")

        token = payload.get("invite_token")
        result = registry.consume_invite_token(token, user_id=user.user_id, user_email=user.email)
        if not result:
            raise HTTPException(status_code=400, detail="Invite token is invalid or expired")
        return {"session_id": result["session_id"], "expires_at": result.get("expires_at")}

    return TestClient(app)


@pytest.fixture()
def client(tmp_path):
    return build_app(tmp_path)


def test_share_claims_ownership_when_unclaimed(client):
    # First sharer claims ownership if unclaimed
    r = client.post(
        "/api/sessions/share",
        json={"session_id": "s1", "expires_in_minutes": 5},
        headers={"X-User-Id": "owner-1", "X-User-Email": "owner@example.com"},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["session_id"] == "s1"
    assert payload["invite_token"]

    # Non-owner must not be able to create a link now
    r2 = client.post(
        "/api/sessions/share",
        json={"session_id": "s1"},
        headers={"X-User-Id": "intruder", "X-User-Email": "intruder@example.com"},
    )
    assert r2.status_code == 403


def test_join_consumes_token_and_adds_member(client):
    # Owner shares with single-use token
    r = client.post(
        "/api/sessions/share",
        json={"session_id": "s2", "expires_in_minutes": 10, "multi_use": False},
        headers={"X-User-Id": "owner-2", "X-User-Email": "owner2@example.com"},
    )
    token = r.json()["invite_token"]

    # Guest joins
    rj = client.post(
        "/api/sessions/join",
        json={"invite_token": token},
        headers={"X-User-Id": "guest-1", "X-User-Email": "guest@example.com"},
    )
    assert rj.status_code == 200
    assert rj.json()["session_id"] == "s2"

    # Token is consumed and cannot be reused
    rj2 = client.post(
        "/api/sessions/join",
        json={"invite_token": token},
        headers={"X-User-Id": "guest-2", "X-User-Email": "guest2@example.com"},
    )
    assert rj2.status_code == 400


def test_invite_expiry(client, monkeypatch):
    # Create a single-use invite with 1 minute TTL
    r = client.post(
        "/api/sessions/share",
        json={"session_id": "s3", "expires_in_minutes": 1, "multi_use": False},
        headers={"X-User-Id": "owner-3", "X-User-Email": "o3@example.com"},
    )
    token = r.json()["invite_token"]

    # Monkeypatch the registry clock to simulate time passing > 1 minute
    import gaia_private.session.session_registry as regmod
    import datetime as _dt

    # Save the original _utc_now to avoid recursion
    original_utc_now = regmod._utc_now

    def _late_now():
        return original_utc_now() + _dt.timedelta(minutes=2)

    monkeypatch.setattr(regmod, "_utc_now", _late_now)

    # Attempt to join should fail as expired
    rj = client.post(
        "/api/sessions/join",
        json={"invite_token": token},
        headers={"X-User-Id": "guest-x", "X-User-Email": "guestx@example.com"},
    )
    assert rj.status_code == 400


def test_regenerate_invalidates_old_tokens(client):
    # Owner shares first time
    r1 = client.post(
        "/api/sessions/share",
        json={"session_id": "sr1", "expires_in_minutes": 30},
        headers={"X-User-Id": "ownx", "X-User-Email": "own@example.com"},
    )
    assert r1.status_code == 200
    token_old = r1.json()["invite_token"]

    # Regenerate invalidates existing tokens and returns a new one
    r2 = client.post(
        "/api/sessions/share",
        json={"session_id": "sr1", "regenerate": True, "expires_in_minutes": 30},
        headers={"X-User-Id": "ownx", "X-User-Email": "own@example.com"},
    )
    assert r2.status_code == 200
    token_new = r2.json()["invite_token"]
    assert token_new != token_old

    # Old token fails
    rj_old = client.post(
        "/api/sessions/join",
        json={"invite_token": token_old},
        headers={"X-User-Id": "guest-old", "X-User-Email": "g1@example.com"},
    )
    assert rj_old.status_code == 400

    # New token succeeds
    rj_new = client.post(
        "/api/sessions/join",
        json={"invite_token": token_new},
        headers={"X-User-Id": "guest-new", "X-User-Email": "g2@example.com"},
    )
    assert rj_new.status_code == 200
    assert rj_new.json()["session_id"] == "sr1"


def test_owner_by_email_controls_share(client):
    # Pre-register session with owner by email only
    reg: SessionRegistry = client.app.state.session_registry  # type: ignore[attr-defined]
    reg.register_session("se1", owner_user_id=None, title="EmailOwned", owner_email="ownermail@example.com")

    # Owner by email can share
    r_ok = client.post(
        "/api/sessions/share",
        json={"session_id": "se1", "expires_in_minutes": 5},
        headers={"X-User-Email": "ownermail@example.com"},
    )
    assert r_ok.status_code == 200

    # Different email cannot share
    r_forbidden = client.post(
        "/api/sessions/share",
        json={"session_id": "se1"},
        headers={"X-User-Email": "notowner@example.com"},
    )
    assert r_forbidden.status_code == 403


def test_multiple_tokens_are_independent_without_regenerate(client):
    # Owner creates two single-use tokens without regenerate
    r1 = client.post(
        "/api/sessions/share",
        json={"session_id": "mt1", "expires_in_minutes": 30, "multi_use": False},
        headers={"X-User-Id": "owner-mt", "X-User-Email": "owner.mt@example.com"},
    )
    t1 = r1.json()["invite_token"]

    r2 = client.post(
        "/api/sessions/share",
        json={"session_id": "mt1", "expires_in_minutes": 30, "multi_use": False},
        headers={"X-User-Id": "owner-mt", "X-User-Email": "owner.mt@example.com"},
    )
    t2 = r2.json()["invite_token"]
    assert t2 != t1

    # Joining with t1 succeeds and consumes t1 only
    j1 = client.post(
        "/api/sessions/join",
        json={"invite_token": t1},
        headers={"X-User-Id": "guest-a", "X-User-Email": "ga@example.com"},
    )
    assert j1.status_code == 200

    # Reusing t1 fails, but t2 still works
    j1_again = client.post(
        "/api/sessions/join",
        json={"invite_token": t1},
        headers={"X-User-Id": "guest-a2", "X-User-Email": "ga2@example.com"},
    )
    assert j1_again.status_code == 400

    j2 = client.post(
        "/api/sessions/join",
        json={"invite_token": t2},
        headers={"X-User-Id": "guest-b", "X-User-Email": "gb@example.com"},
    )
    assert j2.status_code == 200


def test_regenerate_invalidates_all_outstanding_tokens(client):
    # Create two tokens
    r1 = client.post(
        "/api/sessions/share",
        json={"session_id": "mt2", "expires_in_minutes": 30},
        headers={"X-User-Id": "owner-rt", "X-User-Email": "owner.rt@example.com"},
    )
    t1 = r1.json()["invite_token"]

    r2 = client.post(
        "/api/sessions/share",
        json={"session_id": "mt2", "expires_in_minutes": 30},
        headers={"X-User-Id": "owner-rt", "X-User-Email": "owner.rt@example.com"},
    )
    t2 = r2.json()["invite_token"]
    assert t2 != t1

    # Regenerate: both t1 and t2 should be invalidated
    rr = client.post(
        "/api/sessions/share",
        json={"session_id": "mt2", "regenerate": True, "expires_in_minutes": 30},
        headers={"X-User-Id": "owner-rt", "X-User-Email": "owner.rt@example.com"},
    )
    t3 = rr.json()["invite_token"]
    assert t3 not in (t1, t2)

    # Old tokens fail
    for tok in (t1, t2):
        rj = client.post(
            "/api/sessions/join",
            json={"invite_token": tok},
            headers={"X-User-Id": "guest-x", "X-User-Email": "gx@example.com"},
        )
        assert rj.status_code == 400

    # New token works
    rj3 = client.post(
        "/api/sessions/join",
        json={"invite_token": t3},
        headers={"X-User-Id": "guest-y", "X-User-Email": "gy@example.com"},
    )
    assert rj3.status_code == 200
