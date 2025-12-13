"""Response schemas for character admin endpoints."""

from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel

if TYPE_CHECKING:
    from gaia.models.character_db import CharacterProfile
    from gaia.models.character_instance_db import CharacterCampaignInstance
    from gaia.models.npc_profile_db import NpcProfile


class CharacterProfileResponse(BaseModel):
    """Response model for character profile listing."""

    character_id: str
    external_character_id: str
    name: str
    race: str
    character_class: str
    base_level: int
    character_type: str
    created_by_user_id: Optional[str]
    created_by_email: Optional[str]
    voice_id: Optional[str]
    portrait_url: Optional[str]
    total_interactions: int
    first_created: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    is_deleted: bool

    @staticmethod
    def from_model(profile: "CharacterProfile") -> "CharacterProfileResponse":
        """Create response from ORM model.

        Args:
            profile: CharacterProfile ORM model

        Returns:
            CharacterProfileResponse instance
        """
        return CharacterProfileResponse(
            character_id=str(profile.character_id),
            external_character_id=profile.external_character_id,
            name=profile.name,
            race=profile.race,
            character_class=profile.character_class,
            base_level=profile.base_level,
            character_type=profile.character_type,
            created_by_user_id=profile.created_by_user_id,
            created_by_email=profile.created_by_email,
            voice_id=profile.voice_id,
            portrait_url=profile.portrait_url,
            total_interactions=profile.total_interactions,
            first_created=profile.first_created.isoformat() if profile.first_created else None,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
            updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
            is_deleted=profile.is_deleted,
        )


class CampaignInstanceInfo(BaseModel):
    """Summary of a character's campaign instance."""

    instance_id: str
    campaign_id: str
    current_level: int
    hit_points_current: int
    hit_points_max: int
    status: str
    character_role: str
    location: Optional[str]
    first_appearance: Optional[str]
    last_interaction: Optional[str]
    interaction_count: int

    @staticmethod
    def from_model(instance: "CharacterCampaignInstance") -> "CampaignInstanceInfo":
        """Create instance info from ORM model.

        Args:
            instance: CharacterCampaignInstance ORM model

        Returns:
            CampaignInstanceInfo instance
        """
        return CampaignInstanceInfo(
            instance_id=str(instance.instance_id),
            campaign_id=str(instance.campaign_id),
            current_level=instance.current_level,
            hit_points_current=instance.hit_points_current,
            hit_points_max=instance.hit_points_max,
            status=instance.status,
            character_role=instance.character_role,
            location=instance.location,
            first_appearance=instance.first_appearance.isoformat() if instance.first_appearance else None,
            last_interaction=instance.last_interaction.isoformat() if instance.last_interaction else None,
            interaction_count=instance.interaction_count,
        )


class CharacterDetailResponse(BaseModel):
    """Detailed character response with all campaign instances."""

    # Profile data
    character_id: str
    external_character_id: str
    name: str
    race: str
    character_class: str
    base_level: int
    character_type: str
    created_by_user_id: Optional[str]
    created_by_email: Optional[str]

    # Voice and appearance
    voice_id: Optional[str]
    voice_archetype: Optional[str]
    portrait_url: Optional[str]
    portrait_path: Optional[str]
    gender: Optional[str]
    age_category: Optional[str]

    # Descriptions
    backstory: str
    description: str
    appearance: str
    personality_traits: List[str]
    bonds: List[str]
    flaws: List[str]

    # Ability scores
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    # Metadata
    total_interactions: int
    first_created: Optional[str]
    is_deleted: bool

    # Campaign instances
    campaign_instances: List[CampaignInstanceInfo]

    @staticmethod
    def from_model(
        profile: "CharacterProfile",
        instances: List["CharacterCampaignInstance"],
    ) -> "CharacterDetailResponse":
        """Create detailed response from ORM models.

        Args:
            profile: CharacterProfile ORM model
            instances: List of CharacterCampaignInstance ORM models

        Returns:
            CharacterDetailResponse instance
        """
        return CharacterDetailResponse(
            character_id=str(profile.character_id),
            external_character_id=profile.external_character_id,
            name=profile.name,
            race=profile.race,
            character_class=profile.character_class,
            base_level=profile.base_level,
            character_type=profile.character_type,
            created_by_user_id=profile.created_by_user_id,
            created_by_email=profile.created_by_email,
            voice_id=profile.voice_id,
            voice_archetype=profile.voice_archetype,
            portrait_url=profile.portrait_url,
            portrait_path=profile.portrait_path,
            gender=profile.gender,
            age_category=profile.age_category,
            backstory=profile.backstory,
            description=profile.description,
            appearance=profile.appearance,
            personality_traits=list(profile.personality_traits or []),
            bonds=list(profile.bonds or []),
            flaws=list(profile.flaws or []),
            strength=profile.strength,
            dexterity=profile.dexterity,
            constitution=profile.constitution,
            intelligence=profile.intelligence,
            wisdom=profile.wisdom,
            charisma=profile.charisma,
            total_interactions=profile.total_interactions,
            first_created=profile.first_created.isoformat() if profile.first_created else None,
            is_deleted=profile.is_deleted,
            campaign_instances=[CampaignInstanceInfo.from_model(inst) for inst in instances],
        )


