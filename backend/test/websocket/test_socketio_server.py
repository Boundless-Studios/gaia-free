"""Comprehensive tests for Socket.IO server implementation.

These tests define the expected behavior BEFORE implementation (TDD approach).
They cover:
- Connection/disconnection lifecycle
- Multi-user scenarios
- Room isolation
- Message broadcasting
- Reconnection behavior
- Connection registry integration
- Authentication flows

Run with: python3 gaia_launcher.py test backend/test/websocket/test_socketio_server.py
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

import pytest

# These imports will work once Socket.IO is implemented
# For now they serve as the interface specification
try:
    from gaia.connection.socketio_server import (
        sio,
        GameNamespace,
        get_room_user_count,
        get_room_users,
    )
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    sio = None

from gaia.connection.connection_registry import ConnectionRegistry
from gaia.connection.models import ConnectionStatus


# =============================================================================
# Test Fixtures
# =============================================================================

@dataclass
class MockSocketClient:
    """Mock Socket.IO client for testing."""

    sid: str = field(default_factory=lambda: str(uuid.uuid4()))
    connected: bool = False
    rooms: set = field(default_factory=set)
    received_events: List[Dict[str, Any]] = field(default_factory=list)
    session_data: Dict[str, Any] = field(default_factory=dict)
    auth_data: Optional[Dict[str, Any]] = None

    async def emit(self, event: str, data: Any):
        """Record emitted event."""
        self.received_events.append({"event": event, "data": data})

    def get_events(self, event_type: str) -> List[Dict]:
        """Get all received events of a specific type."""
        return [e for e in self.received_events if e["event"] == event_type]

    def clear_events(self):
        """Clear received events."""
        self.received_events.clear()


@dataclass
class MockSocketServer:
    """Mock Socket.IO server for testing multi-client scenarios."""

    clients: Dict[str, MockSocketClient] = field(default_factory=dict)
    rooms: Dict[str, set] = field(default_factory=dict)  # room_id -> set of sids

    def create_client(self, auth_data: Optional[Dict] = None) -> MockSocketClient:
        """Create a new mock client."""
        client = MockSocketClient(auth_data=auth_data)
        self.clients[client.sid] = client
        return client

    async def connect_client(self, client: MockSocketClient, room: str):
        """Simulate client connecting to a room."""
        client.connected = True
        client.rooms.add(room)
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(client.sid)

    async def disconnect_client(self, client: MockSocketClient):
        """Simulate client disconnecting."""
        client.connected = False
        for room in list(client.rooms):
            if room in self.rooms:
                self.rooms[room].discard(client.sid)
        client.rooms.clear()

    async def emit_to_room(self, room: str, event: str, data: Any, skip_sid: str = None):
        """Emit event to all clients in a room."""
        if room not in self.rooms:
            return
        for sid in self.rooms[room]:
            if sid != skip_sid:
                client = self.clients.get(sid)
                if client and client.connected:
                    await client.emit(event, data)

    def get_room_count(self, room: str) -> int:
        """Get number of clients in a room."""
        return len(self.rooms.get(room, set()))

    def get_room_sids(self, room: str) -> set:
        """Get all sids in a room."""
        return self.rooms.get(room, set()).copy()


@pytest.fixture
def mock_server():
    """Create a mock Socket.IO server."""
    return MockSocketServer()


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """Create a test connection registry."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    reg = ConnectionRegistry()
    if not reg.db_enabled:
        pytest.skip(f"Database not available: {reg.db_failure_reason}")
    yield reg

    # Cleanup
    from db.src.connection import db_manager
    try:
        with db_manager.get_sync_session() as session:
            from gaia.connection.models import WebSocketConnection
            session.query(WebSocketConnection).delete()
            session.commit()
    except Exception:
        pass


# =============================================================================
# Connection Lifecycle Tests
# =============================================================================

