"""SQLAlchemy model for scene-entity associations in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy import UniqueConstraint

from db.src.base import BaseModel
from gaia.models.scene_participant import SceneParticipant

if TYPE_CHECKING:
    from gaia.models.scene_db import Scene


class SceneEntity(BaseModel):
    """Generic scene-entity association model.

    Maps to game.scene_entities table. Tracks any entity type in a scene:
    characters, items, objects, quests, locations, etc.

    When characters are moved to database, this table will have foreign key
    relationships to the character table.
    """

    __tablename__ = "scene_entities"
    __table_args__ = (
        UniqueConstraint("scene_id", "entity_id", "entity_type", name="uq_scene_entity"),
        {"schema": "game"},
    )

    # Primary key
    scene_entity_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign keys
    scene_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("game.scenes.scene_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Entity identification
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Presence tracking
    is_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Role (primarily for characters)
    role: Mapped[Optional[str]] = mapped_column(String(50))

    # Entity-specific metadata (named entity_metadata to avoid SQLAlchemy reserved 'metadata')
    entity_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    scene: Mapped["Scene"] = relationship("Scene", back_populates="entities")

    @classmethod
    def from_scene_participant(
        cls, scene_id: str, participant: SceneParticipant
    ) -> "SceneEntity":
        """Create SceneEntity from SceneParticipant.

        Converts a SceneParticipant (character-specific) to a generic
        SceneEntity database record.

        Args:
            scene_id: Scene this entity belongs to
            participant: SceneParticipant to convert

        Returns:
            SceneEntity model instance
        """
        entity_id = participant.character_id or f"unnamed_{participant.display_name}"

        # Store capabilities and source in entity_metadata
        entity_metadata = dict(participant.metadata) if participant.metadata else {}
        entity_metadata["capabilities"] = int(participant.capabilities)
        if participant.source:
            entity_metadata["source"] = participant.source

        return cls(
            scene_id=scene_id,
            entity_id=entity_id,
            entity_type="character",
            is_present=participant.is_present,
            joined_at=participant.joined_at,
            left_at=participant.left_at,
            role=participant.role.value,
            entity_metadata=entity_metadata,
        )

    def mark_departed(self, timestamp: Optional[datetime] = None) -> None:
        """Mark entity as no longer present in the scene."""
        self.is_present = False
        self.left_at = timestamp or datetime.now(timezone.utc)

    def restore(self, timestamp: Optional[datetime] = None) -> None:
        """Mark entity as present again in the scene."""
        self.is_present = True
        self.joined_at = timestamp or datetime.now(timezone.utc)
        self.left_at = None
