"""Combat session model for managing combat encounters."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from gaia.models.combat.mechanics.enums import CombatStatus, VictoryCondition
from gaia.models.combat.persistence.combatant_state import CombatantState
from gaia.models.combat.mechanics.combat_action import CombatAction
from gaia_private.models.combat.agent_io.initiation import BattlefieldConfig


@dataclass
class CombatSession:
    """Complete state of a combat encounter."""
    session_id: str
    scene_id: str
    status: CombatStatus = CombatStatus.INITIALIZING
    round_number: int = 1
    turn_order: List[str] = field(default_factory=list)  # Character IDs in initiative order
    current_turn_index: int = 0
    combatants: Dict[str, CombatantState] = field(default_factory=dict)
    battlefield: Optional[BattlefieldConfig] = None
    combat_log: List[CombatAction] = field(default_factory=list)
    victory_condition: VictoryCondition = VictoryCondition.DEFEAT_ALL_ENEMIES

    def resolve_current_character(self) -> Optional[str]:
        """Return the ID of the combatant whose turn it is, if any remain active."""
        if not self.turn_order:
            return None

        # Ensure index is within range
        if self.current_turn_index >= len(self.turn_order):
            self.current_turn_index = 0

        from gaia.mechanics.combat.combat_engine import CombatEngine

        current_id = self.turn_order[self.current_turn_index]
        current_combatant = self.combatants.get(current_id)

        if current_combatant and CombatEngine.is_fighting_combatant(current_combatant):
            return current_id

        # If the active slot is not available, look for the next active combatant without mutating order
        for offset in range(1, len(self.turn_order)):
            idx = (self.current_turn_index + offset) % len(self.turn_order)
            char_id = self.turn_order[idx]
            combatant = self.combatants.get(char_id)
            if combatant and CombatEngine.is_fighting_combatant(combatant):
                return char_id

        # No active combatants remain
        return None

    def resolve_current_turn(self) -> Optional[str]:
        """Resolve and return the current turn's character ID.

        This method safely handles index issues and wraps around the turn order
        if the current index exceeds the turn order length.

        Returns:
            The character ID whose turn it is, or None if no valid turn
        """
        if not self.turn_order:
            return None

        # Guard against index issues by wrapping around
        if self.current_turn_index >= len(self.turn_order):
            self.current_turn_index = 0

        return self.turn_order[self.current_turn_index]

    # Why are we doing turn advancement here rather than relying on the turn progression in campaign runner 
    def advance_turn(self) -> Dict[str, Any]:
        """Advance to the next character's turn.

        Returns:
            Dict with next turn information including:
            - next_character: Character ID whose turn it is
            - new_round: Whether a new round started
            - round_number: Current round number
        """
        import logging
        logger = logging.getLogger(__name__)

        if not self.turn_order:
            return {"next_character": None, "new_round": False, "round_number": self.round_number}

        # Log initial state
        current_character_id = self.resolve_current_character()
        logger.debug(f"[TURN] Advancing from index {self.current_turn_index} ({current_character_id})")
        logger.debug(f"[TURN] Turn order: {self.turn_order}")
        logger.debug(f"[TURN] Round: {self.round_number}")

        # Move to next character
        prev_index = self.current_turn_index
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)

        # Find next active combatant and ensure the turn index points at them
        if self._find_next_active_combatant() is None:
            # No active combatants - combat should end
            logger.debug(f"[TURN] No active combatants found - combat should end")
            return {
                "next_character": None,
                "new_round": False,
                "round_number": self.round_number,
                "combat_ended": True
            }

        # Check if we've started a new round
        new_round = self._check_round_completion(prev_index)
        if new_round:
            logger.debug(f"[TURN] New round detected! Advancing to round {self.round_number + 1}")
            self.round_number += 1
            # Reset all combatants' AP at start of new round
            for combatant in self.combatants.values():
                if combatant.action_points:
                    combatant.action_points.reset_turn()
                    logger.debug(f"[TURN] Reset AP for {combatant.name}: {combatant.action_points.current_ap}/{combatant.action_points.max_ap}")

        next_character_id = self.resolve_current_character()
        logger.debug(
            f"[TURN] Result: index={self.current_turn_index}, char={next_character_id}, new_round={new_round}, round={self.round_number}"
        )

        return {
            "next_character": next_character_id,
            "new_round": new_round,
            "round_number": self.round_number
        }

    def _find_next_active_combatant(self) -> Optional[int]:
        """Find index of next active combatant (conscious and hp > 0).

        Delegates to CombatEngine.is_fighting_combatant() for business logic.

        Returns:
            Index of next active combatant, or None if combat should end
        """
        from gaia.mechanics.combat.combat_engine import CombatEngine

        if not self.turn_order:
            return None

        order_len = len(self.turn_order)
        attempts = 0

        while attempts < order_len:
            current_char_id = self.turn_order[self.current_turn_index]
            current_combatant = self.combatants.get(current_char_id)

            # Use CombatEngine to check if combatant is active
            if current_combatant and CombatEngine.is_fighting_combatant(current_combatant):
                return self.current_turn_index

            # Move to next combatant
            self.current_turn_index = (self.current_turn_index + 1) % order_len
            attempts += 1

        # No active combatants found - combat should end
        return None

    def _check_round_completion(self, prev_index: int) -> bool:
        """Check if all combatants have acted this round.

        Args:
            prev_index: Previous turn index before advancement

        Returns:
            True if a new round has started, False otherwise
        """
        # New round if we wrapped around to index 0 from a non-zero index
        return self.current_turn_index == 0 and prev_index != 0


    def get_active_combatants(self) -> List[CombatantState]:
        """Get all conscious combatants with HP > 0."""
        from gaia.mechanics.combat.combat_engine import CombatEngine

        return [
            combatant
            for combatant in self.combatants.values()
            if CombatEngine.is_fighting_combatant(combatant)
        ]

    def should_end_turn(self, character_id: str) -> bool:
        """Check if a character's turn should end based on Action Points.

        Delegates to CombatEngine.should_end_turn() for business logic.

        Args:
            character_id: Character to check

        Returns:
            True if character has 0 or negative AP
        """
        from gaia.mechanics.combat.combat_engine import CombatEngine
        return CombatEngine.should_end_turn(self, character_id)

    # TODO This should use victory types
    def check_victory_conditions(self) -> Optional[str]:
        """Check if combat should end, return victory type."""
        active_pcs = [c for c in self.get_active_combatants() if not c.is_npc]
        active_npcs = [c for c in self.get_active_combatants() if c.is_npc]

        # Check for mutual defeat first
        if not active_pcs and not active_npcs:
            return "players_defeat"  # If everyone is down, players lose
        elif not active_pcs:
            return "players_defeat"
        elif not active_npcs:
            return "players_victory"
        elif self.round_number > 20:  # Prevent infinite combat
            return "stalemate"

        return None

    def add_combatant(self, combatant: CombatantState) -> None:
        """Add a combatant to the session."""
        self.combatants[combatant.character_id] = combatant
        # Insert into turn order based on initiative
        self.turn_order.append(combatant.character_id)
        self.turn_order.sort(
            key=lambda cid: self.combatants[cid].initiative,
            reverse=True
        )

    def remove_combatant(self, character_id: str) -> None:
        """Remove a combatant from combat."""
        if character_id in self.combatants:
            del self.combatants[character_id]
            if character_id in self.turn_order:
                self.turn_order.remove(character_id)
                # Adjust current turn index if needed
                if self.current_turn_index >= len(self.turn_order):
                    self.current_turn_index = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "scene_id": self.scene_id,
            "status": self.status.value,
            "round_number": self.round_number,
            "turn_order": self.turn_order,
            "current_turn_index": self.current_turn_index,
            "current_turn": self.resolve_current_character(),
            "combatants": {
                cid: combatant.to_dict(compact=True)
                for cid, combatant in self.combatants.items()
            },
            "battlefield": self.battlefield.to_dict() if self.battlefield else None,
            "combat_log": [action.to_dict() for action in self.combat_log[-20:]],  # Last 20 actions
            "victory_condition": self.victory_condition.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CombatSession':
        """Create CombatSession from dictionary representation.

        Args:
            data: Dictionary containing session data

        Returns:
            Deserialized CombatSession
        """
        # Handle status enum
        status = data.get("status", "initializing")
        if isinstance(status, str):
            try:
                status = CombatStatus[status.upper()]
            except KeyError:
                status = CombatStatus.INITIALIZING

        # Handle victory condition enum
        victory_condition = data.get("victory_condition", "defeat_all_enemies")
        if isinstance(victory_condition, str):
            try:
                victory_condition = VictoryCondition(victory_condition)
            except (KeyError, ValueError):
                victory_condition = VictoryCondition.DEFEAT_ALL_ENEMIES
        else:
            victory_condition = VictoryCondition.DEFEAT_ALL_ENEMIES

        # Create session
        session = cls(
            session_id=data["session_id"],
            scene_id=data["scene_id"],
            status=status,
            round_number=data.get("round_number", 1),
            turn_order=data.get("turn_order", []),
            current_turn_index=data.get("current_turn_index", 0),
            victory_condition=victory_condition
        )

        # Deserialize combatants
        for cid, combatant_data in data.get("combatants", {}).items():
            from .combatant_state import CombatantState
            session.combatants[cid] = CombatantState.from_dict(combatant_data)

        # Deserialize battlefield
        if data.get("battlefield"):
            from gaia_private.models.combat.agent_io.initiation import BattlefieldConfig
            session.battlefield = BattlefieldConfig.from_dict(data["battlefield"])

        # Deserialize combat log
        for action_data in data.get("combat_log", []):
            from .combat_action import CombatAction
            action = CombatAction.from_dict(action_data)
            if action:
                session.combat_log.append(action)

        return session

    def get_summary(self) -> Dict[str, Any]:
        """Get a brief summary of combat state."""
        return {
            "round": self.round_number,
            "current_turn": self.resolve_current_character(),
            "active_combatants": len(self.get_active_combatants()),
            "status": self.status.value,
            "turn_order": [
                {
                    "id": cid,
                    "name": self.combatants[cid].name,
                    "hp": f"{self.combatants[cid].hp}/{self.combatants[cid].max_hp}",
                    "conscious": self.combatants[cid].is_conscious
                }
                for cid in self.turn_order
            ]
        }
