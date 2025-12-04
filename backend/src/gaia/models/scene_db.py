"""SQLAlchemy model for scene persistence in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from db.src.base import BaseModel
from gaia.models.scene_info import SceneInfo
from gaia.models.scene_participant import SceneParticipant
from gaia.models.character.enums import CharacterRole, CharacterCapability

if TYPE_CHECKING:
    from gaia.models.scene_entity_db import SceneEntity


class Scene(BaseModel):
    """SQLAlchemy model for scenes stored in PostgreSQL.

    Maps to game.scenes table. Supports soft deletes and JSONB storage for
    arrays and complex data structures.
    """

    __tablename__ = "scenes"
    __table_args__ = {"schema": "game"}

    # Primary key
    scene_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    # Campaign association - no FK constraint until campaigns are in DB
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Immutable creation fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    location_description: Mapped[Optional[str]] = mapped_column(Text)
    scene_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # JSONB array fields (narrative data)
    objectives: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    narrative_notes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Mutable tracking fields (JSONB arrays)
    outcomes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    objectives_completed: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    objectives_added: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    description_updates: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Status and timing
    completion_status: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    duration_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Turn order (JSONB array of entity IDs)
    turn_order: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    current_turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    in_combat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    combat_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Entity display name overrides (JSONB object: {entity_id: display_name})
    entity_display_names: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Scene metadata (named scene_metadata to avoid SQLAlchemy reserved 'metadata')
    scene_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Soft delete support
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    scene_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    entities: Mapped[List["SceneEntity"]] = relationship(
        "SceneEntity",
        back_populates="scene",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_scene_info(self) -> SceneInfo:
        """Convert SQLAlchemy model to SceneInfo dataclass.

        Reconstructs SceneInfo from database representation, including
        converting scene_entities back to SceneParticipant objects.

        Returns:
            SceneInfo dataclass instance
        """
        # Convert scene_entities to SceneParticipant objects and compute NPC/PC lists
        participants = []
        npcs_involved = []  # All NPCs ever in scene
        npcs_present = []   # Currently present NPCs
        pcs_present = []    # PCs in scene
        npcs_added = []     # NPCs who joined after scene start
        npcs_removed = []   # NPCs who left the scene

        for entity in self.entities:
            if entity.entity_type == "character":
                # Extract role and capabilities from metadata or use defaults
                role_str = entity.role or CharacterRole.NPC_SUPPORT.value
                try:
                    role = CharacterRole(role_str)
                except ValueError:
                    role = CharacterRole.NPC_SUPPORT

                capabilities_int = entity.entity_metadata.get("capabilities", 0)
                try:
                    capabilities = CharacterCapability(capabilities_int)
                except ValueError:
                    capabilities = CharacterCapability.NONE

                participant = SceneParticipant(
                    character_id=entity.entity_id,
                    display_name=self.entity_display_names.get(entity.entity_id, entity.entity_id),
                    role=role,
                    capabilities=capabilities,
                    is_present=entity.is_present,
                    joined_at=entity.joined_at,
                    left_at=entity.left_at,
                    source=entity.entity_metadata.get("source"),
                    metadata=entity.entity_metadata,
                )
                participants.append(participant)

                # Compute NPC/PC tracking from entity data
                is_npc = role != CharacterRole.PLAYER
                is_original = entity.entity_metadata.get("is_original", True)

                if is_npc:
                    npcs_involved.append(entity.entity_id)
                    if entity.is_present:
                        npcs_present.append(entity.entity_id)
                    if not is_original:
                        npcs_added.append(entity.entity_id)
                    if entity.left_at is not None:
                        npcs_removed.append(entity.entity_id)
                else:
                    pcs_present.append(entity.entity_id)

        return SceneInfo(
            scene_id=self.scene_id,
            title=self.title,
            description=self.description,
            location_id=self.location_id or "",
            location_description=self.location_description or "",
            scene_type=self.scene_type,
            objectives=self.objectives or [],
            participants=participants,
            npcs_involved=npcs_involved,
            npcs_present=npcs_present,
            pcs_present=pcs_present,
            narrative_notes=self.narrative_notes or [],
            metadata=self.scene_metadata or {},
            timestamp=self.scene_timestamp,
            outcomes=self.outcomes or [],
            objectives_completed=self.objectives_completed or [],
            objectives_added=self.objectives_added or [],
            npcs_added=npcs_added,
            npcs_removed=npcs_removed,
            description_updates=self.description_updates or [],
            completion_status=self.completion_status,
            duration_turns=self.duration_turns,
            last_updated=self.last_updated,
            turn_order=self.turn_order or [],
            current_turn_index=self.current_turn_index,
            in_combat=self.in_combat,
            combat_data=self.combat_data,
        )

    @classmethod
    def from_scene_info(cls, scene_info: SceneInfo, campaign_id: uuid.UUID) -> "Scene":
        """Create Scene model from SceneInfo dataclass.

        Converts SceneInfo to database representation. Note that this method
        creates the Scene instance but does NOT create SceneEntity records -
        those should be created separately in the repository layer.

        Args:
            scene_info: SceneInfo dataclass to convert
            campaign_id: UUID of the campaign this scene belongs to

        Returns:
            Scene model instance (not yet persisted)
        """
        # Build entity_display_names map from participants
        entity_display_names = {}
        for participant in scene_info.participants:
            if participant.character_id:
                entity_display_names[participant.character_id] = participant.display_name

        # Store npc_display_names from metadata if present (legacy compatibility)
        if scene_info.metadata and "npc_display_names" in scene_info.metadata:
            entity_display_names.update(scene_info.metadata["npc_display_names"])

        return cls(
            scene_id=scene_info.scene_id,
            campaign_id=campaign_id,
            title=scene_info.title,
            description=scene_info.description,
            location_id=scene_info.location_id or None,
            location_description=scene_info.location_description or None,
            scene_type=scene_info.scene_type,
            objectives=scene_info.objectives or [],
            narrative_notes=scene_info.narrative_notes or [],
            outcomes=scene_info.outcomes or [],
            objectives_completed=scene_info.objectives_completed or [],
            objectives_added=scene_info.objectives_added or [],
            description_updates=scene_info.description_updates or [],
            completion_status=scene_info.completion_status,
            duration_turns=scene_info.duration_turns,
            turn_order=scene_info.turn_order or [],
            current_turn_index=scene_info.current_turn_index,
            in_combat=scene_info.in_combat,
            combat_data=scene_info.combat_data,
            entity_display_names=entity_display_names,
            scene_metadata=scene_info.metadata or {},
            is_deleted=False,
            deleted_at=None,
            scene_timestamp=scene_info.timestamp,
            last_updated=scene_info.last_updated,
        )

    def soft_delete(self) -> None:
        """Mark scene as deleted (soft delete)."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
