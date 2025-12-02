from dataclasses import dataclass
from enum import Enum

class GameStyle(Enum):
    """Different D&D game configuration styles"""
    TACTICAL = "tactical"        # Rules-heavy, combat-focused
    NARRATIVE = "narrative"      # Story-focused, flexible rules
    TUTORIAL = "tutorial"        # Teaching new players
    BALANCED = "balanced"        # Standard play
    CINEMATIC = "cinematic"      # Epic, rule-of-cool moments

@dataclass
class GameConfiguration:
    """Configuration for different game styles"""
    style: GameStyle
    rule_strictness: float         # 0.0 (very flexible) to 1.0 (very strict)
    tool_usage_threshold: float    # Lower = more tool usage
    player_agency_level: str       # "full", "guided", "cinematic"
    explanation_detail: str        # "minimal", "standard", "verbose"
    pace_preference: str           # "fast", "moderate", "deliberate"

# Predefined configurations
GAME_CONFIGS = {
    GameStyle.TACTICAL: GameConfiguration(
        style=GameStyle.TACTICAL,
        rule_strictness=0.9,
        tool_usage_threshold=0.3,      # Use tools frequently
        player_agency_level="full",     # Players control everything
        explanation_detail="verbose",   # Explain all rulings
        pace_preference="deliberate"    # Take time for tactics
    ),
    GameStyle.NARRATIVE: GameConfiguration(
        style=GameStyle.NARRATIVE,
        rule_strictness=0.3,
        tool_usage_threshold=0.8,      # Tools only when essential
        player_agency_level="cinematic", # DM adds flourishes
        explanation_detail="minimal",    # Keep story flowing
        pace_preference="fast"          # Don't bog down in rules
    ),
    GameStyle.TUTORIAL: GameConfiguration(
        style=GameStyle.TUTORIAL,
        rule_strictness=1.0,           # Teaching correct rules
        tool_usage_threshold=0.2,      # Frequent rule checks
        player_agency_level="guided",   # Help players learn
        explanation_detail="verbose",   # Explain everything
        pace_preference="moderate"      # Time to learn
    ),
    GameStyle.BALANCED: GameConfiguration(
        style=GameStyle.BALANCED,
        rule_strictness=0.7,
        tool_usage_threshold=0.5,
        player_agency_level="full",
        explanation_detail="standard",
        pace_preference="moderate"
    ),
    GameStyle.CINEMATIC: GameConfiguration(
        style=GameStyle.CINEMATIC,
        rule_strictness=0.2,
        tool_usage_threshold=0.9,      # Almost never check rules
        player_agency_level="cinematic",
        explanation_detail="minimal",
        pace_preference="fast"
    )
}