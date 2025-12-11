"""DM input model for turn-based messaging."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class DMInput:
    """Input from the DM within a turn.

    Captures the DM's additions or modifications to a turn,
    including any changes they made to player input.
    """
    text: str
    user_id: Optional[str] = None
    modifications: Optional[str] = None  # Description of what DM changed
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "user_id": self.user_id,
            "modifications": self.modifications,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DMInput":
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()

        return cls(
            text=data.get("text", ""),
            user_id=data.get("user_id"),
            modifications=data.get("modifications"),
            timestamp=timestamp,
        )
