#!/usr/bin/env python3
"""Simple test for combat initiation flow - checking turn messages."""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gaia_private.models.combat.agent_io.initiation import (
    CombatInitiation,
    InitiativeEntry,
    CombatConditions,
    CombatNarrative,
    BattlefieldConfig,
    OpeningAction
)
from gaia.mechanics.combat.combat_formatter import CombatFormatter
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_combat_initiation_npc_first():
    """Create combat initiation with NPC going first."""
    return CombatInitiation(
        combat_id="test_combat_1",
        scene_id="test_scene",
        campaign_id="test_campaign",
        narrative=CombatNarrative(
            scene_description="Bandits attack in the tavern!",
            enemy_description="Three bandits draw their weapons",
            combat_trigger="The bandit leader shouts 'Get them!'",
            opening_action=None
        ),
        initiative_order=[
            InitiativeEntry(name="Bandit Leader", initiative=18, is_surprised=False, is_player=False),
            InitiativeEntry(name="Thorin", initiative=15, is_surprised=False, is_player=True),
            InitiativeEntry(name="Bandit", initiative=12, is_surprised=False, is_player=False),
            InitiativeEntry(name="Elara", initiative=10, is_surprised=False, is_player=True)
        ],
        battlefield=BattlefieldConfig(terrain="tavern", size="medium"),
        conditions=CombatConditions(weather="indoor", visibility="normal"),
        enemies=[
            {"name": "Bandit Leader", "type": "enemy"},
            {"name": "Bandit", "type": "enemy"}
        ],
        encounter_difficulty="medium",
        enemy_strategy="aggressive"
    )


def create_combat_initiation_player_first():
    """Create combat initiation with player going first."""
    return CombatInitiation(
        combat_id="test_combat_2",
        scene_id="test_scene",
        campaign_id="test_campaign",
        narrative=CombatNarrative(
            scene_description="You confront the goblins!",
            enemy_description="Two goblins snarl at you",
            combat_trigger="Thorin draws his sword",
            opening_action=None
        ),
        initiative_order=[
            InitiativeEntry(name="Thorin", initiative=20, is_surprised=False, is_player=True),
            InitiativeEntry(name="Goblin Chief", initiative=14, is_surprised=False, is_player=False),
            InitiativeEntry(name="Elara", initiative=12, is_surprised=False, is_player=True),
            InitiativeEntry(name="Goblin", initiative=8, is_surprised=False, is_player=False)
        ],
        battlefield=BattlefieldConfig(terrain="forest clearing", size="small"),
        conditions=CombatConditions(weather="clear", visibility="normal"),
        enemies=[
            {"name": "Goblin Chief", "type": "enemy"},
            {"name": "Goblin", "type": "enemy"}
        ],
        encounter_difficulty="easy",
        enemy_strategy="defensive"
    )


def create_combat_initiation_with_opening():
    """Create combat initiation with opening action."""
    return CombatInitiation(
        combat_id="test_combat_3",
        scene_id="test_scene",
        campaign_id="test_campaign",
        narrative=CombatNarrative(
            scene_description="An assassin strikes from the shadows!",
            enemy_description="A cloaked figure emerges",
            combat_trigger="The assassin throws a dagger!"
        ),
        opening_actions=[
            OpeningAction(
                actor="Assassin",
                action_type="ranged attack",
                target="Thorin",
                description="throws a poisoned dagger at Thorin",
                resolution_summary="The poisoned dagger flies toward Thorin!"
            )
        ],
        initiative_order=[
            InitiativeEntry(name="Assassin", initiative=22, is_surprised=False, is_player=False),
            InitiativeEntry(name="Thorin", initiative=15, is_surprised=False, is_player=True),
            InitiativeEntry(name="Elara", initiative=12, is_surprised=False, is_player=True)
        ],
        battlefield=BattlefieldConfig(terrain="alley", size="small"),
        conditions=CombatConditions(weather="night", visibility="dim"),
        enemies=[
            {"name": "Assassin", "type": "enemy"}
        ],
        encounter_difficulty="hard",
        enemy_strategy="hit and run"
    )


def test_combat_formatter():
    """Test the combat formatter's handling of initiation responses."""
    formatter = CombatFormatter()

    logger.info("\n" + "="*60)
    logger.info("TESTING COMBAT INITIATION TURN MESSAGES")
    logger.info("="*60)

    # Test 1: NPC goes first
    logger.info("\nTest 1: NPC Goes First")
    logger.info("-" * 40)

    combat_init = create_combat_initiation_npc_first()

    # Format the scene response (combat initiation)
    scene_response = formatter.format_scene_response(
        agent_response=combat_init,
        interaction_type="combat_initiation"
    )

    turn_message = scene_response["structured_data"]["turn"]
    turn_info = scene_response["structured_data"].get("turn_info", {})

    logger.info(f"Turn message: {turn_message}")
    logger.info(f"Active combatant: {turn_info.get('active_combatant', 'NOT SET')}")

    # Verify
    assert "Bandit Leader" in turn_message, f"NPC first: Turn message should mention Bandit Leader, got: {turn_message}"
    logger.info("✅ NPC first test passed")

    # Test 2: Player goes first
    logger.info("\nTest 2: Player Goes First")
    logger.info("-" * 40)

    combat_init = create_combat_initiation_player_first()
    scene_response = formatter.format_scene_response(
        agent_response=combat_init,
        interaction_type="combat_initiation"
    )

    turn_message = scene_response["structured_data"]["turn"]
    turn_info = scene_response["structured_data"].get("turn_info", {})

    logger.info(f"Turn message: {turn_message}")
    logger.info(f"Active combatant: {turn_info.get('active_combatant', 'NOT SET')}")

    # Verify
    assert "Thorin" in turn_message, f"Player first: Turn message should mention Thorin, got: {turn_message}"
    logger.info("✅ Player first test passed")

    # Test 3: With opening action
    logger.info("\nTest 3: With Opening Action")
    logger.info("-" * 40)

    combat_init = create_combat_initiation_with_opening()
    scene_response = formatter.format_scene_response(
        agent_response=combat_init,
        interaction_type="combat_initiation"
    )

    turn_message = scene_response["structured_data"]["turn"]
    turn_info = scene_response["structured_data"].get("turn_info", {})
    narrative = scene_response["structured_data"]["narrative"]

    logger.info(f"Turn message: {turn_message}")
    logger.info(f"Active combatant: {turn_info.get('active_combatant', 'NOT SET')}")
    logger.info(f"Opening action in narrative: {'poisoned dagger' in narrative}")

    # Verify
    assert "Assassin" in turn_message or "first" in turn_message.lower(), \
        f"Opening action: Should indicate who goes first, got: {turn_message}"
    assert "poisoned dagger" in narrative.lower(), "Opening action should be in narrative"
    logger.info("✅ Opening action test passed")

    logger.info("\n" + "="*60)
    logger.info("ALL TESTS PASSED!")
    logger.info("="*60)


if __name__ == "__main__":
    test_combat_formatter()
    logger.info("\nTests completed successfully!")