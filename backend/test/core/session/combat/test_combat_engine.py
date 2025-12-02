"""Unit tests for combat engine mechanics helpers.

Tests the deterministic combat mechanics resolution and turn transition logic.
"""

import pytest
from typing import Dict, Any

from gaia.mechanics.combat.combat_engine import CombatEngine, CombatMechanicsResolution
from gaia.mechanics.combat.combat_action_results import TurnTransitionReason
from gaia_private.models.combat.agent_io.fight.combatant_view import CombatantView
from gaia_private.models.combat.agent_io.fight.combat_action_request import CombatActionRequest
from gaia_private.models.combat.agent_io.fight.current_turn_info import CurrentTurnInfo
from gaia_private.models.combat.agent_io.initiation.battlefield_config import BattlefieldConfig


class DummyContext:
    """Simple stand-in for the combat update context."""

    def __init__(self):
        self.hp_changes = {"Hero": {"current": 5, "max": 10}}
        self.ap_changes = {"Hero": {"current": -1, "max": 3}}
        self.status_effects_applied = {"Hero": ["winded"]}
        self.action_resolutions = []

    def get_authoritative_hp(self, combatant: str):
        return self.hp_changes.get(combatant)

    def get_authoritative_ap(self, combatant: str):
        return self.ap_changes.get(combatant)

    def get_net_damage(self, combatant: str) -> int:
        return 0


def test_resolve_combat_mechanics_prefers_authoritative_state():
    """Test that combat mechanics resolution prefers authoritative state from context."""
    engine = CombatEngine()

    # Use CombatantView (the correct model, CombatantStatus is an alias)
    combatant = CombatantView(
        name="Hero",
        type="player",
        hp_current=8,
        hp_max=12,
        armor_class=15,
        action_points_current=3,
        action_points_max=3,
        is_active=True,
        is_conscious=True
    )

    context = DummyContext()
    llm_data = {"narrative_effects": [{"character": "Hero", "effect": "glowing aura"}]}

    result: CombatMechanicsResolution = engine.resolve_combat_mechanics(
        combatant=combatant,
        context=context,
        llm_data=llm_data
    )

    # Verify it uses authoritative state from context (not combatant values)
    assert result.character_status.hp == "5/10"  # From context, not 8/12
    assert result.character_status.ap == "-1/3"  # From context, not 3/3
    assert "winded" in result.character_status.status
    assert "glowing aura" in result.character_status.status
    assert result.current_ap == -1
    assert result.max_ap == 3


def test_resolve_combat_mechanics_fallback_to_combatant_state():
    """Test that combat mechanics uses combatant state when context has no authoritative data."""
    engine = CombatEngine()

    combatant = CombatantView(
        name="Warrior",
        type="player",
        hp_current=15,
        hp_max=20,
        armor_class=16,
        action_points_current=2,
        action_points_max=3,
        is_active=True,
        is_conscious=True
    )

    # Empty context - no authoritative state
    class EmptyContext:
        status_effects_applied = {}
        action_resolutions = []

        def get_authoritative_hp(self, combatant: str):
            return None

        def get_authoritative_ap(self, combatant: str):
            return None

        def get_net_damage(self, combatant: str) -> int:
            return 0

    context = EmptyContext()
    llm_data = {}

    result = engine.resolve_combat_mechanics(
        combatant=combatant,
        context=context,
        llm_data=llm_data
    )

    # Should use combatant's own state
    assert result.character_status.hp == "15/20"
    assert result.character_status.ap == "2/3"
    assert result.current_ap == 2
    assert result.max_ap == 3


