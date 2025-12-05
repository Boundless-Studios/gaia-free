"""
Data models for personalized player options.

Each connected player gets their own set of options:
- Active player (turn-taker): Uses active_player_options prompt (action-oriented)
- Secondary players: Uses player_options prompt (discovery/observation-focused)
"""

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


@dataclass
class PersonalizedPlayerOptions:
    """
    Container for all player options in a session.

    Structure:
    {
        "active_character_id": "char_123",
        "characters": {
            "char_123": CharacterOptions(is_active=True, ...),
            "char_456": CharacterOptions(is_active=False, ...)
        }
    }
    """
    active_character_id: Optional[str] = None
    characters: Dict[str, CharacterOptions] = field(default_factory=dict)
    scene_narrative: str = ""  # The narrative that prompted these options
    generated_at: Optional[datetime] = None

    def get_options_for_character(self, character_id: str) -> Optional[CharacterOptions]:
        """Get options for a specific character."""
        return self.characters.get(character_id)

    def get_active_character_options(self) -> Optional[CharacterOptions]:
        """Get options for the active (turn-taking) character."""
        if self.active_character_id:
            return self.characters.get(self.active_character_id)
        # Fallback: find the character marked as active
        for char_opts in self.characters.values():
            if char_opts.is_active:
                return char_opts
        return None

    def add_character_options(
        self,
        character_id: str,
        character_name: str,
        options: List[str],
        is_active: bool = False
    ) -> None:
        """Add or update options for a character."""
        self.characters[character_id] = CharacterOptions(
            character_id=character_id,
            character_name=character_name,
            options=options,
            is_active=is_active,
            generated_at=datetime.now()
        )
        if is_active:
            self.active_character_id = character_id

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "active_character_id": self.active_character_id,
            "characters": {
                char_id: char_opts.to_dict()
                for char_id, char_opts in self.characters.items()
            },
            "scene_narrative": self.scene_narrative,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PersonalizedPlayerOptions":
        """Create from dictionary."""
        generated_at = None
        if data.get("generated_at"):
            generated_at = datetime.fromisoformat(data["generated_at"])

        characters = {}
        for char_id, char_data in data.get("characters", {}).items():
            characters[char_id] = CharacterOptions.from_dict(char_data)

        return cls(
            active_character_id=data.get("active_character_id"),
            characters=characters,
            scene_narrative=data.get("scene_narrative", ""),
            generated_at=generated_at
        )

    def to_legacy_format(self, character_id: Optional[str] = None) -> List[str]:
        """
        Convert to legacy format (single list of options) for backward compatibility.

        Args:
            character_id: If provided, return options for that character.
                         Otherwise, return options for the active character.

        Returns:
            List of option strings
        """
        if character_id:
            char_opts = self.characters.get(character_id)
        else:
            char_opts = self.get_active_character_options()

        return char_opts.options if char_opts else []


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
        """Add a new observation from a secondary player."""
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
