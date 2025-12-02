"""Session isolation tests for WebSocket broadcasting (combat and non-combat)."""

import pytest
from typing import Any, List
from unittest.mock import AsyncMock

from starlette.websockets import WebSocketState

from gaia.connection.websocket.campaign_broadcaster import CampaignBroadcaster


class FakeWebSocket:
    """Minimal WebSocket stub capturing JSON payloads."""

    def __init__(self) -> None:
        self._messages: List[Any] = []
        self._accepted = False
        self._closed = False
        self._close_code = None
        self._close_reason = None

    async def accept(self) -> None:  # noqa: D401
        self._accepted = True

    async def send_json(self, data: Any) -> None:  # noqa: D401
        if self._closed:
            raise RuntimeError("WebSocket is closed")
        self._messages.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:  # noqa: D401
        self._closed = True
        self._close_code = code
        self._close_reason = reason

    @property
    def client_state(self):  # noqa: D401
        return WebSocketState.CONNECTED if (self._accepted and not self._closed) else WebSocketState.DISCONNECTED

    # Helpers for assertions
    @property
    def messages(self) -> List[Any]:
        return list(self._messages)


@pytest.mark.asyncio
async def test_non_combat_broadcast_isolation():
    """Broadcast to one session should not reach others (non-combat generic update)."""
    broadcaster = CampaignBroadcaster()
    # Avoid network calls during connect_player
    broadcaster._load_current_campaign_state = AsyncMock(return_value=None)

    # Session A: two players
    ws_a1, ws_a2 = FakeWebSocket(), FakeWebSocket()
    await broadcaster.connect_player(ws_a1, session_id="sessionA", user_id="u1")
    await broadcaster.connect_player(ws_a2, session_id="sessionA", user_id="u2")

    # Session B: one player
    ws_b1 = FakeWebSocket()
    await broadcaster.connect_player(ws_b1, session_id="sessionB", user_id="u3")

    # Broadcast update for session A only
    payload = {"campaign_id": "sessionA", "structured_data": {"answer": "Hello"}}
    await broadcaster.broadcast_campaign_update("sessionA", "campaign_updated", payload)

    # Expect A players to receive the message
    assert any(m.get("type") == "campaign_updated" and m.get("campaign_id") == "sessionA" for m in ws_a1.messages)
    assert any(m.get("type") == "campaign_updated" and m.get("campaign_id") == "sessionA" for m in ws_a2.messages)
    # B should not receive it
    assert not any(m.get("type") == "campaign_updated" for m in ws_b1.messages)


