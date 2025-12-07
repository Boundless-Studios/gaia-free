"""PlayerObservation data model - an observation from a secondary player."""

from dataclasses import dataclass, field
from typing import Dict
from datetime import datetime


@dataclass
class PlayerObservation:
    """
    An observation from a secondary player to share with the primary player.

    Secondary players can submit observations instead of direct actions.
    These get collected and presented to the primary player for inclusion
    in their turn.
    """
    character_id: str
    character_name: str
    observation_text: str
    submitted_at: datetime = field(default_factory=datetime.now)
    included_in_turn: bool = False  # True once primary player incorporates it

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "observation_text": self.observation_text,
            "submitted_at": self.submitted_at.isoformat(),
            "included_in_turn": self.included_in_turn
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PlayerObservation":
        """Create from dictionary."""
        return cls(
            character_id=data["character_id"],
            character_name=data["character_name"],
            observation_text=data["observation_text"],
            submitted_at=datetime.fromisoformat(data["submitted_at"]),
            included_in_turn=data.get("included_in_turn", False)
        )

    def format_for_submission(self) -> str:
        """Format the observation for inclusion in the primary player's turn."""
        return f"[{self.character_name} observes]: {self.observation_text}"