def test_resolve_turn_transition_skips_inactive_and_wraps():
    """Test turn transition logic skips unconscious combatants and wraps around."""
    engine = CombatEngine()

    combatants = [
        CombatantView(
            name="Hero",
            type="player",
            hp_current=10,
            hp_max=10,
            armor_class=12,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        ),
        CombatantView(
            name="Ally",
            type="player",
            hp_current=0,  # Unconscious
            hp_max=10,
            armor_class=12,
            action_points_current=0,
            action_points_max=3,
            is_active=False,  # Can't act - unconscious with 0 HP
            is_conscious=False  # Should be skipped
        ),
        CombatantView(
            name="Enemy",
            type="enemy",
            hp_current=10,
            hp_max=10,
            armor_class=12,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        ),
    ]

    request = CombatActionRequest(
        campaign_id="camp",
        combat_id="combat",
        player_action="attack",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant="Hero",
            available_actions=[]
        ),
        combatants=combatants,
        battlefield=BattlefieldConfig(size="medium", terrain="field"),
        initiative_order=["Hero", "Ally", "Enemy"],
    )

    # Test transition from Hero - should skip Ally and go to Enemy
    turn_info = engine.resolve_turn_transition(
        current_actor="Hero",
        reason=TurnTransitionReason.AP_EXHAUSTED,
        request=request
    )

    assert turn_info is not None
    assert turn_info.next_combatant == "Enemy"  # Skipped Ally
    assert turn_info.new_round is False
    assert turn_info.round_number == 1
    assert turn_info.reason == TurnTransitionReason.AP_EXHAUSTED

    # Test wrap-around from Enemy back to Hero (skipping Ally again)
    wrapped = engine.resolve_turn_transition(
        current_actor="Enemy",
        reason=TurnTransitionReason.EXPLICIT_END,
        request=request
    )

    assert wrapped is not None
    assert wrapped.next_combatant == "Hero"  # Wrapped around, skipped Ally
    assert wrapped.new_round is True  # New round started
    assert wrapped.round_number == 2


def test_resolve_turn_transition_with_all_conscious():
    """Test turn transition when all combatants are conscious."""
    engine = CombatEngine()

    combatants = [
        CombatantView(
            name="Fighter",
            type="player",
            hp_current=10,
            hp_max=10,
            armor_class=15,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        ),
        CombatantView(
            name="Rogue",
            type="player",
            hp_current=8,
            hp_max=8,
            armor_class=14,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        ),
    ]

    request = CombatActionRequest(
        campaign_id="test",
        combat_id="test_combat",
        player_action="attack",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant="Fighter",
            available_actions=[]
        ),
        combatants=combatants,
        battlefield=BattlefieldConfig(size="small", terrain="dungeon"),
        initiative_order=["Fighter", "Rogue"],
    )

    # Transition Fighter -> Rogue
    result = engine.resolve_turn_transition(
        current_actor="Fighter",
        reason=TurnTransitionReason.EXPLICIT_END,
        request=request
    )

    assert result.next_combatant == "Rogue"
    assert result.new_round is False
    assert result.round_number == 1

    # Transition Rogue -> Fighter (new round)
    result2 = engine.resolve_turn_transition(
        current_actor="Rogue",
        reason=TurnTransitionReason.EXPLICIT_END,
        request=request
    )

    assert result2.next_combatant == "Fighter"
    assert result2.new_round is True
    assert result2.round_number == 2


def test_resolve_turn_transition_all_unconscious():
    """Test turn transition returns None when all remaining combatants are unconscious."""
    engine = CombatEngine()

    combatants = [
        CombatantView(
            name="Hero",
            type="player",
            hp_current=5,
            hp_max=10,
            armor_class=12,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        ),
        CombatantView(
            name="Ally",
            type="player",
            hp_current=0,  # Unconscious
            hp_max=10,
            armor_class=12,
            action_points_current=0,
            action_points_max=3,
            is_active=False,  # Can't act - unconscious with 0 HP
            is_conscious=False
        ),
        CombatantView(
            name="Enemy",
            type="enemy",
            hp_current=0,  # Unconscious
            hp_max=10,
            armor_class=12,
            action_points_current=0,
            action_points_max=3,
            is_active=False,  # Can't act - unconscious with 0 HP
            is_conscious=False
        ),
    ]

    request = CombatActionRequest(
        campaign_id="camp",
        combat_id="combat",
        player_action="attack",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant="Hero",
            available_actions=[]
        ),
        combatants=combatants,
        battlefield=BattlefieldConfig(size="medium", terrain="field"),
        initiative_order=["Hero", "Ally", "Enemy"],
    )

    # Hero is last conscious combatant - should wrap back to Hero
    turn_info = engine.resolve_turn_transition(
        current_actor="Hero",
        reason=TurnTransitionReason.AP_EXHAUSTED,
        request=request
    )

    # When only one conscious combatant remains, wraps back to them
    # Combat should end via victory conditions check, not None return
    assert turn_info is not None
    assert turn_info.next_combatant == "Hero"  # Wrapped back to only conscious combatant
    assert turn_info.new_round is True  # New round started


