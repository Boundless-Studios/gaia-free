"""REST tests for campaign read access using session ACLs.

These tests mount a tiny FastAPI app that reuses the shared
`_enforce_session_access` guard to validate authorization for
campaign read semantics without spinning up the full backend.
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


def user_dep():
    from fastapi import Request

    def _dep(req: Request) -> DummyUser:
        return DummyUser(
            user_id=req.headers.get("X-User-Id"),
            email=req.headers.get("X-User-Email"),
        )

    return _dep


def build_campaign_app(tmp_path) -> TestClient:
    # Isolate registry and storage, disable DB syncing
    os.environ["SESSION_REGISTRY_DISABLE_DB"] = "1"
    os.environ["CAMPAIGN_STORAGE_PATH"] = str(tmp_path)

    app = FastAPI()
    app.state.session_registry = SessionRegistry()

    @app.get("/campaigns/{campaign_id}/read")
    def read_campaign(campaign_id: str, user: DummyUser = Depends(user_dep())):
        try:
            _enforce_session_access(app.state.session_registry, campaign_id, user)
        except HTTPException as exc:
            raise exc
        # Return a minimal response to assert status and payload
        return {"success": True, "campaign_id": campaign_id, "messages": []}

    return TestClient(app)


@pytest.fixture()
def client(tmp_path):
    return build_campaign_app(tmp_path)


def test_campaign_read_allows_when_no_claims(client):
    r = client.get("/campaigns/c01/read")
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_campaign_read_blocks_unauthenticated_and_non_member(client):
    reg: SessionRegistry = client.app.state.session_registry
    reg.register_session("c02", owner_user_id="owner-abc", title="Two")

    # Unauthenticated → 401
    r = client.get("/campaigns/c02/read")
    assert r.status_code == 401

    # Wrong user → 403
    r2 = client.get(
        "/campaigns/c02/read",
        headers={"X-User-Id": "intruder", "X-User-Email": "intruder@example.com"},
    )
    assert r2.status_code == 403


def test_campaign_read_allows_owner_and_member(client):
    reg: SessionRegistry = client.app.state.session_registry
    session_id = "c03"
    reg.register_session(session_id, owner_user_id="o3", owner_email="o3@example.com")

    # Owner allowed
    r_owner = client.get(
        f"/campaigns/{session_id}/read",
        headers={"X-User-Id": "o3", "X-User-Email": "o3@example.com"},
    )
    assert r_owner.status_code == 200

    # Add member (by user id)
    reg.touch_session(session_id, user_id="m3", user_email="m3@example.com")
    r_member = client.get(
        f"/campaigns/{session_id}/read",
        headers={"X-User-Id": "m3", "X-User-Email": "m3@example.com"},
    )
    assert r_member.status_code == 200

    # Member by email-only
    reg.touch_session(session_id, user_id=None, user_email="email-only@example.com")
    r_member_email = client.get(
        f"/campaigns/{session_id}/read",
        headers={"X-User-Email": "email-only@example.com"},
    )
    assert r_member_email.status_code == 200

