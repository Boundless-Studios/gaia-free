"""Enumerations for combat system."""
from enum import Enum


class CombatStatus(Enum):
    """Combat session status."""
    INITIALIZING = "initializing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class VictoryCondition(Enum):
    """Combat victory conditions."""
    DEFEAT_ALL_ENEMIES = "defeat_all_enemies"
    SURVIVE_ROUNDS = "survive_rounds"
    PROTECT_TARGET = "protect_target"
    ESCAPE = "escape"
    SPECIAL_OBJECTIVE = "special_objective"


class ThreatLevel(Enum):
    """Combat threat level assessment."""
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"
    DEADLY = "deadly"


class StatusEffectType(Enum):
    """Types of status effects."""
    POISONED = "poisoned"
    STUNNED = "stunned"
    PRONE = "prone"
    GRAPPLED = "grappled"
    RESTRAINED = "restrained"
    PARALYZED = "paralyzed"
    FRIGHTENED = "frightened"
    CHARMED = "charmed"
    BLINDED = "blinded"
    DEAFENED = "deafened"
    EXHAUSTED = "exhausted"
    INCAPACITATED = "incapacitated"
    INVISIBLE = "invisible"
    UNCONSCIOUS = "unconscious"
    BLESSED = "blessed"
    CURSED = "cursed"
    DEFENDING = "defending"  # +2 AC from defend action
    DODGING = "dodging"  # Attacks against have disadvantage
    DISENGAGED = "disengaged"  # No opportunity attacks when moving
    HELPED = "helped"  # Advantage on next action