#!/usr/bin/env python3
"""Test script for the Combat Initiator agent.

This script validates that the Combat Initiator agent properly:
- Initializes with correct configuration
- Rolls initiative for combatants
- Determines appropriate enemies
- Creates battlefield configurations
- Generates proper output format
- Hands off to the CombatAgent
"""

import sys
import os
import json
import asyncio
import logging
import pytest
from typing import Dict, Any

# Add backend source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_combat_initiator_basic():
    """Test basic initialization of the Combat Initiator agent."""
    print("\n" + "="*60)
    print("Testing Combat Initiator Agent - Basic Initialization")
    print("="*60)

    from gaia_private.agents.combat.initiator import CombatInitiatorAgent

    # Initialize the agent
    agent = CombatInitiatorAgent()

    print("✅ Agent initialized successfully")
    print(f"   - Agent name: {agent.name}")
    print(f"   - Model: {agent.model}")
    print(f"   - Tools registered: {len(agent.tools) if hasattr(agent, 'tools') else 0}")

    # Assert agent has required attributes
    assert agent.name is not None, "Agent must have a name"
    assert agent.model is not None, "Agent must have a model"
    assert hasattr(agent, 'tools'), "Agent must have tools"
    assert len(agent.tools) > 0, "Agent must have at least one tool"


def test_initiative_rolling():
    """Test the initiative rolling functionality."""
    print("\n" + "="*60)
    print("Testing Initiative Rolling (Deterministic)")
    print("="*60)

    from gaia_private.agents.combat.initiator import CombatInitiatorAgent
    from gaia_private.models.combat.agent_io.initiation import CombatInitiationRequest, CombatantInfo, SceneContext

    agent = CombatInitiatorAgent()

    # Create test combatants (converted from old format)
    test_combatants = [
        CombatantInfo(name="Aragorn", type="player", class_or_creature="Ranger", dex_score=16, hostile=False),  # dex_mod = +3
        CombatantInfo(name="Legolas", type="player", class_or_creature="Ranger", dex_score=20, hostile=False),  # dex_mod = +5
        CombatantInfo(name="Gimli", type="player", class_or_creature="Fighter", dex_score=10, hostile=False),    # dex_mod = 0
        CombatantInfo(name="Goblin Scout", type="npc", class_or_creature="Goblin", dex_score=14, hostile=True),  # dex_mod = +2
        CombatantInfo(name="Orc Warrior", type="npc", class_or_creature="Orc", dex_score=12, hostile=True)    # dex_mod = +1
    ]

    # Create a minimal request to pass combatants
    request = CombatInitiationRequest(
        player_action="Combat begins!",
        campaign_id="test_campaign",
        scene=SceneContext(
            scene_id="test_scene",
            title="Test Arena",
            description="A test combat scene",
            location="Arena",
            location_type="arena"
        ),
        combatants=test_combatants
    )

    print("\nRolling initiative for combatants:")
    print("-" * 40)

    # Test the new deterministic initiative rolling
    initiative_order = agent._roll_initiative(request)

    # Display results
    for entry in initiative_order:
        dex_mod = (entry.dex_score - 10) // 2 if entry.dex_score else 0
        player_type = "PC" if entry.is_player else "NPC"
        print(f"  {entry.name:15} ({player_type}) DEX+{dex_mod:2} -> Initiative: {entry.initiative:2}")

        # Assert result structure
        assert entry.name, "Entry must have a name"
        assert entry.initiative is not None, "Entry must have initiative value"
        assert entry.dex_score is not None, "Entry must have dex_score"
        assert entry.initiative >= 1 + dex_mod, "Initiative must be at least 1 + modifier"
        assert entry.initiative <= 20 + dex_mod, "Initiative must be at most 20 + modifier"

    # Verify sorted order (highest first, ties broken by dex)
    print("\nInitiative Order (sorted):")
    print("-" * 40)
    for i, entry in enumerate(initiative_order, 1):
        print(f"  {i}. {entry.name:15} - Initiative: {entry.initiative}")

        # Verify order is correct
        if i < len(initiative_order):
            current = initiative_order[i-1]
            next_entry = initiative_order[i]
            assert current.initiative >= next_entry.initiative, \
                f"Initiative order incorrect: {current.name}({current.initiative}) should be >= {next_entry.name}({next_entry.initiative})"

            # If tied, verify dex tiebreaker
            if current.initiative == next_entry.initiative:
                assert (current.dex_score or 10) >= (next_entry.dex_score or 10), \
                    f"Dex tiebreaker failed: {current.name}(DEX {current.dex_score}) should be >= {next_entry.name}(DEX {next_entry.dex_score})"

    print("\n✅ Initiative rolling successful (now deterministic, not tool-based)")


