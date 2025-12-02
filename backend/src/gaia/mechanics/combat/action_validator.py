"""Simplified action validation for combat system.

This module provides a simpler approach to action validation.
The can_perform_action method focuses on:
1. Can the combatant act (conscious, not incapacitated)?
2. Do they have sufficient AP?
3. What's the overdraw level if insufficient?
"""
from typing import Dict
from dataclasses import dataclass
from enum import IntEnum

from gaia.models.combat import CombatantState, StatusEffectType
from gaia.models.combat.mechanics.action_definitions import ActionCost, ActionName


class OverdrawLevel(IntEnum):
    """Level of AP overdraw for an action."""
    NONE = 0     # No overdraw - action can be performed
    MINOR = 1    # 1 AP short
    MODERATE = 2 # 2 AP short
    MAJOR = 3    # 3+ AP short


@dataclass
class ActionCheck:
    """Result of checking if a combatant can perform an action."""
    can_act: bool
    reason: str = ""
    required_ap: int = 0
    available_ap: int = 0
    overdraw_level: OverdrawLevel = OverdrawLevel.NONE

    @property
    def has_overdraw(self) -> bool:
        """Check if action would cause AP overdraw."""
        return self.overdraw_level > OverdrawLevel.NONE


def can_perform_action(
    combatant: CombatantState,
    action_name: str,
    action_costs: Dict[str, ActionCost]
) -> ActionCheck:
    """
    Check if a combatant can perform an action.

    Simple check focusing on:
    1. Can the combatant act (conscious, not incapacitated)?
    2. Do they have sufficient AP?
    3. What's the overdraw level if insufficient?

    Args:
        combatant: The combatant attempting the action
        action_name: Name of the action to perform
        action_costs: Dictionary of action names to ActionCost objects

    Returns:
        ActionCheck with result and overdraw level
    """
    # Normalize action name
    normalized_action = action_name.lower() if action_name else ""
    is_recover_action = normalized_action == ActionName.RECOVER.value

    # Check if combatant can act
    if not combatant.is_conscious and not is_recover_action:
        return ActionCheck(can_act=False, reason="Unconscious")

    # Check for incapacitating status effects
    incapacitating = {
        StatusEffectType.STUNNED: "Stunned",
        StatusEffectType.PARALYZED: "Paralyzed",
        StatusEffectType.INCAPACITATED: "Incapacitated",
        StatusEffectType.UNCONSCIOUS: "Unconscious"
    }

    for effect in combatant.status_effects or []:
        if effect.effect_type in incapacitating:
            if not is_recover_action:
                return ActionCheck(can_act=False, reason=incapacitating[effect.effect_type])

    # Get action cost
    action_cost = None

    # Check direct match
    if action_name in action_costs:
        action = action_costs[action_name]
        action_cost = action.cost if isinstance(action, ActionCost) else action
    else:
        # Check lowercase match
        normalized = action_name.lower()
        for key, action in action_costs.items():
            if key.lower() == normalized:
                action_cost = action.cost if isinstance(action, ActionCost) else action
                break

    if action_cost is None:
        return ActionCheck(can_act=False, reason=f"Unknown action: {action_name}")

    # Check AP and calculate overdraw
    if not combatant.action_points:
        # Recover action doesn't need AP
        if is_recover_action:
            return ActionCheck(can_act=True, reason="Recovery attempt", required_ap=0, available_ap=0)
        return ActionCheck(can_act=False, reason="No action points")

    available_ap = combatant.action_points.current_ap
    required_ap = action_cost

    # Calculate overdraw level
    overdraw_level = OverdrawLevel.NONE
    if available_ap < required_ap:
        ap_deficit = required_ap - available_ap
        if ap_deficit == 1:
            overdraw_level = OverdrawLevel.MINOR
        elif ap_deficit == 2:
            overdraw_level = OverdrawLevel.MODERATE
        else:
            overdraw_level = OverdrawLevel.MAJOR

    # Determine if action is allowed
    can_act = is_recover_action or available_ap >= required_ap

    reason = ""
    if not can_act:
        reason = f"Insufficient AP (need {required_ap}, have {available_ap})"
    elif overdraw_level > OverdrawLevel.NONE:
        reason = f"Overdraw level {overdraw_level.name.lower()}"

    return ActionCheck(
        can_act=can_act,
        reason=reason,
        required_ap=required_ap,
        available_ap=available_ap,
        overdraw_level=overdraw_level
    )


# Compatibility class for legacy code
class ActionValidator:
    """Simplified action validator using the new approach."""

    def __init__(self, action_costs=None):
        """Initialize with action cost definitions.

        Args:
            action_costs: Dict of action names to costs. If None, uses STANDARD_ACTIONS.
        """
        if action_costs is None:
            from core.models.combat.mechanics.action_definitions import STANDARD_ACTIONS
            self.action_costs = {}
            for action in STANDARD_ACTIONS:
                # Handle both string and enum action names
                if isinstance(action.name, ActionName):
                    action_name = action.name.value
                else:
                    action_name = str(action.name)
                self.action_costs[action_name] = action
        else:
            self.action_costs = action_costs

    def can_perform_action(self, combatant: CombatantState, action_name: str) -> ActionCheck:
        """Check if a combatant can perform an action."""
        return can_perform_action(combatant, action_name, self.action_costs)


# Example usage:
def example_usage():
    """Example of using the simplified action validation."""
    from core.models.combat.mechanics.action_definitions import STANDARD_ACTIONS
    from core.models.combat.mechanics.action_points import ActionPointState

    # Convert STANDARD_ACTIONS to a dict
    action_costs = {}
    for action in STANDARD_ACTIONS:
        # Handle both string and enum action names
        if isinstance(action.name, ActionName):
            action_name = action.name.value
        else:
            action_name = str(action.name)
        action_costs[action_name] = action

    # Mock combatant with 2 AP
    combatant = CombatantState(
        character_id="test",
        name="Test Fighter",
        initiative=10,
        hp=20,
        max_hp=20,
        ac=15,
        level=1,
        is_npc=False,
        action_points=ActionPointState(max_ap=3, current_ap=2)
    )

    # Check if can perform basic attack (costs 2 AP)
    check = can_perform_action(combatant, "basic_attack", action_costs)
    print(f"Basic Attack: can_act={check.can_act}, overdraw={check.overdraw_level.name}")

    # Check if can perform full attack (costs 3 AP - will have overdraw)
    check = can_perform_action(combatant, "full_attack", action_costs)
    print(f"Full Attack: can_act={check.can_act}, overdraw={check.overdraw_level.name}, reason={check.reason}")

    # Check if can move (costs 1 AP)
    check = can_perform_action(combatant, "move", action_costs)
    print(f"Move: can_act={check.can_act}, overdraw={check.overdraw_level.name}")


if __name__ == "__main__":
    example_usage()