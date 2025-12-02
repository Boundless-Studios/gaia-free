"""Combat logging functionality.

This module handles logging for combat actions, agent requests/responses, and state transitions.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from gaia_private.models.combat.agent_io.fight import AgentCombatResponse

logger = logging.getLogger(__name__)


class CombatLogger:
    """Handles combat-specific logging operations."""

    def __init__(self, campaign_runner):
        """Initialize the combat logger.

        Args:
            campaign_runner: Reference to the campaign runner for accessing
                           combat state manager and logger instance.
        """
        self.campaign_runner = campaign_runner

    def get_logger_instance(self):
        """Return the combat logger instance if available."""
        if not hasattr(self.campaign_runner, 'combat_state_manager'):
            return None
        combat_state_manager = self.campaign_runner.combat_state_manager
        return getattr(combat_state_manager, 'logger', None)

    def log_combat_agent_request(
        self,
        campaign_id: str,
        session_id: Optional[str],
        model: str,
        request_context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Log a combat agent request.

        Args:
            campaign_id: Campaign identifier
            session_id: Combat session ID
            model: Model name being used
            request_context: Optional context data for the request

        Returns:
            Event ID if logged successfully, None otherwise
        """
        logger_instance = self.get_logger_instance()
        if not logger_instance or not session_id:
            return None

        try:
            return logger_instance.log_agent_request(
                session_id=session_id,
                campaign_id=campaign_id,
                agent_name="Combat Agent",
                model=model,
                context=request_context or {}
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to log combat agent request: %s", exc)
            return None

    def log_combat_agent_response(
        self,
        campaign_id: str,
        session_id: Optional[str],
        event_id: Optional[str],
        response: Optional[AgentCombatResponse],
        processing_time_ms: int
    ) -> None:
        """Log a combat agent response.

        Args:
            campaign_id: Campaign identifier
            session_id: Combat session ID
            event_id: Event ID from the request
            response: Agent combat response
            processing_time_ms: Processing time in milliseconds
        """
        logger_instance = self.get_logger_instance()
        if not logger_instance or not session_id:
            return

        try:
            response_payload: Any
            if response is not None:
                if hasattr(response, 'to_dict'):
                    response_payload = response.to_dict()
                else:
                    response_payload = response
            else:
                response_payload = None

            resolved_event_id = event_id or str(uuid.uuid4())

            logger_instance.log_agent_response(
                session_id=session_id,
                campaign_id=campaign_id,
                event_id=resolved_event_id,
                agent_name="Combat Agent",
                response=response_payload,
                time_ms=processing_time_ms
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to log combat agent response: %s", exc)

    def log_combat_action_details(self, combat_response: Any, combat_request: Any, campaign_id: Optional[str] = None, campaign_runner: Any = None) -> None:
        """Log detailed combat action results and status updates.

        Args:
            combat_response: The response from combat processing
            combat_request: The original combat request
            campaign_id: Campaign ID to get updated session state
            campaign_runner: Campaign runner to access combat state manager
        """
        # Log the action taken
        if hasattr(combat_response, 'narrative') and combat_response.narrative:
            current_actor = combat_request.current_turn.active_combatant if hasattr(combat_request, 'current_turn') else 'Unknown'
            logger.info(f"   ⚔️ ACTION: {current_actor}: {combat_response.narrative}")

        # Log action breakdown if available
        if hasattr(combat_response, 'action_breakdown') and combat_response.action_breakdown:
            for action in combat_response.action_breakdown:
                if hasattr(action, 'action_type'):
                    action_type = action.action_type
                    if hasattr(action, 'hit') and hasattr(action, 'damage'):
                        if action.hit:
                            logger.info(f"   📝 DETAIL: {action_type} - Hit! Damage: {action.damage}")
                        else:
                            logger.info(f"   📝 DETAIL: {action_type} - Miss!")
                    else:
                        logger.info(f"   📝 DETAIL: {action_type}")

                    # Log dice rolls if available
                    if hasattr(action, 'attack_roll'):
                        logger.info(f"   🎲 TO-HIT: Rolled {action.attack_roll}")
                    if hasattr(action, 'damage_roll'):
                        logger.info(f"   🎲 DAMAGE: Rolled {action.damage_roll}")

        # Log scene description/narrative if available
        if hasattr(combat_response, 'scene_description') and combat_response.scene_description:
            logger.info(f"   📜 NARRATIVE: {combat_response.scene_description}")

        # Try to get updated state from combat session if available
        updated_state_logged = False
        if campaign_id and campaign_runner and hasattr(campaign_runner, 'combat_state_manager'):
            combat_session = campaign_runner.combat_state_manager.get_active_combat(campaign_id)
            if combat_session and hasattr(combat_session, 'combatants'):
                logger.info("   💊 COMBATANT STATUS (Updated):")
                for cid, combatant in combat_session.combatants.items():
                    hp_info = f"HP={combatant.hp}/{combatant.max_hp}" if hasattr(combatant, 'hp') else "HP unknown"

                    # Get AP info from action_points object
                    if hasattr(combatant, 'action_points') and combatant.action_points:
                        ap_current = combatant.action_points.current_ap if hasattr(combatant.action_points, 'current_ap') else 0
                        ap_max = combatant.action_points.max_ap if hasattr(combatant.action_points, 'max_ap') else 3
                        ap_info = f"AP={ap_current}/{ap_max}"
                    else:
                        ap_info = ""

                    # Get conditions if any
                    conditions = ""
                    if hasattr(combatant, 'status_effects') and combatant.status_effects:
                        effect_names = [str(effect.effect_type.value if hasattr(effect.effect_type, 'value') else effect.effect_type)
                                      for effect in combatant.status_effects]
                        if effect_names:
                            conditions = f"Conditions: {', '.join(effect_names)}"

                    status_parts = [hp_info]
                    if ap_info:
                        status_parts.append(ap_info)
                    if conditions:
                        status_parts.append(conditions)
                    logger.info(f"      • {combatant.name}: {', '.join(status_parts)}")
                updated_state_logged = True

        # Fallback to response or request data if we couldn't get session state
        if not updated_state_logged:
            if hasattr(combat_response, 'combatant_updates') and combat_response.combatant_updates:
                logger.info("   💊 STATUS UPDATE:")
                for update in combat_response.combatant_updates:
                    if hasattr(update, 'name'):
                        hp_info = f"HP={update.hp_current}/{update.hp_max}" if hasattr(update, 'hp_current') else "HP unknown"
                        ap_info = f"AP={update.ap_current}/{update.ap_max}" if hasattr(update, 'ap_current') else ""
                        conditions = f"Conditions: {', '.join(update.conditions)}" if hasattr(update, 'conditions') and update.conditions else ""
                        status_parts = [hp_info]
                        if ap_info:
                            status_parts.append(ap_info)
                        if conditions:
                            status_parts.append(conditions)
                        logger.info(f"      • {update.name}: {', '.join(status_parts)}")
            elif hasattr(combat_request, 'combatants') and combat_request.combatants:
                # Fallback: log current status from request
                logger.info("   💊 COMBATANT STATUS:")
                for combatant in combat_request.combatants[:5]:  # Show first 5 to avoid spam
                    hp_info = f"HP={combatant.hp_current}/{combatant.hp_max}" if hasattr(combatant, 'hp_current') else "HP unknown"
                    ap_info = f"AP={combatant.action_points_current}/{combatant.action_points_max}" if hasattr(combatant, 'action_points_current') and combatant.action_points_current is not None else ""
                    status_parts = [hp_info]
                    if ap_info:
                        status_parts.append(ap_info)
                    logger.info(f"      • {combatant.name}: {', '.join(status_parts)}")

    def log_action_result(
        self,
        session_id: str,
        campaign_id: str,
        action: Dict[str, Any],
        time_ms: int = 0,
        turn_id: Optional[str] = None
    ) -> None:
        """Log an action result.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign identifier
            action: Action dictionary with details
            time_ms: Processing time in milliseconds
            turn_id: Optional turn ID to link the action to
        """
        logger_instance = self.get_logger_instance()
        if not logger_instance or not session_id:
            return

        # Add turn_id to action if provided
        if turn_id:
            action = dict(action)  # Make a copy to avoid mutating original
            action['turn_id'] = turn_id

        try:
            logger_instance.log_action_result(
                session_id=session_id,
                campaign_id=campaign_id,
                action=action,
                time_ms=time_ms
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to log action result: %s", exc)

    def log_state_transition(
        self,
        session_id: str,
        campaign_id: str,
        state_before: Dict[str, Any],
        state_after: Dict[str, Any],
        transition_type: str
    ) -> None:
        """Log a state transition.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign identifier
            state_before: State before transition
            state_after: State after transition
            transition_type: Type of transition
        """
        logger_instance = self.get_logger_instance()
        if not logger_instance or not session_id:
            return

        try:
            logger_instance.log_state_transition(
                session_id=session_id,
                campaign_id=campaign_id,
                state_before=state_before,
                state_after=state_after,
                transition_type=transition_type
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to log state transition: %s", exc)

    def log_user_input(
        self,
        session_id: str,
        campaign_id: str,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log user input.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign identifier
            user_input: User's input text
            context: Optional context data
        """
        logger_instance = self.get_logger_instance()
        if not logger_instance or not session_id:
            return

        try:
            logger_instance.log_user_input(
                session_id=session_id,
                campaign_id=campaign_id,
                user_input=user_input,
                context=context or {}
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to log user input: %s", exc)

    def log_dice_roll(
        self,
        session_id: str,
        campaign_id: str,
        roll_type: str,
        dice_expr: str,
        result: int,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a dice roll.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign identifier
            roll_type: Type of roll (attack, damage, save, etc.)
            dice_expr: Dice expression (e.g., "1d20+5")
            result: Final result of the roll
            details: Optional additional details
        """
        logger_instance = self.get_logger_instance()
        if not logger_instance or not session_id:
            return

        try:
            logger_instance.log_dice_roll(
                session_id=session_id,
                campaign_id=campaign_id,
                roll_type=roll_type,
                dice_expr=dice_expr,
                result=result,
                details=details or {}
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to log dice roll: %s", exc)

    def log_combat_action(
        self,
        campaign_id: str,
        combat_session,
        request,
        response,
        user_input: str,
        processing_time_ms: int,
        turn_id: Optional[str] = None
    ) -> None:
        """Log a combat action and state transition.

        Args:
            campaign_id: Campaign identifier
            combat_session: Active combat session
            request: Combat action request
            response: Combat action response
            user_input: Original user input
            processing_time_ms: Processing time in milliseconds
            turn_id: Optional turn ID to link the action to
        """
        if not combat_session:
            return

        # Create action dict from the request and response
        action_dict = {
            "action_type": "combat_action",
            "actor": request.current_turn.active_combatant if request and request.current_turn else "unknown",
            "user_input": user_input,
            "narrative": response.narrative if response else "",
            "combat_state": response.combat_state if response else "ongoing"
        }

        # Log the action result
        self.log_action_result(
            combat_session.session_id,
            campaign_id,
            action_dict,
            processing_time_ms,
            turn_id
        )

        # Log state transition if available
        if response and hasattr(response, 'combat_status'):
            state_before = {"combatants": request.combatants} if request else {}
            state_after = {"combat_status": response.combat_status}
            self.log_state_transition(
                combat_session.session_id,
                campaign_id,
                state_before,
                state_after,
                "combat_turn"
            )