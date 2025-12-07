"""CharacterOptions data model - options for a single character."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class CharacterOptions:
    """Options for a single character."""
    character_id: str
    character_name: str
    options: List[str] = field(default_factory=list)
    is_active: bool = False  # True if this is the turn-taker
    generated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "options": self.options,
            "is_active": self.is_active,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CharacterOptions":
        """Create from dictionary."""
        generated_at = None
        if data.get("generated_at"):
            generated_at = datetime.fromisoformat(data["generated_at"])

        return cls(
            character_id=data["character_id"],
            character_name=data["character_name"],
            options=data.get("options", []),
            is_active=data.get("is_active", False),
            generated_at=generated_at
        )
