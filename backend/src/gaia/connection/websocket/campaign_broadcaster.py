"""WebSocket broadcaster that operates on a per-session basis."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import HTTPException, WebSocket
from starlette.websockets import WebSocketState
from sqlalchemy import select

from gaia.infra.audio.audio_playback_service import audio_playback_service
from gaia_private.session.session_models import CampaignSession, RoomSeat
from gaia_private.session.room_service import RoomService

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""

    websocket: WebSocket
    session_id: str
    connection_type: str  # "player" or "dm"
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    display_name: Optional[str] = None
    seat_id: Optional[uuid.UUID] = None
    connected_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    superseded: bool = False  # Flag to prevent pruning when connection is replaced
    identity_update_callback: Optional[Callable[[], None]] = field(default=None, repr=False)


@dataclass
class SessionState:
    """Tracks connections and cached data for a single session.

    Audio playback is now user-scoped via UserAudioQueue table.
    SessionState only manages connections and campaign state.
    """

    player_connections: List[ConnectionInfo] = field(default_factory=list)
    dm_connections: List[ConnectionInfo] = field(default_factory=list)
    last_campaign_state: Optional[Dict] = None


class CampaignBroadcaster:
    """Manages WebSocket connections scoped to gameplay sessions."""

    def __init__(self, campaign_service=None) -> None:
        self.logger = logging.getLogger(__name__)
        self.sessions: Dict[str, SessionState] = {}
        self._campaign_service = campaign_service
        self._cleanup_task: Optional[asyncio.Task] = None
        self._missing_session_warned: Set[str] = set()  # Track warned sessions to avoid spam
        self._start_cleanup_task()

    def _find_connections_by_user(self, session_id: str, user_id: Optional[str]) -> List[ConnectionInfo]:
        """Return all active connections (player or DM) for a given user."""
        if not user_id:
            return []

        state = self.sessions.get(session_id)
        if not state:
            return []

        connections: List[ConnectionInfo] = []
        for conn in state.player_connections + state.dm_connections:
            if conn.user_id == user_id:
                connections.append(conn)
        return connections

    async def _disconnect_user_connections(
        self,
        session_id: str,
        user_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """Force-disconnect all connections owned by a user within a session."""
        connections = list(self._find_connections_by_user(session_id, user_id))
        if not connections:
            return

        close_reason = reason or "Seat reassigned"
        for conn in connections:
            if conn.connection_type == "dm":
                await self.disconnect_dm(conn, close_code=1012, close_reason=close_reason)
            else:
                await self.disconnect_player(conn, close_code=1012, close_reason=close_reason)

    def update_user_seat_assignments(
        self,
        session_id: str,
        user_id: Optional[str],
        seat_id: Optional[uuid.UUID],
    ) -> None:
        """Update cached ConnectionInfo + registry rows for a user's active connections."""
        if not user_id:
            return

        connections = self._find_connections_by_user(session_id, user_id)
        if not connections:
            return

        for conn in connections:
            conn.seat_id = seat_id
            if hasattr(conn, "registry_connection_id") and conn.registry_connection_id:
                from gaia.connection.connection_registry import connection_registry

                try:
                    connection_registry.update_connection_seat(
                        uuid.UUID(conn.registry_connection_id),
                        seat_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug(
                        "Failed to sync connection seat (session=%s user=%s): %s",
                        session_id,
                        user_id,
                        exc,
                    )

    async def handle_seat_change(
        self,
        session_id: str,
        seat_id: Optional[str],
        previous_owner_id: Optional[str],
        new_owner_id: Optional[str],
    ) -> None:
        """Reconcile WebSocket connections when a seat changes ownership."""
        seat_uuid: Optional[uuid.UUID] = None
        if seat_id:
            try:
                seat_uuid = uuid.UUID(str(seat_id))
            except (ValueError, TypeError):
                seat_uuid = None

        if previous_owner_id and new_owner_id and previous_owner_id != new_owner_id:
            await self._disconnect_user_connections(
                session_id,
                previous_owner_id,
                reason="Seat reassigned",
            )
        elif previous_owner_id and not new_owner_id:
            # Seat was vacated; keep connection but clear cached seat.
            self.update_user_seat_assignments(session_id, previous_owner_id, None)

        if new_owner_id:
            self.update_user_seat_assignments(session_id, new_owner_id, seat_uuid)

    def _log_connected_players(self, session_id: str) -> None:
        """Log the list of connected player identities for a session."""
        state = self.sessions.get(session_id)
        if not state:
            return

        connected_names: List[str] = []
        for conn in state.player_connections:
            if conn.user_email:
                connected_names.append(conn.user_email)
            elif conn.user_id:
                connected_names.append(conn.user_id)
            else:
                connected_names.append("anonymous")

        if connected_names:
            self.logger.info(
                "Connected players for session %s: %s",
                session_id,
                ", ".join(connected_names),
            )

    @staticmethod
    async def _accept_websocket(websocket: WebSocket) -> None:
        """Accept the websocket, preserving negotiated subprotocol when available."""
        subprotocol = None
        scope = getattr(websocket, "scope", None)
        if isinstance(scope, dict):
            subprotocol = scope.get("subprotocol")

        try:
            if subprotocol is not None:
                await websocket.accept(subprotocol=subprotocol)
                return
        except TypeError:
            # Fallback for stubs that don't support keyword arguments
            pass

        await websocket.accept()

    async def connect_player(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> ConnectionInfo:
        """Connect a player to receive updates for a specific session."""
        # Accept WebSocket connection (JWT token extraction happens before this in main.py)
        # Echo back the negotiated subprotocol so bearer tokens sent via Sec-WebSocket-Protocol are preserved
        await self._accept_websocket(websocket)
        state = self._get_state(session_id)

        connection = ConnectionInfo(
            websocket=websocket,
            session_id=session_id,
            connection_type="player",
            user_id=user_id,
            user_email=user_email,
            display_name=display_name,
        )
        connection.identity_update_callback = lambda: self._log_connected_players(session_id)

        # Find user's seat from room_seats table
        seat_id = None
        if user_id:
            from db.src.connection import db_manager

            try:
                with db_manager.get_sync_session() as db:
                    stmt = select(RoomSeat).where(
                        RoomSeat.campaign_id == session_id,
                        RoomSeat.owner_user_id == user_id,
                    )
                    seat = db.execute(stmt).scalar_one_or_none()
                    if seat:
                        seat_id = seat.seat_id
                        self.logger.info(
                            "Player %s occupies seat %s in campaign %s",
                            user_id,
                            seat_id,
                            session_id,
                        )
            except Exception as exc:
                self.logger.error("Failed to find player seat: %s", exc)

        # Register connection in connection registry for connection-scoped tracking
        from gaia.connection.connection_registry import connection_registry
        if connection_registry.db_enabled:
            try:
                conn_info = connection_registry.create_connection(
                    session_id=session_id,
                    connection_type="player",
                    user_id=user_id,
                    user_email=user_email,
                    origin=websocket.headers.get("origin"),
                    user_agent=websocket.headers.get("user-agent"),
                    client_ip=getattr(websocket.client, 'host', None) if websocket.client else None,
                    seat_id=seat_id,  # Store seat_id in connection
                )
                # Store registry connection ID in the ConnectionInfo object
                connection.registry_connection_id = conn_info["connection_id"]
                connection.connection_token = conn_info["connection_token"]

                # Send connection token to client for resume support
                await websocket.send_json({
                    "type": "connection_registered",
                    "connection_token": conn_info["connection_token"],
                    "connection_id": conn_info["connection_id"],
                })
            except Exception as exc:
                self.logger.error("Failed to register connection in registry: %s", exc)

        if seat_id:
            connection.seat_id = seat_id

        state.player_connections.append(connection)
        self._log_connected_players(session_id)

        self.logger.info(
            "Player connected (session=%s user_id=%s). Total players=%d",
            session_id,
            user_id,
            len(state.player_connections),
        )
        

        # Notify DM of player connection
        await self.broadcast_to_dm(
            session_id,
            "player_connected",
            {
                "user_id": user_id,
                "connected_players_count": len(state.player_connections),
            },
        )

        # Send cached state if available
        if state.last_campaign_state:
            await self._send_to_connection(
                connection,
                {
                    "type": "campaign_active",
                    "campaign_id": session_id,
                    "structured_data": state.last_campaign_state,
                    "timestamp": datetime.now().isoformat(),
                },
            )
        else:
            await self._load_current_campaign_state(session_id, state, connection)

        if connection.seat_id:
            await self._broadcast_current_seat_state(session_id, connection.seat_id)

        return connection

    async def connect_dm(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> ConnectionInfo:
        """Connect a DM for a specific session.

        Only allows a single active DM connection per session. Closes existing
        connections before accepting the new one to prevent race conditions.

        Validates DM ownership and updates room_status to 'active'.
        """
        # Validate DM ownership before accepting connection
        if user_id:
            from db.src.connection import db_manager

            try:
                with db_manager.get_sync_session() as db:
                    campaign = db.get(CampaignSession, session_id)
                    if campaign:
                        if campaign.owner_user_id != user_id:
                            self.logger.warning(
                                "DM connection rejected: user_id %s does not own campaign %s (owner: %s)",
                                user_id,
                                session_id,
                                campaign.owner_user_id,
                            )
                            await websocket.close(code=1008, reason="Not campaign owner")
                            raise HTTPException(status_code=403, detail="Only campaign owner can connect as DM")
            except HTTPException:
                raise
            except Exception as exc:
                self.logger.error("Failed to validate DM ownership: %s", exc)

        state = self._get_state(session_id)

        # Remove any stale DM connections (closed sockets lingering in list)
        stale_connections = [
            conn for conn in state.dm_connections
            if conn.websocket.client_state != WebSocketState.CONNECTED
        ]
        for stale in stale_connections:
            # Mark as disconnected in registry before removing
            if hasattr(stale, 'registry_connection_id') and stale.registry_connection_id:
                from gaia.connection.connection_registry import connection_registry
                from gaia.connection.models import ConnectionStatus
                import uuid
                try:
                    connection_registry.disconnect_connection(
                        uuid.UUID(stale.registry_connection_id),
                        ConnectionStatus.DISCONNECTED
                    )
                except Exception as exc:
                    self.logger.warning("Failed to disconnect stale connection in registry: %s", exc)

            state.dm_connections.remove(stale)
            self.logger.debug("Removed stale DM connection for session %s", session_id)

        # Close existing connections BEFORE accepting the new one
        # This prevents the race condition where multiple connections are accepted simultaneously
        existing_connections = list(state.dm_connections)
        if existing_connections:
            self.logger.info(
                "Closing %d existing DM connection(s) for session %s before accepting new connection",
                len(existing_connections),
                session_id,
            )
            for existing in existing_connections:
                # Mark connection as superseded to prevent pruning session state
                existing.superseded = True

                # Mark as superseded in registry before closing
                if hasattr(existing, 'registry_connection_id') and existing.registry_connection_id:
                    from gaia.connection.connection_registry import connection_registry
                    from gaia.connection.models import ConnectionStatus
                    import uuid
                    try:
                        connection_registry.disconnect_connection(
                            uuid.UUID(existing.registry_connection_id),
                            ConnectionStatus.SUPERSEDED
                        )
                    except Exception as exc:
                        self.logger.warning("Failed to mark superseded connection in registry: %s", exc)

                try:
                    await existing.websocket.close(code=1012, reason="Superseded DM connection")
                except Exception:  # noqa: BLE001
                    pass
                # Remove from list
                if existing in state.dm_connections:
                    state.dm_connections.remove(existing)

        # Accept WebSocket connection (JWT token extraction happens before this in main.py)
        # Echo back the negotiated subprotocol so bearer tokens sent via Sec-WebSocket-Protocol are preserved
        await self._accept_websocket(websocket)

        connection = ConnectionInfo(
            websocket=websocket,
            session_id=session_id,
            connection_type="dm",
            user_id=user_id,
            user_email=user_email,
            display_name=display_name,
        )

        # Register connection in connection registry for connection-scoped tracking
        from gaia.connection.connection_registry import connection_registry
        if connection_registry.db_enabled:
            try:
                conn_info = connection_registry.create_connection(
                    session_id=session_id,
                    connection_type="dm",
                    user_id=user_id,
                    user_email=user_email,
                    origin=websocket.headers.get("origin"),
                    user_agent=websocket.headers.get("user-agent"),
                    client_ip=getattr(websocket.client, 'host', None) if websocket.client else None,
                )
                # Store registry connection ID in the ConnectionInfo object
                connection.registry_connection_id = conn_info["connection_id"]
                connection.connection_token = conn_info["connection_token"]

                # Send connection token to client for resume support
                await websocket.send_json({
                    "type": "connection_registered",
                    "connection_token": conn_info["connection_token"],
                    "connection_id": conn_info["connection_id"],
                })
            except Exception as exc:
                self.logger.error("Failed to register connection in registry: %s", exc)

        state.dm_connections.append(connection)

        self.logger.info(
            "DM connected (session=%s user_id=%s)",
            session_id,
            user_id,
        )

        # Update room_status to 'active' when DM joins and claim DM seat
        from db.src.connection import db_manager

        dm_seat_id: Optional[uuid.UUID] = None
        try:
            with db_manager.get_sync_session() as db:
                campaign = db.get(CampaignSession, session_id)
                if campaign:
                    campaign.room_status = 'active'
                    campaign.dm_joined_at = datetime.now(timezone.utc)
                    if hasattr(connection, 'registry_connection_id'):
                        campaign.dm_connection_id = connection.registry_connection_id

                    dm_seat = db.execute(
                        select(RoomSeat).where(
                            RoomSeat.campaign_id == session_id,
                            RoomSeat.seat_type == "dm",
                        )
                    ).scalar_one_or_none()
                    if dm_seat and user_id:
                        dm_seat.owner_user_id = user_id
                        dm_seat_id = dm_seat.seat_id

                    db.commit()

                    self.logger.info(
                        "Room status set to 'active' for campaign %s",
                        session_id,
                    )

                    await self.broadcast_campaign_update(
                        session_id,
                        "room.dm_joined",
                        {
                            "user_id": user_id,
                            "dm_joined_at": campaign.dm_joined_at.isoformat() if campaign.dm_joined_at else None,
                            "room_status": campaign.room_status,
                        },
                    )
        except Exception as exc:
            self.logger.error("Failed to update room_status on DM join: %s", exc)

        if dm_seat_id:
            connection.seat_id = dm_seat_id
            if hasattr(connection, "registry_connection_id") and connection.registry_connection_id:
                from gaia.connection.connection_registry import connection_registry
                try:
                    connection_registry.update_connection_seat(
                        uuid.UUID(connection.registry_connection_id),
                        dm_seat_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug("Failed to persist DM seat mapping: %s", exc)
            await self._broadcast_current_seat_state(session_id, dm_seat_id)

        return connection

    async def disconnect_player(
        self,
        connection: ConnectionInfo,
        *,
        close_code: Optional[int] = None,
        close_reason: Optional[str] = None,
    ) -> None:
        """Remove a player connection."""
        if close_reason and connection.websocket.client_state == WebSocketState.CONNECTED:
            try:
                await connection.websocket.close(code=close_code or 1000, reason=close_reason)
            except Exception:  # noqa: BLE001
                pass
        # Mark connection as disconnected in registry
        if hasattr(connection, 'registry_connection_id') and connection.registry_connection_id:
            from gaia.connection.connection_registry import connection_registry
            from gaia.connection.models import ConnectionStatus
            import uuid
            try:
                connection_registry.disconnect_connection(
                    uuid.UUID(connection.registry_connection_id),
                    ConnectionStatus.DISCONNECTED
                )
            except Exception as exc:
                self.logger.error("Failed to disconnect connection in registry: %s", exc)

        state = self.sessions.get(connection.session_id)
        if not state:
            return

        if connection in state.player_connections:
            state.player_connections.remove(connection)
            self.logger.info(
                "Player disconnected (session=%s). Remaining players=%d",
                connection.session_id,
                len(state.player_connections),
            )

            # Notify DM of player disconnection
            await self.broadcast_to_dm(
                connection.session_id,
                "player_disconnected",
                {
                    "user_id": connection.user_id,
                    "connected_players_count": len(state.player_connections),
                },
            )

        if connection.seat_id:
            await self._broadcast_current_seat_state(connection.session_id, connection.seat_id)
        if hasattr(connection, 'registry_connection_id') and connection.registry_connection_id:
            from gaia.connection.connection_registry import connection_registry
            try:
                connection_registry.update_connection_seat(
                    uuid.UUID(connection.registry_connection_id),
                    None,
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.debug("Failed to clear player connection seat: %s", exc)

        self._prune_state_if_empty(connection.session_id)

    async def disconnect_dm(
        self,
        connection: ConnectionInfo,
        *,
        close_code: Optional[int] = None,
        close_reason: Optional[str] = None,
    ) -> None:
        """Remove a DM connection.

        Sets room_status back to 'waiting_for_dm' and broadcasts event.
        """
        if close_reason and connection.websocket.client_state == WebSocketState.CONNECTED:
            try:
                await connection.websocket.close(code=close_code or 1000, reason=close_reason)
            except Exception:  # noqa: BLE001
                pass
        # Mark connection as disconnected in registry
        if hasattr(connection, 'registry_connection_id') and connection.registry_connection_id:
            from gaia.connection.connection_registry import connection_registry
            from gaia.connection.models import ConnectionStatus
            import uuid
            try:
                connection_registry.disconnect_connection(
                    uuid.UUID(connection.registry_connection_id),
                    ConnectionStatus.DISCONNECTED
                )
            except Exception as exc:
                self.logger.error("Failed to disconnect connection in registry: %s", exc)

        state = self.sessions.get(connection.session_id)
        if not state:
            return

        if connection in state.dm_connections:
            state.dm_connections.remove(connection)
            self.logger.info(
                "DM disconnected (session=%s). Remaining DMs=%d",
                connection.session_id,
                len(state.dm_connections),
            )

            # Update room_status to 'waiting_for_dm' when last DM disconnects
            if not state.dm_connections:
                from db.src.connection import db_manager

                dm_seat_id: Optional[uuid.UUID] = getattr(connection, "seat_id", None)
                try:
                    with db_manager.get_sync_session() as db:
                        campaign = db.get(CampaignSession, connection.session_id)
                        if campaign:
                            campaign.room_status = 'waiting_for_dm'
                            campaign.dm_connection_id = None
                            dm_seat = db.execute(
                                select(RoomSeat).where(
                                    RoomSeat.campaign_id == connection.session_id,
                                    RoomSeat.seat_type == "dm",
                                )
                            ).scalar_one_or_none()
                            if dm_seat:
                                dm_seat.owner_user_id = None
                                dm_seat_id = dm_seat.seat_id
                            db.commit()

                            self.logger.info(
                                "Room status set to 'waiting_for_dm' for campaign %s",
                                connection.session_id,
                            )

                            await self.broadcast_campaign_update(
                                connection.session_id,
                                "room.dm_left",
                                {
                                    "user_id": connection.user_id,
                                    "room_status": campaign.room_status,
                                },
                            )
                except Exception as exc:
                    self.logger.error("Failed to update room_status on DM disconnect: %s", exc)

                if dm_seat_id:
                    await self._broadcast_current_seat_state(connection.session_id, dm_seat_id)
                if hasattr(connection, 'registry_connection_id') and connection.registry_connection_id:
                    from gaia.connection.connection_registry import connection_registry
                    try:
                        connection_registry.update_connection_seat(
                            uuid.UUID(connection.registry_connection_id),
                            None,
                        )
                    except Exception as exc:  # noqa: BLE001
                        self.logger.debug("Failed to clear DM connection seat: %s", exc)

        # Only prune session state if this was a normal disconnect, not a superseded connection
        # Superseded connections are replaced by new ones, so pruning would delete state needed by the new connection
        if not connection.superseded:
            self._prune_state_if_empty(connection.session_id)

    async def broadcast_campaign_update(
        self,
        session_id: str,
        event_type: str,
        data: Dict,
    ) -> None:
        """Broadcast updates to all players in a session."""
        state = self.sessions.get(session_id)
        if not state:
            # Only warn once per missing session to avoid log spam during streaming
            if session_id not in self._missing_session_warned:
                self._missing_session_warned.add(session_id)
                self.logger.warning(
                    "No session state found when broadcasting %s for session %s | Available sessions: %s",
                    event_type,
                    session_id,
                    list(self.sessions.keys()),
                )
            return

        if not state.player_connections and not state.dm_connections:
            self.logger.debug(
                "No connected clients to broadcast %s for session %s",
                event_type,
                session_id,
            )
            return

        message = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            **data,
        }
        message["campaign_id"] = session_id

        if event_type in {"campaign_loaded", "campaign_updated", "campaign_active"}:
            if "structured_data" in data:
                state.last_campaign_state = data["structured_data"]
        elif event_type == "campaign_deactivated":
            state.last_campaign_state = None

        disconnected: List[ConnectionInfo] = []
        for connection in list(state.player_connections):
            try:
                await self._send_to_connection(connection, message)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Failed to send to player (session=%s): %s",
                    session_id,
                    exc,
                )
                disconnected.append(connection)

        for connection in disconnected:
            await self.disconnect_player(connection)

        # Also broadcast to DM connections for audio chunks and other updates
        if state.dm_connections:
            dm_disconnected: List[ConnectionInfo] = []
            for connection in list(state.dm_connections):
                try:
                    await self._send_to_connection(connection, message)
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning(
                        "Failed to send to DM (session=%s): %s",
                        session_id,
                        exc,
                    )
                    dm_disconnected.append(connection)

            for connection in dm_disconnected:
                await self.disconnect_dm(connection)

        total_players = len(state.player_connections)
        total_dms = len(state.dm_connections)
        total_recipients = total_players + total_dms
        self.logger.debug(
            "[WS][broadcast] %s → recipients=%d (players=%d, dms=%d) session=%s",
            event_type,
            total_recipients,
            total_players,
            total_dms,
            session_id,
        )

    async def broadcast_to_dm(
        self,
        session_id: str,
        event_type: str,
        data: Dict,
    ) -> None:
        """Broadcast updates to DM connections in a session."""
        state = self.sessions.get(session_id)
        if not state or not state.dm_connections:
            return

        message = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            **data,
        }
        message["campaign_id"] = session_id

        disconnected: List[ConnectionInfo] = []
        for connection in list(state.dm_connections):
            try:
                await self._send_to_connection(connection, message)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Failed to send to DM (session=%s): %s",
                    session_id,
                    exc,
                )
                disconnected.append(connection)

        for connection in disconnected:
            await self.disconnect_dm(connection)

    async def broadcast_narrative_chunk(
        self,
        session_id: str,
        content: str,
        is_final: bool = False,
    ) -> None:
        """Broadcast narrative chunk to all players in a session.

        Args:
            session_id: The session ID
            content: The narrative text chunk
            is_final: Whether this is the final chunk (empty content signals completion)
        """
        await self.broadcast_campaign_update(
            session_id,
            "narrative_chunk",
            {
                "content": content,
                "is_final": is_final,
            },
        )

    async def broadcast_player_response_chunk(
        self,
        session_id: str,
        content: str,
        is_final: bool = False,
    ) -> None:
        """Broadcast player response chunk to all players in a session.

        Args:
            session_id: The session ID
            content: The player response text chunk
            is_final: Whether this is the final chunk (empty content signals completion)
        """
        await self.broadcast_campaign_update(
            session_id,
            "player_response_chunk",
            {
                "content": content,
                "is_final": is_final,
            },
        )

    async def broadcast_player_options(
        self,
        session_id: str,
        options: List[str],
    ) -> None:
        """Broadcast player options to all players in a session.

        Args:
            session_id: The session ID
            options: List of player action options
        """
        await self.broadcast_campaign_update(
            session_id,
            "player_options",
            {
                "options": options,
            },
        )

    async def broadcast_metadata_update(
        self,
        session_id: str,
        metadata: Dict,
    ) -> None:
        """Broadcast metadata update to all players in a session.

        Args:
            session_id: The session ID
            metadata: Metadata dictionary (environmental conditions, threats, etc.)
        """
        await self.broadcast_campaign_update(
            session_id,
            "metadata_update",
            {
                "metadata": metadata,
            },
        )

    async def broadcast_seat_updated(
        self,
        session_id: str,
        seat_data: Dict,
    ) -> None:
        """Broadcast seat update to all players and DM in a session.

        Args:
            session_id: The campaign/session ID
            seat_data: Seat information dictionary (seat_id, owner, character, status)
        """
        await self.broadcast_campaign_update(
            session_id,
            "room.seat_updated",
            {
                "seat": seat_data,
            },
        )

    async def broadcast_seat_character_update(
        self,
        session_id: str,
        seat_id: str,
        character_id: str,
    ) -> None:
        """Broadcast that a seat has a new character assignment."""
        await self.broadcast_campaign_update(
            session_id,
            "room.seat_character_updated",
            {
                "seat_id": seat_id,
                "character_id": character_id,
            },
        )

    async def broadcast_campaign_started(
        self,
        session_id: str,
        payload: Dict[str, Any],
    ) -> None:
        """Broadcast standard room.campaign_started payload."""
        self.logger.info(
            "room.campaign_started broadcast queued | session_id=%s payload_keys=%s has_structured_data=%s",
            session_id,
            sorted(payload.keys()),
            "structured_data" in payload,
        )
        await self.broadcast_campaign_update(
            session_id,
            "room.campaign_started",
            payload,
        )

    async def broadcast_player_vacated(
        self,
        session_id: str,
        seat_id: str,
        previous_owner_id: str,
    ) -> None:
        """Broadcast DM-forced seat removal."""
        await self.broadcast_campaign_update(
            session_id,
            "room.player_vacated",
            {
                "seat_id": seat_id,
                "previous_owner_id": previous_owner_id,
                "reason": "vacated_by_dm",
            },
        )

    async def send_heartbeat(self) -> None:
        """Send heartbeat frames to all connections."""
        heartbeat = {
            "type": "heartbeat",
            "timestamp": datetime.now().isoformat(),
        }

        for session_id, state in list(self.sessions.items()):
            for connection in list(state.player_connections):
                try:
                    await self._send_to_connection(connection, heartbeat)
                    connection.last_heartbeat = datetime.now()
                except Exception:
                    await self.disconnect_player(connection)
            for connection in list(state.dm_connections):
                try:
                    await self._send_to_connection(connection, heartbeat)
                    connection.last_heartbeat = datetime.now()
                except Exception:
                    await self.disconnect_dm(connection)

            self._prune_state_if_empty(session_id)

    async def _send_to_connection(
        self,
        connection: ConnectionInfo,
        data: Dict,
    ) -> None:
        """Send JSON payload to a specific connection."""
        await connection.websocket.send_json(data)
        # Force flush to prevent WebSocket message batching
        # This ensures chunks arrive progressively instead of all at once
        try:
            if hasattr(connection.websocket, '_send'):
                await connection.websocket._send()
        except Exception:
            # Flush not available or failed - send_json already awaited so message is queued
            pass

    async def _broadcast_current_seat_state(
        self,
        session_id: str,
        seat_id: uuid.UUID,
    ) -> None:
        """Fetch and broadcast the latest state of a specific seat."""
        from db.src.connection import db_manager

        try:
            with db_manager.get_sync_session() as db:
                seat = db.get(RoomSeat, seat_id)
                if not seat:
                    return
                room_service = RoomService(db)
                seat_info = room_service._serialize_single_seat(seat)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Failed to broadcast seat %s for session %s: %s", seat_id, session_id, exc)
            return

        await self.broadcast_seat_updated(session_id, seat_info.__dict__)

    async def _load_current_campaign_state(
        self,
        session_id: str,
        state: SessionState,
        connection: Optional[ConnectionInfo] = None,
        *,
        broadcast: bool = False,
    ) -> None:
        """Attempt to hydrate cached state for a session using internal service."""
        try:
            # Use internal campaign service instead of HTTP self-call
            if not self._campaign_service:
                self.logger.warning(
                    "Campaign service not available for loading state for session %s",
                    session_id,
                )
                return

            self.logger.debug(
                "Loading campaign state for session %s (internal service)",
                session_id,
            )

            # Call internal method directly - no HTTP overhead
            # Note: Accessing private method _get_campaign_data for performance
            # (avoids HTTP overhead). This is acceptable for internal service communication.
            try:
                data = self._campaign_service._get_campaign_data(session_id)
                structured = data.get("structured_data")
            except HTTPException as e:
                # Campaign not found - this is expected for new/invalid sessions
                self.logger.warning(
                    "Campaign %s not found when loading state: %s",
                    session_id,
                    e.detail,
                )
                return

            if structured:
                state.last_campaign_state = structured
                message = {
                    "type": "campaign_loaded",
                    "campaign_id": session_id,
                    "structured_data": structured,
                    "timestamp": datetime.now().isoformat(),
                }
                if connection:
                    await self._send_to_connection(connection, message)
                if broadcast:
                    await self.broadcast_campaign_update(
                        session_id,
                        "campaign_loaded",
                        {
                            "campaign_id": session_id,
                            "structured_data": structured,
                        },
                    )
            else:
                self.logger.warning(
                    "No structured data found for session %s",
                    session_id,
                )
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "Error loading campaign state for %s: %s",
                session_id,
                exc,
            )

    def get_connection_stats(self) -> Dict:
        """Return aggregate connection statistics."""
        total_players = sum(len(state.player_connections) for state in self.sessions.values())
        total_dms = sum(len(state.dm_connections) for state in self.sessions.values())

        return {
            "total_sessions": len(self.sessions),
            "total_player_connections": total_players,
            "total_dm_connections": total_dms,
            "sessions": {
                session_id: {
                    "player_connections": len(state.player_connections),
                    "dm_connections": len(state.dm_connections),
                    "has_campaign_state": state.last_campaign_state is not None,
                }
                for session_id, state in self.sessions.items()
            },
        }

    def get_connected_user_ids(self, session_id: str) -> List[str]:
        """Get list of unique user IDs currently connected to a session.

        Returns user_ids from both player and DM connections.
        Filters out None values and deduplicates.

        Args:
            session_id: Session/campaign identifier

        Returns:
            List of unique user IDs
        """
        state = self.sessions.get(session_id)
        if not state:
            logger.warning(
                "[AUDIO_DEBUG] ⚠️ No session state found for %s in get_connected_user_ids - no WebSocket connections registered!",
                session_id,
            )
            return []

        user_ids = set()

        # Collect user IDs from player connections
        logger.info(
            "[AUDIO_DEBUG] 🔍 Session %s has %d player connections, %d DM connections",
            session_id,
            len(state.player_connections),
            len(state.dm_connections),
        )

        for conn in state.player_connections:
            logger.info(
                "[AUDIO_DEBUG] 👤 Player connection: user_id=%s email=%s",
                conn.user_id or "None",
                conn.user_email or "None",
            )
            if conn.user_id:
                user_ids.add(conn.user_id)

        # Collect user IDs from DM connections
        for conn in state.dm_connections:
            logger.info(
                "[AUDIO_DEBUG] 🎭 DM connection: user_id=%s email=%s",
                conn.user_id or "None",
                conn.user_email or "None",
            )
            if conn.user_id:
                user_ids.add(conn.user_id)

        logger.info(
            "[AUDIO_DEBUG] ✅ Collected %d unique user IDs from session %s: %s",
            len(user_ids),
            session_id,
            list(user_ids),
        )
        return list(user_ids)

    async def set_active_campaign(
        self,
        session_id: str,
        structured_data: Optional[Dict] = None,
    ) -> None:
        """Mark a session as active and optionally broadcast state."""
        state = self._get_state(session_id)

        if structured_data:
            state.last_campaign_state = structured_data
            await self.broadcast_campaign_update(
                session_id,
                "campaign_loaded",
                {
                    "campaign_id": session_id,
                    "structured_data": structured_data,
                },
            )
        else:
            await self._load_current_campaign_state(
                session_id,
                state,
                broadcast=True,
            )

    async def clear_active_campaign(self, session_id: str) -> None:
        """Clear cached state for a session and notify listeners."""
        state = self.sessions.get(session_id)
        if not state:
            return

        state.last_campaign_state = None
        await self.broadcast_campaign_update(
            session_id,
            "campaign_deactivated",
            {"campaign_id": session_id},
        )
        self._prune_state_if_empty(session_id)

    async def force_refresh_campaign_state(self, session_id: str) -> None:
        """Reload campaign state and broadcast to players."""
        state = self._get_state(session_id)
        state.last_campaign_state = None
        await self._load_current_campaign_state(
            session_id,
            state,
            broadcast=True,
        )

    def _get_state(self, session_id: str) -> SessionState:
        """Get or create session state."""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
            # Clear warning flag since session now exists
            self._missing_session_warned.discard(session_id)
        return self.sessions[session_id]

    def _prune_state_if_empty(self, session_id: str) -> None:
        """Remove session state if there are no active connections or data."""
        state = self.sessions.get(session_id)
        if not state:
            return

        # Check if we can prune the entire state
        # IMPORTANT: Don't prune if collab_session has actual text content - user might just be refreshing
        has_collab_content = (
            hasattr(state, 'collab_session')
            and state.collab_session is not None
            and state.collab_session.has_text_content()
        )

        if (
            not state.player_connections
            and not state.dm_connections
            and state.last_campaign_state is None
            and not has_collab_content
        ):
            self.sessions.pop(session_id, None)

    def get_connected_players(self, session_id: str) -> List[Dict]:
        """Get list of connected players for a session.

        Deduplicates by user_id to handle multiple browser tabs/windows.
        Shows the earliest connection time for each unique user.
        """
        state = self.sessions.get(session_id)
        if not state:
            return []

        # Deduplicate by user_id, keeping the earliest connection
        users: Dict[str, ConnectionInfo] = {}
        for conn in state.player_connections:
            key = conn.user_id or f"anon_{id(conn)}"  # Unique key for anonymous users
            if key not in users or conn.connected_at < users[key].connected_at:
                users[key] = conn

        return [
            {
                "user_id": conn.user_id,
                "display_name": conn.display_name or conn.user_email or conn.user_id,
                "connection_type": conn.connection_type,
                "connected_at": conn.connected_at.isoformat(),
                "last_heartbeat": conn.last_heartbeat.isoformat(),
            }
            for conn in users.values()
        ]

    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task for stale collaborative players."""
        try:
            loop = asyncio.get_running_loop()
            self._cleanup_task = loop.create_task(self._cleanup_loop())
            logger.info("[CampaignBroadcaster] Started collaborative player cleanup task")
        except RuntimeError:
            # No running event loop yet - cleanup will be started when loop is available
            logger.debug("[CampaignBroadcaster] No event loop yet, cleanup task will start later")

    async def _cleanup_loop(self) -> None:
        """Periodically cleanup stale collaborative players from all sessions."""
        while True:
            try:
                await asyncio.sleep(15)  # Run every 15 seconds
                await self._cleanup_stale_collaborative_players()
            except asyncio.CancelledError:
                logger.info("[CampaignBroadcaster] Cleanup task cancelled")
                break
            except Exception as e:
                logger.error("[CampaignBroadcaster] Error in cleanup loop: %s", e, exc_info=True)

    async def _cleanup_stale_collaborative_players(self) -> None:
        """Remove stale players from all collaborative sessions."""
        for session_id, state in list(self.sessions.items()):
            if not hasattr(state, 'collab_session'):
                continue

            collab_session = state.collab_session
            removed_players = collab_session.cleanup_stale_players(grace_period_seconds=10)

            if removed_players:
                # Broadcast updated player list
                players_payload = collab_session.get_all_players()
                await self.broadcast_campaign_update(
                    session_id,
                    "player_list",
                    {
                        "sessionId": session_id,
                        "players": players_payload,
                    }
                )
                logger.info("[CampaignBroadcaster] Cleaned up %d stale players from session=%s",
                           len(removed_players), session_id)


# Singleton instance - will be initialized with campaign_service in main.py
campaign_broadcaster = CampaignBroadcaster()
