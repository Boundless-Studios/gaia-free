"""Tests for WebSocket connection registry."""

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from gaia.connection.connection_registry import ConnectionRegistry, connection_registry
from gaia.connection.models import ConnectionStatus
from gaia.connection.connection_playback_tracker import ConnectionPlaybackTracker, connection_playback_tracker


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """Create a test connection registry with database enabled."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    reg = ConnectionRegistry()
    if not reg.db_enabled:
        pytest.skip(f"Database not available: {reg.db_failure_reason}")
    yield reg

    # Cleanup: Delete all connections after test
    from db.src.connection import db_manager
    try:
        with db_manager.get_sync_session() as session:
            from gaia.connection.models import WebSocketConnection
            session.query(WebSocketConnection).delete()
            session.commit()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def playback_tracker(monkeypatch):
    """Create a test playback tracker with database enabled."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    tracker = ConnectionPlaybackTracker()
    if not tracker.db_enabled:
        pytest.skip(f"Database not available: {tracker.db_failure_reason}")
    yield tracker

    # Cleanup: Delete all playback state after test
    from db.src.connection import db_manager
    try:
        with db_manager.get_sync_session() as session:
            from gaia.connection.models import ConnectionPlaybackState
            session.query(ConnectionPlaybackState).delete()
            session.commit()
    except Exception:
        pass  # Ignore cleanup errors


def test_create_connection(registry):
    """Test creating a new WebSocket connection."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
        user_id="user-123",
        user_email="test@example.com",
        origin="https://example.com",
        user_agent="Mozilla/5.0",
        client_ip="192.168.1.1",
    )

    assert "connection_id" in result
    assert "connection_token" in result
    assert len(result["connection_token"]) > 20  # Should be a secure token

    # Verify connection was stored
    connection = registry.get_connection(uuid.UUID(result["connection_id"]))
    assert connection is not None
    assert connection["session_id"] == "test-session"
    assert connection["user_id"] == "user-123"
    assert connection["connection_type"] == "player"
    assert connection["status"] == ConnectionStatus.CONNECTED.value


def test_get_connection_by_token(registry):
    """Test retrieving connection by resume token."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="dm",
        user_id="user-456",
    )

    token = result["connection_token"]

    # Retrieve by token
    connection = registry.get_connection_by_token(token)
    assert connection is not None
    assert connection["connection_id"] == result["connection_id"]
    assert connection["session_id"] == "test-session"
    assert connection["connection_type"] == "dm"


def test_update_heartbeat(registry):
    """Test updating connection heartbeat."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
    )

    connection_id = uuid.UUID(result["connection_id"])

    # Update heartbeat
    success = registry.update_heartbeat(connection_id)
    assert success is True

    # Verify heartbeat was updated
    connection = registry.get_connection(connection_id)
    assert connection["last_heartbeat"] is not None


def test_disconnect_connection(registry):
    """Test disconnecting a connection."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
    )

    connection_id = uuid.UUID(result["connection_id"])

    # Disconnect
    success = registry.disconnect_connection(connection_id, ConnectionStatus.DISCONNECTED)
    assert success is True

    # Verify disconnection
    connection = registry.get_connection(connection_id)
    assert connection["status"] == ConnectionStatus.DISCONNECTED.value
    assert connection["disconnected_at"] is not None


def test_get_active_connections(registry):
    """Test getting active connections for a session."""
    # Create multiple connections
    conn1 = registry.create_connection(
        session_id="session-1",
        connection_type="player",
        user_id="user-1",
    )
    conn2 = registry.create_connection(
        session_id="session-1",
        connection_type="dm",
        user_id="user-2",
    )
    conn3 = registry.create_connection(
        session_id="session-2",
        connection_type="player",
        user_id="user-3",
    )

    # Disconnect one connection
    registry.disconnect_connection(uuid.UUID(conn2["connection_id"]))

    # Get active connections for session-1
    active = registry.get_active_connections("session-1")
    assert len(active) == 1  # Only conn1 should be active
    assert active[0]["connection_id"] == conn1["connection_id"]

    # Get active connections for session-2
    active2 = registry.get_active_connections("session-2")
    assert len(active2) == 1
    assert active2[0]["connection_id"] == conn3["connection_id"]


def test_record_chunk_sent(registry, playback_tracker):
    """Test recording that a chunk was sent to a connection."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
    )

    connection_id = uuid.UUID(result["connection_id"])
    chunk_id = uuid.uuid4()
    request_id = uuid.uuid4()

    # Record chunk sent
    success = playback_tracker.record_chunk_sent(
        connection_id=connection_id,
        chunk_id=chunk_id,
        request_id=request_id,
        sequence_number=0,
    )
    assert success is True

    # Verify playback state
    position = playback_tracker.get_playback_position(connection_id)
    assert position["total_chunks"] == 1
    assert position["sent"] == 1
    assert position["acknowledged"] == 0
    assert position["played"] == 0


def test_record_chunk_acknowledged(registry, playback_tracker):
    """Test recording chunk acknowledgment."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
    )

    connection_id = uuid.UUID(result["connection_id"])
    chunk_id = uuid.uuid4()
    request_id = uuid.uuid4()

    # Send chunk first
    playback_tracker.record_chunk_sent(connection_id, chunk_id, request_id, 0)

    # Acknowledge chunk
    success = playback_tracker.record_chunk_acknowledged(connection_id, chunk_id)
    assert success is True

    # Verify playback state
    position = playback_tracker.get_playback_position(connection_id)
    assert position["sent"] == 1
    assert position["acknowledged"] == 1
    assert position["played"] == 0


