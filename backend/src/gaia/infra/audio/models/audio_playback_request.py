"""SQLAlchemy model for audio playback requests."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.src.base import BaseModel
from db.src.db_utils import _uuid_column
from gaia.infra.audio.models.playback_status import PlaybackStatus


class AudioPlaybackRequest(BaseModel):
    """Tracks client audio playback requests with submission order."""

    __tablename__ = "audio_playback_requests"
    __table_args__ = (
        Index("ix_audio_playback_requests_campaign", "campaign_id", "requested_at"),
        Index("ix_audio_playback_requests_status", "campaign_id", "status"),
    )

    request_id: Mapped[uuid.UUID] = _uuid_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    playback_group: Mapped[str] = mapped_column(String(100), nullable=False)  # "narrative", "response", etc.
    status: Mapped[PlaybackStatus] = mapped_column(
        SQLEnum(PlaybackStatus, native_enum=False),
        default=PlaybackStatus.PENDING,
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_chunks: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    text: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )
    message_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Relationship to chunks
    chunks: Mapped[list["AudioChunk"]] = relationship(
        "AudioChunk",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AudioChunk.sequence_number",
    )