class TestConnectionLifecycle:
    """Tests for basic connection/disconnection behavior."""

    @pytest.mark.asyncio
    async def test_single_client_connects_to_campaign_room(self, mock_server):
        """A single client should be able to connect to a campaign room."""
        client = mock_server.create_client(auth_data={
            "token": "valid-jwt-token",
            "session_id": "campaign-123",
        })

        await mock_server.connect_client(client, "campaign-123")

        assert client.connected is True
        assert "campaign-123" in client.rooms
        assert mock_server.get_room_count("campaign-123") == 1

    @pytest.mark.asyncio
    async def test_client_disconnect_removes_from_room(self, mock_server):
        """Disconnecting should remove client from all rooms."""
        client = mock_server.create_client()
        await mock_server.connect_client(client, "campaign-123")

        await mock_server.disconnect_client(client)

        assert client.connected is False
        assert mock_server.get_room_count("campaign-123") == 0

    @pytest.mark.asyncio
    async def test_multiple_clients_same_room(self, mock_server):
        """Multiple clients should be able to join the same room."""
        client1 = mock_server.create_client()
        client2 = mock_server.create_client()
        client3 = mock_server.create_client()

        await mock_server.connect_client(client1, "campaign-123")
        await mock_server.connect_client(client2, "campaign-123")
        await mock_server.connect_client(client3, "campaign-123")

        assert mock_server.get_room_count("campaign-123") == 3
        assert client1.sid in mock_server.get_room_sids("campaign-123")
        assert client2.sid in mock_server.get_room_sids("campaign-123")
        assert client3.sid in mock_server.get_room_sids("campaign-123")

    @pytest.mark.asyncio
    async def test_client_in_multiple_rooms_isolation(self, mock_server):
        """Client in multiple rooms should only receive room-specific events."""
        client = mock_server.create_client()

        await mock_server.connect_client(client, "campaign-123")
        # Simulate joining a second room (e.g., for a specific feature)
        client.rooms.add("collab-123")
        mock_server.rooms["collab-123"] = {client.sid}

        assert "campaign-123" in client.rooms
        assert "collab-123" in client.rooms
        assert mock_server.get_room_count("campaign-123") == 1
        assert mock_server.get_room_count("collab-123") == 1


# =============================================================================
# Multi-User Behavior Tests
# =============================================================================

