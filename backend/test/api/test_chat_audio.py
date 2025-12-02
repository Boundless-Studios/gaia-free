"""API tests for chat audio payloads."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace

from gaia.api.routes.chat import router as chat_router
from gaia.infra.audio.auto_tts_service import auto_tts_service
from auth.src.flexible_auth import optional_auth
from db.src import get_async_db


@pytest.fixture
def chat_app_client():
    app = FastAPI()
    app.include_router(chat_router)

    orchestrator_mock = AsyncMock()
    orchestrator_mock.run_campaign = AsyncMock(return_value={
        "campaign_id": "session-123",
        "structured_data": {
            "answer": "The DM responds.",
        }
    })
    app.state.orchestrator = orchestrator_mock

    fake_user = SimpleNamespace(user_id=uuid4(), is_admin=False)

    app.dependency_overrides[optional_auth] = lambda: fake_user

    class DummyResult:
        def first(self):
            return object()

    class DummyDB:
        async def execute(self, _stmt):
            return DummyResult()

    async def override_db():
        yield DummyDB()

    app.dependency_overrides[get_async_db] = override_db

    return TestClient(app)


@patch('gaia.api.routes.chat.room_access_guard')
def test_chat_endpoint_no_auto_audio_generation(mock_guard, chat_app_client):
    """Test that chat endpoint does NOT auto-generate audio.

    Audio generation is now manual/on-demand only via TTS API endpoints.
    The chat endpoint should return structured data without audio payload.
    """
    # Mock room access guard methods to allow test to proceed
    mock_guard.ensure_dm_present.return_value = None
    mock_guard.ensure_player_has_character.return_value = None

    auto_tts_service.client_audio_enabled = True

    try:
        response = chat_app_client.post(
            "/api/chat",
            json={
                "message": "Test",
                "session_id": "session-123",
            }
        )
    finally:
        auto_tts_service.client_audio_enabled = False

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True

    # Verify no audio payload is included (auto-generation disabled)
    structured_data = body["message"]["structured_data"]
    assert "audio" not in structured_data or structured_data["audio"] is None
