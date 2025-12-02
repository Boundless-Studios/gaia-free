"""Tests for combat initiator guardrail behavior."""

import pytest
from agents import RunContextWrapper

from gaia_private.agents.combat.initiator import (
    CombatInitiatorRunContext,
    validate_combat_initiator_output
)
from gaia_private.models.combat.agent_io.initiation import (
    CombatInitiation,
    BattlefieldConfig,
    CombatNarrative,
    CombatConditions
)


@pytest.mark.asyncio
async def test_validate_combat_initiator_backfills_scene_id():
    """Test that combat initiator guardrail backfills scene_id when missing."""

    # Create run context with expected_scene_id
    ctx = RunContextWrapper(context=CombatInitiatorRunContext(expected_scene_id="scene_campaign_48"))

    # Create combat output with empty scene_id
    combat_output = CombatInitiation(
        scene_id="",  # Empty - should be backfilled
        campaign_id="campaign_48",
        initiative_order=[],
        battlefield=BattlefieldConfig(),
        narrative=CombatNarrative(),
        conditions=CombatConditions(),
        opening_actions=[]
    )

    # Call the guardrail function directly
    result = await validate_combat_initiator_output.guardrail_function(ctx, agent=None, output=combat_output)

    # Verify scene_id was backfilled
    assert combat_output.scene_id == "scene_campaign_48", "Guardrail should backfill scene_id from context"

    # Verify guardrail didn't trigger tripwire
    assert result.tripwire_triggered == False, "Guardrail should not trigger tripwire for normal backfill"
