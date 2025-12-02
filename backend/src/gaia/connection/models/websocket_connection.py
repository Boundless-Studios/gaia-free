"""WebSocket connection model for tracking individual connection instances."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.src.base import BaseModel
from db.src.db_utils import _uuid_column
from .connection_status import ConnectionStatus


class WebSocketConnection(BaseModel):
    """Tracks individual WebSocket connection instances.

    Each connection is unique and has its own:
    - Connection lifecycle (connect/disconnect events)
    - Audio playback state (which chunks have been sent/played)
    - Client metadata (user agent, IP, etc.)

    When a client reconnects, a NEW connection record is created.
    The connection_token allows the client to resume their previous playback state.
    """

    __tablename__ = "websocket_connections"
    __table_args__ = (
        Index("ix_ws_connections_session", "session_id", "connected_at"),
        Index("ix_ws_connections_token", "connection_token"),
        Index("ix_ws_connections_user", "user_id", "connected_at"),
        Index("ix_ws_connections_status", "status", "disconnected_at"),
    )

    # Connection identity
    connection_id: Mapped[uuid.UUID] = _uuid_column(primary_key=True)
    connection_token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="Client-stored token to resume playback on reconnect"
    )

    # Session/user context
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    connection_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="player or dm"
    )

    # Connection lifecycle
    status: Mapped[ConnectionStatus] = mapped_column(
        SQLEnum(ConnectionStatus, native_enum=False),
        default=ConnectionStatus.CONNECTED,
        nullable=False,
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Client metadata
    origin: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 max length

    # Game room seat association
    seat_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("room_seats.seat_id", ondelete="SET NULL"),
        nullable=True
    )

    # Playback state tracking
    playback_states: Mapped[list["ConnectionPlaybackState"]] = relationship(
        "ConnectionPlaybackState",
        back_populates="connection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
