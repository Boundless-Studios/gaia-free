"""Combat output formatting functionality.

This module handles formatting combat responses for the frontend.
"""

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from gaia_private.models.combat.agent_io.fight import (
    AgentCombatResponse,
    AgentCharacterStatus,
    CombatActionRequest,
    CombatantView
)
from gaia_private.models.combat.agent_io.initiation import CombatInitiation
from gaia.models.combat.mechanics.action_definitions import (
    ActionName,
    format_available_actions,
)


class CombatFormatter:
    """Handles combat response formatting for frontend display."""

    def format_combat_response(
        self,
        combat_response: AgentCombatResponse,
        request: CombatActionRequest,
        combat_session: Any = None
    ) -> Dict[str, Any]:
        """Format CombatAgent response for the frontend.

        Args:
            combat_response: Raw response from CombatAgent
            request: The original combat action request
            combat_session: Optional combat session with current state (for AP reset)

        Returns:
            Formatted response with structured_data for the frontend
        """
        run_result = getattr(combat_response, "run_result", None)

        # Extract what happened (answer)
        active_combatant = request.current_turn.active_combatant

        # Build answer with scene description first (vivid narrative), then action narrative, then turn prompt
        scene_description = combat_response.scene_description or ""
        action_narrative = combat_response.narrative or ""
        next_turn_prompt = getattr(combat_response, 'next_turn_prompt', '')

        # Combine: vivid scene description + action narrative + turn prompt
        answer_parts = []
        if scene_description:
            answer_parts.append(scene_description)
        if action_narrative:
            answer_parts.append(action_narrative)
        if next_turn_prompt:
            answer_parts.append(next_turn_prompt)

        answer = "\n\n".join(answer_parts) if answer_parts else f"{active_combatant} acts."

        # Build narrative without combat status (status is now in structured combat_status field)
        narrative_parts = []
        if scene_description:
            narrative_parts.append(scene_description)
        if action_narrative:
            narrative_parts.append(action_narrative)

        narrative = "\n\n".join(narrative_parts) if narrative_parts else ""

        turn_resolution = combat_response.turn_resolution
        
        # Build combat_status - always use session state if available (it has the correct state after turn transition)
        combat_status_dict = {}
        if combat_session and hasattr(combat_session, 'combatants'):
            # Rebuild combat_status from session (which has correct AP/HP after turn transition)
            for combatant_state in combat_session.combatants.values():
                status_dict = {
                    "hp": f"{combatant_state.hp}/{combatant_state.max_hp}",
                    "hostile": getattr(combatant_state, 'hostile', False),
                    "status": [eff.effect_type.value if hasattr(eff.effect_type, 'value') else str(eff.effect_type)
                              for eff in combatant_state.status_effects]
                }
                # Add AP if available
                if combatant_state.action_points:
                    status_dict["ap"] = f"{combatant_state.action_points.current_ap}/{combatant_state.action_points.max_ap}"
                else:
                    status_dict["ap"] = "Unknown"

                combat_status_dict[combatant_state.name] = status_dict
        else:
            if run_result is not None:
                name_to_id = getattr(request, 'name_to_combatant_id', {}) or {}

                for combatant in request.combatants:
                    name = combatant.name
                    identifier = name_to_id.get(name, name)

                    hp_data = None
                    ap_data = None
                    status_entries: List[str] = []

                    if hasattr(run_result, 'get_authoritative_hp'):
                        hp_data = run_result.get_authoritative_hp(identifier) or run_result.get_authoritative_hp(name)
                    if hasattr(run_result, 'get_authoritative_ap'):
                        ap_data = run_result.get_authoritative_ap(identifier) or run_result.get_authoritative_ap(name)
                    if hasattr(run_result, 'status_end'):
                        status_entries = run_result.status_end.get(identifier) or run_result.status_end.get(name) or []

                    status_dict = {
                        "hp": "Unknown",
                        "ap": "Unknown",
                        "status": list(status_entries),
                        "hostile": getattr(combatant, 'hostile', False)
                    }

                    if hp_data:
                        current = hp_data.get("current")
                        maximum = hp_data.get("max")
                        if current is not None and maximum is not None:
                            status_dict["hp"] = f"{current}/{maximum}"

                    if ap_data:
                        current_ap = ap_data.get("current")
                        max_ap = ap_data.get("max")
                        if current_ap is not None and max_ap is not None:
                            status_dict["ap"] = f"{current_ap}/{max_ap}"

                    combat_status_dict[name] = status_dict

            else:
                # Fallback to combat_response combat_status only if no session available and no run_result
                for name, status in combat_response.combat_status.items():
                    if isinstance(status, AgentCharacterStatus):
                        combat_status_dict[name] = asdict(status)
                    elif isinstance(status, dict):
                        combat_status_dict[name] = status
                    else:
                        combat_status_dict[name] = {
                            "hp": getattr(status, 'hp', "Unknown"),
                            "ap": getattr(status, 'ap', "Unknown"),
                            "status": getattr(status, 'status', [])
                        }

        # Always show current turn info, not the next turn
        # The frontend will handle the transition when appropriate
        current_combatant_name = active_combatant
        current_round = request.current_turn.round_number
        current_turn_number = getattr(request.current_turn, "turn_number", 1)

        # Get character_id from name_to_combatant_id mapping
        name_to_id = getattr(request, 'name_to_combatant_id', {}) or {}
        character_id = name_to_id.get(current_combatant_name, current_combatant_name)

        # Use player_options if available, otherwise use next_turn_prompt as fallback
        player_options = getattr(combat_response, 'player_options', [])
        if player_options:
            turn = player_options
        elif next_turn_prompt:
            turn = next_turn_prompt
        else:
            # Fallback turn message
            turn = f"It is {current_combatant_name}'s turn."

        # Build initiative order names for UI display
        initiative_names: List[str] = []
        if combat_session and hasattr(combat_session, "turn_order"):
            for cid in combat_session.turn_order:
                state = combat_session.combatants.get(cid)
                initiative_names.append(state.name if state else cid)
        elif getattr(request, "initiative_order", None):
            initiative_names = list(request.initiative_order)
        else:
            initiative_names = [
                combatant.name for combatant in request.combatants if getattr(combatant, "name", None)
            ]

        # Determine if current turn is an NPC turn
        is_npc_turn = False
        if combat_session and hasattr(combat_session, 'combatants'):
            current_combatant_state = combat_session.combatants.get(character_id)
            if current_combatant_state:
                is_npc_turn = getattr(current_combatant_state, 'is_npc', False)

        turn_info = {
            "turn_id": f"{character_id}-r{current_round}-t{current_turn_number}" if character_id else f"turn-r{current_round}-t{current_turn_number}",
            "character_id": character_id,
            "character_name": current_combatant_name,
            "active_combatant": current_combatant_name,
            "round": current_round,
            "round_number": current_round,
            "turn_number": current_turn_number,
            "available_actions": request.current_turn.available_actions or [],
            "initiative_order": initiative_names,
            "is_combat": True,
            "is_npc_turn": is_npc_turn,
        }
        combat_session_id = getattr(combat_session, "session_id", None)
        if combat_session_id:
            turn_info["combat_session_id"] = combat_session_id

        combat_state_payload: Dict[str, Any] = {
            "state": combat_response.combat_state or "ongoing",
            "is_active": (combat_response.combat_state or "ongoing").lower() in {"ongoing", "active"},
            "round_number": current_round,
            "turn_number": current_turn_number,
            "initiative_order": initiative_names,
        }
        if combat_session_id:
            combat_state_payload.update({
                "session_id": combat_session_id,
                "turn_index": getattr(combat_session, "current_turn_index", 0),
                "turn_order_ids": list(getattr(combat_session, "turn_order", [])),
            })

        return {
            "structured_data": {
                "answer": answer,
                "narrative": narrative,
                "turn": turn,
                "combat_status": combat_status_dict,  # Structured combat status
                "combat_state": combat_state_payload,
                "action_breakdown": [asdict(action) for action in combat_response.action_breakdown] if hasattr(combat_response, 'action_breakdown') and combat_response.action_breakdown else None,
                "turn_info": turn_info,
                "turn_resolution": turn_resolution.to_dict() if turn_resolution and hasattr(turn_resolution, 'to_dict') else turn_resolution
            },
            "timestamp": datetime.now().isoformat()
        }

    def format_scene_response(
        self,
        agent_response: Any,
        interaction_type: str,
        combat_session: Any = None
    ) -> Dict[str, Any]:
        """Format scene agent response to match DM response structure.

        Args:
            agent_response: Raw response from scene agent (dict or CombatInitiation model)
            interaction_type: Type of interaction
            combat_session: Optional combat session with actual HP/AP data

        Returns:
            Formatted response matching DM structure
        """
        # Handle both dict and CombatInitiation pydantic model
        status = ""
        turn_info: Optional[Dict[str, Any]] = None
        combat_state_payload: Optional[Dict[str, Any]] = None
        initiative_names: List[str] = []
        first_combatant_name: Optional[str] = None
        first_combatant_initiative: Optional[int] = None

        if hasattr(agent_response, 'narrative'):
            # It's a CombatInitiation pydantic model
            narrative = ""
            answer = ""

            # Extract narrative from the model
            if agent_response.narrative:
                try:
                    narrative = agent_response.to_narrative_text()
                except Exception:  # pragma: no cover - defensive
                    scene_desc = agent_response.narrative.scene_description or ""
                    enemy_desc = agent_response.narrative.enemy_description or ""
                    narrative = "\n".join(filter(None, [scene_desc, enemy_desc]))
                # Answer should be distinct from narrative - use combat_trigger only
                answer = agent_response.narrative.combat_trigger or ""

            # Build turn information from initiative order
            turn = ""
            combat_status_dict = {}
            if agent_response.initiative_order:
                first_combatant = agent_response.initiative_order[0]
                if first_combatant and hasattr(first_combatant, 'name'):
                    first_combatant_name = first_combatant.name
                    first_combatant_initiative = getattr(first_combatant, "initiative", None)
                    turn = f"Combat begins! {first_combatant.name} goes first."

                initiative_names = [
                    entry.name for entry in agent_response.initiative_order if hasattr(entry, "name")
                ]

                # Build combat_status from combat session if available, otherwise from initiative
                if combat_session and hasattr(combat_session, 'combatants'):
                    for combatant_state in combat_session.combatants.values():
                        status_dict = {
                            "hp": f"{combatant_state.hp}/{combatant_state.max_hp}",
                            "status": [eff.effect_type.value if hasattr(eff.effect_type, 'value') else str(eff.effect_type)
                                      for eff in combatant_state.status_effects],
                            "hostile": getattr(combatant_state, 'hostile', False)
                        }
                        if combatant_state.action_points:
                            status_dict["ap"] = f"{combatant_state.action_points.current_ap}/{combatant_state.action_points.max_ap}"
                        else:
                            status_dict["ap"] = "Unknown"
                        combat_status_dict[combatant_state.name] = status_dict
                    if not initiative_names and hasattr(combat_session, "turn_order"):
                        for cid in combat_session.turn_order:
                            state = combat_session.combatants.get(cid)
                            initiative_names.append(state.name if state else cid)
                else:
                    # Fallback: create basic structure from initiative order
                    # Note: initiative_names was already populated above (line 274-276)
                    for combatant in agent_response.initiative_order:
                        if hasattr(combatant, 'name'):
                            combat_status_dict[combatant.name] = {
                                "hp": "Unknown",
                                "ap": "Unknown",
                                "status": [],
                                "hostile": getattr(combatant, "hostile", False)
                            }
            status = self._summarize_initiative_order(agent_response.initiative_order)
        else:
            # It's a dict (fallback for compatibility)
            narrative = ''
            answer = ''
            combat_status_dict = {}
            if isinstance(agent_response, dict):
                narrative_dict = agent_response.get('narrative') if isinstance(agent_response.get('narrative'), dict) else {}
                scene_description = narrative_dict.get('scene_description') if narrative_dict else None
                enemy_description = narrative_dict.get('enemy_description') if narrative_dict else None
                combat_trigger = narrative_dict.get('combat_trigger') if narrative_dict else None

                narrative_candidates = [scene_description, enemy_description, agent_response.get('narrative_text')]
                narrative = "\n\n".join(filter(None, narrative_candidates))
                answer = combat_trigger or agent_response.get('response', '') or (scene_description or '')

                status = self._summarize_initiative_order(agent_response.get('initiative_order', []))

                # Build combat_status from combat session if available
                initiative_order = agent_response.get('initiative_order', [])
                if combat_session and hasattr(combat_session, 'combatants'):
                    for combatant_state in combat_session.combatants.values():
                        status_dict = {
                            "hp": f"{combatant_state.hp}/{combatant_state.max_hp}",
                            "status": [eff.effect_type.value if hasattr(eff.effect_type, 'value') else str(eff.effect_type)
                                      for eff in combatant_state.status_effects],
                            "hostile": getattr(combatant_state, 'hostile', False)
                        }
                        if combatant_state.action_points:
                            status_dict["ap"] = f"{combatant_state.action_points.current_ap}/{combatant_state.action_points.max_ap}"
                        else:
                            status_dict["ap"] = "Unknown"
                        combat_status_dict[combatant_state.name] = status_dict
                    if not initiative_names and hasattr(combat_session, "turn_order"):
                        for cid in combat_session.turn_order:
                            state = combat_session.combatants.get(cid)
                            initiative_names.append(state.name if state else cid)
                elif initiative_order:
                    # Fallback from initiative order
                    for combatant in initiative_order:
                        if isinstance(combatant, dict) and combatant.get('name'):
                            name = combatant['name']
                            initiative_names.append(name)
                            combat_status_dict[name] = {
                                "hp": "Unknown",
                                "ap": "Unknown",
                                "status": [],
                                "hostile": combatant.get('hostile', False)
                            }
            else:
                narrative = ''
                answer = ''

            # Build turn information
            turn = ""
            if isinstance(agent_response, dict) and 'initiative_order' in agent_response:
                first_combatant = agent_response['initiative_order'][0] if agent_response['initiative_order'] else {}
                if isinstance(first_combatant, dict) and first_combatant.get('name'):
                    first_combatant_name = first_combatant['name']
                    first_combatant_initiative = first_combatant.get('initiative')
                    turn = f"Combat begins! {first_combatant['name']} goes first."

        # Derive turn metadata when we have initiative context
        if initiative_names or (combat_session and hasattr(combat_session, "turn_order") and combat_session.turn_order):
            round_number = getattr(combat_session, "round_number", 1)
            turn_number = getattr(combat_session, "current_turn_index", 0) + 1 if combat_session else 1
            session_id = getattr(combat_session, "session_id", None)

            active_id = None
            active_name = None
            if combat_session and hasattr(combat_session, "resolve_current_character"):
                active_id = combat_session.resolve_current_character()
                active_state = combat_session.combatants.get(active_id) if active_id else None
                active_name = active_state.name if active_state else None

            if not active_name:
                active_name = first_combatant_name or (initiative_names[0] if initiative_names else None)

            if combat_session and not initiative_names and hasattr(combat_session, "turn_order"):
                for cid in combat_session.turn_order:
                    state = combat_session.combatants.get(cid)
                    initiative_names.append(state.name if state else cid)

            if not active_id:
                if combat_session and active_name:
                    for cid, state in combat_session.combatants.items():
                        if state.name == active_name:
                            active_id = cid
                            break
                elif active_name:
                    active_id = active_name

            # Determine if first turn is an NPC turn
            is_npc_turn = False
            if combat_session and hasattr(combat_session, 'combatants') and active_id:
                active_state = combat_session.combatants.get(active_id)
                if active_state:
                    is_npc_turn = getattr(active_state, 'is_npc', False)

            turn_info = {
                "turn_id": f"{active_id}-r{round_number}-t{turn_number}" if active_id else f"turn-r{round_number}-t{turn_number}",
                "character_id": active_id,
                "character_name": active_name,
                "active_combatant": active_name,
                "round": round_number,
                "round_number": round_number,
                "turn_number": turn_number,
                "available_actions": [],
                "initiative_order": initiative_names,
                "is_combat": True,
                "phase": "combat_initiation",
                "is_npc_turn": is_npc_turn,
            }
            if first_combatant_initiative is not None:
                turn_info["initiative"] = first_combatant_initiative
            if session_id:
                turn_info["combat_session_id"] = session_id

            combat_state_payload = {
                "state": "ongoing",
                "phase": "combat_initiation",
                "is_active": True,
                "round_number": round_number,
                "turn_number": turn_number,
                "initiative_order": initiative_names,
            }
            if session_id:
                combat_state_payload.update({
                    "session_id": session_id,
                    "turn_index": getattr(combat_session, "current_turn_index", 0),
                    "turn_order_ids": list(getattr(combat_session, "turn_order", [])),
                })

        return {
            "structured_data": {
                "answer": answer,
                "narrative": narrative,
                "turn": turn,
                "status": status,
                "combat_status": combat_status_dict,  # Always include, even if empty dict
                "interaction_type": interaction_type,
                "turn_info": turn_info,
                "combat_state": combat_state_payload
            },
            "timestamp": datetime.now().isoformat()
        }

    def _format_combat_status(self, combat_status: Dict[str, Any]) -> str:
        """Format combat status dictionary into a string.

        Args:
            combat_status: Dictionary of combatant statuses

        Returns:
            Formatted status string
        """
        if not combat_status:
            return ""

        status_lines = []
        for name, status in combat_status.items():
            hp = "Unknown"
            ap = "Unknown"
            conditions = []

            if isinstance(status, dict):
                hp = status.get('hp', hp)
                ap = status.get('ap', ap)
                conditions = status.get('status', conditions)
            elif isinstance(status, AgentCharacterStatus):
                hp = status.hp or hp
                ap = status.ap or ap
                conditions = status.status or conditions
            else:  # pragma: no cover - defensive fallback for unexpected types
                try:
                    hp = getattr(status, 'hp', hp)
                    ap = getattr(status, 'ap', ap)
                    conditions = getattr(status, 'status', conditions)
                except Exception:
                    pass

            line = f"{name}: HP={hp}, AP={ap}"
            if conditions:
                line += f", Conditions: {', '.join(conditions)}"
            status_lines.append(line)

        return "\n".join(status_lines)

    def _generate_turn_options(self, combatant_name: str, combatants: List[CombatantView]) -> str:
        """Generate available turn options for a combatant.

        Args:
            combatant_name: Name of the combatant
            combatants: List of all combatants

        Returns:
            String describing available actions
        """
        combatant = next((c for c in combatants if c.name == combatant_name), None)
        if combatant and combatant.action_points_current is not None:
            return format_available_actions(combatant.action_points_current)
        return "Available actions: Move (1 AP), Attack (2 AP), End Turn (0 AP)"

    def _get_next_combatant(self, current_combatant: str, initiative_order: List[str]) -> str:
        """Determine the next combatant in initiative order.

        Args:
            current_combatant: Name of the current active combatant
            initiative_order: List of combatant names in turn order

        Returns:
            Name of the next combatant to act
        """
        if not initiative_order:
            return current_combatant

        try:
            current_index = initiative_order.index(current_combatant)
            next_index = (current_index + 1) % len(initiative_order)
            return initiative_order[next_index]
        except ValueError:
            # Current combatant not in initiative order, return first in order
            return initiative_order[0] if initiative_order else current_combatant

    def _summarize_initiative_order(self, initiative_order: List[Any]) -> str:
        """Generate a readable summary of the initiative order."""
        if not initiative_order:
            return ""

        lines: List[str] = []
        for idx, entry in enumerate(initiative_order, start=1):
            name = getattr(entry, 'name', None)
            if name is None and isinstance(entry, dict):
                name = entry.get('name')
            if not name:
                continue

            is_player = getattr(entry, 'is_player', None)
            if isinstance(entry, dict):
                is_player = entry.get('is_player', is_player)
            if is_player is True:
                role = 'PC'
            elif is_player is False:
                role = 'Enemy'
            else:
                role = 'NPC'

            initiative_value = getattr(entry, 'initiative', None)
            if isinstance(entry, dict):
                initiative_value = entry.get('initiative', initiative_value)

            surprised = getattr(entry, 'is_surprised', False)
            if isinstance(entry, dict):
                surprised = entry.get('is_surprised', surprised)

            initiative_text = f"Init {initiative_value}" if initiative_value is not None else "Init ?"
            surprised_text = " (surprised)" if surprised else ""

            lines.append(f"{idx}. {name} [{role}] - {initiative_text}{surprised_text}")

        return "\n".join(lines)
