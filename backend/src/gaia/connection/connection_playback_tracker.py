"""Playback state tracking for WebSocket connections.

Manages per-connection audio chunk delivery tracking:
- What chunks were sent to each connection
- Which chunks were acknowledged
- Which chunks were played

This is separated from connection lifecycle management to maintain clean responsibilities.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError

from db.src.connection import db_manager
from gaia.connection.models import ConnectionPlaybackState

logger = logging.getLogger(__name__)


class ConnectionPlaybackTracker:
    """Tracks audio chunk delivery and playback state per WebSocket connection."""

    def __init__(self) -> None:
        self._db_enabled = False
        self._db_failed_reason: Optional[str] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database connection for playback tracking."""
        try:
            db_manager.initialize()
            engine = getattr(db_manager, "sync_engine", None)
            if engine is None:
                raise RuntimeError("Database sync engine not available")

            self._db_enabled = True
            logger.info("[PLAYBACK_TRACKER] Database initialized successfully")

        except Exception as exc:
            self._disable_db(f"Failed to initialize: {exc}")

    def _disable_db(self, reason: str) -> None:
        """Disable database operations due to failure."""
        self._db_enabled = False
        self._db_failed_reason = reason
        logger.warning("[PLAYBACK_TRACKER] Database disabled: %s", reason)

    @property
    def db_enabled(self) -> bool:
        """Check if database operations are available."""
        return self._db_enabled

    @property
    def db_failure_reason(self) -> Optional[str]:
        """Get reason for database failure, if any."""
        return self._db_failed_reason

    def record_chunk_sent(
        self,
        connection_id: uuid.UUID,
        chunk_id: uuid.UUID,
        request_id: uuid.UUID,
        sequence_number: int,
    ) -> bool:
        """Record that a chunk was sent to a connection.

        Args:
            connection_id: Connection that received the chunk
            chunk_id: Audio chunk ID
            request_id: Parent request ID
            sequence_number: Playback order for this connection

        Returns:
            True if successful
        """
        if not self._db_enabled:
            return False

        try:
            with db_manager.get_sync_session() as session:
                # Check if already exists
                stmt = select(ConnectionPlaybackState).where(
                    and_(
                        ConnectionPlaybackState.connection_id == connection_id,
                        ConnectionPlaybackState.chunk_id == str(chunk_id),
                    )
                )
                existing = session.execute(stmt).scalar_one_or_none()

                if existing:
                    # Update existing record
                    existing.sent_to_client = True
                    existing.sent_at = datetime.now(timezone.utc)
                else:
                    # Create new record
                    state = ConnectionPlaybackState(
                        connection_id=connection_id,
                        chunk_id=str(chunk_id),
                        request_id=str(request_id),
                        sequence_number=sequence_number,
                        sent_to_client=True,
                        sent_at=datetime.now(timezone.utc),
                    )
                    session.add(state)

                session.commit()
                return True

        except SQLAlchemyError as exc:
            logger.warning("[PLAYBACK_TRACKER] Failed to record chunk sent: %s", exc)
            return False

    def record_chunk_acknowledged(
        self,
        connection_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> bool:
        """Record that client acknowledged receipt of chunk.

        Returns:
            True if successful
        """
        if not self._db_enabled:
            return False

        try:
            with db_manager.get_sync_session() as session:
                stmt = select(ConnectionPlaybackState).where(
                    and_(
                        ConnectionPlaybackState.connection_id == connection_id,
                        ConnectionPlaybackState.chunk_id == str(chunk_id),
                    )
                )
                state = session.execute(stmt).scalar_one_or_none()

                if not state:
                    logger.warning(
                        "[PLAYBACK_TRACKER] Cannot acknowledge chunk %s - not found for connection %s",
                        chunk_id,
                        connection_id,
                    )
                    return False

                state.acknowledged_by_client = True
                state.acknowledged_at = datetime.now(timezone.utc)
                session.commit()
                return True

        except SQLAlchemyError as exc:
            logger.warning("[PLAYBACK_TRACKER] Failed to record chunk acknowledged: %s", exc)
            return False

    def record_chunk_played(
        self,
        connection_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> bool:
        """Record that client finished playing a chunk.

        Returns:
            True if successful
        """
        if not self._db_enabled:
            return False

        try:
            with db_manager.get_sync_session() as session:
                stmt = select(ConnectionPlaybackState).where(
                    and_(
                        ConnectionPlaybackState.connection_id == connection_id,
                        ConnectionPlaybackState.chunk_id == str(chunk_id),
                    )
                )
                state = session.execute(stmt).scalar_one_or_none()

                if not state:
                    logger.warning(
                        "[PLAYBACK_TRACKER] Cannot mark chunk %s played - not found for connection %s",
                        chunk_id,
                        connection_id,
                    )
                    return False

                state.played_by_client = True
                state.played_at = datetime.now(timezone.utc)
                session.commit()

                logger.debug(
                    "[PLAYBACK_TRACKER] Marked chunk played | conn=%s chunk=%s",
                    connection_id,
                    chunk_id,
                )
                return True

        except SQLAlchemyError as exc:
            logger.warning("[PLAYBACK_TRACKER] Failed to record chunk played: %s", exc)
            return False

    def get_unsent_chunks(
        self,
        connection_id: uuid.UUID,
        all_chunk_ids: List[uuid.UUID],
    ) -> List[uuid.UUID]:
        """Get list of chunks that haven't been sent to this connection yet.

        Args:
            connection_id: Connection to check
            all_chunk_ids: Complete list of chunk IDs for the session

        Returns:
            List of chunk IDs not yet sent to this connection
        """
        if not self._db_enabled:
            return all_chunk_ids  # Fail open - send all chunks

        try:
            with db_manager.get_sync_session() as session:
                # Get all chunks already sent to this connection
                stmt = select(ConnectionPlaybackState.chunk_id).where(
                    and_(
                        ConnectionPlaybackState.connection_id == connection_id,
                        ConnectionPlaybackState.sent_to_client == True,
                    )
                )
                sent_chunk_ids = set(session.execute(stmt).scalars().all())

                # Return chunks not in sent list
                return [
                    chunk_id for chunk_id in all_chunk_ids
                    if str(chunk_id) not in sent_chunk_ids
                ]

        except SQLAlchemyError as exc:
            logger.warning("[PLAYBACK_TRACKER] Failed to get unsent chunks: %s", exc)
            return all_chunk_ids  # Fail open

    def get_playback_position(self, connection_id: uuid.UUID) -> Dict:
        """Get playback state for a connection.

        Returns:
            Dict with playback statistics
        """
        if not self._db_enabled:
            return {"sent": 0, "acknowledged": 0, "played": 0}

        try:
            with db_manager.get_sync_session() as session:
                stmt = select(ConnectionPlaybackState).where(
                    ConnectionPlaybackState.connection_id == connection_id
                ).order_by(ConnectionPlaybackState.sequence_number)

                states = session.execute(stmt).scalars().all()

                sent_count = sum(1 for s in states if s.sent_to_client)
                ack_count = sum(1 for s in states if s.acknowledged_by_client)
                played_count = sum(1 for s in states if s.played_by_client)

                return {
                    "total_chunks": len(states),
                    "sent": sent_count,
                    "acknowledged": ack_count,
                    "played": played_count,
                    "last_played_sequence": max(
                        (s.sequence_number for s in states if s.played_by_client),
                        default=0
                    ),
                }

        except SQLAlchemyError as exc:
            logger.warning("[PLAYBACK_TRACKER] Failed to get playback position: %s", exc)
            return {"sent": 0, "acknowledged": 0, "played": 0}


# Global singleton instance
connection_playback_tracker = ConnectionPlaybackTracker()
