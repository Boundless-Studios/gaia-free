"""PersonalizedPlayerOptions data model - container for all player options in a session."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

from .character_options import CharacterOptions


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
