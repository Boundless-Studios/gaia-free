"""SQLAlchemy model for user-scoped audio playback queue."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.src.base import BaseModel
from db.src.db_utils import _uuid_column


class UserAudioQueue(BaseModel):
    """Tracks which audio chunks each user needs to hear (user-scoped playback queue).

    This model replaces connection-scoped playback tracking with a simpler user-scoped approach:
    - Users are stable (user_id persists across reconnections)
    - Connections are ephemeral (WebSocket drops don't lose playback state)
    - Queue is per-user per-campaign (multiple tabs share same queue)
    - Client GETs pending chunks on connect/reconnect

    Lifecycle:
    1. New audio generated → rows created for each active user in campaign
    2. Client connects → GET /api/audio/queue/{user_id}/{campaign_id}
    3. Client plays chunk → marks delivered_at/played_at
    4. Cleanup task → removes old played chunks
    """

    __tablename__ = "user_audio_queue"
    __table_args__ = (
        Index("ix_user_queue_pending", "user_id", "campaign_id", "played_at"),
        Index("ix_user_queue_chunk", "chunk_id"),
        Index("ix_user_queue_request", "request_id"),
        Index("ix_user_queue_delivered", "user_id", "campaign_id", "delivered_at"),
    )

    # Identity
    queue_id: Mapped[uuid.UUID] = _uuid_column(primary_key=True)

    # User/campaign scope (stable keys)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Audio references
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audio_chunks.chunk_id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audio_playback_requests.request_id", ondelete="CASCADE"),
        nullable=False,
    )

    # State tracking
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When chunk was sent/made available to client",
    )
    played_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When client reported playback complete",
    )

    # Relationships
    chunk: Mapped["AudioChunk"] = relationship("AudioChunk")
    request: Mapped["AudioPlaybackRequest"] = relationship("AudioPlaybackRequest")
