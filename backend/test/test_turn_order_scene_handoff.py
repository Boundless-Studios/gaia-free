"""Test turn order persistence across scene transitions.

This test suite validates that:
1. Turn order is stored at campaign level, not scene level
2. Scenes load turn order from campaign
3. Turn advancement happens when turn completes BEFORE scene transition
4. New characters are appended to existing turn order
5. Turn order persists correctly across scene boundaries
"""

import pytest
from datetime import datetime
from gaia_private.session.turn_manager import TurnManager
from gaia.models.turn import TurnStatus
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager


class TestCampaignLevelTurnOrder:
    """Test that turn order is stored and managed at campaign level."""

    @pytest.fixture
    def campaign_id(self):
        return "test_campaign_turn_order"

    @pytest.fixture
    def campaign_manager(self):
        """Create campaign manager for testing."""
        return SimpleCampaignManager()

    @pytest.fixture
    def turn_manager(self, campaign_manager):
        """Create turn manager with campaign manager."""
        return TurnManager(campaign_manager)

    def test_turn_order_stored_in_campaign_data(self, campaign_id, campaign_manager, turn_manager):
        """Turn order should be stored in campaign_data, not scene."""
        # ARRANGE: Create campaign
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")

        # ACT: Set turn order at campaign level
        turn_order = ["pc:alice", "pc:bob", "pc:charlie"]
        turn_manager.set_campaign_turn_order(campaign_id, turn_order)

        # ASSERT: Turn order stored in campaign
        campaign_data = campaign_manager.load_campaign(campaign_id)
        assert hasattr(campaign_data, 'turn_order')
        assert campaign_data.turn_order == turn_order
        assert campaign_data.current_turn_index == 0

    def test_scenes_load_turn_order_from_campaign(self, campaign_id, campaign_manager, turn_manager):
        """Scenes should reference campaign turn order, not store their own."""
        # ARRANGE: Campaign with turn order
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_order = ["pc:alice", "pc:bob"]
        turn_manager.set_campaign_turn_order(campaign_id, turn_order)

        # ACT: Get current character for scene (should load from campaign)
        scene_id = "scene_001_tavern"
        current_char = turn_manager.get_current_character(campaign_id)

        # ASSERT: Returns character from campaign turn order
        assert current_char == "pc:alice"

        # Scene should NOT have its own turn order
        assert scene_id not in turn_manager.non_combat_order

    def test_turn_order_persists_across_campaigns(self, campaign_manager, turn_manager):
        """Each campaign should have independent turn order."""
        # ARRANGE: Two campaigns
        campaign_1 = "campaign_001"
        campaign_2 = "campaign_002"

        campaign_manager.save_campaign(campaign_1, [], name="Campaign 1")
        campaign_manager.save_campaign(campaign_2, [], name="Campaign 2")

        # ACT: Set different turn orders
        turn_manager.set_campaign_turn_order(campaign_1, ["pc:alice", "pc:bob"])
        turn_manager.set_campaign_turn_order(campaign_2, ["pc:charlie", "pc:dave"])

        # ASSERT: Each campaign maintains separate turn order
        assert turn_manager.get_current_character(campaign_1) == "pc:alice"
        assert turn_manager.get_current_character(campaign_2) == "pc:charlie"


