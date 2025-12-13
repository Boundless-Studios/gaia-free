"""SQLAlchemy model for NPC profiles in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from db.src.base import BaseModel
from gaia.models.character.npc_profile import NpcProfile as NpcProfileDataclass
from gaia.models.character.enums import CharacterRole, CharacterCapability

if TYPE_CHECKING:
    from gaia.models.campaign_db import Campaign
    from gaia.models.character_db import CharacterProfile


class NpcProfile(BaseModel):
    """SQLAlchemy model for NPC profiles.

    Maps to game.npc_profiles table. Lightweight NPC records that can be
    promoted to full CharacterProfile when needed.
    """

    __tablename__ = "npc_profiles"
    __table_args__ = {"schema": "game"}

    # Primary key
    npc_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # External identifier (for backward compatibility)
    external_npc_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # Ownership (required for NPCs)
    created_by_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    created_by_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Campaign association (NULL = reusable across campaigns)
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("game.campaigns.campaign_id", ondelete="SET NULL"),
        index=True,
    )

    # Core NPC data
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="npc_support")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    relationships: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    capabilities: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Promotion tracking
    has_full_sheet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promoted_to_character_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("game.character_profiles.character_id", ondelete="SET NULL"),
        index=True,
    )
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Metadata
    npc_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign")
    promoted_character: Mapped[Optional["CharacterProfile"]] = relationship("CharacterProfile")

    def to_dataclass(self) -> NpcProfileDataclass:
        """Convert to NpcProfile dataclass.

        Returns:
            NpcProfile dataclass instance
        """
        role = CharacterRole(self.role)
        capabilities = CharacterCapability(self.capabilities)

        return NpcProfileDataclass(
            npc_id=self.external_npc_id,
            display_name=self.display_name,
            role=role,
            description=self.description,
            tags=list(self.tags or []),
            relationships=dict(self.relationships or {}),
            notes=list(self.notes or []),
            has_full_sheet=self.has_full_sheet,
            capabilities=capabilities,
            created_at=self.created_at,
            updated_at=self.updated_at,
            metadata=dict(self.npc_metadata or {}),
        )

    @classmethod
    def from_dataclass(
        cls,
        npc: NpcProfileDataclass,
        created_by_user_id: str,
        created_by_email: Optional[str] = None,
        campaign_id: Optional[uuid.UUID] = None,
    ) -> "NpcProfile":
        """Create from NpcProfile dataclass.

        Args:
            npc: NpcProfile dataclass
            created_by_user_id: User who created this NPC
            created_by_email: Email of creating user
            campaign_id: Optional campaign association

        Returns:
            NpcProfile SQLAlchemy model
        """
        return cls(
            external_npc_id=npc.npc_id,
            created_by_user_id=created_by_user_id,
            created_by_email=created_by_email,
            campaign_id=campaign_id,
            display_name=npc.display_name,
            role=npc.role.value,
            description=npc.description,
            tags=list(npc.tags or []),
            relationships=dict(npc.relationships or {}),
            notes=list(npc.notes or []),
            has_full_sheet=npc.has_full_sheet,
            capabilities=int(npc.capabilities),
            npc_metadata=dict(npc.metadata or {}),
            created_at=npc.created_at,
            updated_at=npc.updated_at,
        )

    def soft_delete(self) -> None:
        """Mark NPC as deleted (soft delete)."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted NPC."""
        self.is_deleted = False
        self.deleted_at = None
