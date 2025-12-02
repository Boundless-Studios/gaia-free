"""Status effect model for combat system."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .enums import StatusEffectType


@dataclass
class StatusEffect:
    """A status effect applied to a combatant."""
    effect_type: StatusEffectType
    duration_rounds: int  # -1 for permanent
    source: str  # Who/what applied this effect
    description: str
    modifiers: Dict[str, Any] = field(default_factory=dict)  # AC bonus, disadvantage, etc.

    def tick(self) -> bool:
        """Reduce duration by 1 round, return True if expired."""
        if self.duration_rounds > 0:
            self.duration_rounds -= 1
            return self.duration_rounds == 0
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "effect_type": self.effect_type.value,
            "duration_rounds": self.duration_rounds,
            "source": self.source,
            "description": self.description,
            "modifiers": self.modifiers
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['StatusEffect']:
        """Create StatusEffect from dictionary representation.

        Args:
            data: Dictionary containing effect data

        Returns:
            Deserialized StatusEffect or None if invalid
        """
        try:
            effect_type = data.get("effect_type")
            if isinstance(effect_type, str):
                effect_type = StatusEffectType[effect_type.upper()]

            return cls(
                effect_type=effect_type,
                duration_rounds=data.get("duration_rounds", 0),
                source=data.get("source", ""),
                description=data.get("description", ""),
                modifiers=data.get("modifiers", {})
            )
        except Exception:
            return None