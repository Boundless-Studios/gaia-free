"""Standard action definitions for the Action Point combat system."""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Union


class ActionType(str, Enum):
    """Enumeration of available action types."""

    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"
    BONUS = "bonus"


class ActionName(str, Enum):
    """Enumeration of the standard combat action identifiers."""

    END_TURN = "end_turn"
    MOVE = "move"
    BASIC_ATTACK = "basic_attack"
    CAST_SIMPLE_SPELL = "cast_simple_spell"
    DEFEND = "defend"
    COMPLEX_SPELL = "complex_spell"
    SPECIAL_ABILITY = "special_ability"
    FULL_ATTACK = "full_attack"
    BONUS_ACTION = "bonus_action"
    DODGE = "dodge"
    DASH = "dash"
    DISENGAGE = "disengage"
    HELP = "help"
    HIDE = "hide"
    SEARCH = "search"
    HEAL = "heal"
    GRAPPLE = "grapple"
    SHOVE = "shove"
    READY_ACTION = "ready_action"
    RECOVER = "recover"


def _name_to_string(name: Union[ActionName, str]) -> str:
    """Return the canonical string representation of an action name."""

    return name.value if isinstance(name, ActionName) else name


def _type_to_string(action_type: Union[ActionType, str]) -> str:
    """Return the canonical string representation of an action type."""

    return action_type.value if isinstance(action_type, ActionType) else action_type


@dataclass
class ActionCost:
    """Definition of an action and its AP cost."""

    name: Union[ActionName, str]
    cost: int
    description: str
    action_type: Union[ActionType, str]

    # Resolution mechanics
    damage_dice: str = ""  # Dice to roll for damage (e.g., "1d8+3")
    save_dc: int = 0  # DC for saving throws
    grants_effect: List[str] = field(default_factory=list)  # Effects granted

    def __post_init__(self) -> None:
        """Normalize enum inputs."""

        if isinstance(self.name, str):
            try:
                self.name = ActionName(self.name)
            except ValueError:
                pass
        if isinstance(self.action_type, str):
            try:
                self.action_type = ActionType(self.action_type)
            except ValueError:
                pass
        if isinstance(self.damage_dice, DiceDefinition):
            self.damage_dice = self.damage_dice.to_expression()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": _name_to_string(self.name),
            "cost": self.cost,
            "description": self.description,
            "action_type": _type_to_string(self.action_type),
        }


@dataclass(frozen=True)
class DiceDefinition:
    """Structured representation of a dice expression such as '2d6+3'."""

    count: int
    sides: int
    modifier: int = 0

    _EXPRESSION = re.compile(r"^\s*(\d*)d(\d+)([+-]\d+)?\s*$")

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise ValueError("Dice count must be positive")
        if self.sides <= 0:
            raise ValueError("Dice sides must be positive")

    @classmethod
    def from_expression(cls, expression: str) -> "DiceDefinition":
        if not expression:
            raise ValueError("Dice expression cannot be empty")
        match = cls._EXPRESSION.match(expression)
        if not match:
            raise ValueError(f"Invalid dice expression: {expression}")
        count_str, sides_str, modifier_str = match.groups()
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        modifier = int(modifier_str) if modifier_str else 0
        return cls(count=count, sides=sides, modifier=modifier)

    def to_expression(self) -> str:
        base = f"{self.count}d{self.sides}"
        if self.modifier > 0:
            return f"{base}+{self.modifier}"
        if self.modifier < 0:
            return f"{base}{self.modifier}"
        return base

    def __str__(self) -> str:
        return self.to_expression()

