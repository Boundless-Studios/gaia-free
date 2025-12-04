"""Socket.IO server for real-time communication.

Replaces raw WebSocket connections with Socket.IO for:
- Automatic reconnection with exponential backoff
- Room-based message routing (campaigns)
- Built-in heartbeats and connection health
- Cleaner event-based API

Namespaces:
- /campaign: Main game events (narrative, audio, seats, etc.)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

import socketio

from gaia.connection.connection_registry import connection_registry
from gaia.connection.models import ConnectionStatus

logger = logging.getLogger(__name__)

# =============================================================================
# Socket.IO Server Configuration
# =============================================================================

# Create async Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # Will be restricted in production via CORS middleware
    ping_timeout=30,
    ping_interval=25,
    logger=False,  # Disable socket.io internal logging (too verbose)
    engineio_logger=False,
)


# =============================================================================
# Session Data Helpers
# =============================================================================

async def get_session_data(sid: str, namespace: str = "/campaign") -> Dict[str, Any]:
    """Get session data for a socket."""
    try:
        session = await sio.get_session(sid, namespace=namespace)
        return session or {}
    except Exception:
        return {}


async def set_session_data(sid: str, data: Dict[str, Any], namespace: str = "/campaign") -> None:
    """Set session data for a socket."""
    try:
        await sio.save_session(sid, data, namespace=namespace)
    except Exception as e:
        logger.warning("Failed to save session data for %s: %s", sid, e)


# =============================================================================
# Room Helpers
# =============================================================================

def get_room_sids(room: str, namespace: str = "/campaign") -> Set[str]:
    """Get all socket IDs in a room."""
    try:
        return set(sio.manager.get_participants(namespace, room))
    except Exception:
        return set()


def get_room_count(room: str, namespace: str = "/campaign") -> int:
    """Get count of sockets in a room."""
    return len(get_room_sids(room, namespace))


async def get_room_users(room: str, namespace: str = "/campaign") -> List[Dict[str, Any]]:
    """Get unique users in a room (deduplicated by user_id)."""
    sids = get_room_sids(room, namespace)
    users = {}
    anonymous_count = 0

    for sid in sids:
        session = await get_session_data(sid, namespace)
        user_id = session.get("user_id")
        if user_id:
            if user_id not in users:
                users[user_id] = {
                    "user_id": user_id,
                    "user_email": session.get("user_email"),
                    "connection_type": session.get("connection_type", "player"),
                }
        else:
            anonymous_count += 1

    result = list(users.values())
    if anonymous_count > 0:
        result.append({"user_id": None, "anonymous_count": anonymous_count})
    return result


async def get_unique_user_count(room: str, namespace: str = "/campaign") -> int:
    """Get count of unique users in a room."""
    sids = get_room_sids(room, namespace)
    user_ids = set()
    anonymous_count = 0

    for sid in sids:
        session = await get_session_data(sid, namespace)
        user_id = session.get("user_id")
        if user_id:
            user_ids.add(user_id)
        else:
            anonymous_count += 1

    return len(user_ids) + anonymous_count


# =============================================================================
# Authentication Helper
# =============================================================================

async def authenticate_socket(auth: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Authenticate a socket connection.

    Args:
        auth: Auth data from client containing token and session_id

    Returns:
        User info dict if authenticated, None if auth fails
    """
    if not auth:
        # Allow connection without auth in dev mode
        if os.environ.get("DISABLE_AUTH", "").lower() == "true":
            return {"user_id": None, "user_email": None}
        return None

    token = auth.get("token")
    session_id = auth.get("session_id")

    if not session_id:
        logger.warning("Socket auth missing session_id")
        return None

    # In dev mode without token, allow connection
    if not token:
        if os.environ.get("DISABLE_AUTH", "").lower() == "true":
            return {"user_id": None, "user_email": None, "session_id": session_id}
        return None

    # Validate JWT token
    try:
        from auth.src.flexible_auth import validate_token
        user_info = await validate_token(token)
        if user_info:
            return {
                "user_id": user_info.get("sub") or user_info.get("user_id"),
                "user_email": user_info.get("email"),
                "session_id": session_id,
            }
    except Exception as e:
        logger.warning("Socket auth token validation failed: %s", e)

    return None


# =============================================================================
# Campaign Namespace Event Handlers
# =============================================================================

