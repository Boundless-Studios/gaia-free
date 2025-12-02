"""Combat state management for action point system."""
import logging
import uuid
import time
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime

from gaia.models.combat import (
    CombatSession, CombatantState, CombatAction,
    CombatStatus, StatusEffect
)
from gaia_private.models.combat.agent_io.initiation import BattlefieldConfig, OpeningAction, InitiativeEntry
from gaia.models.combat.mechanics.action_points import ActionPointConfig, ActionPointState
from gaia.models.combat.mechanics.action_definitions import ActionName
from gaia.models.character.character_info import CharacterInfo
from gaia.mechanics.combat.combat_engine import CombatEngine
from gaia.mechanics.combat.combat_persistence import CombatPersistenceManager
from gaia.mechanics.combat.combat_session_logger import CombatLogger
from gaia.models.turn import TurnAction as TurnLogAction

if TYPE_CHECKING:
    from gaia_private.models.combat.orchestration import CombatCachedPayload

logger = logging.getLogger(__name__)


def _normalize_action_name(name: Any) -> str:
    if isinstance(name, ActionName):
        return name.value
    return str(name)


def _format_display_name(action_id: str) -> str:
    return action_id.replace("_", " ").title()


def _build_turn_action(
    action_id: str,
    description: Optional[str] = None,
    ap_cost: Optional[int] = None
) -> TurnLogAction:
    cost = {"ap": ap_cost} if ap_cost is not None else None
    return TurnLogAction(
        action_id=action_id,
        name=_format_display_name(action_id),
        description=description or _format_display_name(action_id),
        cost=cost
    )


