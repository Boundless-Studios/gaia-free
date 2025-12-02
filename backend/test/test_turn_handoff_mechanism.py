"""Test the turn handoff mechanism for proper turn transitions."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gaia.models.turn import Turn, TurnStatus, TurnType
from gaia_private.session.turn_manager import TurnManager
from gaia_private.session.campaign_runner import CampaignRunner
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager


class TestTurnHandoff:
    """Test proper turn handoff between combatants."""

    @pytest.fixture
    def mock_campaign_manager(self):
        """Create a mock campaign manager."""
        from gaia.models.campaign import CampaignData

        manager = Mock(spec=SimpleCampaignManager)
        manager.get_next_turn_number.side_effect = [1, 2, 3, 4]  # Sequential turn numbers
        manager.save_turn.return_value = True

        # Create a proper CampaignData object for turn order management
        campaign_data = CampaignData(
            campaign_id="test_campaign",
            turn_order=[],  # Empty initially, will be set by tests
            current_turn_index=0
        )
        manager.load_campaign.return_value = campaign_data
        manager.save_campaign_data.return_value = True

        return manager

    @pytest.fixture
    def turn_manager(self, mock_campaign_manager):
        """Create a TurnManager with mocked dependencies."""
        return TurnManager(campaign_manager=mock_campaign_manager)

    def test_turn_transition_creates_linked_turns(self, turn_manager, mock_campaign_manager):
        """Test that turn transition properly links turns."""
        campaign_id = "test_campaign"

        # Create initial turn for Lyra
        lyra_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:lyra_the_swift",
            character_name="Lyra the Swift"
        )
        lyra_turn = turn_manager.start_turn(lyra_turn)

        assert lyra_turn.status == TurnStatus.ACTIVE
        assert lyra_turn.previous_turn_id is None
        assert lyra_turn.next_turn_id is None

        # Simulate turn transition to Marcus
        marcus_turn = turn_manager.handle_turn_transition(
            current_turn=lyra_turn,
            next_character_id="pc:marcus_the_gladiator",
            next_character_name="Marcus the Gladiator",
            scene_context={"scene_type": "combat"}
        )

        # Verify Lyra's turn is completed and linked to Marcus's turn
        assert lyra_turn.status == TurnStatus.COMPLETED
        assert lyra_turn.next_turn_id == marcus_turn.turn_id

        # Verify Marcus's turn is started and linked back to Lyra's turn
        assert marcus_turn.status == TurnStatus.ACTIVE
        assert marcus_turn.previous_turn_id == lyra_turn.turn_id
        assert marcus_turn.character_id == "pc:marcus_the_gladiator"
        assert marcus_turn.character_name == "Marcus the Gladiator"

        # Verify both turns were saved
        assert mock_campaign_manager.save_turn.call_count >= 2

    def test_turn_status_progression(self, turn_manager):
        """Test that turns progress through proper status phases."""
        campaign_id = "test_campaign"

        # Create and start turn (ACTIVE)
        turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:test_character",
            character_name="Test Character"
        )
        turn = turn_manager.start_turn(turn)
        assert turn.status == TurnStatus.ACTIVE

        # Complete turn (COMPLETED)
        turn = turn_manager.complete_turn(turn)
        assert turn.status == TurnStatus.COMPLETED

    def test_combat_action_includes_turn_id(self):
        """Test that combat actions include turn_id reference."""
        from gaia.models.combat.mechanics.combat_action_record import CombatActionRecord
        from datetime import datetime

        turn_id = "turn_0003_abc123"

        # Create action with turn_id
        action = CombatActionRecord(
            timestamp=datetime.now(),
            round_number=1,
            actor_id="lyra_the_swift",
            action_type="cast_simple_spell",
            target_id="marcus_the_gladiator",
            ap_cost=2,
            damage_dealt=2,
            success=True,
            turn_id=turn_id
        )

        # Verify turn_id is included in serialization
        action_dict = action.to_dict()
        assert action_dict["turn_id"] == turn_id

        # Verify deserialization preserves turn_id
        restored = CombatActionRecord.from_dict(action_dict)
        assert restored.turn_id == turn_id

    def test_campaign_runner_handles_turn_resolution(self, turn_manager):
        """Test that campaign runner properly handles turn resolution from combat."""
        # Create initial turn for Lyra
        lyra_turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="pc:lyra_the_swift",
            character_name="Lyra the Swift"
        )

        # Mock structured data with turn resolution
        structured_data = {
            "turn_resolution": {
                "next_combatant": "Marcus the Gladiator",
                "reason": "ap_exhausted"
            }
        }

        # Simulate the turn transition logic from campaign_runner
        if structured_data and "turn_resolution" in structured_data:
            turn_res = structured_data["turn_resolution"]
            if turn_res and "next_combatant" in turn_res:
                next_character_name = turn_res["next_combatant"]
                next_character_id = f"pc:{next_character_name.lower().replace(' ', '_')}"

                next_turn = turn_manager.handle_turn_transition(
                    current_turn=lyra_turn,
                    next_character_id=next_character_id,
                    next_character_name=next_character_name,
                    scene_context={"scene_type": "combat"}
                )

                # Verify the transition
                assert next_turn.character_name == "Marcus the Gladiator"
                assert next_turn.character_id == "pc:marcus_the_gladiator"
                assert next_turn.previous_turn_id == lyra_turn.turn_id
                assert lyra_turn.next_turn_id == next_turn.turn_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])