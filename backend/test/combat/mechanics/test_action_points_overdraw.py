"""Test that action points properly allow overdraw (negative AP)."""
import pytest
from gaia.models.combat.mechanics.action_points import ActionPointState


def test_spend_ap_with_sufficient_points():
    """Test spending AP when character has enough."""
    ap_state = ActionPointState(max_ap=4, current_ap=4)

    result = ap_state.spend_ap(2)

    assert result is True  # Should succeed
    assert ap_state.current_ap == 2  # 4 - 2
    assert ap_state.spent_this_turn == 2


def test_spend_ap_with_insufficient_points_allows_overdraw():
    """Test that spending AP when insufficient still deducts (overdraw)."""
    ap_state = ActionPointState(max_ap=4, current_ap=1)

    result = ap_state.spend_ap(2)

    assert result is False  # Indicates overdraw occurred
    assert ap_state.current_ap == -1  # 1 - 2 = -1 (overdraw)
    assert ap_state.spent_this_turn == 2


def test_multiple_overdraws():
    """Test multiple overdraw actions accumulate."""
    ap_state = ActionPointState(max_ap=4, current_ap=1)

    ap_state.spend_ap(2)  # 1 - 2 = -1
    ap_state.spend_ap(1)  # -1 - 1 = -2

    assert ap_state.current_ap == -2
    assert ap_state.spent_this_turn == 3


def test_spend_ap_exact_amount():
    """Test spending exactly remaining AP."""
    ap_state = ActionPointState(max_ap=4, current_ap=2)

    result = ap_state.spend_ap(2)

    assert result is True
    assert ap_state.current_ap == 0
    assert ap_state.spent_this_turn == 2


def test_can_afford_action():
    """Test can_afford_action check."""
    ap_state = ActionPointState(max_ap=4, current_ap=3)

    assert ap_state.can_afford_action(2) is True
    assert ap_state.can_afford_action(3) is True
    assert ap_state.can_afford_action(4) is False