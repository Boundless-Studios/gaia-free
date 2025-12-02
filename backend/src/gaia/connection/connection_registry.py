"""Connection registry for managing WebSocket connection lifecycle.

Manages WebSocket connection state including:
- Connection creation with unique tokens
- Heartbeat tracking
- Disconnect handling
- Connection metadata (user, session, timestamps)

Note: Audio playback tracking has been moved to connection_playback_tracker.py
to maintain clean separation of concerns.

Key features:
- Connection tokens for resume support
- Per-connection metadata tracking
- Active connection queries by session
- Automatic cleanup of old connections
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy import select, and_, or_, delete, update
from sqlalchemy.exc import SQLAlchemyError

from db.src.connection import db_manager
from gaia.connection.models import (
    WebSocketConnection,
    ConnectionPlaybackState,
    ConnectionStatus,
)

logger = logging.getLogger(__name__)


class ConnectionRegistry:
    """Manages WebSocket connection lifecycle and per-connection playback state."""

    def __init__(self) -> None:
        self._db_enabled = False
        self._db_failed_reason: Optional[str] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables for connection registry."""
        try:
            db_manager.initialize()
            engine = getattr(db_manager, "sync_engine", None)
            if engine is None:
                raise RuntimeError("Database sync engine not available")

            with engine.begin() as connection:
                WebSocketConnection.__table__.create(bind=connection, checkfirst=True)
                ConnectionPlaybackState.__table__.create(bind=connection, checkfirst=True)

            self._db_enabled = True
            logger.info("Connection registry database initialized successfully")

        except Exception as exc:
            self._disable_db(f"Failed to initialize connection registry database: {exc}")

    def _disable_db(self, reason: str) -> None:
        """Disable database operations with a reason."""
        if self._db_enabled:
            logger.warning("Disabling connection registry database: %s", reason)
        else:
            logger.debug("Connection registry database unavailable: %s", reason)
        self._db_enabled = False
        self._db_failed_reason = reason

    @property
    def db_enabled(self) -> bool:
        """Return True when database synchronization is active."""
        return self._db_enabled

    @property
    def db_failure_reason(self) -> Optional[str]:
        """Return the reason database synchronization was disabled, if any."""
        return self._db_failed_reason

    # -------------------------------------------------------------------------
    # Connection lifecycle management
    # -------------------------------------------------------------------------

    def create_connection(
        self,
        session_id: str,
        connection_type: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        origin: Optional[str] = None,
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
        seat_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, str]:
        """Register a new WebSocket connection.

        Args:
            seat_id: Optional seat_id for player connections with claimed seats

        Returns:
            Dict with connection_id and connection_token
        """
        if not self._db_enabled:
            raise RuntimeError("Connection registry database is not enabled")

        # Generate unique connection token for resume support
        connection_token = secrets.token_urlsafe(32)
        connection_id = uuid.uuid4()

        try:
            with db_manager.get_sync_session() as session:
                connection = WebSocketConnection(
                    connection_id=connection_id,
                    connection_token=connection_token,
                    session_id=session_id,
                    user_id=user_id,
                    user_email=user_email,
                    connection_type=connection_type,
                    status=ConnectionStatus.CONNECTED,
                    connected_at=datetime.now(timezone.utc),
                    origin=origin,
                    user_agent=user_agent,
                    client_ip=client_ip,
                    seat_id=seat_id,
                )
                session.add(connection)
                session.commit()

            logger.debug(
                "[CONN_REGISTRY] Created connection | id=%s token=%s session=%s type=%s user=%s",
                connection_id,
                connection_token[:12] + "...",
                session_id,
                connection_type,
                user_id,
            )

            return {
                "connection_id": str(connection_id),
                "connection_token": connection_token,
            }

        except SQLAlchemyError as exc:
            logger.error("[CONN_REGISTRY] Failed to create connection: %s", exc)
            raise

    def update_heartbeat(self, connection_id: uuid.UUID) -> bool:
        """Update last heartbeat timestamp for a connection.

        Uses atomic SQL update to avoid race conditions.

        Returns:
            True if successful, False if connection not found
        """
        if not self._db_enabled:
            return False

        try:
            with db_manager.get_sync_session() as session:
                # Use atomic update instead of read-modify-write to avoid race conditions
                stmt = update(WebSocketConnection).where(
                    WebSocketConnection.connection_id == connection_id
                ).values(
                    last_heartbeat=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                result = session.execute(stmt)
                session.commit()
                return result.rowcount > 0

        except SQLAlchemyError as exc:
            logger.warning("[CONN_REGISTRY] Failed to update heartbeat: %s", exc)
            return False

    def update_connection_identity(
        self,
        connection_id: uuid.UUID,
        user_id: Optional[str],
        user_email: Optional[str],
    ) -> bool:
        """Persist user identity for an existing connection."""
        if not self._db_enabled:
            return False

        try:
            with db_manager.get_sync_session() as session:
                stmt = (
                    update(WebSocketConnection)
                    .where(WebSocketConnection.connection_id == connection_id)
                    .values(
                        user_id=user_id,
                        user_email=user_email,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                result = session.execute(stmt)
                session.commit()
                return result.rowcount > 0
        except SQLAlchemyError as exc:
            logger.warning("[CONN_REGISTRY] Failed to update connection identity: %s", exc)
            return False

    def update_connection_seat(
        self,
        connection_id: uuid.UUID,
        seat_id: Optional[uuid.UUID],
    ) -> bool:
        """Persist seat association for a connection row."""
        if not self._db_enabled:
            return False
        try:
            with db_manager.get_sync_session() as session:
                stmt = (
                    update(WebSocketConnection)
                    .where(WebSocketConnection.connection_id == connection_id)
                    .values(
                        seat_id=seat_id,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                result = session.execute(stmt)
                session.commit()
                return result.rowcount > 0
        except SQLAlchemyError as exc:
            logger.warning("[CONN_REGISTRY] Failed to update connection seat: %s", exc)
            return False

    def update_user_seat(
        self,
        session_id: str,
        user_id: Optional[str],
        seat_id: Optional[str],
    ) -> bool:
        """Update seat references for all active connections by user within a session."""
        if not self._db_enabled or not user_id:
            return False
        try:
            seat_uuid: Optional[uuid.UUID] = None
            if seat_id:
                seat_uuid = uuid.UUID(str(seat_id))
            with db_manager.get_sync_session() as session:
                stmt = (
                    update(WebSocketConnection)
                    .where(
                        WebSocketConnection.session_id == session_id,
                        WebSocketConnection.user_id == user_id,
                        WebSocketConnection.status == ConnectionStatus.CONNECTED,
                    )
                    .values(
                        seat_id=seat_uuid,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                result = session.execute(stmt)
                session.commit()
                return result.rowcount > 0
        except SQLAlchemyError as exc:
            logger.warning("[CONN_REGISTRY] Failed to update user seat: %s", exc)
            return False

    def disconnect_connection(
        self,
        connection_id: uuid.UUID,
        status: ConnectionStatus = ConnectionStatus.DISCONNECTED,
    ) -> bool:
        """Mark a connection as disconnected.

        Args:
            connection_id: Connection to disconnect
            status: DISCONNECTED (clean) or FAILED (error)

        Returns:
            True if successful, False if connection not found
        """
        if not self._db_enabled:
            return False

        try:
            with db_manager.get_sync_session() as session:
                connection = session.get(WebSocketConnection, connection_id)
                if not connection:
                    return False

                connection.status = status
                connection.disconnected_at = datetime.now(timezone.utc)
                session.commit()

            logger.info(
                "[CONN_REGISTRY] Disconnected | id=%s status=%s",
                connection_id,
                status.value,
            )
            return True

        except SQLAlchemyError as exc:
            logger.error("[CONN_REGISTRY] Failed to disconnect connection: %s", exc)
            return False

    def get_connection(self, connection_id: uuid.UUID) -> Optional[Dict]:
        """Get connection metadata.

        Returns:
            Connection dict or None if not found
        """
        if not self._db_enabled:
            return None

        try:
            with db_manager.get_sync_session() as session:
                connection = session.get(WebSocketConnection, connection_id)
                if not connection:
                    return None

                return {
                    "connection_id": str(connection.connection_id),
                    "connection_token": connection.connection_token,
                    "session_id": connection.session_id,
                    "user_id": connection.user_id,
                    "connection_type": connection.connection_type,
                    "status": connection.status.value,
                    "connected_at": connection.connected_at.isoformat(),
                    "disconnected_at": connection.disconnected_at.isoformat() if connection.disconnected_at else None,
                    "last_heartbeat": connection.last_heartbeat.isoformat() if connection.last_heartbeat else None,
                }

        except SQLAlchemyError as exc:
            logger.warning("[CONN_REGISTRY] Failed to get connection: %s", exc)
            return None

    def get_connection_by_token(self, connection_token: str) -> Optional[Dict]:
        """Get connection by resume token.

        Used for reconnection scenarios.

        Returns:
            Connection dict or None if not found
        """
        if not self._db_enabled:
            return None

        try:
            with db_manager.get_sync_session() as session:
                stmt = select(WebSocketConnection).where(
                    WebSocketConnection.connection_token == connection_token
                )
                connection = session.execute(stmt).scalar_one_or_none()

                if not connection:
                    return None

                return {
                    "connection_id": str(connection.connection_id),
                    "connection_token": connection.connection_token,
                    "session_id": connection.session_id,
                    "user_id": connection.user_id,
                    "connection_type": connection.connection_type,
                    "status": connection.status.value,
                    "connected_at": connection.connected_at.isoformat(),
                    "disconnected_at": connection.disconnected_at.isoformat() if connection.disconnected_at else None,
                }

        except SQLAlchemyError as exc:
            logger.warning("[CONN_REGISTRY] Failed to get connection by token: %s", exc)
            return None

    def get_active_connections(self, session_id: str) -> List[Dict]:
        """Get all active connections for a session.

        Returns:
            List of connection dicts
        """
        if not self._db_enabled:
            return []

        try:
            with db_manager.get_sync_session() as session:
                stmt = select(WebSocketConnection).where(
                    and_(
                        WebSocketConnection.session_id == session_id,
                        WebSocketConnection.status == ConnectionStatus.CONNECTED,
                    )
                ).order_by(WebSocketConnection.connected_at)

                connections = session.execute(stmt).scalars().all()

                return [
                    {
                        "connection_id": str(conn.connection_id),
                        "user_id": conn.user_id,
                        "connection_type": conn.connection_type,
                        "connected_at": conn.connected_at.isoformat(),
                        "last_heartbeat": conn.last_heartbeat.isoformat() if conn.last_heartbeat else None,
                    }
                    for conn in connections
                ]

        except SQLAlchemyError as exc:
            logger.warning("[CONN_REGISTRY] Failed to get active connections: %s", exc)
            return []

    # -------------------------------------------------------------------------
    # Cleanup operations
    # -------------------------------------------------------------------------

    def cleanup_old_connections(self, max_age_hours: int = 24) -> int:
        """Remove connections older than max_age_hours.

        Args:
            max_age_hours: Age threshold in hours

        Returns:
            Number of connections removed
        """
        if not self._db_enabled:
            return 0

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

            with db_manager.get_sync_session() as session:
                # Delete old disconnected connections
                stmt = delete(WebSocketConnection).where(
                    and_(
                        WebSocketConnection.status != ConnectionStatus.CONNECTED,
                        WebSocketConnection.disconnected_at < cutoff,
                    )
                )
                result = session.execute(stmt)
                session.commit()

                removed = result.rowcount
                logger.info(
                    "[CONN_REGISTRY] Cleaned up %d old connections (older than %dh)",
                    removed,
                    max_age_hours,
                )
                return removed

        except SQLAlchemyError as exc:
            logger.error("[CONN_REGISTRY] Failed to cleanup old connections: %s", exc)
            return 0


# Singleton instance
connection_registry = ConnectionRegistry()
