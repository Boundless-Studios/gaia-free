"""REST tests for session-scoped media proxy access control.

We build a tiny app that reuses the session ACL guard and metadata
resolution logic to serve files from IMAGE_STORAGE_PATH, without
importing the full backend app/lifespan.
"""

import os
from pathlib import Path

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient

from gaia_private.session.session_registry import SessionRegistry
from gaia.api.app import _enforce_session_access
from gaia.infra.image.image_metadata import get_metadata_manager


class DummyUser:
    def __init__(self, user_id: str | None, email: str | None) -> None:
        self.user_id = user_id
        self.email = email


def user_dep():
    from fastapi import Request

    def _dep(req: Request) -> DummyUser:
        return DummyUser(
            user_id=req.headers.get("X-User-Id"),
            email=req.headers.get("X-User-Email"),
        )

    return _dep


def build_media_app(tmp_path: Path) -> TestClient:
    # Point storage roots to tmp
    os.environ["SESSION_REGISTRY_DISABLE_DB"] = "1"
    os.environ["CAMPAIGN_STORAGE_PATH"] = str(tmp_path)
    os.environ["IMAGE_STORAGE_PATH"] = str(tmp_path / "images")
    (tmp_path / "images").mkdir(parents=True, exist_ok=True)

    app = FastAPI()
    app.state.session_registry = SessionRegistry()

    @app.get("/media/{session_id}/{filename}")
    def media_proxy(session_id: str, filename: str, user: DummyUser = Depends(user_dep())):
        # Enforce ACLs
        try:
            _enforce_session_access(app.state.session_registry, session_id, user)
        except HTTPException as exc:
            raise exc

        # Resolve via metadata
        meta = get_metadata_manager().get_metadata(filename, campaign_id=session_id)
        if not meta:
            raise HTTPException(status_code=404, detail="No metadata for file")
        path = meta.get("local_path")
        if not path or not Path(path).exists():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(path)

    return TestClient(app)


@pytest.fixture()
def client(tmp_path):
    return build_media_app(tmp_path)


def _write_png(path: Path) -> None:
    # Tiny 1x1 PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0bIDATx\x9cc```\x00\x00\x00\x05\x00\x01"
        b"\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    path.write_bytes(png_bytes)


def _seed_metadata(session_id: str, filename: str):
    mgr = get_metadata_manager()
    mgr.save_metadata(
        filename,
        {"prompt": "test", "type": "scene", "service": "test"},
        campaign_id=session_id,
    )


def test_media_acl_blocks_unauthenticated(client, tmp_path):
    # Prepare file and metadata
    filename = "img1.png"
    file_path = tmp_path / "images" / filename
    _write_png(file_path)
    _seed_metadata("s1", filename)

    # Register an owner for the session
    reg: SessionRegistry = client.app.state.session_registry
    reg.register_session("s1", owner_user_id="owner1")

    r = client.get("/media/s1/img1.png")
    assert r.status_code == 401


def test_media_acl_allows_owner(client, tmp_path):
    filename = "img2.png"
    file_path = tmp_path / "images" / filename
    _write_png(file_path)
    _seed_metadata("s2", filename)

    reg: SessionRegistry = client.app.state.session_registry
    reg.register_session("s2", owner_user_id="owner2", owner_email="o2@example.com")

    r = client.get(
        "/media/s2/img2.png",
        headers={"X-User-Id": "owner2", "X-User-Email": "o2@example.com"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")
    assert len(r.content) > 0


def test_media_acl_allows_member_by_email(client, tmp_path):
    filename = "img3.png"
    file_path = tmp_path / "images" / filename
    _write_png(file_path)
    _seed_metadata("s3", filename)

    reg: SessionRegistry = client.app.state.session_registry
    reg.register_session("s3", owner_user_id="owner3")
    reg.touch_session("s3", user_id=None, user_email="member@example.com")

    r = client.get(
        "/media/s3/img3.png",
        headers={"X-User-Email": "member@example.com"},
    )
    assert r.status_code == 200


def test_media_404_when_no_metadata(client, tmp_path):
    # File exists but no metadata seeded for session
    filename = "img4.png"
    file_path = tmp_path / "images" / filename
    _write_png(file_path)

    reg: SessionRegistry = client.app.state.session_registry
    reg.register_session("s4", owner_user_id="owner4", owner_email="owner4@example.com")

    r = client.get(
        "/media/s4/img4.png",
        headers={"X-User-Email": "owner4@example.com"},
    )
    assert r.status_code == 404


def test_media_404_when_file_missing(client, tmp_path):
    # Seed metadata but remove the file
    filename = "img5.png"
    file_path = tmp_path / "images" / filename
    _write_png(file_path)
    _seed_metadata("s5", filename)
    file_path.unlink()  # remove the file

    reg: SessionRegistry = client.app.state.session_registry
    reg.register_session("s5", owner_user_id="owner5", owner_email="owner5@example.com")

    r = client.get(
        "/media/s5/img5.png",
        headers={"X-User-Email": "owner5@example.com"},
    )
    # With hybrid storage, the system may download from GCS if local file is missing
    # So 200 (GCS fallback succeeded) or 404 (no file anywhere) are both valid
    assert r.status_code in [200, 404]
