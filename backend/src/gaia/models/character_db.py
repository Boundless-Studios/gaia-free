"""SQLAlchemy model for character profiles in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from db.src.base import BaseModel
from gaia.models.character.character_profile import CharacterProfile as CharacterProfileDataclass
from gaia.models.character.enums import CharacterType, VoiceArchetype

if TYPE_CHECKING:
    from gaia.models.character_instance_db import CharacterCampaignInstance
    from gaia.models.character_user_db import CharacterUser


class CharacterProfile(BaseModel):
    """SQLAlchemy model for character profiles.

    Maps to game.character_profiles table. Stores canonical character
    identity, appearance, voice, and base attributes. This is the global
    profile that can be reused across multiple campaigns.
    """

    __tablename__ = "character_profiles"
    __table_args__ = {"schema": "game"}

    # Primary key
    character_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # External identifier (for backward compatibility with filesystem)
    external_character_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # Ownership (NULL = system character)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
    )
    created_by_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Core identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    race: Mapped[str] = mapped_column(String(100), nullable=False, default="human")
    character_class: Mapped[str] = mapped_column(String(100), nullable=False, default="adventurer")
    base_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    character_type: Mapped[str] = mapped_column(String(50), nullable=False, default="player", index=True)

    # Voice assignment
    voice_id: Mapped[Optional[str]] = mapped_column(String(255))
    voice_settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    voice_archetype: Mapped[Optional[str]] = mapped_column(String(50))

    # Visual representation
    portrait_url: Mapped[Optional[str]] = mapped_column(Text)
    portrait_path: Mapped[Optional[str]] = mapped_column(Text)
    portrait_prompt: Mapped[Optional[str]] = mapped_column(Text)
    additional_images: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Visual metadata for portrait generation
    gender: Mapped[Optional[str]] = mapped_column(String(50))
    age_category: Mapped[Optional[str]] = mapped_column(String(50))
    build: Mapped[Optional[str]] = mapped_column(String(50))
    height_description: Mapped[Optional[str]] = mapped_column(String(100))
    facial_expression: Mapped[Optional[str]] = mapped_column(String(100))
    facial_features: Mapped[Optional[str]] = mapped_column(Text)
    attire: Mapped[Optional[str]] = mapped_column(Text)
    primary_weapon: Mapped[Optional[str]] = mapped_column(String(255))
    distinguishing_feature: Mapped[Optional[str]] = mapped_column(Text)
    background_setting: Mapped[Optional[str]] = mapped_column(Text)
    pose: Mapped[Optional[str]] = mapped_column(String(100))

    # Descriptions
    backstory: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    appearance: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visual_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    personality_traits: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    bonds: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    flaws: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    # Base ability scores
    strength: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    constitution: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    wisdom: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    charisma: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # Metadata
    total_interactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    campaign_instances: Mapped[List["CharacterCampaignInstance"]] = relationship(
        "CharacterCampaignInstance",
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    user_associations: Mapped[List["CharacterUser"]] = relationship(
        "CharacterUser",
        back_populates="character",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def to_dataclass(self) -> CharacterProfileDataclass:
        """Convert SQLAlchemy model to CharacterProfile dataclass.

        Returns:
            CharacterProfile dataclass instance
        """
        # Convert enum strings back to enums
        character_type = CharacterType(self.character_type) if self.character_type else CharacterType.NPC
        voice_archetype = VoiceArchetype(self.voice_archetype) if self.voice_archetype else None

        return CharacterProfileDataclass(
            character_id=self.external_character_id,
            name=self.name,
            character_type=character_type,
            race=self.race,
            character_class=self.character_class,
            base_level=self.base_level,
            voice_id=self.voice_id,
            voice_settings=self.voice_settings or {},
            voice_archetype=voice_archetype,
            portrait_url=self.portrait_url,
            portrait_path=self.portrait_path,
            portrait_prompt=self.portrait_prompt,
            additional_images=self.additional_images or [],
            gender=self.gender,
            age_category=self.age_category,
            build=self.build,
            height_description=self.height_description,
            facial_expression=self.facial_expression,
            facial_features=self.facial_features,
            attire=self.attire,
            primary_weapon=self.primary_weapon,
            distinguishing_feature=self.distinguishing_feature,
            background_setting=self.background_setting,
            pose=self.pose,
            backstory=self.backstory,
            description=self.description,
            appearance=self.appearance,
            visual_description=self.visual_description,
            first_created=self.first_created,
            total_interactions=self.total_interactions,
        )

    @classmethod
    def from_dataclass(
        cls,
        profile: CharacterProfileDataclass,
        created_by_user_id: Optional[str] = None,
        created_by_email: Optional[str] = None,
    ) -> "CharacterProfile":
        """Create CharacterProfile from dataclass.

        Args:
            profile: CharacterProfile dataclass
            created_by_user_id: User who created the character (None for system)
            created_by_email: Email of creating user

        Returns:
            CharacterProfile SQLAlchemy model
        """
        return cls(
            external_character_id=profile.character_id,
            created_by_user_id=created_by_user_id,
            created_by_email=created_by_email,
            name=profile.name,
            race=profile.race,
            character_class=profile.character_class,
            base_level=profile.base_level,
            character_type=profile.character_type.value,
            voice_id=profile.voice_id,
            voice_settings=profile.voice_settings or {},
            voice_archetype=profile.voice_archetype.value if profile.voice_archetype else None,
            portrait_url=profile.portrait_url,
            portrait_path=profile.portrait_path,
            portrait_prompt=profile.portrait_prompt,
            additional_images=profile.additional_images or [],
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
            backstory=profile.backstory,
            description=profile.description,
            appearance=profile.appearance,
            visual_description=profile.visual_description,
            personality_traits=list(profile.personality_traits or []),
            bonds=list(profile.bonds or []),
            flaws=list(profile.flaws or []),
            strength=10,  # These come from instances, not profiles
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
            total_interactions=profile.total_interactions,
            first_created=profile.first_created,
        )

    def soft_delete(self) -> None:
        """Mark character profile as deleted (soft delete)."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted character profile."""
        self.is_deleted = False
        self.deleted_at = None