@sio.event(namespace="/campaign")
async def connect(sid: str, environ: Dict, auth: Optional[Dict] = None):
    """Handle new socket connection to campaign namespace."""
    logger.info("[SocketIO] Connection attempt | sid=%s", sid)

    # Authenticate
    user_info = await authenticate_socket(auth or {})

    # In production, require auth
    is_production = os.environ.get("ENVIRONMENT", "").lower() == "production"
    if is_production and not user_info:
        logger.warning("[SocketIO] Auth required in production | sid=%s", sid)
        raise socketio.exceptions.ConnectionRefusedError("Authentication required")

    # Get session_id from auth
    session_id = (auth or {}).get("session_id")
    if not session_id:
        logger.warning("[SocketIO] Missing session_id | sid=%s", sid)
        raise socketio.exceptions.ConnectionRefusedError("session_id required")

    # Determine connection type (default to player)
    connection_type = (auth or {}).get("role", "player")

    # Store session data
    session_data = {
        "user_id": user_info.get("user_id") if user_info else None,
        "user_email": user_info.get("user_email") if user_info else None,
        "session_id": session_id,
        "connection_type": connection_type,
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    await set_session_data(sid, session_data)

    # Join the campaign room
    await sio.enter_room(sid, session_id, namespace="/campaign")
    logger.info(
        "[SocketIO] Joined room | sid=%s session=%s user=%s type=%s",
        sid, session_id, session_data.get("user_id"), connection_type
    )

    # Create registry entry for audit trail
    if connection_registry.db_enabled:
        try:
            # Extract request metadata from environ
            origin = None
            user_agent = None
            client_ip = None
            if environ:
                headers = environ.get("asgi.scope", {}).get("headers", [])
                header_dict = {k.decode(): v.decode() for k, v in headers if isinstance(k, bytes)}
                origin = header_dict.get("origin")
                user_agent = header_dict.get("user-agent")
                # Client IP from scope
                scope = environ.get("asgi.scope", {})
                client = scope.get("client")
                if client:
                    client_ip = client[0]

            conn_info = connection_registry.create_connection(
                session_id=session_id,
                connection_type=connection_type,
                user_id=session_data.get("user_id"),
                user_email=session_data.get("user_email"),
                origin=origin,
                user_agent=user_agent,
                client_ip=client_ip,
            )
            # Store registry connection_id in session
            session_data["registry_connection_id"] = conn_info["connection_id"]
            session_data["connection_token"] = conn_info["connection_token"]
            await set_session_data(sid, session_data)

            # Send connection_registered to client
            await sio.emit(
                "connection_registered",
                {
                    "connection_id": conn_info["connection_id"],
                    "connection_token": conn_info["connection_token"],
                },
                to=sid,
                namespace="/campaign",
            )
        except Exception as e:
            logger.error("[SocketIO] Failed to create registry entry: %s", e)

    # Notify others in the room
    user_count = await get_unique_user_count(session_id)
    await sio.emit(
        "player_connected",
        {
            "user_id": session_data.get("user_id"),
            "user_email": session_data.get("user_email"),
            "connected_count": user_count,
        },
        room=session_id,
        skip_sid=sid,
        namespace="/campaign",
    )

    logger.info(
        "[SocketIO] Connected | sid=%s session=%s users=%d",
        sid, session_id, user_count
    )


@sio.event(namespace="/campaign")
async def disconnect(sid: str):
    """Handle socket disconnection."""
    session = await get_session_data(sid)
    session_id = session.get("session_id")
    user_id = session.get("user_id")

    logger.info(
        "[SocketIO] Disconnecting | sid=%s session=%s user=%s",
        sid, session_id, user_id
    )

    # Update registry
    registry_conn_id = session.get("registry_connection_id")
    if registry_conn_id and connection_registry.db_enabled:
        try:
            connection_registry.disconnect_connection(
                uuid.UUID(registry_conn_id),
                ConnectionStatus.DISCONNECTED,
            )
        except Exception as e:
            logger.warning("[SocketIO] Failed to update registry on disconnect: %s", e)

    # Notify others (if we have session_id)
    if session_id:
        user_count = await get_unique_user_count(session_id)
        # Subtract 1 since we're still technically in the room
        user_count = max(0, user_count - 1)

        await sio.emit(
            "player_disconnected",
            {
                "user_id": user_id,
                "connected_count": user_count,
            },
            room=session_id,
            skip_sid=sid,
            namespace="/campaign",
        )

    logger.info("[SocketIO] Disconnected | sid=%s", sid)


# =============================================================================
# Game Event Handlers
# =============================================================================

@sio.event(namespace="/campaign")
async def yjs_update(sid: str, data: Dict[str, Any]):
    """Handle Yjs CRDT update from collaborative editor."""
    session = await get_session_data(sid)
    session_id = session.get("session_id")

    if not session_id:
        logger.warning("[SocketIO] yjs_update without session_id | sid=%s", sid)
        return

    # Broadcast to room except sender
    await sio.emit(
        "yjs_update",
        data,
        room=session_id,
        skip_sid=sid,
        namespace="/campaign",
    )


@sio.event(namespace="/campaign")
async def awareness_update(sid: str, data: Dict[str, Any]):
    """Handle awareness update (cursor positions, selections)."""
    session = await get_session_data(sid)
    session_id = session.get("session_id")

    if not session_id:
        return

    await sio.emit(
        "awareness_update",
        data,
        room=session_id,
        skip_sid=sid,
        namespace="/campaign",
    )


@sio.event(namespace="/campaign")
async def audio_played(sid: str, data: Dict[str, Any]):
    """Handle audio playback acknowledgment."""
    session = await get_session_data(sid)
    session_id = session.get("session_id")
    chunk_id = data.get("chunk_id")

    if not chunk_id:
        return

    # Track playback in registry
    registry_conn_id = session.get("registry_connection_id")
    if registry_conn_id:
        try:
            from gaia.connection.connection_playback_tracker import connection_playback_tracker
            connection_playback_tracker.record_chunk_played(
                uuid.UUID(registry_conn_id),
                uuid.UUID(chunk_id),
            )
        except Exception as e:
            logger.debug("Failed to record chunk played: %s", e)


@sio.event(namespace="/campaign")
async def register(sid: str, data: Dict[str, Any]):
    """Handle player registration for collaborative session."""
    session = await get_session_data(sid)
    session_id = session.get("session_id")
    player_id = data.get("playerId")
    player_name = data.get("playerName")

    if not session_id or not player_id:
        return

    # Update session with player info
    session["player_id"] = player_id
    session["player_name"] = player_name
    await set_session_data(sid, session)

    # This will be handled by the collaborative session manager
    # For now, emit acknowledgment
    await sio.emit(
        "registered",
        {"playerId": player_id, "playerName": player_name},
        to=sid,
        namespace="/campaign",
    )


@sio.event(namespace="/campaign")
async def start_audio_stream(sid: str, data: Dict[str, Any]):
    """Handle request to start audio streaming."""
    session = await get_session_data(sid)
    session_id = session.get("session_id")
    user_id = session.get("user_id")

    if not session_id:
        return

    # Forward to audio handler (will be integrated with AudioWebSocketHandler)
    logger.info("[SocketIO] start_audio_stream | session=%s user=%s", session_id, user_id)


@sio.event(namespace="/campaign")
async def stop_audio_stream(sid: str, data: Dict[str, Any]):
    """Handle request to stop audio streaming."""
    session = await get_session_data(sid)
    session_id = session.get("session_id")

    if not session_id:
        return

    logger.info("[SocketIO] stop_audio_stream | session=%s", session_id)


@sio.event(namespace="/campaign")
async def clear_audio_queue(sid: str, data: Dict[str, Any]):
    """Handle request to clear audio queue."""
    session = await get_session_data(sid)
    session_id = session.get("session_id")

    if not session_id:
        return

    logger.info("[SocketIO] clear_audio_queue | session=%s", session_id)

    # Acknowledge
    await sio.emit(
        "audio_queue_cleared",
        {"session_id": session_id},
        to=sid,
        namespace="/campaign",
    )


# =============================================================================
# Broadcast Helpers (for use by other modules)
# =============================================================================

async def broadcast_to_room(
    session_id: str,
    event: str,
    data: Dict[str, Any],
    skip_sid: Optional[str] = None,
) -> None:
    """Broadcast an event to all clients in a campaign room.

    Args:
        session_id: Campaign/session ID (room name)
        event: Event name
        data: Event data
        skip_sid: Optional socket ID to exclude
    """
    await sio.emit(
        event,
        data,
        room=session_id,
        skip_sid=skip_sid,
        namespace="/campaign",
    )


async def broadcast_to_user(
    session_id: str,
    user_id: str,
    event: str,
    data: Dict[str, Any],
) -> None:
    """Broadcast an event to all sockets belonging to a specific user.

    Args:
        session_id: Campaign/session ID
        user_id: Target user ID
        event: Event name
        data: Event data
    """
    sids = get_room_sids(session_id)
    for sid in sids:
        session = await get_session_data(sid)
        if session.get("user_id") == user_id:
            await sio.emit(event, data, to=sid, namespace="/campaign")


async def send_to_socket(sid: str, event: str, data: Dict[str, Any]) -> None:
    """Send an event to a specific socket.

    Args:
        sid: Socket ID
        event: Event name
        data: Event data
    """
    await sio.emit(event, data, to=sid, namespace="/campaign")


# =============================================================================
# ASGI App
# =============================================================================

def create_socketio_app(other_app):
    """Create Socket.IO ASGI app wrapping another ASGI app.

    Args:
        other_app: The main ASGI app (e.g., FastAPI)

    Returns:
        Combined ASGI app with Socket.IO
    """
    return socketio.ASGIApp(sio, other_asgi_app=other_app)
