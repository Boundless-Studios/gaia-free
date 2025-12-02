"""Connection playback state model for tracking audio delivery per connection."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Index,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import String as SAString

from db.src.base import BaseModel


try:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
except ImportError:  # pragma: no cover - fallback for environments without dialect
    PG_UUID = None  # type: ignore


def _uuid_column(**kwargs) -> Mapped[uuid.UUID]:
    """Helper to create UUID columns compatible with Postgres + SQLite."""
    if PG_UUID:
        column_type = PG_UUID(as_uuid=True)
        default_factory = uuid.uuid4
    else:
        column_type = SAString(36)
        default_factory = lambda: str(uuid.uuid4())
    return mapped_column(
        column_type,
        default=default_factory,
        nullable=False,
        **kwargs,
    )


class ConnectionPlaybackState(BaseModel):
    """Tracks what audio has been sent/played to a specific connection.

    This enables:
    - Resume playback after reconnection (don't resend played chunks)
    - Per-connection acknowledgment (track what each client has actually received)
    - Connection-scoped audio queueing (different clients can be at different positions)
    """

    __tablename__ = "connection_playback_states"
    __table_args__ = (
        Index("ix_conn_playback_connection", "connection_id", "sequence_number"),
        Index("ix_conn_playback_chunk", "chunk_id"),
        Index("ix_conn_playback_request", "request_id", "connection_id"),
    )

    # Identity
    playback_state_id: Mapped[uuid.UUID] = _uuid_column(primary_key=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("websocket_connections.connection_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Audio reference (links to AudioChunk and AudioPlaybackRequest)
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        String(255),  # Reference to AudioChunk.chunk_id
        nullable=False,
        index=True,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        String(255),  # Reference to AudioPlaybackRequest.request_id
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Playback order for this connection"
    )

    # State tracking
    sent_to_client: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether chunk was sent via WebSocket"
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    acknowledged_by_client: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether client confirmed receipt"
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    played_by_client: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether client reported playback complete"
    )
    played_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    connection: Mapped["WebSocketConnection"] = relationship(
        "WebSocketConnection",
        back_populates="playback_states",
    )
