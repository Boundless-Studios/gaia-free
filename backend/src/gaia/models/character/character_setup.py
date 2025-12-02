"""Character setup and extraction data models."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any

from gaia.models.character.enums import CharacterType


@dataclass
class CharacterSetupSlot:
    """Represents a character slot during campaign setup."""
    slot_id: int
    name: str = ""
    description: str = ""
    character_class: str = ""
    race: str = ""
    generate_backstory: bool = False
    backstory: str = ""
    voice_id: Optional[str] = None
    is_filled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "slot_id": self.slot_id,
            "name": self.name,
            "description": self.description,
            "character_class": self.character_class,
            "race": self.race,
            "generate_backstory": self.generate_backstory,
            "backstory": self.backstory,
            "voice_id": self.voice_id,
            "is_filled": self.is_filled
        }
