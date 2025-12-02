"""Game-related enumerations."""

from enum import Enum


class GameStyle(Enum):
    """Available game styles for campaigns."""
    BALANCED = "balanced"
    COMBAT_HEAVY = "combat_heavy"
    ROLEPLAY_HEAVY = "roleplay_heavy"
    EXPLORATION = "exploration"


class GameTheme(Enum):
    """Available game themes for campaigns."""
    FANTASY = "fantasy"
    MYSTERY = "mystery"
    HORROR = "horror"
    ADVENTURE = "adventure"
    POLITICAL_INTRIGUE = "political_intrigue"
    SURVIVAL = "survival"
    COMEDY = "comedy"
    DARK_FANTASY = "dark_fantasy"