class TestTurnAdvancementOnSceneTransition:
    """Test that turns advance correctly when scene transitions occur."""

    @pytest.fixture
    def campaign_id(self):
        return "test_campaign_advancement"

    @pytest.fixture
    def campaign_manager(self):
        return SimpleCampaignManager()

    @pytest.fixture
    def turn_manager(self, campaign_manager):
        return TurnManager(campaign_manager)

    def test_turn_advances_before_scene_transition(self, campaign_id, campaign_manager, turn_manager):
        """When Bob's turn ends and scene transitions, turn should advance to next character."""
        # ARRANGE: Campaign with Alice and Bob
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice", "pc:bob"])

        # Alice takes her turn in Scene A
        scene_a = "scene_001_tavern"
        alice_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:alice",
            character_name="Alice",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(alice_turn)

        # Alice's turn completes - should advance to Bob
        turn_manager.complete_turn(alice_turn)

        # Verify advancement happened
        current_char = turn_manager.get_current_character(campaign_id)
        assert current_char == "pc:bob"

        # ACT: Bob takes his turn and it completes before scene transition
        bob_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:bob",
            character_name="Bob",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(bob_turn)
        turn_manager.complete_turn(bob_turn)

        # ASSERT: Turn should have advanced (would wrap to Alice since no new chars)
        current_char = turn_manager.get_current_character(campaign_id)
        assert current_char == "pc:alice"  # Wrapped around

    def test_new_character_joins_gets_next_turn(self, campaign_id, campaign_manager, turn_manager):
        """When new character joins after current turn completes, they get the next turn."""
        # ARRANGE: Campaign with Alice and Bob
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice", "pc:bob"])

        # Alice's turn
        scene_a = "scene_001_tavern"
        alice_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:alice",
            character_name="Alice",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(alice_turn)
        turn_manager.complete_turn(alice_turn)

        # Bob's turn
        bob_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:bob",
            character_name="Bob",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(bob_turn)

        # ACT: Scene transition - Charlie joins BEFORE Bob's turn completes
        scene_b = "scene_002_forest"
        turn_manager.add_characters_to_campaign(campaign_id, ["pc:charlie"])

        # Bob's turn completes
        turn_manager.complete_turn(bob_turn)

        # ASSERT: Charlie should be next (was appended, and turn advanced from Bob -> Charlie)
        current_char = turn_manager.get_current_character(campaign_id)
        assert current_char == "pc:charlie"

        # Verify turn order is correct
        campaign_data = campaign_manager.load_campaign(campaign_id)
        assert campaign_data.turn_order == ["pc:alice", "pc:bob", "pc:charlie"]

    def test_turn_wraps_on_scene_transition_without_new_chars(self, campaign_id, campaign_manager, turn_manager):
        """When last character's turn ends and scene transitions, wrap to first."""
        # ARRANGE: Campaign with Alice and Bob, Bob is last
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice", "pc:bob"])

        # Alice's turn
        scene_a = "scene_001_tavern"
        alice_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:alice",
            character_name="Alice",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(alice_turn)
        turn_manager.complete_turn(alice_turn)

        # Bob's turn (last in order)
        bob_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:bob",
            character_name="Bob",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(bob_turn)

        # ACT: Scene transitions, Bob's turn completes (no new characters)
        scene_b = "scene_002_forest"
        turn_manager.complete_turn(bob_turn)

        # ASSERT: Should wrap to Alice (index 2 -> 0)
        current_char = turn_manager.get_current_character(campaign_id)
        assert current_char == "pc:alice"

        campaign_data = campaign_manager.load_campaign(campaign_id)
        assert campaign_data.current_turn_index == 0

    def test_multiple_characters_join_appended_in_order(self, campaign_id, campaign_manager, turn_manager):
        """Multiple new characters should be appended in the order they join."""
        # ARRANGE: Campaign with Alice
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice"])

        # ACT: Add Bob then Charlie
        turn_manager.add_characters_to_campaign(campaign_id, ["pc:bob", "pc:charlie"])

        # ASSERT: Order is Alice, Bob, Charlie
        campaign_data = campaign_manager.load_campaign(campaign_id)
        assert campaign_data.turn_order == ["pc:alice", "pc:bob", "pc:charlie"]


class TestCharacterDepartureHandling:
    """Test handling of characters leaving the campaign."""

    @pytest.fixture
    def campaign_id(self):
        return "test_campaign_departure"

    @pytest.fixture
    def campaign_manager(self):
        return SimpleCampaignManager()

    @pytest.fixture
    def turn_manager(self, campaign_manager):
        return TurnManager(campaign_manager)

    def test_character_departure_removes_from_turn_order(self, campaign_id, campaign_manager, turn_manager):
        """When a character leaves, they should be removed from turn order."""
        # ARRANGE: Campaign with 3 characters, Bob is current
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice", "pc:bob", "pc:charlie"])

        # Advance to Bob
        turn_manager.advance_campaign_turn(campaign_id)
        assert turn_manager.get_current_character(campaign_id) == "pc:bob"

        # ACT: Bob leaves
        turn_manager.remove_characters_from_campaign(campaign_id, ["pc:bob"])

        # ASSERT: Bob removed from turn order
        campaign_data = campaign_manager.load_campaign(campaign_id)
        assert campaign_data.turn_order == ["pc:alice", "pc:charlie"]

        # Current index should adjust to stay valid (was 1, now should point to Charlie at index 1)
        assert turn_manager.get_current_character(campaign_id) == "pc:charlie"

    def test_current_character_departs_advances_turn(self, campaign_id, campaign_manager, turn_manager):
        """If current character departs mid-turn, advance to next."""
        # ARRANGE: Campaign with Alice, Bob, Charlie - Bob is current
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice", "pc:bob", "pc:charlie"])
        turn_manager.advance_campaign_turn(campaign_id)  # Alice -> Bob

        # ACT: Bob departs during his turn
        turn_manager.remove_characters_from_campaign(campaign_id, ["pc:bob"])

        # ASSERT: Turn advances to Charlie
        current_char = turn_manager.get_current_character(campaign_id)
        assert current_char == "pc:charlie"


