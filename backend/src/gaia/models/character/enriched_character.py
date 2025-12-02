"""Enriched character model combining CharacterProfile and CharacterInfo."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

from gaia.models.character.character_profile import CharacterProfile
from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.enums import CharacterStatus, CharacterRole, CharacterCapability
from gaia.models.item import Item


@dataclass
class EnrichedCharacter:
    """Merged view of CharacterInfo + CharacterProfile for API responses.

    This provides a complete character view to frontend without requiring
    separate calls. All identity data comes from CharacterProfile, all
    campaign state comes from CharacterInfo.

    This model is used for API responses only and is not persisted.
    """

    # Identity from CharacterProfile
    character_id: str
    profile_id: str
    name: str
    race: str
    character_class: str
    character_type: str = "player"

    # Visual metadata from CharacterProfile
    gender: Optional[str] = None
    age_category: Optional[str] = None
    build: Optional[str] = None
    height_description: Optional[str] = None
    facial_expression: Optional[str] = None
    facial_features: Optional[str] = None
    attire: Optional[str] = None
    primary_weapon: Optional[str] = None
    distinguishing_feature: Optional[str] = None
    background_setting: Optional[str] = None
    pose: Optional[str] = None

    # Portrait from CharacterProfile
    portrait_url: Optional[str] = None
    portrait_path: Optional[str] = None
    portrait_prompt: Optional[str] = None

    # Voice from CharacterProfile
    voice_id: Optional[str] = None
    voice_settings: Dict[str, Any] = field(default_factory=dict)

    # Descriptions from CharacterProfile
    backstory: str = ""
    description: str = ""
    appearance: str = ""
    visual_description: str = ""

    # Campaign state from CharacterInfo
    level: int = 1  # Resolved from profile.base_level or campaign override
    hit_points_current: int = 10
    hit_points_max: int = 10
    armor_class: int = 10
    status: CharacterStatus = CharacterStatus.HEALTHY
    inventory: Dict[str, Item] = field(default_factory=dict)
    abilities: Dict[str, Any] = field(default_factory=dict)
    location: Optional[str] = None
    quests: List[str] = field(default_factory=list)

    # Additional campaign state
    character_role: CharacterRole = CharacterRole.PLAYER
    capabilities: CharacterCapability = CharacterCapability.NONE
    alignment: str = "neutral"
    personality_traits: List[str] = field(default_factory=list)
    bonds: List[str] = field(default_factory=list)
    flaws: List[str] = field(default_factory=list)

    # Ability scores
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    @classmethod
    def from_character_and_profile(
        cls,
        character_info: CharacterInfo,
        profile: CharacterProfile
    ) -> 'EnrichedCharacter':
        """Merge CharacterInfo and CharacterProfile into enriched view.

        Args:
            character_info: Campaign-specific character state
            profile: Global character identity and appearance

        Returns:
            EnrichedCharacter with combined data
        """
        # Resolve level (campaign override or profile default)
        level = character_info.level if character_info.level else profile.base_level

        return cls(
            # Identity from profile
            character_id=profile.character_id,
            profile_id=profile.character_id,
            name=profile.name,
            race=profile.race,
            character_class=profile.character_class,
            character_type=profile.character_type.value if hasattr(profile.character_type, 'value') else str(profile.character_type),

            # Visual metadata from profile
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

            # Portrait from profile
            portrait_url=profile.portrait_url,
            portrait_path=profile.portrait_path,
            portrait_prompt=profile.portrait_prompt,

            # Voice from profile
            voice_id=profile.voice_id,
            voice_settings=profile.voice_settings,

            # Descriptions from profile
            backstory=profile.backstory,
            description=profile.description,
            appearance=profile.appearance,
            visual_description=profile.visual_description,

            # Campaign state from CharacterInfo
            level=level,
            hit_points_current=character_info.hit_points_current,
            hit_points_max=character_info.hit_points_max,
            armor_class=character_info.armor_class,
            status=character_info.status,
            inventory=character_info.inventory,
            abilities=character_info.abilities,
            location=character_info.location,
            quests=character_info.quests,

            # Additional campaign state
            character_role=character_info.character_role,
            capabilities=character_info.capabilities,
            alignment=character_info.alignment,
            personality_traits=character_info.personality_traits,
            bonds=character_info.bonds,
            flaws=character_info.flaws,

            # Ability scores
            strength=character_info.strength,
            dexterity=character_info.dexterity,
            constitution=character_info.constitution,
            intelligence=character_info.intelligence,
            wisdom=character_info.wisdom,
            charisma=character_info.charisma
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization.

        Returns dictionary with all character data in a format
        that matches what the frontend expects.
        """
        return {
            # Identity
            "character_id": self.character_id,
            "profile_id": self.profile_id,
            "name": self.name,
            "race": self.race,
            "character_class": self.character_class,
            "character_type": self.character_type,

            # Visual metadata
            "gender": self.gender,
            "age_category": self.age_category,
            "build": self.build,
            "height_description": self.height_description,
            "facial_expression": self.facial_expression,
            "facial_features": self.facial_features,
            "attire": self.attire,
            "primary_weapon": self.primary_weapon,
            "distinguishing_feature": self.distinguishing_feature,
            "background_setting": self.background_setting,
            "pose": self.pose,

            # Portrait
            "portrait_url": self.portrait_url,
            "portrait_path": self.portrait_path,
            "portrait_prompt": self.portrait_prompt,

            # Voice
            "voice_id": self.voice_id,
            "voice_settings": self.voice_settings,

            # Descriptions
            "backstory": self.backstory,
            "description": self.description,
            "appearance": self.appearance,
            "visual_description": self.visual_description,

            # Campaign state
            "level": self.level,
            "hit_points_current": self.hit_points_current,
            "hit_points_max": self.hit_points_max,
            "armor_class": self.armor_class,
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "inventory": {k: v.to_dict() for k, v in self.inventory.items()},
            "abilities": {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self.abilities.items()},
            "location": self.location,
            "quests": self.quests,

            # Additional state
            "character_role": self.character_role.value if hasattr(self.character_role, 'value') else str(self.character_role),
            "capabilities": int(self.capabilities) if isinstance(self.capabilities, CharacterCapability) else self.capabilities,
            "alignment": self.alignment,
            "personality_traits": self.personality_traits,
            "bonds": self.bonds,
            "flaws": self.flaws,

            # Ability scores
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma
        }