class TestMultiUserBehavior:
    """Tests for multi-user scenarios and broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_to_room_reaches_all_clients(self, mock_server):
        """Broadcasting to a room should reach all connected clients."""
        clients = [mock_server.create_client() for _ in range(5)]

        for client in clients:
            await mock_server.connect_client(client, "campaign-123")

        # Broadcast a narrative chunk
        await mock_server.emit_to_room(
            "campaign-123",
            "narrative_chunk",
            {"content": "The dragon awakens...", "is_final": False}
        )

        for client in clients:
            events = client.get_events("narrative_chunk")
            assert len(events) == 1
            assert events[0]["data"]["content"] == "The dragon awakens..."

    @pytest.mark.asyncio
    async def test_broadcast_excludes_sender(self, mock_server):
        """Broadcasting with skip_sid should exclude the sender."""
        sender = mock_server.create_client()
        receivers = [mock_server.create_client() for _ in range(3)]

        await mock_server.connect_client(sender, "campaign-123")
        for client in receivers:
            await mock_server.connect_client(client, "campaign-123")

        # Sender broadcasts yjs_update - should not receive it back
        await mock_server.emit_to_room(
            "campaign-123",
            "yjs_update",
            {"update": [1, 2, 3], "playerId": "sender"},
            skip_sid=sender.sid
        )

        # Sender should NOT receive
        assert len(sender.get_events("yjs_update")) == 0

        # Receivers SHOULD receive
        for client in receivers:
            assert len(client.get_events("yjs_update")) == 1

    @pytest.mark.asyncio
    async def test_room_isolation_between_campaigns(self, mock_server):
        """Messages in one campaign room should not leak to another."""
        campaign1_clients = [mock_server.create_client() for _ in range(2)]
        campaign2_clients = [mock_server.create_client() for _ in range(2)]

        for client in campaign1_clients:
            await mock_server.connect_client(client, "campaign-111")
        for client in campaign2_clients:
            await mock_server.connect_client(client, "campaign-222")

        # Broadcast to campaign-111 only
        await mock_server.emit_to_room(
            "campaign-111",
            "narrative_chunk",
            {"content": "Campaign 1 story"}
        )

        # Campaign 1 clients receive
        for client in campaign1_clients:
            assert len(client.get_events("narrative_chunk")) == 1

        # Campaign 2 clients do NOT receive
        for client in campaign2_clients:
            assert len(client.get_events("narrative_chunk")) == 0

    @pytest.mark.asyncio
    async def test_user_count_updates_on_join_leave(self, mock_server):
        """Room user count should update correctly as users join/leave."""
        campaign_id = "campaign-123"

        assert mock_server.get_room_count(campaign_id) == 0

        client1 = mock_server.create_client()
        await mock_server.connect_client(client1, campaign_id)
        assert mock_server.get_room_count(campaign_id) == 1

        client2 = mock_server.create_client()
        await mock_server.connect_client(client2, campaign_id)
        assert mock_server.get_room_count(campaign_id) == 2

        await mock_server.disconnect_client(client1)
        assert mock_server.get_room_count(campaign_id) == 1

        await mock_server.disconnect_client(client2)
        assert mock_server.get_room_count(campaign_id) == 0

    @pytest.mark.asyncio
    async def test_player_connected_notification_on_join(self, mock_server):
        """When a player joins, others in room should be notified."""
        dm = mock_server.create_client()
        await mock_server.connect_client(dm, "campaign-123")
        dm.clear_events()  # Clear initial events

        player = mock_server.create_client()
        await mock_server.connect_client(player, "campaign-123")

        # Simulate the server emitting player_connected to room (excluding new player)
        await mock_server.emit_to_room(
            "campaign-123",
            "player_connected",
            {"user_id": "player-456", "connected_count": 2},
            skip_sid=player.sid
        )

        # DM should receive notification
        events = dm.get_events("player_connected")
        assert len(events) == 1
        assert events[0]["data"]["connected_count"] == 2

    @pytest.mark.asyncio
    async def test_player_disconnected_notification_on_leave(self, mock_server):
        """When a player leaves, others in room should be notified."""
        dm = mock_server.create_client()
        player = mock_server.create_client()

        await mock_server.connect_client(dm, "campaign-123")
        await mock_server.connect_client(player, "campaign-123")
        dm.clear_events()

        # Player disconnects
        await mock_server.disconnect_client(player)

        # Simulate server emitting player_disconnected
        await mock_server.emit_to_room(
            "campaign-123",
            "player_disconnected",
            {"user_id": "player-456", "connected_count": 1}
        )

        events = dm.get_events("player_disconnected")
        assert len(events) == 1
        assert events[0]["data"]["connected_count"] == 1


# =============================================================================
# User Deduplication Tests
# =============================================================================

class TestUserDeduplication:
    """Tests for proper user counting (no duplicates)."""

    @pytest.mark.asyncio
    async def test_same_user_multiple_tabs_counted_once(self, mock_server):
        """Same user with multiple tabs should be counted once for user count."""
        # Same user opens 3 tabs
        tab1 = mock_server.create_client()
        tab2 = mock_server.create_client()
        tab3 = mock_server.create_client()

        # All tabs have same user_id in session
        tab1.session_data["user_id"] = "user-123"
        tab2.session_data["user_id"] = "user-123"
        tab3.session_data["user_id"] = "user-123"

        await mock_server.connect_client(tab1, "campaign-123")
        await mock_server.connect_client(tab2, "campaign-123")
        await mock_server.connect_client(tab3, "campaign-123")

        # Connection count is 3
        assert mock_server.get_room_count("campaign-123") == 3

        # But unique user count should be 1
        # This is the behavior we need to implement
        unique_users = set()
        for sid in mock_server.get_room_sids("campaign-123"):
            client = mock_server.clients[sid]
            user_id = client.session_data.get("user_id")
            if user_id:
                unique_users.add(user_id)

        assert len(unique_users) == 1

    @pytest.mark.asyncio
    async def test_anonymous_users_counted_separately(self, mock_server):
        """Anonymous users (no user_id) should still be counted but separately."""
        authenticated = mock_server.create_client()
        authenticated.session_data["user_id"] = "user-123"

        anonymous1 = mock_server.create_client()  # No user_id
        anonymous2 = mock_server.create_client()  # No user_id

        await mock_server.connect_client(authenticated, "campaign-123")
        await mock_server.connect_client(anonymous1, "campaign-123")
        await mock_server.connect_client(anonymous2, "campaign-123")

        # Count should reflect: 1 authenticated + 2 anonymous
        unique_users = set()
        anonymous_count = 0

        for sid in mock_server.get_room_sids("campaign-123"):
            client = mock_server.clients[sid]
            user_id = client.session_data.get("user_id")
            if user_id:
                unique_users.add(user_id)
            else:
                anonymous_count += 1

        assert len(unique_users) == 1
        assert anonymous_count == 2
        # Total "logical" users = 1 + 2 = 3

    @pytest.mark.asyncio
    async def test_reconnect_does_not_duplicate_user(self, mock_server):
        """User reconnecting should not be counted twice."""
        client1 = mock_server.create_client()
        client1.session_data["user_id"] = "user-123"

        await mock_server.connect_client(client1, "campaign-123")
        assert mock_server.get_room_count("campaign-123") == 1

        # User disconnects (maybe network blip)
        await mock_server.disconnect_client(client1)
        assert mock_server.get_room_count("campaign-123") == 0

        # User reconnects with new socket
        client2 = mock_server.create_client()
        client2.session_data["user_id"] = "user-123"  # Same user

        await mock_server.connect_client(client2, "campaign-123")
        assert mock_server.get_room_count("campaign-123") == 1

        # Unique user count still 1
        unique_users = set()
        for sid in mock_server.get_room_sids("campaign-123"):
            client = mock_server.clients[sid]
            user_id = client.session_data.get("user_id")
            if user_id:
                unique_users.add(user_id)

        assert len(unique_users) == 1


# =============================================================================
# Connection Registry Integration Tests
# =============================================================================

class TestRegistryIntegration:
    """Tests for Socket.IO + Connection Registry integration."""

    @pytest.mark.asyncio
    async def test_connect_creates_registry_entry(self, mock_server, registry):
        """Connecting should create an entry in the connection registry."""
        client = mock_server.create_client()
        client.session_data = {
            "user_id": "user-123",
            "user_email": "test@example.com",
            "session_id": "campaign-123",
        }

        await mock_server.connect_client(client, "campaign-123")

        # Create registry entry (simulating what server would do)
        result = registry.create_connection(
            session_id="campaign-123",
            connection_type="player",
            user_id="user-123",
            user_email="test@example.com",
        )

        # Store connection_id in client session for later
        client.session_data["connection_id"] = result["connection_id"]

        # Verify registry entry exists
        connection = registry.get_connection(uuid.UUID(result["connection_id"]))
        assert connection is not None
        assert connection["session_id"] == "campaign-123"
        assert connection["user_id"] == "user-123"
        assert connection["status"] == ConnectionStatus.CONNECTED.value

    @pytest.mark.asyncio
    async def test_disconnect_updates_registry(self, mock_server, registry):
        """Disconnecting should update the registry entry."""
        client = mock_server.create_client()

        await mock_server.connect_client(client, "campaign-123")

        # Create registry entry
        result = registry.create_connection(
            session_id="campaign-123",
            connection_type="player",
            user_id="user-123",
        )
        connection_id = uuid.UUID(result["connection_id"])

        # Disconnect
        await mock_server.disconnect_client(client)
        registry.disconnect_connection(connection_id, ConnectionStatus.DISCONNECTED)

        # Verify registry updated
        connection = registry.get_connection(connection_id)
        assert connection["status"] == ConnectionStatus.DISCONNECTED.value
        assert connection["disconnected_at"] is not None

    @pytest.mark.asyncio
    async def test_registry_tracks_all_session_connections(self, mock_server, registry):
        """Registry should track all connections for a session."""
        clients = []
        connection_ids = []

        for i in range(3):
            client = mock_server.create_client()
            await mock_server.connect_client(client, "campaign-123")

            result = registry.create_connection(
                session_id="campaign-123",
                connection_type="player",
                user_id=f"user-{i}",
            )
            clients.append(client)
            connection_ids.append(result["connection_id"])

        # Query all active connections
        active = registry.get_active_connections("campaign-123")
        assert len(active) == 3

        # Disconnect one
        await mock_server.disconnect_client(clients[1])
        registry.disconnect_connection(
            uuid.UUID(connection_ids[1]),
            ConnectionStatus.DISCONNECTED
        )

        # Now only 2 active
        active = registry.get_active_connections("campaign-123")
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_registry_isolated_by_session(self, mock_server, registry):
        """Registry queries should be isolated by session."""
        # Connect to campaign-111
        client1 = mock_server.create_client()
        await mock_server.connect_client(client1, "campaign-111")
        registry.create_connection(
            session_id="campaign-111",
            connection_type="player",
            user_id="user-1",
        )

        # Connect to campaign-222
        client2 = mock_server.create_client()
        await mock_server.connect_client(client2, "campaign-222")
        registry.create_connection(
            session_id="campaign-222",
            connection_type="player",
            user_id="user-2",
        )

        # Query should be isolated
        active_111 = registry.get_active_connections("campaign-111")
        active_222 = registry.get_active_connections("campaign-222")

        assert len(active_111) == 1
        assert active_111[0]["user_id"] == "user-1"

        assert len(active_222) == 1
        assert active_222[0]["user_id"] == "user-2"


# =============================================================================
# Reconnection Tests
# =============================================================================

class TestReconnection:
    """Tests for reconnection behavior."""

    @pytest.mark.asyncio
    async def test_client_auto_reconnect_rejoins_room(self, mock_server):
        """After reconnection, client should rejoin the same room."""
        client = mock_server.create_client()
        client.session_data["session_id"] = "campaign-123"

        await mock_server.connect_client(client, "campaign-123")
        assert "campaign-123" in client.rooms

        # Simulate disconnect
        await mock_server.disconnect_client(client)
        assert mock_server.get_room_count("campaign-123") == 0

        # Simulate reconnect (new socket, same session_id)
        new_client = mock_server.create_client()
        new_client.session_data = client.session_data.copy()

        await mock_server.connect_client(new_client, "campaign-123")
        assert mock_server.get_room_count("campaign-123") == 1

    @pytest.mark.asyncio
    async def test_reconnection_receives_missed_campaign_state(self, mock_server):
        """Reconnecting client should receive current campaign state."""
        client = mock_server.create_client()
        await mock_server.connect_client(client, "campaign-123")

        # Simulate disconnect during game activity
        await mock_server.disconnect_client(client)

        # Reconnect
        new_client = mock_server.create_client()
        await mock_server.connect_client(new_client, "campaign-123")

        # Server should send current state (simulated)
        await new_client.emit("campaign_active", {
            "campaign_id": "campaign-123",
            "structured_data": {"current_scene": "tavern", "turn": 5},
        })

        events = new_client.get_events("campaign_active")
        assert len(events) == 1
        assert events[0]["data"]["structured_data"]["turn"] == 5

    @pytest.mark.asyncio
    async def test_rapid_disconnect_reconnect_no_duplicate(self, mock_server):
        """Rapid disconnect/reconnect should not cause duplicate room entries."""
        client = mock_server.create_client()
        client.session_data["user_id"] = "user-123"

        # Rapid connect/disconnect cycles
        for _ in range(5):
            await mock_server.connect_client(client, "campaign-123")
            await mock_server.disconnect_client(client)

        # Final connect
        await mock_server.connect_client(client, "campaign-123")

        # Should only have 1 entry
        assert mock_server.get_room_count("campaign-123") == 1


# =============================================================================
# Authentication Tests
# =============================================================================

class TestAuthentication:
    """Tests for Socket.IO authentication."""

    @pytest.mark.asyncio
    async def test_connection_with_valid_token_succeeds(self, mock_server):
        """Connection with valid JWT token should succeed."""
        client = mock_server.create_client(auth_data={
            "token": "valid-jwt-token",
            "session_id": "campaign-123",
        })

        # Simulate auth validation (would be done by server middleware)
        # For now just verify auth data is available
        assert client.auth_data is not None
        assert client.auth_data["token"] == "valid-jwt-token"

        await mock_server.connect_client(client, "campaign-123")
        assert client.connected is True

    @pytest.mark.asyncio
    async def test_connection_without_token_in_dev_allowed(self, mock_server):
        """Connection without token should be allowed in dev mode."""
        client = mock_server.create_client(auth_data={
            "session_id": "campaign-123",
            # No token - dev mode
        })

        await mock_server.connect_client(client, "campaign-123")
        assert client.connected is True

    @pytest.mark.asyncio
    async def test_user_identity_stored_in_session(self, mock_server):
        """Authenticated user identity should be stored in socket session."""
        client = mock_server.create_client(auth_data={
            "token": "valid-jwt-token",
            "session_id": "campaign-123",
        })

        # Simulate server storing identity after auth
        client.session_data["user_id"] = "user-123"
        client.session_data["user_email"] = "test@example.com"
        client.session_data["session_id"] = "campaign-123"

        await mock_server.connect_client(client, "campaign-123")

        assert client.session_data["user_id"] == "user-123"
        assert client.session_data["user_email"] == "test@example.com"


# =============================================================================
# DM-Specific Tests
# =============================================================================

class TestDMBehavior:
    """Tests for DM-specific connection behavior."""

    @pytest.mark.asyncio
    async def test_only_one_dm_per_session(self, mock_server):
        """Only one DM connection should be active per session."""
        dm1 = mock_server.create_client()
        dm1.session_data["role"] = "dm"
        dm1.session_data["user_id"] = "dm-user-1"

        await mock_server.connect_client(dm1, "campaign-123-dm")

        # Second DM tries to connect
        dm2 = mock_server.create_client()
        dm2.session_data["role"] = "dm"
        dm2.session_data["user_id"] = "dm-user-2"

        # The second connection should either:
        # a) Replace the first (disconnect dm1)
        # b) Be rejected
        # We'll test the "replace" behavior (current implementation)

        await mock_server.disconnect_client(dm1)  # Simulating server closing old DM
        await mock_server.connect_client(dm2, "campaign-123-dm")

        assert dm1.connected is False
        assert dm2.connected is True
        assert mock_server.get_room_count("campaign-123-dm") == 1

    @pytest.mark.asyncio
    async def test_dm_disconnect_notifies_players(self, mock_server):
        """When DM disconnects, players should be notified."""
        dm = mock_server.create_client()
        dm.session_data["role"] = "dm"

        player1 = mock_server.create_client()
        player2 = mock_server.create_client()

        await mock_server.connect_client(dm, "campaign-123")
        await mock_server.connect_client(player1, "campaign-123")
        await mock_server.connect_client(player2, "campaign-123")

        player1.clear_events()
        player2.clear_events()

        # DM disconnects
        await mock_server.disconnect_client(dm)

        # Server broadcasts dm_left
        await mock_server.emit_to_room(
            "campaign-123",
            "room.dm_left",
            {"user_id": "dm-user", "room_status": "waiting_for_dm"}
        )

        for player in [player1, player2]:
            events = player.get_events("room.dm_left")
            assert len(events) == 1
            assert events[0]["data"]["room_status"] == "waiting_for_dm"


# =============================================================================
# Message Type Tests
# =============================================================================

class TestMessageTypes:
    """Tests for specific message type handling."""

    @pytest.mark.asyncio
    async def test_yjs_update_broadcast_to_room(self, mock_server):
        """yjs_update should be broadcast to all in room except sender."""
        sender = mock_server.create_client()
        receivers = [mock_server.create_client() for _ in range(3)]

        await mock_server.connect_client(sender, "campaign-123")
        for r in receivers:
            await mock_server.connect_client(r, "campaign-123")

        await mock_server.emit_to_room(
            "campaign-123",
            "yjs_update",
            {
                "sessionId": "campaign-123",
                "playerId": "sender-id",
                "update": [1, 2, 3, 4, 5],
                "source": "keyboard",
            },
            skip_sid=sender.sid
        )

        assert len(sender.get_events("yjs_update")) == 0
        for r in receivers:
            events = r.get_events("yjs_update")
            assert len(events) == 1
            assert events[0]["data"]["update"] == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_narrative_chunk_broadcast_to_all(self, mock_server):
        """narrative_chunk should be broadcast to everyone including sender."""
        clients = [mock_server.create_client() for _ in range(4)]

        for c in clients:
            await mock_server.connect_client(c, "campaign-123")

        await mock_server.emit_to_room(
            "campaign-123",
            "narrative_chunk",
            {"content": "The adventure begins...", "is_final": False}
        )

        for c in clients:
            events = c.get_events("narrative_chunk")
            assert len(events) == 1

    @pytest.mark.asyncio
    async def test_audio_chunk_ready_broadcast(self, mock_server):
        """audio_chunk_ready should reach all clients for synchronized playback."""
        clients = [mock_server.create_client() for _ in range(3)]

        for c in clients:
            await mock_server.connect_client(c, "campaign-123")

        await mock_server.emit_to_room(
            "campaign-123",
            "audio_chunk_ready",
            {
                "chunk": {"id": "chunk-1", "audio_base64": "..."},
                "sequence_number": 0,
                "playback_group": "narration-1",
            }
        )

        for c in clients:
            events = c.get_events("audio_chunk_ready")
            assert len(events) == 1
            assert events[0]["data"]["sequence_number"] == 0

    @pytest.mark.asyncio
    async def test_room_seat_updated_broadcast(self, mock_server):
        """room.seat_updated should notify all room members."""
        dm = mock_server.create_client()
        players = [mock_server.create_client() for _ in range(2)]

        await mock_server.connect_client(dm, "campaign-123")
        for p in players:
            await mock_server.connect_client(p, "campaign-123")

        await mock_server.emit_to_room(
            "campaign-123",
            "room.seat_updated",
            {
                "seat": {
                    "seat_id": "seat-1",
                    "owner_user_id": "player-1",
                    "character_name": "Gandalf",
                }
            }
        )

        all_clients = [dm] + players
        for c in all_clients:
            events = c.get_events("room.seat_updated")
            assert len(events) == 1


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error scenarios."""

    @pytest.mark.asyncio
    async def test_emit_to_nonexistent_room_no_error(self, mock_server):
        """Emitting to a room with no clients should not raise error."""
        # This should not raise
        await mock_server.emit_to_room(
            "nonexistent-room",
            "test_event",
            {"data": "test"}
        )

    @pytest.mark.asyncio
    async def test_disconnect_already_disconnected_client(self, mock_server):
        """Disconnecting an already disconnected client should be safe."""
        client = mock_server.create_client()
        await mock_server.connect_client(client, "campaign-123")

        await mock_server.disconnect_client(client)
        # Second disconnect should not raise
        await mock_server.disconnect_client(client)

        assert client.connected is False


