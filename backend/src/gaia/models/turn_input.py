"""Turn input model for turn-based messaging."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from gaia.models.player_input import PlayerInput
from gaia.models.dm_input import DMInput


@dataclass
class TurnInput:
    """Structured input for a turn - preserves all contributor attribution.

    A turn input contains:
    - The active player's primary action
    - Any observer inputs from other players
    - DM additions or modifications
    - The final combined prompt sent to the LLM
    """
    active_player: Optional[PlayerInput] = None
    observer_inputs: List[PlayerInput] = field(default_factory=list)
    dm_input: Optional[DMInput] = None
    combined_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "active_player": self.active_player.to_dict() if self.active_player else None,
            "observer_inputs": [obs.to_dict() for obs in self.observer_inputs],
            "dm_input": self.dm_input.to_dict() if self.dm_input else None,
            "combined_prompt": self.combined_prompt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TurnInput":
        """Create from dictionary."""
        active_player = None
        if data.get("active_player"):
            active_player = PlayerInput.from_dict(data["active_player"])

        observer_inputs = []
        for obs_data in data.get("observer_inputs", []):
            observer_inputs.append(PlayerInput.from_dict(obs_data))

        dm_input = None
        if data.get("dm_input"):
            dm_input = DMInput.from_dict(data["dm_input"])

        return cls(
            active_player=active_player,
            observer_inputs=observer_inputs,
            dm_input=dm_input,
            combined_prompt=data.get("combined_prompt", ""),
        )
