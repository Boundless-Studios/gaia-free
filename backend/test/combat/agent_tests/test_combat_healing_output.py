"""Tests for healing integration in combat agent output formatting."""

from gaia_private.agents.combat import Combat
from gaia_private.agents.combat.run_result import CombatRunResult
from gaia_private.models.combat.agent_io.fight import (
    CombatActionRequest,
    CombatantView,
    CurrentTurnInfo,
)
from gaia_private.models.combat.agent_io.initiation import BattlefieldConfig


def test_normalize_output_includes_healing_hp():
    """Ensure healing updates are reflected in formatted combat status."""
    combat = Combat()

    request = CombatActionRequest(
        campaign_id="test-campaign",
        combat_id="combat-1",
        player_action="Cleric channels healing onto Fighter",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant="Cleric",
            available_actions=["heal"]
        ),
        combatants=[
            CombatantView(
                name="Cleric",
                type="player",
                hp_current=12,
                hp_max=18,
                armor_class=14,
                action_points_current=3,
                action_points_max=3,
                is_active=True,
                is_conscious=True
            ),
            CombatantView(
                name="Fighter",
                type="player",
                hp_current=10,
                hp_max=20,
                armor_class=16,
                action_points_current=2,
                action_points_max=3,
                is_active=True,
                is_conscious=True
            ),
        ],
        battlefield=BattlefieldConfig(terrain="forest", size="medium"),
        name_to_combatant_id={"Cleric": "cleric-id", "Fighter": "fighter-id"}
    )

    narrative_response = {
        "scene_description": "",
        "narrative": "",
        "combat_state": "ongoing",
        "next_turn_prompt": ""
    }

    initial = combat._capture_initial_state(request)
    run_result = CombatRunResult()
    run_result.register_start_state(
        hp=initial["hp"],
        ap=initial["ap"],
        statuses=initial["statuses"],
        aliases=initial["aliases"]
    )

    final_hp = {key: value.copy() for key, value in initial["hp"].items()}
    final_ap = {key: (value.copy() if value is not None else {"current": None, "max": None}) for key, value in initial["ap"].items()}
    final_status = {key: list(value) for key, value in initial["statuses"].items()}
    for key in ["fighter-id", "Fighter"]:
        final_hp[key]["current"] = 15

    run_result.apply_final_state(
        hp=final_hp,
        ap=final_ap,
        statuses=final_status,
        defeated_aliases=[]
    )

    response = combat._normalize_combat_output(
        narrative_response=narrative_response,
        run_result=run_result,
        request=request
    )

    assert "Fighter" in response.combat_status
    assert response.combat_status["Fighter"].hp == "15/20"
    assert response.run_result is run_result
