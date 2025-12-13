"""SQLAlchemy model for character campaign instances in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from db.src.base import BaseModel
from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.enums import CharacterStatus, Effect, CharacterRole, CharacterCapability

if TYPE_CHECKING:
    from gaia.models.character_db import CharacterProfile
    from gaia.models.campaign_db import Campaign


class CharacterCampaignInstance(BaseModel):
    """SQLAlchemy model for campaign-specific character state.

    Maps to game.character_campaign_instances table. Stores campaign-specific
    state (HP, inventory, location) while referencing global profile for identity.
    """

    __tablename__ = "character_campaign_instances"
    __table_args__ = (
        UniqueConstraint("character_id", "campaign_id", name="uq_character_campaign"),
        {"schema": "game"},
    )

    # Primary key
    instance_id: Mapped[uuid.UUID] = mapped_column(
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
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("game.campaigns.campaign_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Campaign-specific state
    current_level: Mapped[int] = mapped_column(Integer, nullable=False)
    hit_points_current: Mapped[int] = mapped_column(Integer, nullable=False)
    hit_points_max: Mapped[int] = mapped_column(Integer, nullable=False)
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="healthy", index=True)
    status_effects: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Inventory and abilities (JSONB dicts)
    inventory: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    abilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Quests and location
    quests: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    location: Mapped[Optional[str]] = mapped_column(String(500))

    # Dialog history
    dialog_history: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Role and capabilities
    character_role: Mapped[str] = mapped_column(String(50), nullable=False, default="player")
    capabilities: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Combat fields
    action_points: Mapped[Optional[dict]] = mapped_column(JSONB)
    combat_stats: Mapped[Optional[dict]] = mapped_column(JSONB)
    initiative_modifier: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hostile: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Tracking
    first_appearance: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_interaction: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    profile: Mapped["CharacterProfile"] = relationship(
        "CharacterProfile",
        back_populates="campaign_instances",
    )
    campaign: Mapped["Campaign"] = relationship("Campaign")

    def to_character_info(self, profile: "CharacterProfile") -> CharacterInfo:
        """Convert to CharacterInfo dataclass, merging with profile data.

        Args:
            profile: The CharacterProfile to merge with instance data

        Returns:
            CharacterInfo dataclass with combined profile + instance data
        """
        # Parse enums
        status = CharacterStatus(self.status)
        role = CharacterRole(self.character_role)
        capabilities = CharacterCapability(self.capabilities)

        # Parse status effects
        status_effects = []
        for effect_value in (self.status_effects or []):
            try:
                status_effects.append(Effect(effect_value))
            except (ValueError, KeyError):
                pass  # Skip invalid effects

        # Parse complex objects from JSONB
        from gaia.models.item import Item
        from gaia.models.character.ability import Ability
        from gaia.models.combat.mechanics.action_points import ActionPointState
        from gaia.models.combat import CombatStats

        inventory = {}
        for k, v in (self.inventory or {}).items():
            try:
                inventory[k] = Item.from_dict(v) if isinstance(v, dict) else v
            except Exception:
                pass  # Skip invalid items

        abilities = {}
        for k, v in (self.abilities or {}).items():
            try:
                abilities[k] = Ability.from_dict(v) if isinstance(v, dict) else v
            except Exception:
                pass  # Skip invalid abilities

        action_points = None
        if self.action_points:
            try:
                action_points = ActionPointState(**self.action_points)
            except Exception:
                pass

        combat_stats = None
        if self.combat_stats:
            try:
                combat_stats = CombatStats(**self.combat_stats)
            except Exception:
                pass

        return CharacterInfo(
            character_id=profile.external_character_id,
            name=profile.name,
            character_class=profile.character_class,
            level=self.current_level,
            race=profile.race,
            alignment="neutral",  # TODO: Add alignment to profile or instance?
            hit_points_current=self.hit_points_current,
            hit_points_max=self.hit_points_max,
            armor_class=self.armor_class,
            status=status,
            status_effects=status_effects,
            inventory=inventory,
            abilities=abilities,
            backstory=profile.backstory,
            personality_traits=list(profile.personality_traits or []),
            bonds=list(profile.bonds or []),
            flaws=list(profile.flaws or []),
            dialog_history=list(self.dialog_history or []),
            quests=list(self.quests or []),
            location=self.location,
            character_type=profile.character_type,
            character_role=role,
            capabilities=capabilities,
            description=profile.description,
            appearance=profile.appearance,
            visual_description=profile.visual_description,
            voice_id=profile.voice_id,
            voice_settings=profile.voice_settings or {},
            first_appearance=self.first_appearance,
            last_interaction=self.last_interaction,
            interaction_count=self.interaction_count,
            strength=profile.strength,
            dexterity=profile.dexterity,
            constitution=profile.constitution,
            intelligence=profile.intelligence,
            wisdom=profile.wisdom,
            charisma=profile.charisma,
            action_points=action_points,
            combat_stats=combat_stats,
            initiative_modifier=self.initiative_modifier,
            hostile=self.hostile,
            portrait_url=profile.portrait_url,
            portrait_path=profile.portrait_path,
            portrait_prompt=profile.portrait_prompt,
            gender=profile.gender,
            age_category=profile.age_category,
            build=profile.build,
            height_description=profile.height_description,
            facial_expression=profile.facial_expression,
            facial_features=profile.facial_features,
            attire=profile.attire,
            primary_weapon=profile.primary_weapon,
            distinguishing_feature=profile.distinguishing_feature,
            background_setting=profile.background_setting,
            pose=profile.pose,
        )

    @classmethod
    def from_character_info(
        cls,
        character_info: CharacterInfo,
        character_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> "CharacterCampaignInstance":
        """Create CharacterCampaignInstance from CharacterInfo dataclass.

        Args:
            character_info: CharacterInfo with campaign state
            character_id: UUID of the character profile
            campaign_id: UUID of the campaign

        Returns:
            CharacterCampaignInstance SQLAlchemy model
        """
        # Serialize complex objects to JSONB
        inventory = {}
        for k, v in (character_info.inventory or {}).items():
            try:
                inventory[k] = v.to_dict() if hasattr(v, 'to_dict') else v
            except Exception:
                pass

        abilities = {}
        for k, v in (character_info.abilities or {}).items():
            try:
                abilities[k] = v.to_dict() if hasattr(v, 'to_dict') else v
            except Exception:
                pass

        action_points = None
        if character_info.action_points:
            try:
                action_points = character_info.action_points.to_dict()
            except Exception:
                pass

        combat_stats = None
        if character_info.combat_stats:
            try:
                combat_stats = character_info.combat_stats.to_dict()
            except Exception:
                pass

        status_effects = [e.value for e in (character_info.status_effects or [])]

        return cls(
            character_id=character_id,
            campaign_id=campaign_id,
            current_level=character_info.level,
            hit_points_current=character_info.hit_points_current,
            hit_points_max=character_info.hit_points_max,
            armor_class=character_info.armor_class,
            status=character_info.status.value,
            status_effects=status_effects,
            inventory=inventory,
            abilities=abilities,
            quests=list(character_info.quests or []),
            location=character_info.location,
            dialog_history=list(character_info.dialog_history or []),
            character_role=character_info.character_role.value,
            capabilities=int(character_info.capabilities),
            action_points=action_points,
            combat_stats=combat_stats,
            initiative_modifier=character_info.initiative_modifier,
            hostile=character_info.hostile,
            first_appearance=character_info.first_appearance,
            last_interaction=character_info.last_interaction,
            interaction_count=character_info.interaction_count,
        )

    def soft_delete(self) -> None:
        """Mark instance as deleted (soft delete)."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted instance."""
        self.is_deleted = False
        self.deleted_at = None
