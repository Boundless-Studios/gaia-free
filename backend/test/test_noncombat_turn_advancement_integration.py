"""Integration test for non-combat turn advancement.

This test demonstrates the complete turn advancement system working end-to-end:
1. Scene initialization with pcs_present
2. Turn creation and character rotation
3. Agent selection determining turn advancement
4. Free actions (scene_describer) not advancing turns
5. No duplicate turns created
"""

import pytest
import sys
import os
from typing import Dict, Any
from datetime import datetime
from types import SimpleNamespace

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaia.models.turn import Turn, TurnStatus
from gaia_private.session.turn_manager import TurnManager, should_advance_turn
from gaia_private.session.scene.scene_integration import SceneIntegration
from gaia.models.scene_info import SceneInfo
from gaia_private.orchestration.agent_types import AgentType
from gaia_private.session.scene.scene_roster_manager import SceneRosterManager
from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia_private.session.campaign_runner import CampaignRunner


def generate_unique_scene_id(base: str) -> str:
    """Generate a unique scene ID with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{base}_{timestamp}"


class TestNonCombatTurnAdvancement:
    """Integration test for multi-character turn advancement in non-combat."""

    def test_full_turn_advancement_cycle_with_agent_selection(self):
        """Test complete turn advancement cycle with agent-based turn advancement.

        Scenario:
        - Scene with Silas and Tink (from actual campaign)
        - Turn 1: Silas acts, DM agent responds, turn advances to Tink
        - Turn 2: Tink acts, DM agent responds, turn advances to Silas (wrap)
        - Turn 3: Silas acts, scene_describer responds (free action), turn stays with Silas
        - Turn 4: Silas acts again, DM agent responds, turn advances to Tink
        """
        # Initialize components
        turn_manager = TurnManager()
        scene_integration = SceneIntegration(turn_manager=turn_manager)
        turn_manager.scene_integration = scene_integration

        # Use unique campaign ID to avoid conflicts with previous test runs
        campaign_id = f"test_campaign_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # Character names from actual campaign
        silas_id = "pc:silas_grimwood"
        silas_name = "Silas Grimwood"
        tink_id = "pc:tink_gearspark"
        tink_name = "Tink Gearspark"

        # Create scene with unique ID
        scene_id = generate_unique_scene_id("tavern_exploration")
        scene_info = SceneInfo(
            scene_id=scene_id,
            title="The Rusty Dragon Tavern",
            scene_type="exploration",
            location_id="rusty_dragon",
            location_description="A cozy tavern with warm lighting and wooden furnishings",
            description="A warm tavern filled with adventurers",
            pcs_present=["silas_grimwood", "tink_gearspark"],
            npcs_present=["bartender"]
        )

        # Initialize scene manager and set character order
        scene_manager = scene_integration.get_scene_manager(campaign_id)
        created_scene_id = scene_manager.create_scene(scene_info)

        # Set character order from scene's pcs_present
        character_ids = [f"pc:{pc}" for pc in scene_info.pcs_present]
        turn_manager.set_non_combat_order(created_scene_id, character_ids)

        scene_context = {
            "scene_id": created_scene_id,
            "scene_type": "exploration",
            "in_combat": False
        }

        # === TURN 1: Silas with DM agent (should advance) ===
        turn1 = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id=silas_id,
            character_name=silas_name,
            scene_context=scene_context
        )
        turn_manager.start_turn(turn1)

        assert turn1.status == TurnStatus.ACTIVE
        assert turn1.character_id == silas_id
        # Turn number may not be 1 if campaign has previous turns

        # DM agent responds - should advance turn
        agent_used = AgentType.DUNGEON_MASTER.value_name
        assert should_advance_turn(agent_used) is True

        # Advance to next character
        next_character_id = turn_manager.advance_non_combat_turn(created_scene_id)
        assert next_character_id == tink_id

        # Create next turn
        turn2 = turn_manager.handle_turn_transition(
            current_turn=turn1,
            next_character_id=next_character_id,
            next_character_name=tink_name,
            scene_context=scene_context
        )

        # Verify turn 1 completed
        assert turn1.status == TurnStatus.COMPLETED
        assert turn1.next_turn_id == turn2.turn_id

        # === TURN 2: Tink with DM agent (should advance and wrap) ===
        assert turn2.status == TurnStatus.ACTIVE
        assert turn2.character_id == tink_id
        assert turn2.character_name == tink_name
        assert turn2.turn_number == turn1.turn_number + 1  # Sequential turn numbers
        assert turn2.previous_turn_id == turn1.turn_id

        # DM agent responds - should advance turn
        agent_used = AgentType.DUNGEON_MASTER.value_name
        assert should_advance_turn(agent_used) is True

        # Advance (should wrap to Silas)
        next_character_id = turn_manager.advance_non_combat_turn(created_scene_id)
        assert next_character_id == silas_id

        # Create next turn
        turn3 = turn_manager.handle_turn_transition(
            current_turn=turn2,
            next_character_id=next_character_id,
            next_character_name=silas_name,
            scene_context=scene_context
        )

        # Verify turn 2 completed
        assert turn2.status == TurnStatus.COMPLETED
        assert turn2.next_turn_id == turn3.turn_id

        # === TURN 3: Silas with scene_describer (FREE ACTION - should NOT advance) ===
        assert turn3.status == TurnStatus.ACTIVE
        assert turn3.character_id == silas_id
        assert turn3.character_name == silas_name
        assert turn3.turn_number == turn2.turn_number + 1  # Sequential turn numbers

        # Scene describer responds - FREE ACTION, should NOT advance
        agent_used = AgentType.SCENE_DESCRIBER.value_name
        assert should_advance_turn(agent_used) is False

        # Turn should remain active
        assert turn3.status == TurnStatus.ACTIVE
        current_char = turn_manager.get_current_character_non_combat(created_scene_id)
        assert current_char == silas_id  # Still pointing to Silas (last advancement wrapped to Silas)

        # === TURN 4: Advance to next character after free action ===
        # After scene_describer (free action), DM acts and turn should advance
        agent_used = AgentType.DUNGEON_MASTER.value_name
        assert should_advance_turn(agent_used) is True

        # Now advance (should go to Tink)
        next_character_id = turn_manager.advance_non_combat_turn(created_scene_id)
        assert next_character_id == tink_id  # Advances to Tink

        turn4 = turn_manager.handle_turn_transition(
            current_turn=turn3,
            next_character_id=next_character_id,
            next_character_name=tink_name,
            scene_context=scene_context
        )

        # Verify turn 3 completed
        assert turn3.status == TurnStatus.COMPLETED
        assert turn3.next_turn_id == turn4.turn_id

        # Verify turn 4 is active
        assert turn4.status == TurnStatus.ACTIVE
        assert turn4.turn_number == turn3.turn_number + 1  # Sequential turn numbers

        # === Verify no duplicates ===
        # All turns should have unique IDs
        turn_ids = {turn1.turn_id, turn2.turn_id, turn3.turn_id, turn4.turn_id}
        assert len(turn_ids) == 4  # All unique

        # Verify turn numbers are sequential (regardless of starting number)
        assert turn2.turn_number == turn1.turn_number + 1
        assert turn3.turn_number == turn2.turn_number + 1
        assert turn4.turn_number == turn3.turn_number + 1


    def test_no_duplicate_turns_created(self):
        """Verify that checking for existing active turn prevents duplicates."""
        turn_manager = TurnManager()
        campaign_id = "test_no_duplicates"

        # Create and start turn 1
        turn1 = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:alice",
            character_name="Alice"
        )
        turn_manager.start_turn(turn1)

        # Get current turn - should return turn1
        current = turn_manager.get_current_turn(campaign_id)
        assert current is not None
        assert current.turn_id == turn1.turn_id
        assert current.status == TurnStatus.ACTIVE

        # Try to get current again - should still be turn1, not a new turn
        current2 = turn_manager.get_current_turn(campaign_id)
        assert current2.turn_id == turn1.turn_id

        # Complete turn1
        turn_manager.complete_turn(turn1)

        # Now get_current_turn should return None (no active turn)
        current_after = turn_manager.get_current_turn(campaign_id)
        assert current_after is None

    def test_scene_character_order_initialization(self):
        """Test that character order is properly initialized from scene's pcs_present."""
        scene_integration = SceneIntegration(turn_manager=TurnManager())
        campaign_id = "test_scene_init"

        # Create scene with specific character order and unique ID
        test_scene_id = generate_unique_scene_id("test_scene")
        scene_info = SceneInfo(
            scene_id=test_scene_id,
            title="Test Scene",
            scene_type="exploration",
            location_id="test_location",
            location_description="A generic test location",
            description="A test location",
            pcs_present=["silas_grimwood", "tink_gearspark", "lyra_moonwhisper"],
            npcs_present=[]
        )

        scene_manager = scene_integration.get_scene_manager(campaign_id)
        scene_id = scene_manager.create_scene(scene_info)

        # Manually initialize character order (simulating what scene_integration does)
        turn_manager = TurnManager()
        character_ids = [f"pc:{pc}" for pc in scene_info.pcs_present]
        turn_manager.set_non_combat_order(scene_id, character_ids)

        # Verify order is correct
        assert turn_manager.get_current_character_non_combat(scene_id) == "pc:silas_grimwood"

        turn_manager.advance_non_combat_turn(scene_id)
        assert turn_manager.get_current_character_non_combat(scene_id) == "pc:tink_gearspark"

        turn_manager.advance_non_combat_turn(scene_id)
        assert turn_manager.get_current_character_non_combat(scene_id) == "pc:lyra_moonwhisper"

        # Wrap around
        turn_manager.advance_non_combat_turn(scene_id)
        assert turn_manager.get_current_character_non_combat(scene_id) == "pc:silas_grimwood"

    def test_agent_types_turn_advancement_rules(self):
        """Verify which agents advance turns and which are free actions."""
        # Free actions (do NOT advance turn)
        free_action_agents = [
            AgentType.SCENE_DESCRIBER.value_name
        ]

        for agent in free_action_agents:
            assert should_advance_turn(agent) is False, f"{agent} should be a free action"

        # Turn-advancing actions
        advancing_agents = [
            AgentType.DUNGEON_MASTER.value_name,
            "exploration",
            "dialog",
            "action",
            "encounter",
            "combat_initiation"
        ]

        for agent in advancing_agents:
            assert should_advance_turn(agent) is True, f"{agent} should advance turn"