def test_enemy_determination():
    """Test the enemy determination functionality."""
    print("\n" + "="*60)
    print("Testing Enemy Determination")
    print("="*60)

    from gaia_private.agents.combat.initiator import CombatInitiatorAgent

    agent = CombatInitiatorAgent()

    # Test scenarios - determine_enemies requires 'enemy_types' array
    test_scenarios = [
        {"enemy_types": ["goblin", "hobgoblin"], "party_level": 3, "party_size": 4, "difficulty": "medium"},
        {"enemy_types": ["dragon wyrmling", "kobold"], "party_level": 5, "party_size": 4, "difficulty": "hard"},
        {"enemy_types": ["bandit", "thug"], "party_level": 1, "party_size": 3, "difficulty": "easy"},
        {"enemy_types": ["skeleton", "zombie", "wight"], "party_level": 7, "party_size": 5, "difficulty": "deadly"}
    ]

    # Find the determine_enemies tool
    determine_enemies_tool = None
    for tool in agent.tools:
        if tool.name == "determine_enemies":
            determine_enemies_tool = tool
            break

    assert determine_enemies_tool is not None, "determine_enemies tool must exist"

    print("\nEnemy Configurations:")
    print("-" * 60)

    ctx = {}  # Mock context

    for scenario in test_scenarios:
        # Call the tool handler properly
        result_json = asyncio.run(determine_enemies_tool.on_invoke_tool(ctx, scenario))
        result = json.loads(result_json)

        print(f"\n📍 {scenario['enemy_types'][0].upper()} Encounter")
        print(f"   Party: Level {scenario['party_level']}, Size {scenario['party_size']}")
        print(f"   Difficulty: {scenario['difficulty'].upper()}")
        print(f"   → Total Enemies: {result.get('total_enemies', 0)}")
        print(f"   → HP: ~{result['suggested_hp']} per enemy")
        print(f"   → AC: {result['suggested_ac']}")
        if 'enemies' in result and result['enemies']:
            print(f"   → CR: {result['enemies'][0].get('challenge_rating', 'N/A')}")

        if 'enemies' in result:
            enemy_types = [e.get('type', 'Unknown') for e in result['enemies'][:2]]
            print(f"   → Types: {', '.join(enemy_types)}")

        # Assert required fields
        assert "total_enemies" in result, "Result must contain total_enemies"
        assert "suggested_hp" in result, "Result must contain suggested_hp"
        assert "suggested_ac" in result, "Result must contain suggested_ac"
        assert "enemies" in result, "Result must contain enemies list"
        assert result["total_enemies"] > 0, "Must have at least one enemy"
        assert result["suggested_hp"] > 0, "HP must be positive"
        assert len(result["enemies"]) > 0, "Enemies list must not be empty"

    print("\n✅ Enemy determination successful")


def test_battlefield_creation():
    """Test the battlefield creation functionality."""
    print("\n" + "="*60)
    print("Testing Battlefield Creation")
    print("="*60)

    from gaia_private.agents.combat.initiator import CombatInitiatorAgent

    agent = CombatInitiatorAgent()

    # Test different terrain types - create_battlefield expects 'terrain' not 'terrain_type'
    test_terrains = [
        {"terrain": "forest", "size": "medium", "features": ["trees", "bushes"], "hazards": []},
        {"terrain": "dungeon", "size": "large", "features": ["pillars", "alcoves"], "hazards": ["pit trap", "spikes"]},
        {"terrain": "tavern", "size": "small", "features": ["tables", "bar"], "hazards": []},
        {"terrain": "cave", "size": "medium", "features": ["stalagmites"], "hazards": ["unstable ceiling"]}
    ]

    # Find the create_battlefield tool
    create_battlefield_tool = None
    for tool in agent.tools:
        if tool.name == "create_battlefield":
            create_battlefield_tool = tool
            break

    assert create_battlefield_tool is not None, "create_battlefield tool must exist"

    print("\nBattlefield Configurations:")
    print("-" * 60)

    ctx = {}  # Mock context

    for terrain in test_terrains:
        # Call the tool handler properly
        result_json = asyncio.run(create_battlefield_tool.on_invoke_tool(ctx, terrain))
        result = json.loads(result_json)

        print(f"\n🗺️  {terrain['terrain'].upper()} Battlefield")
        print(f"   Size: {result['dimensions']}")
        print(f"   Lighting: {result['lighting']}")

        if result.get('features'):
            print(f"   Features: {', '.join(result['features'][:2])}")

        if result.get('hazards'):
            print(f"   Hazards: {', '.join(result['hazards'])}")

        if 'movement_difficulty' in result:
            print(f"   Movement: {result['movement_difficulty']}")

        # Assert required fields
        assert "dimensions" in result, "Result must contain dimensions"
        assert "lighting" in result, "Result must contain lighting"
        assert "terrain" in result, "Result must contain terrain"
        assert result["terrain"] == terrain["terrain"], "Terrain must match"

    print("\n✅ Battlefield creation successful")


