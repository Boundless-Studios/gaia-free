"""Well-formed data structures for combat action results."""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from enum import Enum


class ActionType(str, Enum):
    """Types of combat actions."""
    BASIC_ATTACK = "basic_attack"
    FULL_ATTACK = "full_attack"
    DEFEND = "defend"
    MOVE = "move"
    RECOVER = "recover"
    CAST_SPELL = "cast_spell"
    DODGE = "dodge"
    DASH = "dash"
    HELP = "help"
    HIDE = "hide"


class TurnTransitionReason(str, Enum):
    """Reasons why a combat turn transitioned or continued."""

    AP_EXHAUSTED = "ap_exhausted"
    AP_OVERDRAWN = "ap_overdrawn"
    ACTION_FAILED = "action_failed"
    ACTION_EXHAUSTED_AP = "action_exhausted_ap"
    EXPLICIT_END = "explicit_end"
    TURN_CONTINUES = "turn_continues"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass
class InvalidTargetActionResult:
    """Result when target validation fails - can be used by any action type.

    This universal result type includes all possible fields from other action
    results, with null/default values. This allows it to be returned from any
    action handler without type issues.
    """
    success: bool = False
    target_id: str = ""
    description: str = ""
    effects_applied: List[str] = field(default_factory=lambda: ["invalid_target"])

    # Attack-related fields (null for invalid target)
    damage: Optional[int] = None
    attack_roll: Optional[int] = None
    critical: bool = False

    # Defend-related fields
    ac_bonus: int = 0

    # Move-related fields
    new_position: Optional[Dict[str, int]] = None
    distance_moved: Optional[float] = None

    # Recover-related fields
    hp_recovered: int = 0
    effects_removed: List[str] = field(default_factory=list)
    roll_result: Optional[int] = None

    def to_tuple(self):
        """Legacy conversion to tuple format."""
        return (self.success, None, self.description, None, self.effects_applied)


@dataclass
class AttackActionResult:
    """Result of an attack action."""
    success: bool
    damage: Optional[int] = None
    description: str = ""
    attack_roll: Optional[int] = None
    effects_applied: List[str] = field(default_factory=list)
    target_id: Optional[str] = None
    critical: bool = False

    def to_tuple(self):
        """Legacy conversion to tuple format."""
        return (self.success, self.damage, self.description,
                self.attack_roll, self.effects_applied)


@dataclass
class DefendActionResult:
    """Result of a defend action."""
    success: bool
    description: str = ""
    effects_applied: List[str] = field(default_factory=list)
    ac_bonus: int = 0

    def to_tuple(self):
        """Legacy conversion to tuple format."""
        return (self.success, self.description, self.effects_applied)


@dataclass
class MoveActionResult:
    """Result of a movement action."""
    success: bool
    description: str = ""
    new_position: Optional[Dict[str, int]] = None
    distance_moved: Optional[float] = None

    def to_tuple(self):
        """Legacy conversion to tuple format."""
        return (self.success, self.description)


@dataclass
class RecoverActionResult:
    """Result of a recovery attempt."""
    success: bool
    description: str = ""
    hp_recovered: int = 0
    effects_removed: List[str] = field(default_factory=list)
    roll_result: Optional[int] = None

    def to_tuple(self):
        """Legacy conversion to tuple format."""
        return (self.success, self.description, self.hp_recovered, self.effects_removed)


@dataclass
class CombatMechanicsContext:
    """Context for resolving combat mechanics."""
    action_type: str
    actor_id: str
    target_id: Optional[str] = None
    action_details: Dict[str, Any] = field(default_factory=dict)
    llm_narrative: Optional[str] = None


@dataclass
class CombatMechanicsResult:
    """Result of resolving combat mechanics."""
    success: bool
    action_type: str
    damage: Optional[int] = None
    description: str = ""
    effects_applied: List[str] = field(default_factory=list)
    state_changes: Dict[str, Any] = field(default_factory=dict)
    narrative: Optional[str] = None


@dataclass
class TurnTransitionResult:
    """Result of determining the next turn in combat."""
    current_actor: str
    next_combatant: str
    reason: TurnTransitionReason
    new_round: bool
    round_number: int
    order_index: int

    def __post_init__(self) -> None:
        """Ensure reason is always represented as a TurnTransitionReason enum."""
        if isinstance(self.reason, str):
            self.reason = TurnTransitionReason(self.reason)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for backward compatibility."""
        return {
            "current_actor": self.current_actor,
            "next_combatant": self.next_combatant,
            "reason": str(self.reason),
            "new_round": self.new_round,
            "round": self.round_number,
            "order_index": self.order_index
        }
