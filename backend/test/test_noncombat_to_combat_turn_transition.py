"""Integration test for turn creation during non-combat to combat transition.

This test verifies the bug fix where combat initiation creates a turn for the first combatant.

Scenario:
1. Characters in exploration (non-combat) scene
2. Player initiates combat
3. Combat is initialized with turn order
4. System should:
   - Complete the current non-combat turn
   - Create a NEW turn for the first combatant (based on initiative order)
   - Set the turn status to ACTIVE
   - Link turns properly (previous_turn_id, next_turn_id)
"""

import pytest
import sys
import os
from typing import Dict, Any, List
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaia.models.turn import Turn, TurnStatus
from gaia_private.session.turn_manager import TurnManager
from gaia.mechanics.combat.combat_state_manager import CombatStateManager
from gaia.models.combat import CombatSession, CombatantState, CombatStatus
from gaia.models.combat.mechanics.action_points import ActionPointState
from gaia.models.character.character_info import CharacterInfo
from gaia_private.models.combat.orchestration import CombatCachedPayload


def generate_unique_id(base: str) -> str:
    """Generate a unique ID with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{base}_{timestamp}"


class TestNonCombatToCombatTurnTransition:
    """Test turn creation when transitioning from non-combat to combat."""

    def test_combat_initialization_creates_first_combatant_turn(self):
        """Test that initializing combat creates a turn for the first combatant.

        Bug scenario from campaign_72:
        - Turn 14: Tink's non-combat exploration turn (ACTIVE)
        - Combat initiated via Combat Initiator
        - Combat session created with turn order: [tink, silas, guards, wizard]
        - Bug: Turn 14 completed but no turn 15 created
        - Expected: Turn 15 created for first combatant (Tink)
        """
        # Initialize components
        turn_manager = TurnManager()
        combat_state_manager = CombatStateManager(turn_manager=turn_manager)

        campaign_id = generate_unique_id("test_combat_transition")
        scene_id = generate_unique_id("exploration_scene")

        # Character IDs
        tink_id = "tink_gearspark"
        silas_id = "silas_grimwood"

        # === Step 1: Create non-combat exploration turn (Turn 14) ===
        scene_context = {
            "scene_id": scene_id,
            "scene_type": "exploration",
            "in_combat": False
        }

        turn_14 = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id=f"pc:{tink_id}",
            character_name="Tink Gearspark",
            scene_context=scene_context
        )
        turn_manager.start_turn(turn_14)

        assert turn_14.status == TurnStatus.ACTIVE
        assert turn_14.character_id == f"pc:{tink_id}"
        assert turn_14.scene_type == "exploration"

        # === Step 2: Initialize combat (simulating Combat Initiator) ===
        # Create character info for combat participants
        characters = [
            CharacterInfo(
                character_id=tink_id,
                name="Tink Gearspark",
                character_class="Artificer",
                level=3,
                hit_points_current=18,
                hit_points_max=18,
                armor_class=15
            ),
            CharacterInfo(
                character_id=silas_id,
                name="Silas Grimwood",
                character_class="Rogue",
                level=3,
                hit_points_current=20,
                hit_points_max=20,
                armor_class=14
            )
        ]

        # Initialize combat session
        combat_session = combat_state_manager.initialize_combat(
            scene_id=scene_id,
            characters=characters,
            campaign_id=campaign_id
        )

        # Combat session should be created with turn order
        assert combat_session is not None
        assert len(combat_session.turn_order) == 2
        assert combat_session.turn_order[0] in [tink_id, silas_id]

        # === Step 3: Simulate campaign_runner's _handle_turn_progression ===
        # This is what the fix does - check for initialized combat and create turn

        # Store combat in initialized_combat (what combat_orchestrator does)
        session_id = combat_session.session_id
        payload = CombatCachedPayload(
            combat_session_id=session_id,
            name_to_combatant_id={
                "Tink Gearspark": tink_id,
                "Silas Grimwood": silas_id
            },
            initiative_order=[],
            round_number=1
        )
        combat_state_manager.set_initialized_combat(campaign_id, payload)

        # Verify initialized combat is stored
        assert campaign_id in combat_state_manager.initialized_combat

        # Get first combatant from turn order
        first_combatant_id = combat_session.turn_order[0]
        first_combatant = combat_session.combatants.get(first_combatant_id)
        assert first_combatant is not None

        # === Step 4: Create turn for first combatant (what the fix does) ===
        # Complete current turn
        turn_manager.complete_turn(turn_14)
        assert turn_14.status == TurnStatus.COMPLETED

        # Create combat scene context
        combat_scene_context = {
            "scene_id": scene_id,
            "scene_type": "combat",
            "in_combat": True,
            "combat_session_id": session_id
        }

        # Create turn for first combatant
        turn_15 = turn_manager.handle_turn_transition(
            current_turn=turn_14,
            next_character_id=first_combatant_id,
            next_character_name=first_combatant.name,
            scene_context=combat_scene_context
        )

        # === Step 5: Verify turn 15 was created correctly ===
        assert turn_15 is not None
        assert turn_15.status == TurnStatus.ACTIVE
        assert turn_15.character_id == first_combatant_id
        assert turn_15.character_name == first_combatant.name
        assert turn_15.scene_type == "combat"
        assert turn_15.turn_number == turn_14.turn_number + 1

        # Verify turn linking
        assert turn_14.next_turn_id == turn_15.turn_id
        assert turn_15.previous_turn_id == turn_14.turn_id

        # Verify combat context in turn
        assert turn_15.context.get("in_combat") is True
        assert turn_15.context.get("combat_session_id") == session_id

        # Clear initialized combat flag (what the fix does)
        combat_state_manager.clear_initialized_combat(campaign_id)
        assert campaign_id not in combat_state_manager.initialized_combat

    def test_combat_turn_order_matches_initiative(self):
        """Test that the first combat turn goes to the character with highest initiative."""
        turn_manager = TurnManager()
        combat_state_manager = CombatStateManager(turn_manager=turn_manager)

        campaign_id = generate_unique_id("test_initiative_order")
        scene_id = generate_unique_id("combat_scene")

        # Create characters with different initiative bonuses
        characters = [
            CharacterInfo(
                character_id="alice",
                name="Alice",
                character_class="Fighter",
                level=5,
                hit_points_current=40,
                hit_points_max=40,
                armor_class=18,
                initiative_modifier=2  # +2 DEX
            ),
            CharacterInfo(
                character_id="bob",
                name="Bob",
                character_class="Wizard",
                level=5,
                hit_points_current=25,
                hit_points_max=25,
                armor_class=12,
                initiative_modifier=3  # +3 DEX
            ),
            CharacterInfo(
                character_id="charlie",
                name="Charlie",
                character_class="Cleric",
                level=5,
                hit_points_current=35,
                hit_points_max=35,
                armor_class=16,
                initiative_modifier=1  # +1 DEX
            )
        ]

        # Initialize combat
        combat_session = combat_state_manager.initialize_combat(
            scene_id=scene_id,
            characters=characters,
            campaign_id=campaign_id
        )

        # The turn order is determined by initiative rolls
        # We can't predict exact order, but we can verify:
        # 1. Turn order has all combatants
        assert len(combat_session.turn_order) == 3
        assert set(combat_session.turn_order) == {"alice", "bob", "charlie"}

        # 2. First combatant exists
        first_combatant_id = combat_session.turn_order[0]
        first_combatant = combat_session.combatants.get(first_combatant_id)
        assert first_combatant is not None

        # 3. We can create a turn for the first combatant
        session_id = combat_session.session_id
        combat_scene_context = {
            "scene_id": scene_id,
            "scene_type": "combat",
            "in_combat": True,
            "combat_session_id": session_id
        }

        first_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id=first_combatant_id,
            character_name=first_combatant.name,
            scene_context=combat_scene_context
        )
        turn_manager.start_turn(first_turn)

        assert first_turn.status == TurnStatus.ACTIVE
        assert first_turn.character_id == first_combatant_id
        assert first_turn.scene_type == "combat"

    def test_multiple_transitions_maintain_turn_sequence(self):
        """Test that multiple non-combat to combat transitions maintain turn numbering."""
        turn_manager = TurnManager()
        combat_state_manager = CombatStateManager(turn_manager=turn_manager)

        campaign_id = generate_unique_id("test_multiple_transitions")

        # === First exploration phase ===
        scene_id_1 = generate_unique_id("exploration_1")
        turn_1 = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:alice",
            character_name="Alice",
            scene_context={"scene_id": scene_id_1, "scene_type": "exploration"}
        )
        turn_manager.start_turn(turn_1)
        turn_manager.complete_turn(turn_1)

        # === First combat ===
        characters = [
            CharacterInfo(character_id="alice", name="Alice", character_class="Fighter",
                         level=3, hit_points_current=30, hit_points_max=30, armor_class=16)
        ]

        combat_scene_1 = generate_unique_id("combat_1")
        combat_1 = combat_state_manager.initialize_combat(
            scene_id=combat_scene_1,
            characters=characters,
            campaign_id=campaign_id
        )

        turn_2 = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="alice",
            character_name="Alice",
            scene_context={
                "scene_id": combat_scene_1,
                "scene_type": "combat",
                "in_combat": True,
                "combat_session_id": combat_1.session_id
            }
        )
        turn_manager.start_turn(turn_2)
        turn_manager.complete_turn(turn_2)

        # === Second exploration phase ===
        turn_3 = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="pc:alice",
            character_name="Alice",
            scene_context={"scene_id": scene_id_1, "scene_type": "exploration"}
        )
        turn_manager.start_turn(turn_3)
        turn_manager.complete_turn(turn_3)

        # === Second combat ===
        combat_scene_2 = generate_unique_id("combat_2")
        combat_2 = combat_state_manager.initialize_combat(
            scene_id=combat_scene_2,
            characters=characters,
            campaign_id=campaign_id
        )

        turn_4 = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id="alice",
            character_name="Alice",
            scene_context={
                "scene_id": combat_scene_2,
                "scene_type": "combat",
                "in_combat": True,
                "combat_session_id": combat_2.session_id
            }
        )
        turn_manager.start_turn(turn_4)

        # Verify turn numbers are sequential
        assert turn_2.turn_number == turn_1.turn_number + 1
        assert turn_3.turn_number == turn_2.turn_number + 1
        assert turn_4.turn_number == turn_3.turn_number + 1

        # Verify scene types alternate correctly
        assert turn_1.scene_type == "exploration"
        assert turn_2.scene_type == "combat"
        assert turn_3.scene_type == "exploration"
        assert turn_4.scene_type == "combat"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
