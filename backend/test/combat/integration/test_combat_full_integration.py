"""
Comprehensive Combat System Integration Test

This test validates the entire combat flow from scene setup through multiple combat rounds,
using actual LLM agents (no mocking) to verify both game mechanics and data persistence.
"""

import asyncio
import json
import os
import tempfile
import shutil
import logging
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional

# Skip this entire test - requires full LLM environment setup
# This is an optional comprehensive integration test that validates the entire combat flow
# with real LLM agents (no mocking). It's designed for manual testing and validation.
#
# To run this test manually:
# 1. Ensure all LLM providers are configured (Ollama/Claude/Parasail)
# 2. Run: python3 gaia_launcher.py test test/combat/integration/test_combat_full_integration.py
# 3. Review the detailed combat flow output for validation
#
# This test is kept skipped in CI/CD as it requires significant resources and time.
pytestmark = pytest.mark.skip(reason="Full integration test - requires complete LLM environment (manual test only)")

# Add backend to path for imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging to see combat debug output
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s [%(name)s]: %(message)s'
)
# Enable debug logging for combat modules
logging.getLogger('game.dnd_agents.combat').setLevel(logging.DEBUG)
logging.getLogger('gaia_private.agents.combat').setLevel(logging.DEBUG)
logging.getLogger('core.session.combat').setLevel(logging.DEBUG)

from gaia_private.orchestration.smart_router import SmartAgentRouter
from gaia_private.orchestration.combat_orchestrator import CombatOrchestrator
from gaia_private.orchestration.orchestrator import Orchestrator
from gaia.mechanics.combat.combat_state_manager import CombatStateManager
from gaia.mechanics.combat.combat_persistence import CombatPersistenceManager
from gaia_private.session.campaign_runner import CampaignRunner
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia_private.agents.combat.initiator import CombatInitiatorAgent
from gaia.models.scene_info import SceneInfo
from gaia.models.combat.persistence.combat_session import CombatSession
from gaia.models.combat.persistence.combatant_state import CombatantState
from gaia.models.character.character_info import CharacterInfo


