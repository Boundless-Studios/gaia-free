"""Test the Combat orchestrator with current architecture.

Tests the 4-step combat flow:
1. CombatActionSelectionAgent selects actions
2. _resolve_combat_actions handles mechanics in code
3. CombatNarrativeAgent generates narrative
4. _normalize_combat_output merges all data
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from typing import Dict, Any

from gaia_private.agents.combat.combat import Combat
from gaia_private.models.combat.agent_io.fight import (
    CombatActionRequest,
    CombatantView,
    CurrentTurnInfo
)
from gaia_private.models.combat.agent_io.initiation.battlefield_config import BattlefieldConfig
from gaia_private.agents.combat.models import (
    CombatActionSelectionOutput,
    CombatNarrativeOutput
)
from gaia_private.models.combat.agent_io import AgentCombatResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_combat_has_required_methods():
    """Test that Combat class has all required methods."""
    combat = Combat()

    # Check methods exist
    assert hasattr(combat, 'run_player_combat'), "Should have run_player_combat method"
    assert hasattr(combat, 'run_npc_combat'), "Should have run_npc_combat method"
    assert hasattr(combat, '_build_player_prompt'), "Should have _build_player_prompt method"
    assert hasattr(combat, '_build_npc_prompt'), "Should have _build_npc_prompt method"
    assert hasattr(combat, '_resolve_combat_actions'), "Should have _resolve_combat_actions method"
    assert hasattr(combat, '_normalize_combat_output'), "Should have _normalize_combat_output method"

    print("✅ Combat class has all required methods")


def test_combat_sub_agents_exist():
    """Test that Combat orchestrator has required sub-agents."""
    combat = Combat()

    # Check sub-agents exist
    assert combat.action_selector is not None, "Action selector should exist"
    assert combat.narrator is not None, "Narrator should exist"

    # Check sub-agent types
    from gaia_private.agents.combat.action_selector import CombatActionSelectionAgent
    from gaia_private.agents.combat.narrator import CombatNarrativeAgent

    assert isinstance(combat.action_selector, CombatActionSelectionAgent), "Action selector should be correct type"
    assert isinstance(combat.narrator, CombatNarrativeAgent), "Narrator should be correct type"

    print("✅ Combat orchestrator has all required sub-agents")


def test_combat_initialization():
    """Test Combat orchestrator initializes correctly."""
    combat = Combat()

    assert combat.combat_engine is not None, "Combat engine should be initialized"
    assert combat.action_validator is not None, "Action validator should be initialized"
    assert combat.action_selector is not None, "Action selector should be initialized"
    assert combat.narrator is not None, "Narrator should be initialized"
    assert combat.config is not None, "Config should be set"
    assert combat.name() == "combat_orchestrator", "Name should be combat_orchestrator"

    print("✅ Combat orchestrator initialized with all components")


def test_combat_prompt_building():
    """Test that prompt building works for player and NPC."""
    combat = Combat()

    request = CombatActionRequest(
        campaign_id="test",
        combat_id="test_001",
        player_action="I attack",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant="Fighter",
            available_actions=["basic_attack"]
        ),
        combatants=[
            CombatantView(
                name="Fighter",
                type="player",
                hp_current=20,
                hp_max=20,
                action_points_current=3,
                action_points_max=3,
                armor_class=15,
                is_active=True,
                is_conscious=True
            )
        ],
        battlefield=BattlefieldConfig(size="small", terrain="dungeon"),
        initiative_order=["Fighter"]
    )

    # Test player prompt building
    player_prompt = combat._build_player_prompt(request, current_ap=3, max_ap=3)
    assert "PLAYER REQUEST" in player_prompt
    assert "I attack" in player_prompt
    assert "Fighter" in player_prompt

    # Test NPC prompt building
    npc_prompt = combat._build_npc_prompt(request, current_ap=3, max_ap=3)
    assert "NPC TURN" in npc_prompt
    assert "Fighter" in npc_prompt

    print("✅ Prompt building works correctly")
