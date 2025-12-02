"""Combat action record model for recording combat events."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class CombatActionRecord:
    """Historical record of a combat action that was taken.

    This model stores the complete history of what happened during combat
    for replay, analysis, and persistence.
    """
    timestamp: datetime
    round_number: int
    actor_id: str
    action_type: str
    target_id: Optional[str]
    ap_cost: int
    roll_result: Optional[int] = None
    ac_dc: Optional[int] = None  # AC or DC the roll was compared against
    damage_dealt: Optional[int] = None
    success: bool = True
    description: str = ""
    effects_applied: List[str] = field(default_factory=list)
    turn_should_end: bool = False  # Signal that this action should trigger turn end
    turn_id: Optional[str] = None  # Link to the turn this action belongs to

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "round_number": self.round_number,
            "actor_id": self.actor_id,
            "action_type": self.action_type,
            "target_id": self.target_id,
            "ap_cost": self.ap_cost,
            "roll_result": self.roll_result,
            "ac_dc": self.ac_dc,
            "damage_dealt": self.damage_dealt,
            "success": self.success,
            "description": self.description,
            "effects_applied": self.effects_applied,
            "turn_should_end": self.turn_should_end,
            "turn_id": self.turn_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['CombatActionRecord']:
        """Create CombatActionRecord from dictionary representation.

        Args:
            data: Dictionary containing action data

        Returns:
            Deserialized CombatActionRecord or None if invalid
        """
        try:
            timestamp = datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now()

            return cls(
                timestamp=timestamp,
                round_number=data.get("round_number", 1),
                actor_id=data.get("actor_id", ""),
                action_type=data.get("action_type", ""),
                target_id=data.get("target_id"),
                ap_cost=data.get("ap_cost", 0),
                roll_result=data.get("roll_result"),
                ac_dc=data.get("ac_dc"),
                damage_dealt=data.get("damage_dealt"),
                success=data.get("success", True),
                description=data.get("description", ""),
                effects_applied=data.get("effects_applied", []),
                turn_should_end=data.get("turn_should_end", False),
                turn_id=data.get("turn_id")
            )
        except Exception:
            return None


# Backward compatibility alias
CombatAction = CombatActionRecord