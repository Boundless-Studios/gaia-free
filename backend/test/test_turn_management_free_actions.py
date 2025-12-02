"""Tests for turn management with free actions and simplified status.

This test suite validates:
1. Scene describer (free action) doesn't advance turn
2. Other agents (turn actions) advance turn
3. Turn status is ACTIVE or COMPLETED only
4. Non-combat turn tracking works correctly
"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaia.models.turn import Turn, TurnStatus, TurnType
from gaia_private.session.turn_manager import TurnManager, should_advance_turn
from gaia_private.orchestration.agent_types import AgentType


class TestFreeActionLogic:
    """Test that free actions don't advance turns."""

    def test_should_advance_turn_scene_describer(self):
        """Scene describer should NOT advance turn (free action)."""
        assert should_advance_turn("scene_describer") is False
        assert should_advance_turn(AgentType.SCENE_DESCRIBER.value_name) is False

    def test_should_advance_turn_other_agents(self):
        """All other agents SHOULD advance turn."""
        # Scene agents
        assert should_advance_turn("dialog") is True
        assert should_advance_turn("exploration") is True
        assert should_advance_turn("action") is True

        # DM and combat
        assert should_advance_turn("dungeon_master") is True
        assert should_advance_turn("encounter") is True
        assert should_advance_turn("combat_initiation") is True


class TestSimplifiedTurnStatus:
    """Test that turn status only has ACTIVE and COMPLETED."""

    def test_turn_status_enum_only_two_values(self):
        """TurnStatus should only have ACTIVE and COMPLETED."""
        status_values = [status.value for status in TurnStatus]
        assert "active" in status_values
        assert "completed" in status_values
        assert len(status_values) == 2

    def test_turn_status_no_pending(self):
        """PENDING should not exist in TurnStatus."""
        with pytest.raises(AttributeError):
            _ = TurnStatus.PENDING

    def test_turn_status_no_resolving(self):
        """RESOLVING should not exist in TurnStatus."""
        with pytest.raises(AttributeError):
            _ = TurnStatus.RESOLVING

    def test_turn_status_no_cancelled(self):
        """CANCELLED should not exist in TurnStatus."""
        with pytest.raises(AttributeError):
            _ = TurnStatus.CANCELLED

    def test_turn_starts_active(self):
        """New turns should start with ACTIVE status."""
        turn = Turn(
            turn_id="test_001",
            campaign_id="test_campaign",
            turn_number=1,
            character_id="pc:test_player"
        )
        assert turn.status == TurnStatus.ACTIVE

    def test_turn_complete_marks_completed(self):
        """Calling complete() should mark turn as COMPLETED."""
        turn = Turn(
            turn_id="test_002",
            campaign_id="test_campaign",
            turn_number=2,
            character_id="pc:test_player"
        )
        assert turn.status == TurnStatus.ACTIVE

        turn.complete()
        assert turn.status == TurnStatus.COMPLETED

    def test_turn_is_active_check(self):
        """is_active() should return True only for ACTIVE status."""
        turn = Turn(
            turn_id="test_003",
            campaign_id="test_campaign",
            turn_number=3,
            character_id="pc:test_player"
        )
        assert turn.is_active() is True

        turn.complete()
        assert turn.is_active() is False

    def test_turn_is_complete_check(self):
        """is_complete() should return True only for COMPLETED status."""
        turn = Turn(
            turn_id="test_004",
            campaign_id="test_campaign",
            turn_number=4,
            character_id="pc:test_player"
        )
        assert turn.is_complete() is False

        turn.complete()
        assert turn.is_complete() is True


class TestNonCombatTurnTracking:
    """Test non-combat turn order tracking."""

    def test_set_non_combat_order(self):
        """Should be able to set character order for a scene."""
        manager = TurnManager()
        scene_id = "tavern_001"
        characters = ["pc:alice", "pc:bob", "npc:bartender"]

        manager.set_non_combat_order(scene_id, characters)

        assert scene_id in manager.non_combat_order
        assert manager.non_combat_order[scene_id] == characters
        assert manager.non_combat_index[scene_id] == 0

    def test_get_current_character_non_combat(self):
        """Should get the current character in turn order."""
        manager = TurnManager()
        scene_id = "tavern_002"
        characters = ["pc:alice", "pc:bob", "npc:bartender"]

        manager.set_non_combat_order(scene_id, characters)

        current = manager.get_current_character_non_combat(scene_id)
        assert current == "pc:alice"

    def test_advance_non_combat_turn(self):
        """Should advance to next character in order."""
        manager = TurnManager()
        scene_id = "tavern_003"
        characters = ["pc:alice", "pc:bob", "npc:bartender"]

        manager.set_non_combat_order(scene_id, characters)

        # Start at alice (index 0)
        assert manager.get_current_character_non_combat(scene_id) == "pc:alice"

        # Advance to bob (index 1)
        next_char = manager.advance_non_combat_turn(scene_id)
        assert next_char == "pc:bob"
        assert manager.get_current_character_non_combat(scene_id) == "pc:bob"

        # Advance to bartender (index 2)
        next_char = manager.advance_non_combat_turn(scene_id)
        assert next_char == "npc:bartender"

        # Advance wraps back to alice (index 0)
        next_char = manager.advance_non_combat_turn(scene_id)
        assert next_char == "pc:alice"

    def test_non_combat_order_no_scene(self):
        """Should return None for scenes without order set."""
        manager = TurnManager()

        current = manager.get_current_character_non_combat("unknown_scene")
        assert current is None

        next_char = manager.advance_non_combat_turn("unknown_scene")
        assert next_char is None


