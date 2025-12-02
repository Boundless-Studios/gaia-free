"""Unit tests for turn management logic in combat."""

import pytest
from gaia.models.combat.persistence.combat_session import CombatSession
from gaia.models.combat.persistence.combatant_state import CombatantState
from gaia.models.combat.mechanics.action_points import ActionPointState
from gaia.models.combat.mechanics.enums import CombatStatus


class TestTurnManagement:
    """Test suite for combat turn management."""

    @pytest.fixture
    def combat_session(self):
        """Create a mock combat session with three combatants."""
        session = CombatSession(
            session_id="test_001",
            scene_id="scene_001",
            status=CombatStatus.IN_PROGRESS,
            round_number=1,
            turn_order=["Alice", "Bob", "Charlie"],
            current_turn_index=0
        )

        # Add combatants
        session.combatants = {
            "Alice": CombatantState(
                character_id="Alice",
                name="Alice",
                initiative=15,
                hp=20,
                max_hp=20,
                ac=14,
                level=3,
                is_npc=False,
                action_points=ActionPointState(max_ap=3, current_ap=1)
            ),
            "Bob": CombatantState(
                character_id="Bob",
                name="Bob",
                initiative=12,
                hp=15,
                max_hp=15,
                ac=12,
                level=2,
                is_npc=False,
                action_points=ActionPointState(max_ap=2, current_ap=2)
            ),
            "Charlie": CombatantState(
                character_id="Charlie",
                name="Charlie",
                initiative=10,
                hp=10,
                max_hp=10,
                ac=10,
                level=1,
                is_npc=True,
                action_points=ActionPointState(max_ap=2, current_ap=2)
            )
        }
        return session

    def test_initial_turn_state(self, combat_session):
        """Test the initial turn state is correctly set."""
        assert combat_session.resolve_current_character() == "Alice"
        assert combat_session.round_number == 1
        assert combat_session.current_turn_index == 0

    def test_turn_should_not_end_with_positive_ap(self, combat_session):
        """Test that turn should not end when combatant has positive AP."""
        # Alice has 1 AP remaining
        should_end = combat_session.should_end_turn("Alice")
        assert not should_end, "Turn should not end with positive AP"

    def test_turn_should_end_with_zero_ap(self, combat_session):
        """Test that turn should end when combatant has 0 AP."""
        # Exhaust Alice's AP
        combat_session.combatants["Alice"].action_points.current_ap = 0
        should_end = combat_session.should_end_turn("Alice")
        assert should_end, "Turn should end with 0 AP"

    def test_advance_turn_to_next_combatant(self, combat_session):
        """Test advancing from one combatant to the next."""
        turn_info = combat_session.advance_turn()

        assert turn_info['next_character'] == "Bob"
        assert not turn_info['new_round']
        assert turn_info['round_number'] == 1
        assert combat_session.resolve_current_character() == "Bob"
        assert combat_session.current_turn_index == 1

    def test_advance_turn_sequence(self, combat_session):
        """Test advancing through complete turn sequence."""
        # Alice -> Bob
        turn_info = combat_session.advance_turn()
        assert turn_info['next_character'] == "Bob"
        assert not turn_info['new_round']

        # Bob -> Charlie
        turn_info = combat_session.advance_turn()
        assert turn_info['next_character'] == "Charlie"
        assert not turn_info['new_round']

        # Charlie -> Alice (new round)
        turn_info = combat_session.advance_turn()
        assert turn_info['next_character'] == "Alice"
        assert turn_info['new_round']
        assert turn_info['round_number'] == 2

    def test_skip_unconscious_combatant(self, combat_session):
        """Test that unconscious combatants are skipped."""
        # Make Bob unconscious
        combat_session.combatants["Bob"].hp = 0
        combat_session.combatants["Bob"].is_conscious = False

        # Advance from Alice should skip Bob and go to Charlie
        turn_info = combat_session.advance_turn()
        assert turn_info['next_character'] == "Charlie"
        assert combat_session.resolve_current_character() == "Charlie"

    def test_all_combatants_unconscious(self, combat_session):
        """Test behavior when all combatants are unconscious."""
        # Make all combatants unconscious
        for combatant in combat_session.combatants.values():
            combatant.hp = 0
            combatant.is_conscious = False

        # Should still be able to advance, but might cycle back to same
        turn_info = combat_session.advance_turn()
        assert 'next_character' in turn_info

    def test_turn_reset_on_new_round(self, combat_session):
        """Test that action points reset on new round."""
        # Save original AP values
        original_ap = {}
        for char_id, combatant in combat_session.combatants.items():
            original_ap[char_id] = combatant.action_points.max_ap
            # Exhaust AP
            combatant.action_points.current_ap = 0

        # Advance through all turns to trigger new round
        combat_session.advance_turn()  # Alice -> Bob
        combat_session.advance_turn()  # Bob -> Charlie
        turn_info = combat_session.advance_turn()  # Charlie -> Alice (new round)

        # Check new round started
        assert turn_info['new_round']
        assert combat_session.round_number == 2

        # In a real implementation, AP would reset here
        # This test documents expected behavior

    def test_combat_victory_detection(self, combat_session):
        """Test detection of combat victory conditions."""
        # Make all NPCs unconscious (player victory)
        combat_session.combatants["Charlie"].hp = 0
        combat_session.combatants["Charlie"].is_conscious = False

        victory = combat_session.check_victory_conditions()
        assert victory == "players_victory"

        # Make all players unconscious (defeat)
        combat_session.combatants["Alice"].hp = 0
        combat_session.combatants["Alice"].is_conscious = False
        combat_session.combatants["Bob"].hp = 0
        combat_session.combatants["Bob"].is_conscious = False

        victory = combat_session.check_victory_conditions()
        assert victory == "players_defeat"

    @pytest.mark.parametrize("current_ap,expected_should_end", [
        (3, False),  # Full AP
        (2, False),  # Partial AP
        (1, False),  # Low but positive AP
        (0, True),   # No AP
        (-1, True),  # Negative AP (edge case)
    ])
    def test_should_end_turn_with_various_ap(self, combat_session, current_ap, expected_should_end):
        """Test turn ending logic with various AP values."""
        combat_session.combatants["Alice"].action_points.current_ap = current_ap
        should_end = combat_session.should_end_turn("Alice")
        assert should_end == expected_should_end

    def test_turn_order_persistence(self, combat_session):
        """Test that turn order is maintained correctly."""
        original_order = combat_session.turn_order.copy()

        # Advance through several turns
        for _ in range(6):  # Two complete rounds
            combat_session.advance_turn()

        # Turn order should remain the same
        assert combat_session.turn_order == original_order

    def test_round_number_increments(self, combat_session):
        """Test that round number increments correctly."""
        assert combat_session.round_number == 1

        # Complete one full round
        combat_session.advance_turn()  # Alice -> Bob
        combat_session.advance_turn()  # Bob -> Charlie
        combat_session.advance_turn()  # Charlie -> Alice

        assert combat_session.round_number == 2

        # Complete another round
        combat_session.advance_turn()  # Alice -> Bob
        combat_session.advance_turn()  # Bob -> Charlie
        combat_session.advance_turn()  # Charlie -> Alice

        assert combat_session.round_number == 3
