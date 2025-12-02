"""Ability data model for character abilities, spells, and skills."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Ability:
    """Represents a character ability, spell, or skill."""
    ability_id: str
    name: str
    ability_type: str  # spell, skill, feature, trait
    level: int = 0  # spell level or minimum character level required
    description: str = ""
    range: str = "self"
    duration: str = "instantaneous"
    components: List[str] = field(default_factory=list)  # V, S, M for spells
    damage_dice: Optional[str] = None  # e.g., "2d6+3"
    saving_throw: Optional[str] = None  # e.g., "CON DC 15"
    cooldown: Optional[str] = None  # e.g., "short rest", "long rest", "1/day"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ability_id": self.ability_id,
            "name": self.name,
            "ability_type": self.ability_type,
            "level": self.level,
            "description": self.description,
            "range": self.range,
            "duration": self.duration,
            "components": self.components,
            "damage_dice": self.damage_dice,
            "saving_throw": self.saving_throw,
            "cooldown": self.cooldown
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Ability':
        """Create from dictionary."""
        return cls(**data)