class CombatStateManager:
    """Manages combat session state and persistence."""

    def __init__(self, campaign_manager=None, turn_manager=None, auto_recover: bool = False):
        """Initialize the combat state manager.

        Args:
            campaign_manager: Campaign manager for accessing storage paths
            turn_manager: Turn manager for updating turn state with combat results
            auto_recover: When True, eagerly load all active combat sessions from disk.
        """
        self.active_sessions: Dict[str, CombatSession] = {}
        self.session_campaign_map: Dict[str, str] = {}
        # Import here to avoid circular dependency
        from gaia_private.models.combat.orchestration import CombatCachedPayload
        self.initialized_combat: Dict[str, CombatCachedPayload] = {}  # Store initialized but not started combat
        self.combat_engine = CombatEngine()
        self.ap_config = ActionPointConfig()
        self.campaign_manager = campaign_manager
        self.turn_manager = turn_manager
        self._auto_recover = auto_recover

        # Initialize persistence and logging
        if campaign_manager:
            self.persistence = CombatPersistenceManager(campaign_manager)
            self.logger = CombatLogger(campaign_manager)
            if auto_recover:
                self._recover_active_sessions()
        else:
            self.persistence = None
            self.logger = None

    def _recover_active_sessions(self):
        """Load any active combat sessions from disk on startup."""
        if self.persistence:
            recovered = self.persistence.recover_active_sessions()
            for campaign_id, session in recovered.items():
                self.active_sessions[session.session_id] = session
                self.session_campaign_map[session.session_id] = campaign_id
                logger.info(f"Recovered combat session {session.session_id} for campaign {campaign_id}")

    def recover_all_active_sessions(self) -> None:
        """Public helper to eagerly recover all active combat sessions."""
        self._recover_active_sessions()

    def initialize_combat(
        self,
        scene_id: str,
        characters: List[CharacterInfo],
        battlefield_config: Optional[Dict[str, Any]] = None,
        campaign_id: Optional[str] = None
    ) -> CombatSession:
        """
        Initialize a new combat session.

        Args:
            scene_id: ID of the scene where combat occurs
            characters: List of characters involved in combat
            battlefield_config: Optional battlefield configuration
            campaign_id: Campaign ID for persistence

        Returns:
            Initialized CombatSession
        """
        # Use simple session ID format: scene_id - round #
        # Count existing combats for this scene to generate unique ID
        counter = 1
        if self.persistence and campaign_id:
            import os
            combat_path = self.persistence.get_combat_path(campaign_id)
            if combat_path:
                active_dir = combat_path / "active"
                if active_dir.exists():
                    existing = [f for f in os.listdir(active_dir) if f.startswith(f"{scene_id} - ")]
                    counter = len(existing) + 1

        session_id = f"{scene_id} - round {counter}"
        logger.info(f"Initializing combat session {session_id} for scene {scene_id}")

        # Log initialization
        if self.logger and campaign_id:
            self.logger.log_user_input(
                session_id, campaign_id,
                f"Initialize combat with {len(characters)} characters",
                {"scene_id": scene_id, "character_count": len(characters)}
            )

        # Create battlefield
        battlefield = None
        if battlefield_config:
            if isinstance(battlefield_config, dict):
                battlefield = BattlefieldConfig.from_dict(battlefield_config)
            else:
                battlefield = battlefield_config

        # Initialize combat session
        combat_session = CombatSession(
            session_id=session_id,
            scene_id=scene_id,
            status=CombatStatus.INITIALIZING,
            battlefield=battlefield
        )

        # Initialize combatants
        for character in characters:
            combatant = self.combat_engine.initialize_combatant(character)
            combat_session.add_combatant(combatant)
            logger.debug(f"Added combatant: {combatant.name} (Initiative: {combatant.initiative})")

        # Set initial turn
        if combat_session.turn_order:
            combat_session.current_turn_index = 0
            logger.info(f"Combat turn order: {combat_session.turn_order}")

        # Mark as in progress
        combat_session.status = CombatStatus.IN_PROGRESS

        # Store session
        self.active_sessions[session_id] = combat_session
        if campaign_id:
            self.session_campaign_map[session_id] = campaign_id

        # Save to disk
        if self.persistence and campaign_id:
            self.persistence.save_combat_session(campaign_id, combat_session)

        # Log state transition
        if self.logger and campaign_id:
            self.logger.log_state_transition(
                session_id, campaign_id,
                {"status": "initializing"},
                {"status": "in_progress", "combatants": len(combat_session.combatants)},
                "initialize_combat"
            )

        return combat_session

    def apply_initiative_order(
        self,
        combat_session: CombatSession,
        initiative_entries: List[InitiativeEntry],
        name_to_combatant_id: Dict[str, str],
        campaign_id: Optional[str] = None
    ) -> None:
        """Align session initiative order with agent-determined results."""

        if not combat_session or not initiative_entries:
            return

        # Build reverse lookup so we can fall back to matching by name
        session_name_to_id = {
            state.name: cid for cid, state in combat_session.combatants.items()
        }

        resolved_order: List[str] = []
        for entry in initiative_entries:
            combatant_id = name_to_combatant_id.get(entry.name) or session_name_to_id.get(entry.name)
            if not combatant_id:
                logger.warning("Unable to match initiative entry '%s' to combatant id", entry.name)
                continue

            combatant_state = combat_session.combatants.get(combatant_id)
            if not combatant_state:
                logger.warning("Combatant state missing for id %s (entry %s)", combatant_id, entry.name)
                continue

            combatant_state.initiative = entry.initiative
            resolved_order.append(combatant_id)

        if not resolved_order:
            logger.debug("No initiative overrides applied; keeping existing turn order")
            return

        # Append any combatants not present in the initiative entries to preserve participation
        remaining_ids = [
            cid for cid in combat_session.turn_order
            if cid not in resolved_order
        ]

        combat_session.turn_order = resolved_order + remaining_ids
        combat_session.current_turn_index = 0

        if self.persistence and campaign_id:
            self.persistence.save_combat_session(campaign_id, combat_session)

    def apply_opening_actions(
        self,
        combat_session: CombatSession,
        opening_actions: List[OpeningAction],
        name_to_combatant_id: Dict[str, str],
        campaign_id: Optional[str] = None
    ) -> List[CombatAction]:
        """Resolve and apply opening actions before the first combat round.

        Args:
            combat_session: Active combat session to mutate
            opening_actions: Declarative opening actions from CombatInitiation
            name_to_combatant_id: Mapping from combatant names to session character IDs
            campaign_id: Campaign identifier for persistence/logging

        Returns:
            List of resolved CombatAction records generated for round 0
        """

        if not opening_actions:
            return []

        resolved_actions: List[CombatAction] = []
        original_round = combat_session.round_number

        for action in opening_actions:
            actor_id = name_to_combatant_id.get(action.actor)
            if not actor_id:
                logger.warning("Opening action actor not found in session: %s", action.actor)
                continue

            target_id = None
            if action.target:
                target_id = name_to_combatant_id.get(action.target)
                if action.target and not target_id:
                    logger.warning("Opening action target not found: %s", action.target)

            actor_state = combat_session.combatants.get(actor_id)
            if not actor_state:
                logger.warning("Combatant state missing for actor %s", actor_id)
                continue

            # Ensure actor starts with full AP for the actual first turn
            if actor_state.action_points:
                actor_state.action_points.reset_turn()

            # Temporarily mark as round 0 for logging
            combat_session.round_number = 0
            try:
                combat_action = self.combat_engine.process_action(
                    combat_session=combat_session,
                    actor_id=actor_id,
                    action_type=action.action_type,
                    target_id=target_id
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                combat_session.round_number = original_round
                logger.warning("Failed to resolve opening action %s -> %s: %s", action.actor, action.target, exc)
                continue

            # Mark the action as round 0 explicitly
            combat_action.round_number = 0
            resolved_actions.append(combat_action)

            # Update opening action with deterministic results
            action.success = combat_action.success
            action.hit = combat_action.success if combat_action.action_type == "basic_attack" else None
            action.damage = combat_action.damage_dealt
            action.ap_cost = combat_action.ap_cost
            action.roll = combat_action.roll_result
            action.effects_applied = list(combat_action.effects_applied or [])
            action.resolution_summary = combat_action.description or action.description

            # Reset AP for the actor so round one starts fresh
            if actor_state.action_points:
                actor_state.action_points.reset_turn()

        # Restore round number
        combat_session.round_number = original_round

        # Persist mutated session state if possible
        if resolved_actions and self.persistence and campaign_id:
            self.persistence.save_combat_session(campaign_id, combat_session)

        return resolved_actions

    def get_active_combat(self, campaign_id: str) -> Optional[CombatSession]:
        """Get the active combat session for a campaign."""
        if not campaign_id:
            return None

        for session_id, session in list(self.active_sessions.items()):
            if self.session_campaign_map.get(session_id) == campaign_id and session.status == CombatStatus.IN_PROGRESS:
                return session

        if self.persistence:
            session = self.persistence.load_active_combat(campaign_id)
            if session:
                self.active_sessions[session.session_id] = session
                self.session_campaign_map[session.session_id] = campaign_id
                logger.info(f"Loaded active combat session {session.session_id} for campaign {campaign_id}")
                return session

        return None

    def get_session(self, session_id: str) -> Optional[CombatSession]:
        """Get a combat session by ID."""
        return self.active_sessions.get(session_id)

    def load_session_from_disk(
        self,
        campaign_id: str,
        session_id: str
    ) -> Optional[CombatSession]:
        """Ensure a combat session is loaded into memory from persistence.

        Args:
            campaign_id: Campaign identifier
            session_id: Combat session identifier

        Returns:
            CombatSession if loaded, otherwise None
        """
        if not session_id or not self.persistence:
            return None

        existing = self.active_sessions.get(session_id)
        if existing:
            return existing

        session = self.persistence.load_combat_session(campaign_id, session_id)
        if session:
            self.active_sessions[session_id] = session
            self.session_campaign_map[session_id] = campaign_id
            logger.info(f"Loaded combat session {session_id} for campaign {campaign_id} into memory")
        return session

    def update_turn_available_actions(self, campaign_id: str, character_id: str, turn_id: str) -> None:
        """Update turn manager with available actions for a character.

        Args:
            campaign_id: Campaign identifier
            character_id: Character taking the turn
            turn_id: Turn identifier
        """
        if not self.turn_manager:
            return

        # Find the combat session for this campaign
        session = None
        for sid, cid in self.session_campaign_map.items():
            if cid == campaign_id:
                session = self.active_sessions.get(sid)
                break

        if session and character_id in session.combatants:
            combatant = session.combatants[character_id]
            action_costs = self.combat_engine.get_actions_for_combatant(combatant)
            turn_actions = []
            for action_cost in action_costs:
                action_name = _normalize_action_name(action_cost.name)
                turn_actions.append(
                    _build_turn_action(
                        action_id=action_name,
                        description=action_cost.description,
                        ap_cost=getattr(action_cost, "cost", None)
                    )
                )

            self.turn_manager.set_available_actions(turn_id, turn_actions)
            logger.info(
                "Updated turn %s with %d available actions",
                turn_id,
                len(turn_actions)
            )

    def get_active_session_for_scene(self, scene_id: str) -> Optional[CombatSession]:
        """Get the active combat session for a scene."""
        for session in self.active_sessions.values():
            if session.scene_id == scene_id and session.status == CombatStatus.IN_PROGRESS:
                return session
        return None

    def get_initialized_combat(self, campaign_id: str) -> Optional['CombatCachedPayload']:
        """Get initialized combat data for a campaign.

        Args:
            campaign_id: Campaign identifier

        Returns:
            Initialized combat payload if exists, None otherwise
        """
        return self.initialized_combat.get(campaign_id)

    def set_initialized_combat(self, campaign_id: str, payload: 'CombatCachedPayload') -> None:
        """Set initialized combat data for a campaign.

        Args:
            campaign_id: Campaign identifier
            payload: Combat initialization payload to store
        """
        self.initialized_combat[campaign_id] = payload
        logger.info(f"Stored initialized combat for campaign {campaign_id}")

    def clear_initialized_combat(self, campaign_id: str) -> None:
        """Clear initialized combat data for a campaign.

        Args:
            campaign_id: Campaign identifier
        """
        if campaign_id in self.initialized_combat:
            del self.initialized_combat[campaign_id]
            logger.info(f"Cleared initialized combat for campaign {campaign_id}")

    def process_action(
        self,
        session_id: str,
        actor_id: str,
        action_name: str,
        target_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        user_input: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process a combat action.

        Args:
            session_id: Combat session ID
            actor_id: ID of acting character
            action_name: Name of action to perform
            target_id: Optional target ID
            campaign_id: Campaign ID for logging
            user_input: Original user input for logging
            **kwargs: Additional action parameters

        Returns:
            Action result with details
        """
        session = self.get_session(session_id)
        if not session:
            error_msg = f"Combat session {session_id} not found"
            if self.logger and campaign_id:
                self.logger.log_error(session_id, campaign_id, error_msg)
            return {"error": error_msg}

        # Derive campaign_id from active mapping if not provided
        if campaign_id is None:
            campaign_id = self.session_campaign_map.get(session_id)

        # Log user input
        if self.logger and campaign_id:
            self.logger.log_user_input(
                session_id, campaign_id,
                user_input or f"{actor_id} performs {action_name}",
                {"actor_id": actor_id, "action_name": action_name, "target_id": target_id}
            )

        # Check if it's the actor's turn
        current_character_id = session.resolve_current_character()
        if current_character_id != actor_id:
            error_msg = f"Not {actor_id}'s turn"
            if self.logger and campaign_id:
                self.logger.log_validation_failure(
                    session_id, campaign_id,
                    action_name, error_msg,
                    {"current_turn": current_character_id}
                )
            return {
                "error": error_msg,
                "current_turn": current_character_id
            }

        current_turn = None
        if self.turn_manager and campaign_id:
            current_turn = self.turn_manager.get_current_turn(campaign_id)

        # Process the action through combat engine
        try:
            start_time = time.time()
            state_before = session.to_dict() if self.logger else None

            action = self.combat_engine.process_action(
                session, actor_id, action_name, target_id, **kwargs
            )

            if current_turn:
                action.turn_id = current_turn.turn_id

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Log action result
            if self.logger and campaign_id:
                self.logger.log_action_result(
                    session_id, campaign_id,
                    action.to_dict(), processing_time_ms
                )

                # Log any dice rolls that occurred
                # (This would be integrated with the dice roller)

                # Log state changes
                state_after = session.to_dict()
                self.logger.log_state_transition(
                    session_id, campaign_id,
                    state_before, state_after, action_name
                )

            # Save session to disk
            if self.persistence and campaign_id:
                self.persistence.save_combat_session(campaign_id, session)

            # Update turn manager with combat result if available
            if self.turn_manager and current_turn and campaign_id:
                turn_action = _build_turn_action(
                    action_id=_normalize_action_name(action_name),
                    description=getattr(action, "description", None),
                    ap_cost=getattr(action, "ap_cost", None)
                )
                self.turn_manager.update_turn_with_combat_result(
                    current_turn.turn_id,
                    turn_action,
                    action.to_dict()
                )

            # Check for combat end
            victory = self.combat_engine.check_combat_end(session)
            if victory:
                session.status = CombatStatus.COMPLETED
                logger.info(f"Combat ended: {victory}")

                # Archive completed combat
            if self.persistence and campaign_id:
                self.persistence.archive_completed_combat(campaign_id, session)

            if victory:
                self.active_sessions.pop(session_id, None)
                self.session_campaign_map.pop(session_id, None)

                # Finalize logs
                if self.logger and campaign_id:
                    self.logger.finalize_session(session_id, campaign_id)

            return {
                "success": True,
                "action": action.to_dict(),
                "combat_state": session.get_summary(),
                "victory": victory
            }

        except Exception as e:
            error_msg = f"Error processing action: {e}"
            logger.error(error_msg)

            # Log error with full context
            if self.logger and campaign_id:
                import traceback
                self.logger.log_error(
                    session_id, campaign_id,
                    error_msg, traceback.format_exc(),
                    {"action": action_name, "actor": actor_id, "target": target_id}
                )

            return {"error": str(e)}


    def add_combatant_mid_combat(
        self,
        session_id: str,
        character: CharacterInfo
    ) -> bool:
        """
        Add a combatant to an ongoing combat.

        Args:
            session_id: Combat session ID
            character: Character to add

        Returns:
            Success status
        """
        session = self.get_session(session_id)
        if not session or session.status != CombatStatus.IN_PROGRESS:
            return False

        combatant = self.combat_engine.initialize_combatant(character)
        session.add_combatant(combatant)
        logger.info(f"Added {combatant.name} to ongoing combat")

        return True

    def remove_combatant(self, session_id: str, character_id: str) -> bool:
        """
        Remove a combatant from combat.

        Args:
            session_id: Combat session ID
            character_id: Character ID to remove

        Returns:
            Success status
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.remove_combatant(character_id)
        logger.info(f"Removed {character_id} from combat")

        # Check if combat should end
        victory = self.combat_engine.check_combat_end(session)
        if victory:
            session.status = CombatStatus.COMPLETED
            logger.info(f"Combat ended after removal: {victory}")
            self.active_sessions.pop(session_id, None)
            self.session_campaign_map.pop(session_id, None)

        return True

    def apply_status_effect(
        self,
        session_id: str,
        target_id: str,
        effect: StatusEffect
    ) -> bool:
        """
        Apply a status effect to a combatant.

        Args:
            session_id: Combat session ID
            target_id: Target character ID
            effect: Status effect to apply

        Returns:
            Success status
        """
        session = self.get_session(session_id)
        if not session:
            return False

        target = session.combatants.get(target_id)
        if not target:
            return False

        target.add_status_effect(effect)
        logger.info(f"Applied {effect.effect_type.value} to {target.name}")

        return True

    def heal_combatant(
        self,
        session_id: str,
        target_id: str,
        amount: int
    ) -> int:
        """
        Heal a combatant.

        Args:
            session_id: Combat session ID
            target_id: Target character ID
            amount: Amount to heal

        Returns:
            Actual amount healed
        """
        session = self.get_session(session_id)
        if not session:
            return 0

        target = session.combatants.get(target_id)
        if not target:
            return 0

        healed = target.heal(amount)
        logger.info(f"Healed {target.name} for {healed} HP")

        return healed

    def end_combat(
        self,
        session_id: str,
        reason: str = "manual"
    ) -> Dict[str, Any]:
        """
        End a combat session.

        Args:
            session_id: Combat session ID
            reason: Reason for ending combat

        Returns:
            Combat summary
        """
        session = self.get_session(session_id)
        if not session:
            return {"error": f"Combat session {session_id} not found"}

        # Mark as completed
        session.status = CombatStatus.COMPLETED if reason != "abandoned" else CombatStatus.ABANDONED

        # Track associated campaign before removing the session from memory
        campaign_id = self.session_campaign_map.pop(session_id, None)

        # Generate summary
        summary = {
            "session_id": session_id,
            "rounds": session.round_number,
            "reason": reason,
            "survivors": [
                {
                    "name": c.name,
                    "hp": f"{c.hp}/{c.max_hp}",
                    "conscious": c.is_conscious
                }
                for c in session.combatants.values()
            ],
            "actions_taken": len(session.combat_log)
        }

        logger.info(f"Combat session {session_id} ended: {reason}")

        # Remove from active sessions
        del self.active_sessions[session_id]

        # Clean up persisted active combat if available
        if self.persistence and campaign_id:
            self.persistence.remove_active_combat_session(campaign_id, session_id)

        return summary

    def get_available_actions(
        self,
        session_id: str,
        character_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get available actions for a character.

        Args:
            session_id: Combat session ID
            character_id: Character ID

        Returns:
            List of available actions with costs
        """
        session = self.get_session(session_id)
        if not session:
            return []

        combatant = session.combatants.get(character_id)
        if not combatant or not combatant.action_points:
            return []

        available = []
        current_ap = combatant.action_points.current_ap

        actions = self.combat_engine.get_actions_for_combatant(combatant)
        if not actions and combatant.is_conscious:
            actions = self.combat_engine.get_available_actions(combatant.level)

        for action in actions:
            # Check if combatant can afford it
            if action.cost > current_ap:
                continue

            # Check prerequisites
            valid = True
            for prereq in action.prerequisites:
                if "level >=" in prereq:
                    required_level = int(prereq.split(">=")[1].strip())
                    if combatant.level < required_level:
                        valid = False
                        break

            if valid:
                available.append(action.to_dict())

        return available

    def serialize_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Serialize a combat session for storage.

        Args:
            session_id: Combat session ID

        Returns:
            Serialized session data
        """
        session = self.get_session(session_id)
        if not session:
            return None

        return session.to_dict()

    def deserialize_session(self, data: Dict[str, Any]) -> CombatSession:
        """
        Deserialize a combat session from storage.

        Args:
            data: Serialized session data

        Returns:
            Reconstructed CombatSession
        """
        # This would reconstruct a CombatSession from serialized data
        # Implementation would handle all the dataclass conversions
        pass  # TODO: Implement deserialization