class _StubCharacterManager:
    """Lightweight character manager stub for non-combat tests."""

    def __init__(self, characters):
        self.characters = {c.character_id: c for c in characters}
        self._players = [
            c for c in characters if getattr(c, "character_type", "player") == "player"
        ]

    def get_player_characters(self):
        return list(self._players)

    def get_character(self, character_id: str):
        return self.characters.get(character_id)

    def get_character_by_name(self, name: str):
        lowered = name.lower()
        for character in self.characters.values():
            if character.name.lower() == lowered:
                return character
        return None


class _DummyCombatStateManager:
    """Stub combat state manager that disables combat-specific resolution."""

    def get_active_combat(self, campaign_id: str):
        return None


class TestNonCombatCharacterAssignment:
    """Non-combat regression tests for character selection and roster wiring."""

    def test_resolve_acting_character_without_scene_defaults_to_first_player(self):
        """New campaigns with no current scene still assign a player turn."""
        althea = CharacterInfo(
            character_id="pc:althea_storm",
            name="Althea Storm",
            character_class="Wizard",
        )
        brander = CharacterInfo(
            character_id="pc:brander_ironheart",
            name="Brander Ironheart",
            character_class="Fighter",
        )
        character_manager = _StubCharacterManager([althea, brander])

        runner = CampaignRunner.__new__(CampaignRunner)
        runner.combat_state_manager = _DummyCombatStateManager()
        runner.scene_integration = SimpleNamespace(current_scenes={})
        runner.character_manager = character_manager

        character_id, character_name = CampaignRunner._resolve_acting_character(
            runner, user_input="Look around", campaign_id="campaign_new"
        )

        assert character_id == "pc:althea_storm"
        assert character_name == "Althea Storm"

    def test_scene_roster_bootstrap_links_new_npc_to_character_manager(self):
        """DM-introduced NPCs during scene creation retain their character IDs."""
        hero = CharacterInfo(
            character_id="pc:althea_storm",
            name="Althea Storm",
            character_class="Wizard",
        )
        npc = CharacterInfo(
            character_id="npc:theron_the_mystic",
            name="Theron the Mystic",
            character_class="Wizard",
            character_type="npc",
            character_role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE,
        )
        character_manager = _StubCharacterManager([hero, npc])

        scene_info = SceneInfo(
            scene_id="scene_001",
            title="Mystic Archive",
            description="Shelves of ancient tomes line the walls.",
            location_id="mystic_archive",
            location_description="Dusty library infused with arcane energy.",
            scene_type="exploration",
            pcs_present=[],
            npcs_present=["Theron the Mystic"],
        )

        roster_manager = SceneRosterManager(
            campaign_id="campaign_new",
            character_manager=character_manager,
        )

        roster_manager.bootstrap_scene(scene_info)

        npc_participants = [
            participant
            for participant in scene_info.participants
            if participant.display_name == "Theron the Mystic"
        ]

        assert scene_info.pcs_present == ["pc:althea_storm"]
        assert npc_participants, "Expected Theron the Mystic to be added to participants"
        assert npc_participants[0].character_id == "npc:theron_the_mystic"
        assert npc_participants[0].role != CharacterRole.PLAYER
        assert scene_info.npcs_present == ["npc:theron_the_mystic"]


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
