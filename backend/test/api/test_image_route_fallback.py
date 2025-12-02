"""Tests for `/api/images/{filename:path}` fallback behaviour."""

import os
from pathlib import Path

import pytest

from gaia.api.app import serve_image
from gaia.infra.image.image_artifact_store import image_artifact_store
from gaia.infra.image.image_metadata import get_metadata_manager


def _write_png(path: Path) -> None:
    """Write a 1x1 transparent PNG for testing."""
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc````\x00\x00\x00\x04"
        b"\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    path.write_bytes(png_bytes)


@pytest.mark.asyncio
async def test_serve_image_fallback_reads_from_artifact_store(tmp_path, test_campaign_storage):
    """Ensure route serves files via artifact store when metadata/local lookup fails."""
    # Redirect image storage to tmp path and reset metadata singleton
    image_root = tmp_path / "images"
    image_root.mkdir(parents=True, exist_ok=True)

    original_env = os.environ.get("IMAGE_STORAGE_PATH")
    os.environ["IMAGE_STORAGE_PATH"] = str(image_root)
    # Touch metadata manager so it re-initializes with new root
    get_metadata_manager()

    # Point artifact store at tmp path
    original_root = image_artifact_store.local_root
    image_artifact_store.local_root = image_root

    try:
        session_id = "campaign_999"
        filename = "runware_image_test.png"
        portrait_dir = image_root / session_id / "portraits"
        portrait_dir.mkdir(parents=True, exist_ok=True)
        _write_png(portrait_dir / filename)

        path = f"media/images/{session_id}/portraits/{filename}"
        response = await serve_image(path, current_user=None)

        assert response.status_code == 200
        assert response.media_type == "image/png"
        # Response has been rendered with bytes content
        assert response.body is not None and len(response.body) > 0
        assert response.headers.get("Cache-Control") == "public, max-age=31536000, immutable"
    finally:
        # Restore globals/env
        image_artifact_store.local_root = original_root
        if original_env is not None:
            os.environ["IMAGE_STORAGE_PATH"] = original_env
        else:
            os.environ.pop("IMAGE_STORAGE_PATH", None)