def test_record_chunk_played(registry, playback_tracker):
    """Test recording chunk played."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
    )

    connection_id = uuid.UUID(result["connection_id"])
    chunk_id = uuid.uuid4()
    request_id = uuid.uuid4()

    # Send and acknowledge chunk first
    playback_tracker.record_chunk_sent(connection_id, chunk_id, request_id, 0)
    playback_tracker.record_chunk_acknowledged(connection_id, chunk_id)

    # Mark as played
    success = playback_tracker.record_chunk_played(connection_id, chunk_id)
    assert success is True

    # Verify playback state
    position = playback_tracker.get_playback_position(connection_id)
    assert position["sent"] == 1
    assert position["acknowledged"] == 1
    assert position["played"] == 1
    assert position["last_played_sequence"] == 0


def test_get_unsent_chunks(registry, playback_tracker):
    """Test getting list of chunks not yet sent to a connection."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
    )

    connection_id = uuid.UUID(result["connection_id"])
    request_id = uuid.uuid4()

    # Create 5 chunks
    all_chunks = [uuid.uuid4() for _ in range(5)]

    # Send chunks 0, 1, 2
    for i in range(3):
        playback_tracker.record_chunk_sent(connection_id, all_chunks[i], request_id, i)

    # Get unsent chunks
    unsent = playback_tracker.get_unsent_chunks(connection_id, all_chunks)
    assert len(unsent) == 2
    assert all_chunks[3] in unsent
    assert all_chunks[4] in unsent
    assert all_chunks[0] not in unsent


def test_playback_position_tracking(registry, playback_tracker):
    """Test comprehensive playback position tracking."""
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
    )

    connection_id = uuid.UUID(result["connection_id"])
    request_id = uuid.uuid4()

    # Send 5 chunks
    chunks = [uuid.uuid4() for _ in range(5)]
    for i, chunk_id in enumerate(chunks):
        playback_tracker.record_chunk_sent(connection_id, chunk_id, request_id, i)

    # Acknowledge chunks 0-2
    for chunk_id in chunks[:3]:
        playback_tracker.record_chunk_acknowledged(connection_id, chunk_id)

    # Play chunks 0-1
    for chunk_id in chunks[:2]:
        playback_tracker.record_chunk_played(connection_id, chunk_id)

    # Check position
    position = playback_tracker.get_playback_position(connection_id)
    assert position["total_chunks"] == 5
    assert position["sent"] == 5
    assert position["acknowledged"] == 3
    assert position["played"] == 2
    assert position["last_played_sequence"] == 1


def test_cleanup_old_connections(registry):
    """Test cleanup of old disconnected connections."""
    # Create connection and immediately disconnect it
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
    )

    connection_id = uuid.UUID(result["connection_id"])
    registry.disconnect_connection(connection_id)

    # Manually set disconnected_at to 25 hours ago (simulating old connection)
    from db.src.connection import db_manager
    with db_manager.get_sync_session() as session:
        from gaia.connection.models import WebSocketConnection
        conn = session.get(WebSocketConnection, connection_id)
        if conn:
            conn.disconnected_at = datetime.now(timezone.utc) - timedelta(hours=25)
            session.commit()

    # Cleanup old connections (24 hour threshold)
    removed = registry.cleanup_old_connections(max_age_hours=24)
    assert removed == 1

    # Verify connection was removed
    connection = registry.get_connection(connection_id)
    assert connection is None


def test_connection_lifecycle(registry, playback_tracker):
    """Test complete connection lifecycle."""
    # 1. Create connection
    result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
        user_id="user-123",
    )

    connection_id = uuid.UUID(result["connection_id"])
    token = result["connection_token"]

    # 2. Send some audio chunks
    request_id = uuid.uuid4()
    chunks = [uuid.uuid4() for _ in range(3)]

    for i, chunk_id in enumerate(chunks):
        playback_tracker.record_chunk_sent(connection_id, chunk_id, request_id, i)

    # 3. Client plays first chunk
    playback_tracker.record_chunk_acknowledged(connection_id, chunks[0])
    playback_tracker.record_chunk_played(connection_id, chunks[0])

    # 4. Connection drops
    registry.disconnect_connection(connection_id)

    # 5. Client reconnects with same token
    old_connection = registry.get_connection_by_token(token)
    assert old_connection is not None
    assert old_connection["status"] == ConnectionStatus.DISCONNECTED.value

    # 6. Create new connection for resumed session
    new_result = registry.create_connection(
        session_id="test-session",
        connection_type="player",
        user_id="user-123",
    )

    new_connection_id = uuid.UUID(new_result["connection_id"])

    # 7. Get playback state from old connection
    old_position = playback_tracker.get_playback_position(connection_id)
    assert old_position["played"] == 1

    # 8. Resume playback in new connection (send remaining chunks)
    remaining_chunks = [chunks[1], chunks[2]]
    for i, chunk_id in enumerate(remaining_chunks, start=1):
        playback_tracker.record_chunk_sent(new_connection_id, chunk_id, request_id, i)

    new_position = playback_tracker.get_playback_position(new_connection_id)
    assert new_position["sent"] == 2


def test_singleton_instance():
    """Test that connection_registry singleton is available."""
    from gaia.connection.connection_registry import connection_registry
    assert connection_registry is not None
    assert isinstance(connection_registry, ConnectionRegistry)