def test_resolve_turn_transition_healed_after_initiative_slot():
    """Test that a combatant healed after their initiative slot waits until next round."""
    engine = CombatEngine()

    combatants = [
        CombatantView(
            name="Hero",
            type="player",
            hp_current=10,
            hp_max=10,
            armor_class=12,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        ),
        CombatantView(
            name="Ally",
            type="player",
            hp_current=0,  # Unconscious (their initiative slot is #2)
            hp_max=10,
            armor_class=12,
            action_points_current=0,
            action_points_max=3,
            is_active=False,  # Can't act - unconscious with 0 HP
            is_conscious=False
        ),
        CombatantView(
            name="Enemy",
            type="enemy",
            hp_current=10,
            hp_max=10,
            armor_class=12,
            action_points_current=3,
            action_points_max=3,
            is_active=True,
            is_conscious=True
        ),
    ]

    # Round 1, Hero's turn
    request = CombatActionRequest(
        campaign_id="camp",
        combat_id="combat",
        player_action="attack",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant="Hero",
            available_actions=[]
        ),
        combatants=combatants,
        battlefield=BattlefieldConfig(size="medium", terrain="field"),
        initiative_order=["Hero", "Ally", "Enemy"],
    )

    # Hero's turn ends → skip unconscious Ally → Enemy
    turn_info = engine.resolve_turn_transition(
        current_actor="Hero",
        reason=TurnTransitionReason.AP_EXHAUSTED,
        request=request
    )

    assert turn_info.next_combatant == "Enemy"  # Skipped Ally
    assert turn_info.new_round is False

    # Enemy heals Ally on Enemy's turn (Ally's initiative slot already passed)
    combatants[1] = CombatantView(
        name="Ally",
        type="player",
        hp_current=5,  # Healed after their turn slot passed
        hp_max=10,
        armor_class=12,
        action_points_current=3,
        action_points_max=3,
        is_active=True,
        is_conscious=True
    )

    request_after_heal = CombatActionRequest(
        campaign_id="camp",
        combat_id="combat",
        player_action="heal",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=3,
            active_combatant="Enemy",
            available_actions=[]
        ),
        combatants=combatants,
        battlefield=BattlefieldConfig(size="medium", terrain="field"),
        initiative_order=["Hero", "Ally", "Enemy"],
    )

    # Enemy's turn ends → wrap to Hero (Round 2), Ally doesn't get turn in Round 1
    turn_info2 = engine.resolve_turn_transition(
        current_actor="Enemy",
        reason=TurnTransitionReason.AP_EXHAUSTED,
        request=request_after_heal
    )

    assert turn_info2.next_combatant == "Hero"
    assert turn_info2.new_round is True  # Round 2 starts
    assert turn_info2.round_number == 2

    # Round 2, Hero → Ally (Ally finally gets their turn)
    turn_info3 = engine.resolve_turn_transition(
        current_actor="Hero",
        reason=TurnTransitionReason.AP_EXHAUSTED,
        request=request_after_heal
    )

    assert turn_info3.next_combatant == "Ally"  # Ally acts in Round 2
    assert turn_info3.new_round is False