class TestTurnManagerCreatesActiveStatus:
    """Test that TurnManager creates turns with ACTIVE status."""

    def test_create_turn_starts_active(self):
        """Created turns should have ACTIVE status."""
        manager = TurnManager()

        turn = manager.create_turn(
            campaign_id="test_campaign",
            character_id="pc:test_player",
            character_name="Test Player"
        )

        assert turn.status == TurnStatus.ACTIVE
        assert turn.is_active() is True
        assert turn.is_complete() is False


class TestAgentTypeEnum:
    """Test that SCENE_DESCRIBER exists in AgentType enum."""

    def test_scene_describer_exists(self):
        """SCENE_DESCRIBER should exist in AgentType enum."""
        assert hasattr(AgentType, 'SCENE_DESCRIBER')

    def test_scene_describer_value(self):
        """SCENE_DESCRIBER should have correct value."""
        assert AgentType.SCENE_DESCRIBER.value_name == "scene_describer"

    def test_scene_describer_in_valid_names(self):
        """scene_describer should be in valid agent names list."""
        valid_names = AgentType.get_valid_names()
        assert "scene_describer" in valid_names


class TestTurnTransitionWithNonCombat:
    """Test turn transition creates next turn for next character."""

    def test_handle_turn_transition_creates_next_turn(self):
        """handle_turn_transition should complete current turn and create next."""
        manager = TurnManager()

        # Create first turn for Alice
        turn_alice = manager.create_turn(
            campaign_id="test_campaign",
            character_id="pc:alice",
            character_name="Alice",
            scene_context={"scene_id": "tavern_001", "scene_type": "exploration"}
        )
        manager.start_turn(turn_alice)

        assert turn_alice.status == TurnStatus.ACTIVE

        # Transition to Bob
        turn_bob = manager.handle_turn_transition(
            current_turn=turn_alice,
            next_character_id="pc:bob",
            next_character_name="Bob",
            scene_context={"scene_id": "tavern_001", "scene_type": "exploration"}
        )

        # Alice's turn should be completed
        assert turn_alice.status == TurnStatus.COMPLETED
        assert turn_alice.next_turn_id == turn_bob.turn_id

        # Bob's turn should be active
        assert turn_bob.status == TurnStatus.ACTIVE
        assert turn_bob.previous_turn_id == turn_alice.turn_id
        assert turn_bob.character_id == "pc:bob"
        assert turn_bob.character_name == "Bob"
        assert turn_bob.turn_number == turn_alice.turn_number + 1

    def test_turn_transition_links_turns(self):
        """Turn transitions should properly link previous and next turns."""
        manager = TurnManager()

        turn1 = manager.create_turn(
            campaign_id="test_campaign",
            character_id="pc:alice",
            character_name="Alice"
        )
        manager.start_turn(turn1)

        turn2 = manager.handle_turn_transition(
            current_turn=turn1,
            next_character_id="pc:bob",
            next_character_name="Bob"
        )

        turn3 = manager.handle_turn_transition(
            current_turn=turn2,
            next_character_id="pc:charlie",
            next_character_name="Charlie"
        )

        # Verify chain
        assert turn1.next_turn_id == turn2.turn_id
        assert turn2.previous_turn_id == turn1.turn_id
        assert turn2.next_turn_id == turn3.turn_id
        assert turn3.previous_turn_id == turn2.turn_id


class TestNonCombatAdvancementIntegration:
    """Test non-combat turn advancement integrated with turn transition."""

    def test_advance_and_transition_full_cycle(self):
        """Test full cycle: set order, advance, create next turn."""
        manager = TurnManager()
        scene_id = "tavern_party"
        characters = ["pc:silas_grimwood", "pc:tink_gearspark"]

        # Set non-combat order
        manager.set_non_combat_order(scene_id, characters)

        # Create turn for first character (Silas)
        turn_silas = manager.create_turn(
            campaign_id="test_campaign",
            character_id="pc:silas_grimwood",
            character_name="Silas Grimwood",
            scene_context={"scene_id": scene_id, "scene_type": "exploration"}
        )
        manager.start_turn(turn_silas)

        # Advance to next character (should be Tink)
        next_character_id = manager.advance_non_combat_turn(scene_id)
        assert next_character_id == "pc:tink_gearspark"

        # Create next turn for Tink
        turn_tink = manager.handle_turn_transition(
            current_turn=turn_silas,
            next_character_id=next_character_id,
            next_character_name="Tink Gearspark",
            scene_context={"scene_id": scene_id, "scene_type": "exploration"}
        )

        # Verify transition
        assert turn_silas.status == TurnStatus.COMPLETED
        assert turn_tink.status == TurnStatus.ACTIVE
        assert turn_tink.character_id == "pc:tink_gearspark"

        # Advance again (should wrap to Silas)
        next_character_id = manager.advance_non_combat_turn(scene_id)
        assert next_character_id == "pc:silas_grimwood"

    def test_multiple_characters_wrap_around(self):
        """Test that advancing through multiple characters wraps correctly."""
        manager = TurnManager()
        scene_id = "market_square"
        characters = ["pc:alice", "pc:bob", "pc:charlie"]

        manager.set_non_combat_order(scene_id, characters)

        # Go through full cycle
        current_char = manager.get_current_character_non_combat(scene_id)
        assert current_char == "pc:alice"

        # Advance 3 times should wrap back to Alice
        manager.advance_non_combat_turn(scene_id)  # -> Bob
        manager.advance_non_combat_turn(scene_id)  # -> Charlie
        wrapped_char = manager.advance_non_combat_turn(scene_id)  # -> Alice

        assert wrapped_char == "pc:alice"
        assert manager.get_current_character_non_combat(scene_id) == "pc:alice"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