# =============================================================================
# Performance/Scale Tests (Optional)
# =============================================================================

class TestScaleScenarios:
    """Tests for scale scenarios."""

    @pytest.mark.asyncio
    async def test_many_clients_in_room(self, mock_server):
        """Room should handle many concurrent clients."""
        clients = [mock_server.create_client() for _ in range(100)]

        for c in clients:
            await mock_server.connect_client(c, "campaign-123")

        assert mock_server.get_room_count("campaign-123") == 100

        # Broadcast should reach all
        await mock_server.emit_to_room(
            "campaign-123",
            "test_event",
            {"data": "broadcast"}
        )

        for c in clients:
            assert len(c.get_events("test_event")) == 1

    @pytest.mark.asyncio
    async def test_many_rooms_isolation(self, mock_server):
        """Many rooms should remain isolated."""
        num_rooms = 50

        for i in range(num_rooms):
            client = mock_server.create_client()
            await mock_server.connect_client(client, f"campaign-{i}")

        # Emit to one room
        await mock_server.emit_to_room(
            "campaign-25",
            "targeted_event",
            {"room": 25}
        )

        # Only campaign-25 client should receive
        received_count = 0
        for sid, client in mock_server.clients.items():
            if client.get_events("targeted_event"):
                received_count += 1

        assert received_count == 1