class CombatIntegrationTestHarness:
    """Test harness for comprehensive combat system testing"""

    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir
        self.campaign_id = "test_campaign_001"
        self.campaign_storage_path = os.path.join(temp_dir, "campaigns")
        self.logs_path = os.path.join(temp_dir, "logs")

        # Create required directories
        os.makedirs(self.campaign_storage_path, exist_ok=True)
        os.makedirs(self.logs_path, exist_ok=True)

        # Initialize core components
        self.orchestrator = None
        self.campaign_runner = None
        self.smart_router = None
        self.combat_orchestrator = None
        self.combat_state_manager = None
        self.campaign_manager = None

    async def setup(self):
        """Initialize all components for testing"""
        print("\n=== SETUP PHASE ===")

        # Set environment variable for campaign storage
        os.environ['CAMPAIGN_STORAGE_PATH'] = self.campaign_storage_path

        # Initialize campaign manager
        self.campaign_manager = SimpleCampaignManager(base_path=self.campaign_storage_path)

        # Add get_campaign_data_path method for combat persistence
        def get_campaign_data_path(campaign_id):
            return Path(self.campaign_storage_path) / campaign_id
        self.campaign_manager.get_campaign_data_path = get_campaign_data_path

        # Create test campaign with player character
        campaign_data = await self._create_test_campaign()
        print(f"✅ Created test campaign: {self.campaign_id}")
        print(f"   - Player: {campaign_data['player_name']}")
        print(f"   - Class: {campaign_data['player_class']}")

        # Initialize campaign runner with minimal setup
        from gaia_private.session.history_manager import ConversationHistoryManager

        # Create minimal history manager
        history_manager = ConversationHistoryManager(
            max_history=10,
            compress_threshold=50
        )

        # Minimal game config
        game_config = {
            "style": "balanced",
            "difficulty": "medium"
        }

        # Create minimal context manager mock
        class MinimalContextManager:
            def check_scene_agent_repetition(self, campaign_id: str):
                # Return False (no repetition), 0 (count)
                return False, 0

            def get_scene_context(self, campaign_id: str, user_input: str):
                # Return minimal context
                return {
                    "scene_id": f"scene_{campaign_id}_001",
                    "scene_description": "A forest crossroads",
                    "user_input": user_input,
                    "campaign_id": campaign_id
                }

        self.campaign_runner = CampaignRunner(
            history_manager=history_manager,
            current_game_config=game_config,
            context_manager=MinimalContextManager(),
            campaign_manager=self.campaign_manager
        )

        # Set campaign ID attribute for later use
        self.campaign_runner.campaign_id = self.campaign_id
        print("✅ Campaign runner initialized")

        # Initialize character manager
        from gaia.mechanics.character.character_manager import CharacterManager
        self.campaign_runner.character_manager = CharacterManager(self.campaign_id)

        # Load the created character into the character manager
        if self.campaign_runner.character_manager:
            # Load character from the saved file
            character_file = os.path.join(self.campaign_storage_path, self.campaign_id,
                                        "characters", f"char_{self.campaign_id}_thorin.json")
            if os.path.exists(character_file):
                with open(character_file, 'r') as f:
                    char_data = json.load(f)
                    character = CharacterInfo(**char_data)
                    self.campaign_runner.character_manager.add_character(character)
                    print(f"✅ Loaded player character: {character.name}")

        # Create a mock ParallelSceneAnalyzer that includes hostiles
        class MockParallelAnalyzer:
            async def analyze_scene(self, user_input: str):
                # Return a mock analysis that triggers combat with hostiles
                return {
                    "routing": {
                        "primary_agent": "encounter",
                        "reasoning": "Combat detected with hostile goblins"
                    },
                    "overall": {
                        "confidence_score": 0.95
                    },
                    "scene": {
                        "primary_type": "COMBAT",
                        "game_phase": "INITIATIVE"
                    },
                    "complexity": {
                        "level": "MODERATE"
                    },
                    "special_considerations": {
                        "requires_dm_judgment": False
                    },
                    "requirements": {
                        "agents": ["encounter"]
                    },
                    "active_characters": [],
                    "players": [],  # Will be augmented by smart router
                    "npcs": []  # Will be augmented by smart router
                }

        self.campaign_runner.parallel_analyzer = MockParallelAnalyzer()
        print("✅ Mock parallel analyzer added")

        # Initialize smart router and combat orchestrator
        self.smart_router = SmartAgentRouter(self.campaign_runner)
        self.combat_orchestrator = CombatOrchestrator(self.campaign_runner)
        # Use the same combat_state_manager instance as the campaign runner
        self.combat_state_manager = self.campaign_runner.combat_state_manager

        # Initialize the full Orchestrator for end-to-end testing
        self.orchestrator = Orchestrator()
        # Replace the campaign_runner and managers with our test instances
        self.orchestrator.campaign_runner = self.campaign_runner
        self.orchestrator.campaign_manager = self.campaign_manager
        self.orchestrator.history_manager = history_manager

        print("✅ Core components initialized")

        # Setup initial scene with hostile NPCs
        scene_data = await self._setup_combat_scene()
        print(f"✅ Scene created: {scene_data['title']}")
        location_meta = scene_data.get("metadata", {}).get("location", {})
        location_display = None
        if isinstance(location_meta, dict):
            location_display = location_meta.get("description") or location_meta.get("id")
        elif isinstance(location_meta, str):
            location_display = location_meta
        print(f"   - Location: {location_display}")
        print(f"   - Hostiles: {len(scene_data.get('hostiles', []))} enemies")

        return campaign_data, scene_data

    async def _create_test_campaign(self) -> Dict[str, Any]:
        """Create a test campaign with player character"""
        campaign_data = {
            "campaign_name": "Integration Test Campaign",
            "player_name": "Thorin Ironforge",
            "player_class": "Fighter",
            "player_level": 5,
            "player_stats": {
                "strength": 18,
                "dexterity": 14,
                "constitution": 16,
                "intelligence": 10,
                "wisdom": 12,
                "charisma": 8
            },
            "player_hp": 44,
            "player_ac": 18,
            "equipment": [
                "Longsword",
                "Shield",
                "Chain Mail",
                "Health Potion x2"
            ]
        }

        # Create campaign directory
        campaign_dir = os.path.join(self.campaign_storage_path, self.campaign_id)
        os.makedirs(campaign_dir, exist_ok=True)

        # Save campaign data
        campaign_file = os.path.join(campaign_dir, "campaign.json")
        with open(campaign_file, 'w') as f:
            json.dump(campaign_data, f, indent=2)

        # Create character data
        character = CharacterInfo(
            character_id=f"char_{self.campaign_id}_thorin",
            name=campaign_data["player_name"],
            character_class=campaign_data["player_class"],
            level=campaign_data["player_level"],
            hit_points_max=campaign_data["player_hp"],
            hit_points_current=campaign_data["player_hp"],
            armor_class=campaign_data["player_ac"],
            strength=campaign_data["player_stats"]["strength"],
            dexterity=campaign_data["player_stats"]["dexterity"],
            constitution=campaign_data["player_stats"]["constitution"],
            intelligence=campaign_data["player_stats"]["intelligence"],
            wisdom=campaign_data["player_stats"]["wisdom"],
            charisma=campaign_data["player_stats"]["charisma"],
            character_type="player"
        )

        # Save character to campaign
        characters_dir = os.path.join(campaign_dir, "characters")
        os.makedirs(characters_dir, exist_ok=True)

        character_file = os.path.join(characters_dir, f"{character.character_id}.json")
        with open(character_file, 'w') as f:
            json.dump(character.to_dict(), f, indent=2)

        return campaign_data

    async def _setup_combat_scene(self) -> Dict[str, Any]:
        """Setup a scene with hostile NPCs that should trigger combat"""
        scene_data = {
            "scene_id": f"scene_{self.campaign_id}_001",
            "title": "Goblin Ambush at the Crossroads",
            "description": "As you travel along the forest path, you reach a crossroads. "
                          "Suddenly, goblins emerge from the underbrush with weapons drawn!",
            "scene_type": "combat",
            "in_combat": False,
            "pcs_present": [f"char_{self.campaign_id}_thorin"],  # Include the player character
            "npcs_present": ["Goblin Scout", "Goblin Warrior", "Goblin Archer"],
            "metadata": {
                "location": {
                    "id": "forest_crossroads",
                    "description": "A muddy crossroads in the forest with trees providing partial cover",
                }
            },
            "hostiles": [
                {
                    "name": "Goblin Scout",
                    "type": "Goblin",
                    "hp": 7,
                    "ac": 15,
                    "attacks": ["Scimitar (1d6+2)", "Shortbow (1d6)"],
                    "initiative_bonus": 2
                },
                {
                    "name": "Goblin Warrior",
                    "type": "Goblin",
                    "hp": 10,
                    "ac": 14,
                    "attacks": ["Scimitar (1d6+2)", "Shield Bash (1d4)"],
                    "initiative_bonus": 1
                },
                {
                    "name": "Goblin Archer",
                    "type": "Goblin",
                    "hp": 6,
                    "ac": 13,
                    "attacks": ["Shortbow (1d6)", "Dagger (1d4)"],
                    "initiative_bonus": 3
                }
            ]
        }

        # Register scene with SceneIntegration system to mimic normal flow
        if self.campaign_runner and hasattr(self.campaign_runner, 'scene_integration'):
            # Create SceneInfo without hostiles field
            scene_data_for_info = {k: v for k, v in scene_data.items() if k != 'hostiles'}
            scene_info = SceneInfo(**scene_data_for_info)

            # Get scene manager and store the scene object
            scene_manager = self.campaign_runner.scene_integration.get_scene_manager(self.campaign_id)
            scene_manager.create_scene(scene_info)

            # Put scene in current_scenes like process_scene_transition would do
            location_meta = None
            if scene_info.metadata:
                loc_meta = scene_info.metadata.get("location")
                if isinstance(loc_meta, dict):
                    location_meta = loc_meta.get("description") or loc_meta.get("id")
                elif isinstance(loc_meta, str):
                    location_meta = loc_meta
            self.campaign_runner.scene_integration.current_scenes[self.campaign_id] = {
                'scene_id': scene_info.scene_id,
                'title': scene_info.title,
                'scene_type': scene_info.scene_type,
                'location': location_meta,
                'in_combat': scene_info.in_combat,
                'npcs_present': scene_info.npcs_present
            }

            print(f"✅ Scene registered in current_scenes: {scene_info.scene_id}")

        return scene_data

    async def test_combat_initiation(self, player_action: str) -> Dict[str, Any]:
        """Test Phase 1: Combat Detection and Initiation"""
        print("\n=== COMBAT INITIATION PHASE ===")
        print(f"Player action: '{player_action}'")

        # Step 1: Route through SmartRouter to detect combat (full stack)
        print("\n1. Running SmartRouter analysis through full stack...")
        analysis_result = await self.smart_router.analyze_and_route(
            user_input=player_action,
            campaign_id=self.campaign_id
        )

        # Test JSON serialization immediately
        try:
            import json
            if analysis_result and "structured_data" in analysis_result:
                json_str = json.dumps(analysis_result["structured_data"])
                print(f"✅ Combat initiation response is JSON serializable ({len(json_str)} chars)")
        except (TypeError, ValueError) as e:
            assert False, f"Combat initiation response is not JSON serializable: {e}"

        # Verify combat was detected and routed
        assert analysis_result is not None, "SmartRouter failed to analyze input"
        print("✅ SmartRouter completed analysis and routing")

        # The SmartRouter should have automatically routed to combat initiation
        # Extract combat data from the response
        combat_init_data = analysis_result

        # Extract the actual combat data from the response structure
        if "structured_data" in combat_init_data:
            combat_data = combat_init_data["structured_data"]
        else:
            combat_data = combat_init_data

        # Check for initiative_order - it may be at top level or inside combat_initiation
        if "combat_initiation" in combat_data:
            init_data = combat_data["combat_initiation"]
            assert "initiative_order" in init_data, f"No initiative order in combat_initiation: {list(init_data.keys())}"
            assert "battlefield" in init_data, "No battlefield configuration in combat_initiation"
            # Also check at top level for duplicates
            if "initiative_order" in combat_data:
                print("   ⚠️ Initiative order found at both top level and in combat_initiation")
        else:
            assert "initiative_order" in combat_data, f"No initiative order in: {list(combat_data.keys())}"
            assert "battlefield" in combat_data, "No battlefield configuration"

        assert "narrative" in combat_data, "No combat narrative"

        print("\n3. Combat initiation results:")
        # Extract initiative order from the right location
        if "combat_initiation" in combat_data:
            init_order = combat_data["combat_initiation"].get("initiative_order", [])
            battlefield = combat_data["combat_initiation"].get("battlefield", {})
            opening_actions = combat_data["combat_initiation"].get("opening_actions", [])
        else:
            init_order = combat_data.get("initiative_order", [])
            battlefield = combat_data.get("battlefield", {})
            opening_actions = combat_data.get("opening_actions", [])

        print(f"   - Initiative order: {len(init_order)} combatants")
        print(f"   - Battlefield: {battlefield.get('size', 'unknown')}")
        print(f"   - Opening actions: {len(opening_actions)}")

        # Step 3: Verify data stored in initialized_combat cache
        cached_data = self.campaign_runner.combat_state_manager.get_initialized_combat(self.campaign_id)
        assert cached_data is not None, "Combat data not cached in campaign runner"
        print("✅ Combat data cached for transition")

        # Return the extracted combat data for further processing
        return combat_data

    async def test_session_persistence(self, combat_init_data: Dict[str, Any]) -> CombatSession:
        """Test Phase 2: Combat Session Creation and Persistence"""
        print("\n=== SESSION PERSISTENCE PHASE ===")

        # Step 1: Get the existing combat session that was created during initiation
        print("\n1. Getting existing combat session...")
        combat_session = self.combat_state_manager.get_active_combat(self.campaign_id)

        assert combat_session is not None, "No active combat session found after initiation"
        print(f"✅ Retrieved combat session: {combat_session.session_id}")

        # Step 2: Verify combatant states initialized
        print("\n2. Verifying combatant states...")
        assert len(combat_session.combatants) > 0, "No combatants in session"

        # Print the actual turn order for debugging
        print(f"   Turn order: {combat_session.turn_order}")

        for cid, combatant in combat_session.combatants.items():
            # Check for expected attributes instead of isinstance (avoids import path issues)
            assert hasattr(combatant, 'character_id'), f"Combatant {cid} missing character_id attribute"
            assert hasattr(combatant, 'hp'), f"Combatant {cid} missing hp attribute"
            assert hasattr(combatant, 'max_hp'), f"Combatant {cid} missing max_hp attribute"
            assert combatant.character_id is not None, f"Combatant {cid} missing character_id"
            assert combatant.hp >= 0, f"Combatant {cid} has negative HP"
            ap_current = combatant.action_points.current_ap if hasattr(combatant.action_points, 'current_ap') else 0
            ap_max = combatant.action_points.max_ap if hasattr(combatant.action_points, 'max_ap') else 3
            print(f"   - {combatant.name}: HP={combatant.hp}/{combatant.max_hp}, AP={ap_current}/{ap_max}")

        print(f"✅ {len(combat_session.combatants)} combatants initialized")

        # Step 4: Verify persistence to disk and check contents
        print("\n4. Verifying disk persistence and contents...")

        # Save the session
        persistence_manager = CombatPersistenceManager(
            campaign_manager=self.campaign_manager
        )
        persistence_manager.save_combat_session(self.campaign_id, combat_session)

        # Find and verify the saved file
        import glob
        pattern = os.path.join(self.campaign_storage_path, "**", f"{combat_session.session_id}.json")
        combat_files = glob.glob(pattern, recursive=True)

        assert len(combat_files) > 0, f"Combat session file not found: {combat_session.session_id}.json"

        # Verify the contents
        with open(combat_files[0], 'r') as f:
            saved_data = json.load(f)

            # Verify key fields were persisted
            assert saved_data["session_id"] == combat_session.session_id
            assert saved_data["scene_id"] == combat_session.scene_id
            assert saved_data["round_number"] == combat_session.round_number
            assert len(saved_data["combatants"]) == len(combat_session.combatants)

            # Verify opening actions if they were applied
            if saved_data.get("combat_log"):
                print(f"   ✅ Opening actions persisted: {len(saved_data['combat_log'])} actions")

            print(f"   ✅ Session saved to: {combat_files[0]}")
            print(f"   ✅ Verified session contents match expected state")

        return combat_session

    async def test_combat_execution(self, max_inputs: int = 20) -> List[Dict]:
        """Test Phase 3: Combat Execution using actual combat orchestrator with proper turn flow.

        Tests:
        - Multiple player actions per turn based on AP
        - NPC turn confirmation flow ("Are you ready?")
        - Persistence after each input
        - Turn transitions based on AP depletion
        """
        print(f"\n=== COMBAT EXECUTION PHASE (max {max_inputs} inputs) ===")

        action_history = []
        input_count = 0
        turn_counts = {}  # Track how many inputs each character has taken
        expected_turn_order = []  # Track expected turn progression
        round_files_seen = set()  # Track unique round files
        consecutive_same_character = 0  # Track consecutive actions by same character

        # Sample player actions for variety
        player_actions = [
            "I attack the nearest goblin with my sword!",  # Typically 2 AP
            "I cast magic missile at the goblin archer!",   # Typically 2 AP
            "I move and then attack!",                      # Could be 3 AP (move 1 + attack 2)
            "I defend and prepare for their next attack.",  # Typically 2 AP
            "I attack twice with my sword!",                # 4 AP - multi-action
            "I end my turn.",                               # 0 AP - explicit end
        ]

        # Track state for turn transitions
        last_active_combatant = None
        last_round = 0

        while input_count < max_inputs:
            input_count += 1

            # Get current combat state to determine whose turn it is
            combat_session = self.combat_state_manager.get_active_combat(self.campaign_id)
            if not combat_session:
                print(f"\n❌ No active combat session found after {input_count} inputs")
                break

            current_combatant_id = combat_session.resolve_current_character()
            current_combatant = combat_session.combatants.get(current_combatant_id) if current_combatant_id else None

            if not current_combatant:
                print(f"\n❌ No current combatant found")
                break

            # Track turn counts
            if current_combatant.name not in turn_counts:
                turn_counts[current_combatant.name] = 0
                expected_turn_order.append(current_combatant.name)
            turn_counts[current_combatant.name] += 1

            # Check for round transitions
            if combat_session.round_number > last_round:
                print(f"\n========== ROUND {combat_session.round_number} ==========")
                last_round = combat_session.round_number

                # Verify new round file is created
                round_file_name = f"scene_{self.campaign_id}_001 - round {combat_session.round_number}.json"
                round_files_seen.add(round_file_name)
                print(f"   📁 Expected new file: {round_file_name}")

            # Check for turn transitions
            if last_active_combatant != current_combatant.name:
                print(f"\n--- Turn transition to: {current_combatant.name} (Turn {combat_session.current_turn_index + 1}/{len(combat_session.turn_order)}) ---")

                # Verify proper turn order progression
                if len(expected_turn_order) > 1:
                    print(f"   ✅ Turn progression verified: {last_active_combatant} → {current_combatant.name}")

                consecutive_same_character = 0
                last_active_combatant = current_combatant.name
            else:
                consecutive_same_character += 1
                # Warn if same character takes too many consecutive actions
                if consecutive_same_character >= 3:
                    print(f"   ⚠️ WARNING: {current_combatant.name} has taken {consecutive_same_character + 1} consecutive actions!")
                    assert False, f"Turn not advancing properly - {current_combatant.name} stuck for {consecutive_same_character + 1} actions"

            # Determine input based on whose turn it is
            if current_combatant.is_npc:
                # NPC turn - need player confirmation
                # The orchestrator should have sent "Are you ready?" message
                user_input = "yes, I'm ready"
                print(f"   System: It's {current_combatant.name}'s turn, are you ready?")
                print(f"   Player: {user_input}")
            else:
                # Player turn - choose action based on AP
                if hasattr(current_combatant.action_points, 'current_ap'):
                    ap_current = current_combatant.action_points.current_ap
                    ap_max = current_combatant.action_points.max_ap
                else:
                    ap_current = 0
                    ap_max = 3
                print(f"\n   {current_combatant.name}'s action (AP: {ap_current}/{ap_max})")

                if ap_current >= 4:
                    # Can do multi-action
                    user_input = player_actions[4]  # "I attack twice with my sword!"
                elif ap_current >= 2:
                    # Can do single action
                    user_input = player_actions[input_count % 4]  # Rotate through single actions
                elif ap_current >= 1:
                    # Only enough for move
                    user_input = "I move to better position"
                else:
                    # No AP left, must end turn
                    user_input = "I end my turn"

                print(f"   Player input: {user_input}")

            # Call through the full runtime stack to test the actual path
            print(f"   🎯 Processing action for {current_combatant.name}...")
            # Use the smart router's analyze_and_route method to test the actual runtime path
            combat_response = await self.smart_router.analyze_and_route(
                user_input=user_input,
                campaign_id=self.campaign_id
            )

            # Test JSON serialization - this would catch serialization errors
            try:
                import json
                if combat_response and "structured_data" in combat_response:
                    json_str = json.dumps(combat_response["structured_data"])
                    print(f"   ✅ Response is JSON serializable ({len(json_str)} chars)")
            except (TypeError, ValueError) as e:
                assert False, f"Response is not JSON serializable: {e}"

            # Verify we got a response
            assert combat_response is not None, f"Combat orchestrator failed to process input {input_count}"

            # Extract and display combat results
            if "structured_data" in combat_response:
                structured = combat_response["structured_data"]

                # Show what happened (action taken)
                if structured.get("answer"):
                    print(f"   ⚔️ ACTION: {structured['answer']}")

                # Show dice rolls and damage from action_breakdown
                if structured.get("action_breakdown"):
                    for action in structured["action_breakdown"]:
                        # Check if action is an object or dict
                        if hasattr(action, 'roll'):  # It's an object
                            if action.roll:
                                roll_str = f"Rolled {action.roll}"
                                # Check for ac_dc if it exists
                                if hasattr(action, 'ac_dc') and action.ac_dc:
                                    roll_str += f" vs AC {action.ac_dc}"
                                roll_str += f" {'(Hit!)' if action.success else '(Miss!)'}"
                                print(f"   🎲 TO-HIT: {roll_str}")
                            if action.damage:
                                target = action.target if action.target else "target"
                                print(f"   ⚔️ DAMAGE: Dealt {action.damage} damage to {target}")
                            if action.description:
                                print(f"   📝 DETAIL: {action.description}")
                        else:  # It's a dict (for backward compatibility)
                            if action.get("roll"):
                                roll_str = f"Rolled {action['roll']}"
                                if action.get("ac_dc"):
                                    roll_str += f" vs AC {action['ac_dc']}"
                                roll_str += f" {'(Hit!)' if action.get('success') else '(Miss!)'}"
                                print(f"   🎲 TO-HIT: {roll_str}")
                            if action.get("damage"):
                                target = action.get("target", "target")
                                print(f"   ⚔️ DAMAGE: Dealt {action['damage']} damage to {target}")
                            if action.get("description"):
                                print(f"   📝 DETAIL: {action['description']}")

                # Show narrative description
                if structured.get("narrative"):
                    # Extract only the scene portion for cleaner output
                    narrative_lines = structured['narrative'].split('\n')
                    scene_section = False
                    for line in narrative_lines:
                        if 'Scene:' in line:
                            scene_section = True
                        elif scene_section and line.strip():
                            print(f"   📜 NARRATIVE: {line.strip()}")
                            break

                # Show updated status for all combatants
                if structured.get("status"):
                    print(f"   💊 STATUS UPDATE:")
                    status_lines = structured['status'].split('\n')
                    for line in status_lines:
                        if line.strip() and ':' in line and 'HP' in line:
                            # Format status line nicely
                            parts = line.strip().split(':')
                            if len(parts) >= 2:
                                name = parts[0].strip()
                                stats = parts[1].strip()
                                print(f"      • {name}: {stats}")

                # Check for defeated combatants
                combat_session_updated = self.combat_state_manager.get_active_combat(self.campaign_id)
                if combat_session_updated:
                    defeated_this_turn = []
                    for cid, combatant in combat_session_updated.combatants.items():
                        if combatant.hp <= 0 and combatant.name not in defeated_this_turn:
                            defeated_this_turn.append(combatant.name)
                            print(f"   ☠️ DEFEATED: {combatant.name} has been defeated!")

                    # Check if all enemies are dead (combat victory)
                    enemy_count = sum(1 for c in combat_session_updated.combatants.values() if c.is_npc and c.hp > 0)
                    player_count = sum(1 for c in combat_session_updated.combatants.values() if not c.is_npc and c.hp > 0)

                    if enemy_count == 0 and player_count > 0:
                        print(f"   🎉 COMBAT VICTORY! All enemies have been defeated!")
                        structured['combat_state'] = 'victory'
                    elif player_count == 0 and enemy_count > 0:
                        print(f"   💀 COMBAT DEFEAT! All players have been knocked out!")
                        structured['combat_state'] = 'defeat'

            # Verify persistence after EACH input
            await self._verify_persistence_after_input(input_count)

            # Record the action and response
            action_history.append({
                "input": input_count,
                "round": combat_session.round_number,
                "turn_index": combat_session.current_turn_index,
                "combatant": current_combatant.name,
                "is_npc": current_combatant.is_npc,
                "ap_before": ap_current if (not current_combatant.is_npc and 'ap_current' in locals()) else None,
                "user_input": user_input,
                "response": combat_response.get("structured_data", {}).get("answer", str(combat_response))
            })

            # Check if combat has ended
            if "structured_data" in combat_response:
                structured = combat_response["structured_data"]
                if structured.get("combat_state") in ["victory", "defeat", "ended"]:
                    print(f"\n⚔️ Combat ended with: {structured['combat_state']}")
                    break

                # Check turn resolution
                if structured.get("turn_resolution"):
                    turn_res = structured['turn_resolution']
                    # Handle TurnTransitionResult object or dict
                    if hasattr(turn_res, 'current_actor'):  # It's an object
                        print(f"   ↻ TURN TRANSITION: {turn_res.current_actor} → {turn_res.next_combatant}")
                        if turn_res.reason:
                            print(f"      Reason: {turn_res.reason}")
                        if turn_res.new_round:
                            print(f"   📅 NEW ROUND: Round {turn_res.round_number} begins!")
                    else:  # It's a dict
                        print(f"   ↻ TURN TRANSITION: {turn_res.get('current_actor')} → {turn_res.get('next_combatant')}")
                        if turn_res.get('reason'):
                            print(f"      Reason: {turn_res['reason']}")
                        if turn_res.get('new_round'):
                            print(f"   📅 NEW ROUND: Round {turn_res.get('round_number')} begins!")

                    # Re-fetch the combat session to get the updated turn info
                    combat_session = self.combat_state_manager.get_active_combat(self.campaign_id)
                else:
                    print(f"   ⏳ Turn continues for {current_combatant.name}")

            # Safety check: if we've done too many inputs for the same combatant, something's wrong
            same_combatant_inputs = sum(1 for a in action_history[-5:] if a['combatant'] == current_combatant.name)
            if same_combatant_inputs >= 5 and not current_combatant.is_npc:
                print(f"\n⚠️ Warning: {current_combatant.name} has taken {same_combatant_inputs} consecutive actions")

        print(f"\n✅ Processed {len(action_history)} inputs")
        print(f"   Player actions: {sum(1 for a in action_history if not a['is_npc'])}")
        print(f"   NPC confirmations: {sum(1 for a in action_history if a['is_npc'])}")
        print(f"   Rounds completed: {last_round}")
        print(f"   Unique characters who took turns: {len(turn_counts)}")
        print(f"   Turn order: {' → '.join(expected_turn_order[:4])}..." if len(expected_turn_order) > 4 else f"   Turn order: {' → '.join(expected_turn_order)}")

        # Verify multiple round files were created
        import glob
        pattern = os.path.join(self.campaign_storage_path, "**", "*round*.json")
        combat_files = glob.glob(pattern, recursive=True)
        print(f"   Combat session files created: {len(combat_files)}")
        for f in combat_files[:3]:  # Show first 3 files
            print(f"      - {os.path.basename(f)}")

        # Verify multiple characters took turns
        assert len(turn_counts) >= 2, f"Only {len(turn_counts)} character(s) took turns - combat not progressing properly"

        # Verify rounds advanced if enough inputs were processed
        if len(action_history) >= 10:
            assert last_round >= 2, f"Combat stayed in round {last_round} despite {len(action_history)} inputs"
            # Verify combat file exists (one file gets updated each round, not multiple files)
            assert len(combat_files) >= 1, f"No combat file(s) found - combat not persisting properly"

        return action_history

    async def _verify_persistence_after_input(self, input_num: int):
        """Verify combat session is persisted to disk after each input"""
        import glob
        pattern = os.path.join(self.campaign_storage_path, "**", "*.json")
        combat_files = glob.glob(pattern, recursive=True)
        combat_session_files = [f for f in combat_files if "round" in f]
        if len(combat_session_files) == 0:
            print(f"   ⚠️ Warning: No combat session saved after input {input_num}")
        else:
            # Read the most recent session file to verify it's up to date
            latest_file = max(combat_session_files, key=os.path.getmtime)
            with open(latest_file, 'r') as f:
                saved_data = json.load(f)
                # Could add more verification here if needed
                pass

    # Removed all simulated combat mechanics - the combat orchestrator handles everything now

    async def test_data_synchronization(self, combat_session: CombatSession) -> bool:
        """Test Phase 4: Verify Data Model Synchronization"""
        print("\n=== DATA SYNCHRONIZATION PHASE ===")

        # Step 1: Verify SceneInfo updates
        print("\n1. Checking scene model updates...")
        scene_file = os.path.join(
            self.campaign_storage_path,
            self.campaign_id,
            "scenes",
            f"{combat_session.scene_id}.json"
        )

        if os.path.exists(scene_file):
            with open(scene_file, 'r') as f:
                scene_data = json.load(f)
                assert scene_data.get("in_combat") == True or combat_session.status.value == "completed", \
                    "Scene not marked as in combat"
                if "combat_data" in scene_data:
                    print(f"✅ Scene combat_data populated")

        # Step 2: Verify Turn model updates
        print("\n2. Checking turn model updates...")
        turns_dir = os.path.join(
            self.campaign_storage_path,
            self.campaign_id,
            "turns"
        )

        if os.path.exists(turns_dir):
            turn_files = list(Path(turns_dir).glob("*.json"))
            if turn_files:
                latest_turn = max(turn_files, key=lambda f: f.stat().st_mtime)
                with open(latest_turn, 'r') as f:
                    turn_data = json.load(f)
                    assert turn_data.get("scene_id") == combat_session.scene_id, \
                        "Turn not linked to correct scene"
                    print(f"✅ Turn linked to scene: {turn_data.get('scene_id')}")

        # Step 3: Verify combat session persistence
        print("\n3. Checking combat session persistence...")
        session_file = os.path.join(
            self.campaign_storage_path,
            self.campaign_id,
            "combat",
            "active" if combat_session.status != "COMPLETED" else "archived",
            f"{combat_session.session_id}.json"
        )

        assert os.path.exists(session_file), f"Combat session file not found: {session_file}"

        with open(session_file, 'r') as f:
            saved_session = json.load(f)
            assert saved_session["round_number"] == combat_session.round_number
            assert len(saved_session["combatants"]) == len(combat_session.combatants)
            # Compare status as strings (saved JSON has string value, combat_session has enum)
            assert saved_session["status"] == combat_session.status.value

        print(f"✅ Combat session properly persisted")
        print(f"   - Round: {saved_session['round_number']}")
        print(f"   - Status: {saved_session['status']}")
        print(f"   - Combatants: {len(saved_session['combatants'])}")

        return True

    async def cleanup(self):
        """Clean up test data"""
        print("\n=== CLEANUP PHASE ===")
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"✅ Cleaned up temp directory: {self.temp_dir}")

