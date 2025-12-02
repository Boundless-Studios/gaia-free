"""Action Point system models for combat mechanics."""
from dataclasses import dataclass, field
from typing import List, Dict, Any
from .action_definitions import ActionCost, ActionName


@dataclass
class ActionPointConfig:
    """Configuration for action point system."""
    base_ap: int = 3
    level_bonus_interval: int = 5

    def calculate_max_ap(self, level: int) -> int:
        """Calculate maximum AP based on character level."""
        level_bonus = level // self.level_bonus_interval
        return self.base_ap + level_bonus


@dataclass
class ActionPointState:
    """Current state of a character's action points."""
    max_ap: int
    current_ap: int
    spent_this_turn: int = 0
    available_actions: List[ActionCost] = field(default_factory=list)

    def can_afford_action(self, action_cost: int) -> bool:
        """Check if character has enough AP for an action."""
        return self.current_ap >= action_cost

    def spend_ap(self, cost: int) -> bool:
        """Spend AP for an action, allowing overdraw (negative AP).

        Returns:
            True if action can be afforded, False if it requires overdraw
        """
        can_afford = self.can_afford_action(cost)
        # Always spend the AP, even if it goes negative (overdraw)
        self.current_ap -= cost
        self.spent_this_turn += cost
        return can_afford

    def reset_turn(self) -> None:
        """Reset AP at the start of a new turn."""
        self.current_ap = self.max_ap
        self.spent_this_turn = 0

    def to_dict(self, compact: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Args:
            compact: If True, only store action names instead of full definitions
        """
        result = {
            "max_ap": self.max_ap,
            "current_ap": self.current_ap,
            "spent_this_turn": self.spent_this_turn,
        }

        if compact:
            # Only store action names for persistence
            result["available_action_names"] = [
                action.name.value if isinstance(action.name, ActionName) else action.name
                for action in self.available_actions
            ]
        else:
            # Store full action definitions for API responses
            result["available_actions"] = [action.to_dict() for action in self.available_actions]

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionPointState':
        """Create from dictionary representation."""
        from .action_definitions import get_action_by_name, STANDARD_ACTIONS

        state = cls(
            max_ap=data.get("max_ap", 3),
            current_ap=data.get("current_ap", 3),
            spent_this_turn=data.get("spent_this_turn", 0)
        )

        # Handle new compact format with action names
        if "available_action_names" in data:
            for action_name in data["available_action_names"]:
                try:
                    action = get_action_by_name(action_name)
                    state.available_actions.append(action)
                except ValueError:
                    # Skip unknown actions
                    pass
        # Handle old format with full action definitions (for backwards compatibility)
        elif "available_actions" in data and data["available_actions"]:
            for action_data in data["available_actions"]:
                if isinstance(action_data, str):
                    # Just a name, look it up
                    try:
                        action = get_action_by_name(action_data)
                        state.available_actions.append(action)
                    except ValueError:
                        pass
                else:
                    # Full action data, create ActionCost
                    state.available_actions.append(
                        ActionCost(
                            name=action_data["name"],
                            cost=action_data["cost"],
                            description=action_data["description"],
                            action_type=action_data["action_type"],
                            prerequisites=action_data.get("prerequisites", [])
                        )
                    )
        # Default to standard actions if nothing specified
        else:
            state.available_actions = list(STANDARD_ACTIONS)

        return state
