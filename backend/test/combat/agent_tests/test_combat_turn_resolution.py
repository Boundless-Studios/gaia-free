import unittest

from gaia_private.agents.combat.combat import Combat
from gaia_private.agents.combat.run_result import CombatRunResult
from gaia_private.models.combat.agent_io.fight.combat_action_request import CombatActionRequest
from gaia_private.models.combat.agent_io.fight.combatant_view import CombatantView
from gaia_private.models.combat.agent_io.fight.current_turn_info import CurrentTurnInfo
from gaia_private.models.combat.agent_io.initiation.battlefield_config import BattlefieldConfig
from gaia.mechanics.combat.combat_action_results import (
    TurnTransitionReason,
    TurnTransitionResult,
)
from gaia.models.combat.persistence.combat_session import CombatSession
from gaia.models.combat.persistence.combatant_state import CombatantState


class StubCombatEngine:
    def __init__(self):
        self.calls = []

    def resolve_turn_transition(
        self,
        current_actor,
        reason,
        request,
        *,
        turn_ended_by_action=False,
        remaining_ap=None
    ):
        resolved_reason = reason
        if isinstance(resolved_reason, str):
            resolved_reason = TurnTransitionReason(resolved_reason)
        if resolved_reason is None:
            if turn_ended_by_action or (remaining_ap is not None and remaining_ap <= 0):
                ap_value = remaining_ap if remaining_ap is not None else 0
                resolved_reason = (
                    TurnTransitionReason.AP_OVERDRAWN if ap_value < 0
                    else TurnTransitionReason.AP_EXHAUSTED
                )
            else:
                return None

        self.calls.append((current_actor, resolved_reason))
        return TurnTransitionResult(
            current_actor=current_actor,
            next_combatant="Theron the Mystic",
            reason=resolved_reason,
            new_round=False,
            round_number=request.current_turn.round_number,
            order_index=1
        )


def _build_request(active_name: str = "Lyra the Swift") -> CombatActionRequest:
    combatants = [
        CombatantView(
            name="Lyra the Swift",
            type="player",
            hp_current=26,
            hp_max=28,
            armor_class=14,
            action_points_current=4,
            action_points_max=4,
            is_active=True,
            is_conscious=True
        ),
        CombatantView(
            name="Theron the Mystic",
            type="enemy",
            hp_current=32,
            hp_max=32,
            armor_class=15,
            action_points_current=4,
            action_points_max=4,
            is_active=True,
            is_conscious=True
        ),
    ]

    return CombatActionRequest(
        campaign_id="camp",
        combat_id="combat",
        player_action="Lyra attacks",
        current_turn=CurrentTurnInfo(
            round_number=1,
            turn_number=1,
            active_combatant=active_name
        ),
        combatants=combatants,
        battlefield=BattlefieldConfig(terrain="arena"),
        initiative_order=["Lyra the Swift", "Theron the Mystic"],
        name_to_combatant_id={
            "Lyra the Swift": "pc:lyra",
            "Theron the Mystic": "npc:theron"
        }
    )


class CombatTurnResolutionTests(unittest.TestCase):
    def setUp(self):
        self.combat = Combat()
        self.stub_engine = StubCombatEngine()
        self.combat.combat_engine = self.stub_engine

    def test_advance_turn_handles_overdrawn_ap_via_actor_id(self):
        request = _build_request()
        initial = self.combat._capture_initial_state(request)
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
        for key in ["pc:lyra", "Lyra the Swift"]:
            final_ap[key] = {"current": -2, "max": 4}

        run_result.apply_final_state(
            hp=final_hp,
            ap=final_ap,
            statuses=final_status,
            defeated_aliases=[]
        )

        self.combat._advance_or_continue_turn(
            run_result=run_result,
            request=request
        )

        self.assertIsNotNone(run_result.turn_resolution)
        self.assertEqual(
            run_result.turn_resolution.reason,
            TurnTransitionReason.AP_OVERDRAWN
        )
        self.assertEqual(
            run_result.turn_resolution.next_combatant,
            "Theron the Mystic"
        )
        self.assertEqual(
            self.stub_engine.calls,
            [("Lyra the Swift", TurnTransitionReason.AP_OVERDRAWN)]
        )

    def test_advance_turn_continues_when_ap_remaining(self):
        request = _build_request()
        initial = self.combat._capture_initial_state(request)
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
        for key in ["pc:lyra", "Lyra the Swift"]:
            final_ap[key] = {"current": 2, "max": 4}

        run_result.apply_final_state(
            hp=final_hp,
            ap=final_ap,
            statuses=final_status,
            defeated_aliases=[]
        )

        self.combat._advance_or_continue_turn(
            run_result=run_result,
            request=request
        )

        self.assertIsNotNone(run_result.turn_resolution)
        self.assertEqual(
            run_result.turn_resolution.reason,
            TurnTransitionReason.TURN_CONTINUES
        )
        self.assertEqual(
            run_result.turn_resolution.next_combatant,
            "Lyra the Swift"
        )
        self.assertEqual(self.stub_engine.calls, [])

    def test_run_result_records_defeated_from_session(self):
        request = _build_request()

        session = CombatSession(session_id="session-1", scene_id="scene-1")
        session.combatants = {
            "pc:lyra": CombatantState(
                character_id="pc:lyra",
                name="Lyra the Swift",
                initiative=15,
                hp=18,
                max_hp=28,
                ac=14,
                is_npc=False
            ),
            "npc:theron": CombatantState(
                character_id="npc:theron",
                name="Theron the Mystic",
                initiative=12,
                hp=0,
                max_hp=32,
                ac=15,
                is_npc=True,
                is_conscious=False
            )
        }
        session.turn_order = ["pc:lyra", "npc:theron"]

        initial = self.combat._capture_initial_state(request)
        run_result = CombatRunResult()
        run_result.register_start_state(
            hp=initial["hp"],
            ap=initial["ap"],
            statuses=initial["statuses"],
            aliases=initial["aliases"]
        )

        final_hp = {}
        final_ap = {}
        final_status = {}
        defeated = []
        for state in session.combatants.values():
            hp = {"current": state.hp, "max": state.max_hp}
            ap_state = state.action_points
            ap = {
                "current": ap_state.current_ap if ap_state else None,
                "max": ap_state.max_ap if ap_state else None
            }
            statuses = []
            keys = {state.character_id, state.name}
            for key in keys:
                final_hp[key] = hp.copy()
                final_ap[key] = ap.copy()
                final_status[key] = list(statuses)
            if state.hp <= 0 or not state.is_conscious:
                defeated.extend(keys)

        run_result.apply_final_state(
            hp=final_hp,
            ap=final_ap,
            statuses=final_status,
            defeated_aliases=defeated
        )

        updates = run_result.to_combatant_updates()

        self.assertIn("npc:theron", run_result.defeated_combatants)
        self.assertIn("Theron the Mystic", run_result.defeated_combatants)
        self.assertEqual(updates["Theron the Mystic"]["hp_current"], 0)

    def test_run_result_fallback_without_session(self):
        request = _build_request()
        initial = self.combat._capture_initial_state(request)
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
        for key in ["npc:theron", "Theron the Mystic"]:
            final_hp[key]["current"] = 0

        run_result.apply_final_state(
            hp=final_hp,
            ap=final_ap,
            statuses=final_status,
            defeated_aliases=["npc:theron", "Theron the Mystic"]
        )

        updates = run_result.to_combatant_updates()
        self.assertEqual(updates["Theron the Mystic"]["hp_current"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