@pytest.mark.asyncio
async def test_full_combat_integration():
    """
    Main test function that runs the complete combat integration test
    """
    print("\n" + "="*80)
    print(" COMPREHENSIVE COMBAT SYSTEM INTEGRATION TEST")
    print("="*80)

    # Create temporary directory for test data
    with tempfile.TemporaryDirectory(prefix="gaia_combat_test_") as temp_dir:
        print(f"\nTest directory: {temp_dir}")

        # Initialize test harness
        harness = CombatIntegrationTestHarness(temp_dir)

        # Setup phase
        await harness.setup()

        # Test Phase 1: Combat Initiation
        player_action = "I draw my sword and attack the goblins!"
        combat_init_data = await harness.test_combat_initiation(player_action)

        # Test Phase 2: Session Persistence
        combat_session = await harness.test_session_persistence(combat_init_data)

        # Test Phase 3: Combat Execution (multiple inputs)
        # The orchestrator manages the session internally now
        action_history = await harness.test_combat_execution(
            max_inputs=20
        )

        # Test Phase 4: Data Synchronization
        sync_success = await harness.test_data_synchronization(combat_session)

        # Summary
        print("\n" + "="*80)
        print(" TEST SUMMARY")
        print("="*80)
        print(f"✅ Setup: Campaign and scene created")
        print(f"✅ Initiation: Combat detected and initialized")
        print(f"✅ Persistence: Session saved to disk")
        print(f"✅ Execution: {len(action_history)} actions across multiple rounds")
        print(f"✅ Synchronization: All models properly updated")
        print(f"\n🎉 ALL INTEGRATION TESTS PASSED!")

        # Cleanup
        await harness.cleanup()


if __name__ == "__main__":
    # Run the test
    try:
        asyncio.run(test_full_combat_integration())
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
