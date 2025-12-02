"""Combat statistics model."""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class CombatStats:
    """Combat-specific statistics for a character."""
    attack_bonus: int = 0
    damage_bonus: int = 0
    spell_save_dc: int = 10
    initiative_bonus: int = 0
    speed: int = 30  # Movement speed in feet

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attack_bonus": self.attack_bonus,
            "damage_bonus": self.damage_bonus,
            "spell_save_dc": self.spell_save_dc,
            "initiative_bonus": self.initiative_bonus,
            "speed": self.speed
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CombatStats':
        """Create CombatStats from dictionary representation.

        Args:
            data: Dictionary containing stats data

        Returns:
            Deserialized CombatStats
        """
        return cls(
            attack_bonus=data.get("attack_bonus", 0),
            damage_bonus=data.get("damage_bonus", 0),
            spell_save_dc=data.get("spell_save_dc", 10),
            initiative_bonus=data.get("initiative_bonus", 0),
            speed=data.get("speed", 30)
        )