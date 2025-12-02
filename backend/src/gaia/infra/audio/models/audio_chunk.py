"""SQLAlchemy model for audio chunks."""

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
    Float,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.src.base import BaseModel
from db.src.db_utils import _uuid_column
from gaia.infra.audio.models.playback_status import PlaybackStatus


class AudioChunk(BaseModel):
    """Tracks individual audio chunks within a playback request."""

    __tablename__ = "audio_chunks"
    __table_args__ = (
        Index("ix_audio_chunks_campaign", "campaign_id", "created_at"),
        Index("ix_audio_chunks_request", "request_id", "sequence_number"),
        Index("ix_audio_chunks_status", "campaign_id", "status"),
    )

    chunk_id: Mapped[uuid.UUID] = _uuid_column(primary_key=True)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audio_playback_requests.request_id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artifact_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Reference to audio artifact store
    url: Mapped[str] = mapped_column(String(1024), nullable=False)  # Proxy URL for client
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Order within request
    status: Mapped[PlaybackStatus] = mapped_column(
        SQLEnum(PlaybackStatus, native_enum=False),
        default=PlaybackStatus.PENDING,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(String(100), default="audio/mpeg", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)  # GCS or local path
    bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # GCS bucket if used
    played_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship to request
    request: Mapped["AudioPlaybackRequest"] = relationship(
        "AudioPlaybackRequest",
        back_populates="chunks",
    )