@pytest.mark.skip(reason="Requires PARASAIL_API_KEY environment variable")
def test_full_combat_setup():
    """Test a full combat setup scenario using proper request structure."""
    print("\n" + "="*60)
    print("Testing Full Combat Setup Scenario")
    print("="*60)

    from gaia_private.agents.combat.initiator import CombatInitiatorAgent
    from gaia_private.models.combat.agent_io.initiation import (
        CombatInitiationRequest,
        CombatantInfo,
        SceneContext
    )

    agent = CombatInitiatorAgent()

    # Create proper scene context with all required fields
    scene = SceneContext(
        scene_id="scene_001",
        title="Goblin Ambush",
        location="Dark Forest Path",
        location_type="outdoor",
        description="A winding path through a dark forest",
        environmental_factors=["dim light", "dense foliage"]
    )

    # Create combatants
    combatants = [
        CombatantInfo(
            name="Aragorn",
            type="player",
            class_or_creature="Ranger",
            level=3,
            hp_current=30,
            hp_max=30,
            armor_class=16,
            hostile=False,
            initiative_bonus=2
        ),
        CombatantInfo(
            name="Legolas",
            type="player",
            class_or_creature="Ranger",
            level=3,
            hp_current=25,
            hp_max=25,
            armor_class=15,
            hostile=False,
            initiative_bonus=4
        ),
        CombatantInfo(
            name="Gimli",
            type="player",
            class_or_creature="Fighter",
            level=3,
            hp_current=35,
            hp_max=35,
            armor_class=17,
            hostile=False,
            initiative_bonus=0
        ),
        CombatantInfo(
            name="Gandalf",
            type="player",
            class_or_creature="Wizard",
            level=3,
            hp_current=20,
            hp_max=20,
            armor_class=12,
            hostile=False,
            initiative_bonus=1
        )
    ]

    # Create the combat initiation request
    request = CombatInitiationRequest(
        campaign_id="test_campaign_001",
        scene=scene,
        player_action="I attack the goblin scouts blocking our path!",
        combatants=combatants,
        threat_level="medium"
    )

    print("\n📝 Scenario:")
    print(f"   User Input: {request.player_action}")
    print(f"   Location: {request.scene.location}")
    print(f"   Party: {len(request.get_player_combatants())} members")

    print("\n⚔️ Processing combat initiation...")
    print("-" * 40)

    # Process the combat setup with proper request (async method)
    response = asyncio.run(agent.process_input(request))

    print("\n📋 Combat Setup Response:")
    print("-" * 40)

    # The response should be a CombatInitiation object
    from gaia_private.models.combat.agent_io.initiation import CombatInitiation

    assert isinstance(response, CombatInitiation), f"Expected CombatInitiation response, got {type(response)}"
    print(f"✅ Received CombatInitiation response")

    # Check for required attributes
    assert hasattr(response, 'handoff_to'), "Response must have handoff_to attribute"
    assert hasattr(response, 'initiative_order'), "Response must have initiative_order attribute"
    assert hasattr(response, 'battlefield'), "Response must have battlefield attribute"
    assert hasattr(response, 'narrative'), "Response must have narrative attribute"
    print(f"✅ All required attributes present")

    # Check handoff
    assert response.handoff_to == "combat_agent", f"Expected handoff to combat_agent, got {response.handoff_to}"
    print("✅ Correct handoff to combat_agent")

    # Check initiative order
    assert len(response.initiative_order) > 0, "Initiative order must not be empty"
    print(f"✅ Initiative order generated with {len(response.initiative_order)} combatants")

    # Display some response details
    print(f"\n📊 Combat Setup Details:")
    print(f"   - Scene ID: {response.scene_id}")
    print(f"   - Campaign ID: {response.campaign_id}")
    print(f"   - Battlefield: {response.battlefield.terrain} ({response.battlefield.size})")
    print(f"   - Combatants: {', '.join([entry.name for entry in response.initiative_order[:3]])}...")

    print("\n✅ Full combat setup completed successfully")


