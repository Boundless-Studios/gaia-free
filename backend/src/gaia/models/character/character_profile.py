"""Character profile data model for voice and visual tracking."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from datetime import datetime

from gaia.models.character.enums import CharacterType, VoiceArchetype


@dataclass
class CharacterProfile:
    """Character profile for identity, voice, and visual data.

    Single source of truth for character identity and appearance, shared
    across all campaigns. Contains immutable character attributes (appearance,
    voice, backstory) but NOT campaign-specific state (HP, inventory, location).

    Campaign-specific state is stored in CharacterInfo, which references
    this profile via profile_id.
    """
    character_id: str
    name: str
    character_type: CharacterType = CharacterType.NPC

    # Core identity
    race: str = "human"
    character_class: str = "adventurer"
    base_level: int = 1  # Default level, campaigns can override

    # Voice assignment
    voice_id: Optional[str] = None
    voice_settings: Dict[str, Any] = field(default_factory=dict)
    voice_archetype: Optional[VoiceArchetype] = None

    # Visual representation
    portrait_url: Optional[str] = None  # URL to generated portrait
    portrait_path: Optional[str] = None  # Local file path to portrait
    portrait_prompt: Optional[str] = None  # Enhanced prompt used for generation
    additional_images: List[str] = field(default_factory=list)

    # Visual metadata for portrait generation
    gender: Optional[str] = None  # Male, Female, Non-binary
    age_category: Optional[str] = None  # Young, Adult, Middle-aged, Elderly
    build: Optional[str] = None  # Slender, Athletic, Muscular, Stocky, Heavyset
    height_description: Optional[str] = None  # tall, average height, short, etc.
    facial_expression: Optional[str] = None  # Confident, Serene, Determined, etc.
    facial_features: Optional[str] = None  # Distinguishing facial characteristics
    attire: Optional[str] = None  # Clothing and armor description
    primary_weapon: Optional[str] = None  # Main weapon/item
    distinguishing_feature: Optional[str] = None  # Most unique visual element
    background_setting: Optional[str] = None  # Environmental context for portraits
    pose: Optional[str] = None  # Character pose/action

    # Descriptions
    backstory: str = ""
    description: str = ""  # Physical and personality description
    appearance: str = ""  # Visual appearance for consistency
    visual_description: str = ""  # Detailed appearance for image generation

    # Metadata
    first_created: datetime = field(default_factory=datetime.now)
    total_interactions: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "character_id": self.character_id,
            "name": self.name,
            "character_type": self.character_type.value,
            # Core identity
            "race": self.race,
            "character_class": self.character_class,
            "base_level": self.base_level,
            # Voice
            "voice_id": self.voice_id,
            "voice_settings": self.voice_settings,
            "voice_archetype": self.voice_archetype.value if self.voice_archetype else None,
            # Visual representation
            "portrait_url": self.portrait_url,
            "portrait_path": self.portrait_path,
            "portrait_prompt": self.portrait_prompt,
            "additional_images": self.additional_images,
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
            # Descriptions
            "backstory": self.backstory,
            "description": self.description,
            "appearance": self.appearance,
            "visual_description": self.visual_description,
            # Metadata
            "first_created": self.first_created.isoformat(),
            "total_interactions": self.total_interactions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CharacterProfile':
        """Create from dictionary."""
        # Convert enums
        if isinstance(data.get("character_type"), str):
            data["character_type"] = CharacterType(data["character_type"])
        if data.get("voice_archetype") and isinstance(data.get("voice_archetype"), str):
            data["voice_archetype"] = VoiceArchetype(data["voice_archetype"])

        # Convert datetime
        if isinstance(data.get("first_created"), str):
            data["first_created"] = datetime.fromisoformat(data["first_created"])

        # Provide defaults for new fields if not present (for backward compatibility)
        data.setdefault("race", "human")
        data.setdefault("character_class", "adventurer")
        data.setdefault("base_level", 1)
        data.setdefault("portrait_url", None)
        data.setdefault("gender", None)
        data.setdefault("age_category", None)
        data.setdefault("build", None)
        data.setdefault("height_description", None)
        data.setdefault("facial_expression", None)
        data.setdefault("facial_features", None)
        data.setdefault("attire", None)
        data.setdefault("primary_weapon", None)
        data.setdefault("distinguishing_feature", None)
        data.setdefault("background_setting", None)
        data.setdefault("pose", None)
        data.setdefault("backstory", "")
        data.setdefault("description", "")
        data.setdefault("appearance", "")
        data.setdefault("visual_description", "")

        # Remove any legacy fields that might exist in old profiles
        legacy_fields = ["campaigns", "campaign_character_ids", "campaign_data"]
        for field in legacy_fields:
            data.pop(field, None)

        return cls(**data)