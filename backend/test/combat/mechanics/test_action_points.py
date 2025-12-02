"""Tests for Action Point system data models."""
import pytest
from gaia.models.combat.mechanics.action_points import (
    ActionPointConfig, ActionCost, ActionPointState
)
from gaia.models.combat.mechanics.action_definitions import (
    ActionName, ActionType, STANDARD_ACTIONS
)


class TestActionPointConfig:
    """Test ActionPointConfig functionality."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ActionPointConfig()
        assert config.base_ap == 3
        assert config.level_bonus_interval == 5

    def test_calculate_max_ap_base_level(self):
        """Test AP calculation for low-level characters."""
        config = ActionPointConfig()

        # Level 1-4: Should have base 3 AP
        assert config.calculate_max_ap(1) == 3
        assert config.calculate_max_ap(2) == 3
        assert config.calculate_max_ap(3) == 3
        assert config.calculate_max_ap(4) == 3

    def test_calculate_max_ap_with_bonuses(self):
        """Test AP calculation with level bonuses."""
        config = ActionPointConfig()

        # Level 5-9: Should have 4 AP (3 base + 1 bonus)
        assert config.calculate_max_ap(5) == 4
        assert config.calculate_max_ap(7) == 4
        assert config.calculate_max_ap(9) == 4

        # Level 10-14: Should have 5 AP (3 base + 2 bonus)
        assert config.calculate_max_ap(10) == 5
        assert config.calculate_max_ap(12) == 5
        assert config.calculate_max_ap(14) == 5

        # Level 20: Should have 7 AP (3 base + 4 bonus)
        assert config.calculate_max_ap(20) == 7

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ActionPointConfig(base_ap=5, level_bonus_interval=3)

        # With base 5 and bonus every 3 levels
        assert config.calculate_max_ap(1) == 5  # 5 base
        assert config.calculate_max_ap(3) == 6  # 5 + 1 bonus
        assert config.calculate_max_ap(6) == 7  # 5 + 2 bonus
        assert config.calculate_max_ap(9) == 8  # 5 + 3 bonus


class TestActionCost:
    """Test ActionCost data model."""

    def test_action_cost_creation(self):
        """Test creating an action cost."""
        action = ActionCost(
            name="test_action",
            cost=2,
            description="Test action",
            action_type="standard"
        )

        assert action.name == "test_action"
        assert action.cost == 2
        assert action.description == "Test action"
        assert action.action_type == ActionType.STANDARD

    def test_action_cost_with_effects(self):
        """Test action cost with granted effects."""
        action = ActionCost(
            name="defend",
            cost=2,
            description="Take defensive stance",
            action_type="standard",
            grants_effect=["defending"]
        )

        assert len(action.grants_effect) == 1
        assert "defending" in action.grants_effect

    def test_action_cost_to_dict(self):
        """Test serialization to dictionary."""
        action = ActionCost(
            name="defend",
            cost=2,
            description="Take defensive stance",
            action_type="standard"
        )

        data = action.to_dict()
        assert data["name"] == "defend"
        assert data["cost"] == 2
        assert data["action_type"] == "standard"

    def test_standard_actions(self):
        """Test that standard actions are properly defined."""
        assert len(STANDARD_ACTIONS) > 0

        # Check basic attack exists
        basic_attack = next((a for a in STANDARD_ACTIONS if a.name == ActionName.BASIC_ATTACK), None)
        assert basic_attack is not None
        assert basic_attack.cost == 2
        assert basic_attack.action_type == ActionType.STANDARD

        # Check move action exists
        move = next((a for a in STANDARD_ACTIONS if a.name == ActionName.MOVE), None)
        assert move is not None
        assert move.cost == 1
        assert move.action_type == ActionType.SIMPLE


class TestActionPointState:
    """Test ActionPointState management."""

    def test_state_initialization(self):
        """Test initializing action point state."""
        state = ActionPointState(
            max_ap=5,
            current_ap=5
        )

        assert state.max_ap == 5
        assert state.current_ap == 5
        assert state.spent_this_turn == 0
        assert state.available_actions == []

    def test_can_afford_action(self):
        """Test checking if an action is affordable."""
        state = ActionPointState(max_ap=3, current_ap=3)

        assert state.can_afford_action(1) == True
        assert state.can_afford_action(2) == True
        assert state.can_afford_action(3) == True
        assert state.can_afford_action(4) == False
        assert state.can_afford_action(0) == True

    def test_spend_ap_success(self):
        """Test successfully spending AP."""
        state = ActionPointState(max_ap=5, current_ap=5)

        # Spend 2 AP
        result = state.spend_ap(2)
        assert result == True
        assert state.current_ap == 3
        assert state.spent_this_turn == 2

        # Spend 1 more AP
        result = state.spend_ap(1)
        assert result == True
        assert state.current_ap == 2
        assert state.spent_this_turn == 3

    def test_spend_ap_overdraw(self):
        """Test overdraw behavior when spending more AP than available."""
        state = ActionPointState(max_ap=3, current_ap=2)

        # Try to spend 3 AP when only 2 available - triggers overdraw
        result = state.spend_ap(3)
        assert result == False  # Returns False to indicate overdraw occurred
        assert state.current_ap == -1  # AP goes negative (overdraw)
        assert state.spent_this_turn == 3  # AP is still spent

    def test_reset_turn(self):
        """Test resetting AP at start of new turn."""
        state = ActionPointState(max_ap=4, current_ap=1)
        state.spent_this_turn = 3

        state.reset_turn()

        assert state.current_ap == 4  # Reset to max
        assert state.spent_this_turn == 0  # Reset spent counter

    def test_state_to_dict(self):
        """Test serialization of state to dictionary."""
        state = ActionPointState(
            max_ap=5,
            current_ap=3,
            spent_this_turn=2,
            available_actions=[
                ActionCost("move", 1, "Move", "simple"),
                ActionCost("attack", 2, "Attack", "standard")
            ]
        )

        data = state.to_dict()
        assert data["max_ap"] == 5
        assert data["current_ap"] == 3
        assert data["spent_this_turn"] == 2
        assert len(data["available_actions"]) == 2
        assert data["available_actions"][0]["name"] == "move"

    def test_state_with_available_actions(self):
        """Test state with pre-populated available actions."""
        actions = [
            ActionCost("move", 1, "Move", "simple"),
            ActionCost("attack", 2, "Attack", "standard"),
            ActionCost("defend", 2, "Defend", "standard")
        ]

        state = ActionPointState(
            max_ap=4,
            current_ap=4,
            available_actions=actions
        )

        assert len(state.available_actions) == 3
        assert state.available_actions[0].name == ActionName.MOVE

        # Should be able to afford all actions
        for action in state.available_actions:
            assert state.can_afford_action(action.cost) == True

    def test_sequential_action_spending(self):
        """Test spending AP for multiple actions in sequence with overdraw."""
        state = ActionPointState(max_ap=5, current_ap=5)

        # Perform move (1 AP)
        assert state.spend_ap(1) == True
        assert state.current_ap == 4

        # Perform attack (2 AP)
        assert state.spend_ap(2) == True
        assert state.current_ap == 2

        # Try complex action (3 AP) - triggers overdraw
        assert state.spend_ap(3) == False  # Returns False (overdraw)
        assert state.current_ap == -1  # AP goes negative

        # Perform another move (1 AP) - further overdraw (still returns False)
        assert state.spend_ap(1) == False  # Still overdrawing (not enough AP)
        assert state.current_ap == -2

        # Total spent should be 7 (allows overdraw)
        assert state.spent_this_turn == 7
