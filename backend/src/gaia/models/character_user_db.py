"""SQLAlchemy model for character-user associations in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from db.src.base import BaseModel

if TYPE_CHECKING:
    from gaia.models.character_db import CharacterProfile


class CharacterUser(BaseModel):
    """SQLAlchemy model for character-user associations.

    Maps to game.character_users table. Tracks ownership and sharing
    of characters between users.
    """

    __tablename__ = "character_users"
    __table_args__ = (
        UniqueConstraint("character_id", "user_id", name="uq_character_user"),
        {"schema": "game"},
    )

    # Primary key
    association_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign keys
    character_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("game.character_profiles.character_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    user_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Access role
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="owner",
        index=True,
    )

    # Metadata
    granted_by_user_id: Mapped[Optional[str]] = mapped_column(String(255))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    character: Mapped["CharacterProfile"] = relationship(
        "CharacterProfile",
        back_populates="user_associations",
    )