class CharacterStatsResponse(BaseModel):
    """Aggregate statistics about characters in the database."""

    total_profiles: int
    total_instances: int
    total_npcs: int

    # By character type
    player_characters: int
    npc_characters: int

    # By user
    system_characters: int
    user_characters: int

    # By status
    active_characters: int
    deleted_characters: int

    # Campaign distribution
    characters_per_campaign_avg: float
    most_active_campaign_id: Optional[str]
    most_active_campaign_count: int


class NpcProfileResponse(BaseModel):
    """Response model for NPC profile listing."""

    npc_id: str
    external_npc_id: str
    created_by_user_id: str
    created_by_email: Optional[str]
    campaign_id: Optional[str]
    display_name: str
    role: str
    description: str
    has_full_sheet: bool
    promoted_to_character_id: Optional[str]
    promoted_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    is_deleted: bool

    @staticmethod
    def from_model(npc: "NpcProfile") -> "NpcProfileResponse":
        """Create response from ORM model.

        Args:
            npc: NpcProfile ORM model

        Returns:
            NpcProfileResponse instance
        """
        return NpcProfileResponse(
            npc_id=str(npc.npc_id),
            external_npc_id=npc.external_npc_id,
            created_by_user_id=npc.created_by_user_id,
            created_by_email=npc.created_by_email,
            campaign_id=str(npc.campaign_id) if npc.campaign_id else None,
            display_name=npc.display_name,
            role=npc.role,
            description=npc.description,
            has_full_sheet=npc.has_full_sheet,
            promoted_to_character_id=str(npc.promoted_to_character_id) if npc.promoted_to_character_id else None,
            promoted_at=npc.promoted_at.isoformat() if npc.promoted_at else None,
            created_at=npc.created_at.isoformat() if npc.created_at else None,
            updated_at=npc.updated_at.isoformat() if npc.updated_at else None,
            is_deleted=npc.is_deleted,
        )


class NpcDetailResponse(BaseModel):
    """Detailed NPC response."""

    npc_id: str
    external_npc_id: str
    created_by_user_id: str
    created_by_email: Optional[str]
    campaign_id: Optional[str]
    display_name: str
    role: str
    description: str
    tags: List[str]
    relationships: dict
    notes: List[str]
    capabilities: int
    has_full_sheet: bool
    promoted_to_character_id: Optional[str]
    promoted_at: Optional[str]
    metadata: dict
    is_deleted: bool
    created_at: Optional[str]
    updated_at: Optional[str]

    @staticmethod
    def from_model(npc: "NpcProfile") -> "NpcDetailResponse":
        """Create detailed response from ORM model.

        Args:
            npc: NpcProfile ORM model

        Returns:
            NpcDetailResponse instance
        """
        return NpcDetailResponse(
            npc_id=str(npc.npc_id),
            external_npc_id=npc.external_npc_id,
            created_by_user_id=npc.created_by_user_id,
            created_by_email=npc.created_by_email,
            campaign_id=str(npc.campaign_id) if npc.campaign_id else None,
            display_name=npc.display_name,
            role=npc.role,
            description=npc.description,
            tags=list(npc.tags or []),
            relationships=dict(npc.relationships or {}),
            notes=list(npc.notes or []),
            capabilities=npc.capabilities,
            has_full_sheet=npc.has_full_sheet,
            promoted_to_character_id=str(npc.promoted_to_character_id) if npc.promoted_to_character_id else None,
            promoted_at=npc.promoted_at.isoformat() if npc.promoted_at else None,
            metadata=dict(npc.npc_metadata or {}),
            is_deleted=npc.is_deleted,
            created_at=npc.created_at.isoformat() if npc.created_at else None,
            updated_at=npc.updated_at.isoformat() if npc.updated_at else None,
        )


class CharacterListResponse(BaseModel):
    """Response for character list endpoint."""

    characters: List[CharacterProfileResponse]
    total: int
    limit: int
    offset: int


class NpcListResponse(BaseModel):
    """Response for NPC list endpoint."""

    npcs: List[NpcProfileResponse]
    total: int
    limit: int
    offset: int