# Standard action definitions
STANDARD_ACTIONS = [
    ActionCost(
        name=ActionName.RECOVER,
        cost=0,
        description="Attempt to recover from incapacitation (roll 19-20 to stand up)",
        action_type=ActionType.SIMPLE
    ),
    ActionCost(
        name=ActionName.END_TURN,
        cost=0,
        description="End your turn and pass to the next combatant",
        action_type=ActionType.SIMPLE,
        grants_effect=["turn_ended"]
    ),
    ActionCost(
        name=ActionName.MOVE,
        cost=1,
        description="Move up to your speed",
        action_type=ActionType.SIMPLE,
        grants_effect=["moved"]
    ),
    ActionCost(
        name=ActionName.BASIC_ATTACK,
        cost=2,
        description="Make a single melee or ranged attack",
        action_type=ActionType.STANDARD,
        damage_dice="1d8+3"
    ),
    ActionCost(
        name=ActionName.CAST_SIMPLE_SPELL,
        cost=2,
        description="Cast a simple spell or cantrip",
        action_type=ActionType.STANDARD,
        damage_dice="1d6+2",  # Standard spell damage
        save_dc=13,  # Standard spell save DC
    ),
    ActionCost(
        name=ActionName.DEFEND,
        cost=2,
        description="Take defensive stance (+2 AC until next turn)",
        action_type=ActionType.STANDARD,
        grants_effect=["defending"]
    ),
    ActionCost(
        name=ActionName.COMPLEX_SPELL,
        cost=3,
        description="Cast a powerful spell",
        action_type=ActionType.COMPLEX,
        damage_dice="2d8+3",  # Higher spell damage
        save_dc=15,  # Higher spell save DC
    ),
    ActionCost(
        name=ActionName.SPECIAL_ABILITY,
        cost=3,
        description="Use a special class ability",
        action_type=ActionType.COMPLEX
    ),
    ActionCost(
        name=ActionName.FULL_ATTACK,
        cost=5,
        description="Make multiple attacks",
        action_type=ActionType.COMPLEX,
        damage_dice="2d6+3",
    ),
    ActionCost(
        name=ActionName.BONUS_ACTION,
        cost=1,
        description="Quick minor action",
        action_type=ActionType.BONUS
    ),
    ActionCost(
        name=ActionName.DODGE,
        cost=1,
        description="Impose disadvantage on attacks against you",
        action_type=ActionType.SIMPLE
    ),
    ActionCost(
        name=ActionName.DASH,
        cost=1,
        description="Double your movement speed",
        action_type=ActionType.SIMPLE
    ),
    ActionCost(
        name=ActionName.DISENGAGE,
        cost=1,
        description="Move without provoking opportunity attacks",
        action_type=ActionType.SIMPLE
    ),
    ActionCost(
        name=ActionName.HELP,
        cost=1,
        description="Grant advantage to an ally's next action",
        action_type=ActionType.SIMPLE
    ),
    ActionCost(
        name=ActionName.HIDE,
        cost=1,
        description="Attempt to hide from enemies",
        action_type=ActionType.SIMPLE
    ),
    ActionCost(
        name=ActionName.SEARCH,
        cost=1,
        description="Search for hidden objects or creatures",
        action_type=ActionType.SIMPLE
    ),
    ActionCost(
        name=ActionName.HEAL,
        cost=3,
        description="Use healing magic or items",
        action_type=ActionType.COMPLEX,
        damage_dice="2d4+2",  # Negative damage = healing
        grants_effect=["healing"]
    ),
    ActionCost(
        name=ActionName.GRAPPLE,
        cost=2,
        description="Attempt to grapple an enemy",
        action_type=ActionType.STANDARD
    ),
    ActionCost(
        name=ActionName.SHOVE,
        cost=2,
        description="Push an enemy or knock them prone",
        action_type=ActionType.STANDARD
    ),
    ActionCost(
        name=ActionName.READY_ACTION,
        cost=2,
        description="Prepare an action to trigger on a condition",
        action_type=ActionType.STANDARD
    )
]


def get_action_by_name(name: Union[str, ActionName]) -> ActionCost:
    """Get an action definition by its name."""
    if isinstance(name, ActionName):
        target_value = _name_to_string(name)
    else:
        try:
            target_value = ActionName(name).value
        except ValueError:
            target_value = name

    for action in STANDARD_ACTIONS:
        if _name_to_string(action.name) == target_value:
            return action
    raise ValueError(f"Action '{name}' not found in standard actions")


def get_actions_by_type(action_type: Union[str, ActionType]) -> List[ActionCost]:
    """Get all actions of a specific type."""
    try:
        target_type = ActionType(action_type) if isinstance(action_type, str) else action_type
    except ValueError as exc:
        raise ValueError(f"Unknown action type '{action_type}'") from exc

    target_value = _type_to_string(target_type)
    return [
        action
        for action in STANDARD_ACTIONS
        if _type_to_string(action.action_type) == target_value
    ]


def get_affordable_actions(current_ap: int) -> List[ActionCost]:
    """Get all actions that can be afforded with current AP."""
    return [action for action in STANDARD_ACTIONS if action.cost <= current_ap]


def format_available_actions(current_ap: int) -> str:
    """Format available actions based on current AP into a display string.

    Args:
        current_ap: Current action points available

    Returns:
        Formatted string of available actions with AP costs
    """
    if current_ap <= 0:
        return "End Turn (0 AP)"

    affordable = get_affordable_actions(current_ap)

    # Sort by cost for better presentation
    affordable.sort(key=lambda a: (a.cost, _name_to_string(a.name)))

    # Format each action
    options = []
    for action in affordable:
        # Use more user-friendly names
        display_name = _name_to_string(action.name).replace("_", " ").title()
        options.append(f"{display_name} ({action.cost} AP)")

    # Always add end turn as an option
    if current_ap > 0:
        options.append("End Turn (0 AP)")

    return ", ".join(options) if options else "End Turn (0 AP)"


def format_action_list_for_agent(actions: Optional[List[ActionCost]] = None) -> str:
    """Format complete action list for combat agent consumption.

    Args:
        actions: List of actions to format (defaults to STANDARD_ACTIONS)

    Returns:
        Formatted string with all actions, costs, and descriptions
    """
    if actions is None:
        actions = STANDARD_ACTIONS

    lines = []
    # Group by AP cost for clarity
    actions_by_cost = {}
    for action in actions:
        if action.cost not in actions_by_cost:
            actions_by_cost[action.cost] = []
        actions_by_cost[action.cost].append(action)

    # Format each cost group
    for cost in sorted(actions_by_cost.keys()):
        lines.append(f"[{cost} AP Actions]")
        for action in sorted(actions_by_cost[cost], key=lambda a: _name_to_string(a.name)):
            lines.append(f"• {_name_to_string(action.name)}: {action.description}")
        lines.append("")  # Empty line between groups

    return "\n".join(lines)