class TestSceneTransitionIntegration:
    """Integration tests for complete scene transition flow."""

    @pytest.fixture
    def campaign_id(self):
        return "test_campaign_integration"

    @pytest.fixture
    def campaign_manager(self):
        return SimpleCampaignManager()

    @pytest.fixture
    def turn_manager(self, campaign_manager):
        return TurnManager(campaign_manager)

    def test_full_scene_transition_with_character_addition(self, campaign_id, campaign_manager, turn_manager):
        """Complete flow: Scene A -> Bob's turn ends -> Scene B with Charlie -> Charlie's turn."""
        # ARRANGE: Scene A with Alice and Bob
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice", "pc:bob"])

        scene_a = "scene_001_tavern"

        # Turn 1: Alice
        alice_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:alice",
            character_name="Alice",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(alice_turn)
        turn_manager.complete_turn(alice_turn)

        assert turn_manager.get_current_character(campaign_id) == "pc:bob"

        # Turn 2: Bob
        bob_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:bob",
            character_name="Bob",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(bob_turn)

        # ACT: Scene transition - Charlie joins before Bob's turn ends
        scene_b = "scene_002_forest"
        turn_manager.add_characters_to_campaign(campaign_id, ["pc:charlie"])

        # Bob's turn completes
        turn_manager.complete_turn(bob_turn)

        # ASSERT: Next turn should be Charlie's
        current_char = turn_manager.get_current_character(campaign_id)
        assert current_char == "pc:charlie"

        # Create Charlie's turn in new scene
        charlie_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:charlie",
            character_name="Charlie",
            scene_context={"scene_id": scene_b, "scene_type": "exploration", "in_combat": False}
        )
        assert charlie_turn.character_id == "pc:charlie"
        assert charlie_turn.scene_id == scene_b

        # Verify campaign state
        campaign_data = campaign_manager.load_campaign(campaign_id)
        assert campaign_data.turn_order == ["pc:alice", "pc:bob", "pc:charlie"]
        assert campaign_data.current_turn_index == 2  # Charlie

    def test_scene_transition_preserves_turn_order_without_changes(self, campaign_id, campaign_manager, turn_manager):
        """Scene transition with no character changes preserves turn order exactly."""
        # ARRANGE: Scene A with Alice, Bob, Charlie
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice", "pc:bob", "pc:charlie"])

        scene_a = "scene_001_tavern"

        # Alice's turn
        alice_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:alice",
            character_name="Alice",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(alice_turn)
        turn_manager.complete_turn(alice_turn)

        # Bob's turn
        bob_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:bob",
            character_name="Bob",
            scene_context={"scene_id": scene_a, "scene_type": "social", "in_combat": False}
        )
        turn_manager.start_turn(bob_turn)

        # ACT: Scene transition with same characters
        scene_b = "scene_002_forest"
        turn_manager.complete_turn(bob_turn)

        # ASSERT: Turn advances to Charlie (no changes to turn order)
        current_char = turn_manager.get_current_character(campaign_id)
        assert current_char == "pc:charlie"

        campaign_data = campaign_manager.load_campaign(campaign_id)
        assert campaign_data.turn_order == ["pc:alice", "pc:bob", "pc:charlie"]
        assert campaign_data.current_turn_index == 2


class TestEdgeCases:
    """Test edge cases in turn order management."""

    @pytest.fixture
    def campaign_id(self):
        return "test_campaign_edge"

    @pytest.fixture
    def campaign_manager(self):
        return SimpleCampaignManager()

    @pytest.fixture
    def turn_manager(self, campaign_manager):
        return TurnManager(campaign_manager)

    def test_empty_turn_order_handled_gracefully(self, campaign_id, campaign_manager, turn_manager):
        """Empty turn order should be handled without crashing."""
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, [])

        assert turn_manager.get_current_character(campaign_id) is None

    def test_single_character_wraps_to_self(self, campaign_id, campaign_manager, turn_manager):
        """Single character should wrap to themselves."""
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:solo"])

        assert turn_manager.get_current_character(campaign_id) == "pc:solo"

        # Advance - should wrap to same character
        turn_manager.advance_campaign_turn(campaign_id)
        assert turn_manager.get_current_character(campaign_id) == "pc:solo"

    def test_duplicate_character_prevented(self, campaign_id, campaign_manager, turn_manager):
        """Adding duplicate character should be prevented."""
        campaign_manager.save_campaign(campaign_id, [], name="Test Campaign")
        turn_manager.set_campaign_turn_order(campaign_id, ["pc:alice", "pc:bob"])

        # Try to add Alice again
        turn_manager.add_characters_to_campaign(campaign_id, ["pc:alice"])

        # Should still only have 2 characters
        campaign_data = campaign_manager.load_campaign(campaign_id)
        assert campaign_data.turn_order == ["pc:alice", "pc:bob"]
