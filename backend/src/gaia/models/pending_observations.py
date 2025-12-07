"""PendingObservations data model - collection of pending observations from secondary players."""

from dataclasses import dataclass, field
from typing import Dict, List

from .player_observation import PlayerObservation


@dataclass
class PendingObservations:
    """
    Collection of pending observations from secondary players.

    Primary player sees these and can incorporate them into their turn.
    """
    session_id: str
    primary_character_id: str
    primary_character_name: str
    observations: List[PlayerObservation] = field(default_factory=list)

    def add_observation(
        self,
        character_id: str,
        character_name: str,
        observation_text: str
    ) -> PlayerObservation:
        """Add a new observation from a secondary player.

        Deduplicates by character_id + observation_text to prevent duplicates.
        """
        # Check for duplicate (same character, same text, not yet included)
        for existing in self.observations:
            if (existing.character_id == character_id and
                existing.observation_text == observation_text and
                not existing.included_in_turn):
                # Already exists, return existing instead of adding duplicate
                return existing

        obs = PlayerObservation(
            character_id=character_id,
            character_name=character_name,
            observation_text=observation_text
        )
        self.observations.append(obs)
        return obs

    def get_unincluded_observations(self) -> List[PlayerObservation]:
        """Get observations that haven't been included in a turn yet."""
        return [obs for obs in self.observations if not obs.included_in_turn]

    def mark_included(self, character_id: str) -> None:
        """Mark an observation as included in the primary player's turn."""
        for obs in self.observations:
            if obs.character_id == character_id and not obs.included_in_turn:
                obs.included_in_turn = True
                break

    def mark_all_included(self) -> None:
        """Mark all observations as included."""
        for obs in self.observations:
            obs.included_in_turn = True

    def clear_included(self) -> None:
        """Remove all included observations."""
        self.observations = [obs for obs in self.observations if not obs.included_in_turn]

    def format_all_for_submission(self) -> str:
        """
        Format all unincluded observations for submission with primary player's action.

        Returns:
            Formatted string to append to primary player's input
        """
        unincluded = self.get_unincluded_observations()
        if not unincluded:
            return ""

        formatted = []
        for obs in unincluded:
            formatted.append(obs.format_for_submission())

        return "\n\n" + "\n".join(formatted)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "primary_character_id": self.primary_character_id,
            "primary_character_name": self.primary_character_name,
            "observations": [obs.to_dict() for obs in self.observations]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PendingObservations":
        """Create from dictionary."""
        observations = [
            PlayerObservation.from_dict(obs_data)
            for obs_data in data.get("observations", [])
        ]
        return cls(
            session_id=data["session_id"],
            primary_character_id=data["primary_character_id"],
            primary_character_name=data["primary_character_name"],
            observations=observations
        )