def test_combat_engine_integration():
    """Test integration with the combat engine."""
    print("\n" + "="*60)
    print("Testing Combat Engine Integration")
    print("="*60)

    from gaia.mechanics.combat.combat_engine import CombatEngine, AttackResolution
    from gaia.models.combat import CombatSession, CombatantState, CombatStatus
    from gaia.models.combat.mechanics.action_points import ActionPointState

    # Create a combat engine instance
    engine = CombatEngine()

    # Create a test combat session
    session = CombatSession(
        session_id="test_session_001",
        scene_id="test_scene",
        status=CombatStatus.IN_PROGRESS,
        round_number=1,
        current_turn_index=0
    )

    # Add combatants
    player = CombatantState(
        character_id="player_001",
        name="Test Hero",
        is_npc=False,
        initiative=15,
        hp=30,
        max_hp=30,
        ac=16,
        level=3,
        action_points=ActionPointState(max_ap=2, current_ap=2)
    )

    enemy = CombatantState(
        character_id="enemy_001",
        name="Test Goblin",
        is_npc=True,
        initiative=12,
        hp=15,
        max_hp=15,
        ac=13,
        level=1,
        action_points=ActionPointState(max_ap=2, current_ap=2)
    )

    session.combatants = {
        player.character_id: player,
        enemy.character_id: enemy
    }
    session.turn_order = ["player_001", "enemy_001"]

    # Test combat actions
    print("\n📊 Testing Combat Actions:")
    print("-" * 40)

    # Test attack resolution directly with correct method signature
    # Use low damage to avoid killing the enemy (needed for turn advancement test)
    attack_result = engine.resolve_attack(
        attacker=player,
        target=enemy,
        weapon_damage="1d4+1"  # Max 5 damage, enemy has 15 HP
    )

    print(f"✅ Attack resolution:")
    print(f"   - Hit: {attack_result.success}")
    print(f"   - Damage: {attack_result.damage}")

    # Check if damage was dealt
    if attack_result.success:
        print(f"   - Enemy HP: {enemy.hp}/{enemy.max_hp}")
        assert enemy.hp <= enemy.max_hp, "Enemy HP should not exceed max"
        assert enemy.hp > 0, "Enemy should still be alive for turn advancement test"
    else:
        print(f"   - Attack missed")

    # Assert attack result is valid
    assert attack_result is not None, "Attack result must not be None"
    assert hasattr(attack_result, 'success'), "Attack result must have success attribute"
    assert hasattr(attack_result, 'damage'), "Attack result must have damage attribute"

    # Test turn management
    print("\n📊 Testing Turn Management:")
    print("-" * 40)

    # Get current turn from session
    current_turn = session.resolve_current_character()
    print(f"   - Current turn: {current_turn}")
    assert current_turn == "player_001", "First turn should be player_001"

    # Advance turn using session method
    turn_info = session.advance_turn()
    current_turn = session.resolve_current_character()
    print(f"   - Next turn: {current_turn}")
    print(f"   - New round: {turn_info['new_round']}")
    assert current_turn == "enemy_001", "Second turn should be enemy_001"

    # Advance to next round
    turn_info = session.advance_turn()
    print(f"   - Round: {session.round_number}")
    print(f"   - Current turn after advance: {session.resolve_current_character()}")
    assert session.round_number == 2, "Should be round 2 after full rotation"
    assert turn_info['new_round'], "Should indicate new round"

    print("\n✅ Combat engine integration successful")


def main():
    """Run all tests for the Combat Initiator agent."""
    print("\n" + "="*60)
    print("COMBAT INITIATOR AGENT TEST SUITE")
    print("="*60)

    # Track test results
    results = []

    # Run tests - no try/except to hide errors per user request
    tests = [
        ("Basic Initialization", test_combat_initiator_basic),
        ("Initiative Rolling", test_initiative_rolling),
        ("Enemy Determination", test_enemy_determination),
        ("Battlefield Creation", test_battlefield_creation),
        ("Full Combat Setup", test_full_combat_setup),
        ("Combat Engine Integration", test_combat_engine_integration)
    ]

    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        success = test_func()
        results.append((test_name, success))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {test_name:30} {status}")

    print("-" * 60)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
