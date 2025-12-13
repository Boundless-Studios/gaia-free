"""Player input model for turn-based messaging."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class PlayerInput:
    """Input from a player character within a turn.

    Captures the player's action along with attribution metadata
    for display and history purposes.
    """
    character_id: str
    character_name: str
    text: str
    input_type: str = "action"  # action | observation | reaction
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "text": self.text,
            "input_type": self.input_type,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerInput":
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()

        return cls(
            character_id=data.get("character_id", ""),
            character_name=data.get("character_name", ""),
            text=data.get("text", ""),
            input_type=data.get("input_type", "action"),
            user_id=data.get("user_id"),
            timestamp=timestamp,
        )
