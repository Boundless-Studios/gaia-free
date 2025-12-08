"""Combat persistence system for saving and loading combat sessions."""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime

from gaia.models.combat import (
    CombatSession, CombatantState, CombatAction,
    StatusEffect, StatusEffectType, CombatStatus,
    CombatStats, Position
)
from gaia_private.models.combat.agent_io.initiation import BattlefieldConfig
from gaia.models.combat.mechanics.action_points import ActionPointState
from gaia.models.combat.mechanics.action_definitions import ActionCost

from gaia.infra.storage.campaign_store import get_campaign_store

logger = logging.getLogger(__name__)


class CombatPersistenceManager:
    """Manages persistence of combat sessions to disk."""

    def __init__(self, campaign_manager):
        """Initialize the persistence manager.

        Args:
            campaign_manager: Campaign manager for accessing storage paths
        """
        self.campaign_manager = campaign_manager
        # Unified store derived from the campaign manager's session storage
        try:
            self._store = get_campaign_store(self.campaign_manager.storage)
        except Exception:
            self._store = None

    def get_combat_path(self, campaign_id: str) -> Optional[Path]:
        """Get the combat directory path for a campaign.

        Args:
            campaign_id: Campaign identifier

        Returns:
            Path to combat directory or None if campaign doesn't exist
        """
        data_path = self.campaign_manager.get_campaign_data_path(campaign_id)
        if not data_path:
            logger.error(f"No data path found for campaign {campaign_id}")
            return None

        combat_path = data_path / "combat"
        combat_path.mkdir(exist_ok=True)

        # Ensure subdirectories exist
        (combat_path / "active").mkdir(exist_ok=True)
        (combat_path / "history").mkdir(exist_ok=True)

        return combat_path

    def save_combat_session(self, campaign_id: str, session: CombatSession) -> bool:
        """Save a combat session to disk.

        Args:
            campaign_id: Campaign identifier
            session: Combat session to save

        Returns:
            True if saved successfully
        """
        try:
            combat_path = self.get_combat_path(campaign_id)
            if not combat_path:
                return False

            # Save to active combat file
            active_file = combat_path / "active" / f"{session.session_id}.json"

            # Serialize the session
            session_data = self._serialize_session(session)

            # Add metadata
            session_data["_metadata"] = {
                "campaign_id": campaign_id,
                "last_saved": datetime.now().isoformat(),
                "version": "1.0"
            }

            # Write to file
            with open(active_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved combat session {session.session_id} to {active_file}")
            # Mirror to store when available for stateless environments
            if self._store is not None:
                try:
                    self._store.write_json(session_data, campaign_id, f"data/combat/active/{session.session_id}.json")
                except Exception as exc:
                    logger.warning("Combat store mirror (active) failed: %s", exc)
            return True

        except Exception as e:
            logger.error(f"Failed to save combat session: {e}")
            return False

    def remove_active_combat_session(self, campaign_id: str, session_id: str) -> bool:
        """Remove the active combat file for a given session if it exists.

        Args:
            campaign_id: Campaign identifier
            session_id: Combat session identifier

        Returns:
            True if a file was removed or did not exist, False if an error occurred
        """
        try:
            combat_path = self.get_combat_path(campaign_id)
            if not combat_path:
                return False

            active_file = combat_path / "active" / f"{session_id}.json"
            if active_file.exists():
                active_file.unlink()
            if self._store is not None:
                try:
                    self._store.delete(campaign_id, f"data/combat/active/{session_id}.json")
                except Exception:
                    pass
                logger.info(f"Removed active combat file {active_file}")
            return True
        except Exception as exc:
            logger.error(f"Failed to remove active combat file for {session_id}: {exc}")
            return False

    def load_active_combat(self, campaign_id: str) -> Optional[CombatSession]:
        """Load the active combat session for a campaign.

        Args:
            campaign_id: Campaign identifier

        Returns:
            Active CombatSession or None if none exists
        """
        try:
            combat_path = self.get_combat_path(campaign_id)
            if not combat_path:
                return None

            active_dir = combat_path / "active"
            if not active_dir.exists():
                # Fallback to store: try to load the most recently saved active session
                if self._store is not None:
                    try:
                        names = self._store.list_json_prefix(campaign_id, "data/combat/active")
                        latest_payload = None
                        latest_ts = ""
                        for name in names:
                            payload = self._store.read_json(campaign_id, f"data/combat/active/{name}")
                            if isinstance(payload, dict):
                                meta = payload.get("_metadata", {})
                                ts = meta.get("last_saved") or meta.get("updated_at") or ""
                                if ts >= latest_ts:
                                    latest_ts = ts
                                    latest_payload = payload
                        if latest_payload:
                            return self._deserialize_session(latest_payload)
                    except Exception as exc:
                        logger.debug("Combat store load (active) failed: %s", exc)
                return None

            # Find the most recent active combat file
            combat_files = list(active_dir.glob("*.json"))
            if not combat_files:
                return None

            # Get the most recently modified file
            latest_file = max(combat_files, key=lambda f: f.stat().st_mtime)

            with open(latest_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # Deserialize the session
            session = self._deserialize_session(session_data)

            logger.info(f"Loaded active combat session from {latest_file}")
            return session

        except Exception as e:
            logger.error(f"Failed to load active combat: {e}")
            return None

    def load_combat_session(self, campaign_id: str, session_id: str) -> Optional[CombatSession]:
        """Load a specific active combat session by ID.

        Args:
            campaign_id: Campaign identifier
            session_id: Combat session identifier

        Returns:
            CombatSession if found, otherwise None
        """
        try:
            combat_path = self.get_combat_path(campaign_id)
            if not combat_path:
                return None

            active_file = combat_path / "active" / f"{session_id}.json"
            if not active_file.exists():
                # Try store fallback
                if self._store is not None:
                    try:
                        payload = self._store.read_json(campaign_id, f"data/combat/active/{session_id}.json")
                        if isinstance(payload, dict):
                            return self._deserialize_session(payload)
                    except Exception as exc:
                        logger.debug("Combat store read (by id) failed: %s", exc)
                return None

            with open(active_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            session = self._deserialize_session(session_data)
            logger.info(f"Loaded combat session {session_id} from {active_file}")
            return session
        except Exception as exc:
            logger.error(f"Failed to load combat session {session_id} for campaign {campaign_id}: {exc}")
            return None

    def archive_completed_combat(self, campaign_id: str,
                                session: CombatSession) -> bool:
        """Archive a completed combat session.

        Args:
            campaign_id: Campaign identifier
            session: Completed combat session

        Returns:
            True if archived successfully
        """
        try:
            combat_path = self.get_combat_path(campaign_id)
            if not combat_path:
                return False

            # Create timestamp-based filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = (combat_path / "history" /
                          f"combat_{timestamp}_{session.session_id}.json")

            # Serialize with additional metadata
            session_data = self._serialize_session(session)
            session_data["_metadata"] = {
                "campaign_id": campaign_id,
                "archived_at": datetime.now().isoformat(),
                "duration_seconds": (
                    session.updated_at - session.created_at
                ).total_seconds() if session.updated_at else 0,
                "version": "1.0"
            }

            # Write archive file
            with open(archive_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            if self._store is not None:
                try:
                    self._store.write_json(session_data, campaign_id, f"data/combat/history/{archive_file.name}")
                except Exception as exc:
                    logger.warning("Combat store mirror (archive) failed: %s", exc)

            # Remove from active
            active_file = combat_path / "active" / f"{session.session_id}.json"
            if active_file.exists():
                active_file.unlink()

            logger.info(f"Archived combat session to {archive_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to archive combat session: {e}")
            return False

    def list_combat_history(self, campaign_id: str) -> List[Dict[str, Any]]:
        """List all past combat sessions for a campaign.

        Args:
            campaign_id: Campaign identifier

        Returns:
            List of combat summaries
        """
        try:
            combat_path = self.get_combat_path(campaign_id)
            if not combat_path:
                return []

            history_dir = combat_path / "history"
            if not history_dir.exists():
                # Try store listing
                if self._store is not None:
                    try:
                        names = self._store.list_json_prefix(campaign_id, "data/combat/history")
                        summaries: List[Dict[str, Any]] = []
                        for name in names:
                            data = self._store.read_json(campaign_id, f"data/combat/history/{name}")
                            if not isinstance(data, dict):
                                continue
                            metadata = data.get("_metadata", {})
                            summary = {
                                "session_id": data.get("session_id"),
                                "scene_id": data.get("scene_id"),
                                "archived_at": metadata.get("archived_at"),
                                "duration_seconds": metadata.get("duration_seconds", 0),
                                "rounds": data.get("round_number", 0),
                                "combatant_count": len(data.get("combatants", {})),
                                "status": data.get("status", "unknown"),
                                "file": name,
                            }
                            summaries.append(summary)
                        summaries.sort(key=lambda x: x.get("archived_at", ""), reverse=True)
                        return summaries
                    except Exception as exc:
                        logger.debug("Combat store list (history) failed: %s", exc)
                return []

            summaries = []
            for combat_file in history_dir.glob("*.json"):
                try:
                    with open(combat_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    metadata = data.get("_metadata", {})
                    summary = {
                        "session_id": data.get("session_id"),
                        "scene_id": data.get("scene_id"),
                        "archived_at": metadata.get("archived_at"),
                        "duration_seconds": metadata.get("duration_seconds", 0),
                        "rounds": data.get("round_number", 0),
                        "combatant_count": len(data.get("combatants", {})),
                        "status": data.get("status", "unknown"),
                        "file": combat_file.name
                    }
                    summaries.append(summary)

                except Exception as e:
                    logger.error(f"Error reading combat file {combat_file}: {e}")
                    continue

            # Sort by archived date (newest first)
            summaries.sort(key=lambda x: x.get("archived_at", ""), reverse=True)

            return summaries

        except Exception as e:
            logger.error(f"Failed to list combat history: {e}")
            return []

    def recover_active_sessions(self) -> Dict[str, CombatSession]:
        """Recover all active combat sessions on startup.

        Returns:
            Dictionary of campaign_id -> CombatSession
        """
        recovered = {}

        # Scan all campaigns for active combat
        campaigns = self.campaign_manager.list_campaigns()
        for campaign_info in campaigns.get("campaigns", []):
            campaign_id = campaign_info["id"]

            session = self.load_active_combat(campaign_id)
            if session:
                recovered[campaign_id] = session
                logger.info(f"Recovered active combat for campaign {campaign_id}")

        return recovered

    def _serialize_session(self, session: CombatSession) -> Dict[str, Any]:
        """Serialize a combat session to dictionary.

        Args:
            session: Combat session to serialize

        Returns:
            Serialized dictionary
        """
        data = {
            "session_id": session.session_id,
            "scene_id": session.scene_id,
            "status": session.status.value if isinstance(session.status, CombatStatus) else session.status,
            "round_number": session.round_number,
            "turn_order": session.turn_order,
            "current_turn_index": session.current_turn_index,
            "combatants": {},
            "battlefield": None,
            "combat_log": [],
            "victory_condition": getattr(session, 'victory_condition', 'defeat_all_enemies').value if hasattr(getattr(session, 'victory_condition', None), 'value') else getattr(session, 'victory_condition', 'defeat_all_enemies'),
            "created_at": getattr(session, 'created_at', datetime.now()).isoformat() if hasattr(session, 'created_at') else datetime.now().isoformat(),
            "updated_at": getattr(session, 'updated_at', datetime.now()).isoformat() if hasattr(session, 'updated_at') else datetime.now().isoformat()
        }

        # Serialize combatants
        for cid, combatant in session.combatants.items():
            data["combatants"][cid] = self._serialize_combatant(combatant)

        # Serialize battlefield
        if session.battlefield:
            data["battlefield"] = session.battlefield.to_dict()

        # Serialize combat log (last 100 actions to avoid huge files)
        for action in session.combat_log[-100:]:
            data["combat_log"].append(action.to_dict())

        return data

    def _serialize_combatant(self, combatant: CombatantState) -> Dict[str, Any]:
        """Serialize a combatant state.

        Args:
            combatant: Combatant to serialize

        Returns:
            Serialized dictionary
        """
        # Use compact format for persistence (action names only)
        data = combatant.to_dict(compact=True)

        # Status effects are already serialized in to_dict()
        # No need to re-serialize them

        return data

    def _deserialize_session(self, data: Dict[str, Any]) -> CombatSession:
        """Deserialize a combat session from dictionary.

        Args:
            data: Serialized session data

        Returns:
            Deserialized CombatSession
        """
        # Convert status string to enum
        status = data.get("status", "initializing")
        if isinstance(status, str):
            try:
                status = CombatStatus[status.upper()]
            except KeyError:
                status = CombatStatus.INITIALIZING

        # Create session
        session = CombatSession(
            session_id=data["session_id"],
            scene_id=data["scene_id"],
            status=status,
            round_number=data.get("round_number", 1),
            turn_order=data.get("turn_order", []),
            current_turn_index=data.get("current_turn_index", 0),
            victory_condition=data.get("victory_condition", "defeat_all_enemies")
        )

        # Deserialize timestamps
        if data.get("created_at"):
            session.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            session.updated_at = datetime.fromisoformat(data["updated_at"])

        # Deserialize combatants
        for cid, combatant_data in data.get("combatants", {}).items():
            combatant = self._deserialize_combatant(combatant_data)
            session.combatants[cid] = combatant

        # Deserialize battlefield
        if data.get("battlefield"):
            session.battlefield = self._deserialize_battlefield(data["battlefield"])

        # Deserialize combat log
        for action_data in data.get("combat_log", []):
            action = self._deserialize_action(action_data)
            if action:
                session.combat_log.append(action)

        return session

    def _deserialize_combatant(self, data: Dict[str, Any]) -> CombatantState:
        """Deserialize a combatant state.

        Args:
            data: Serialized combatant data

        Returns:
            Deserialized CombatantState
        """
        combatant = CombatantState(
            character_id=data["character_id"],
            name=data["name"],
            initiative=data.get("initiative", 0),
            hp=data.get("hp", 0),
            max_hp=data.get("max_hp", 0),
            ac=data.get("ac", 10),
            level=data.get("level", 1),
            is_npc=data.get("is_npc", False),
            hostile=data.get("hostile", False),
            has_taken_turn=data.get("has_taken_turn", False)
        )

        # Deserialize action points
        if data.get("action_points"):
            ap_data = data["action_points"]
            combatant.action_points = ActionPointState(
                max_ap=ap_data.get("max_ap", 3),
                current_ap=ap_data.get("current_ap", 3),
                spent_this_turn=ap_data.get("spent_this_turn", 0)
            )

        # Deserialize status effects
        for effect_data in data.get("status_effects", []):
            effect = self._deserialize_status_effect(effect_data)
            if effect:
                combatant.status_effects.append(effect)

        # Deserialize position
        if data.get("position"):
            pos_data = data["position"]
            combatant.position = Position(
                x=pos_data.get("x", 0),
                y=pos_data.get("y", 0),
                z=pos_data.get("z", 0)
            )

        # Deserialize combat stats
        if data.get("combat_stats"):
            stats_data = data["combat_stats"]
            combatant.combat_stats = CombatStats(
                attack_bonus=stats_data.get("attack_bonus", 0),
                damage_bonus=stats_data.get("damage_bonus", 0),
                spell_save_dc=stats_data.get("spell_save_dc", 10),
                initiative_bonus=stats_data.get("initiative_bonus", 0),
                speed=stats_data.get("speed", 30)
            )

        return combatant

    def _deserialize_status_effect(self, data: Dict[str, Any]) -> Optional[StatusEffect]:
        """Deserialize a status effect.

        Args:
            data: Serialized effect data

        Returns:
            Deserialized StatusEffect or None
        """
        try:
            effect_type = data.get("effect_type")
            if isinstance(effect_type, str):
                effect_type = StatusEffectType[effect_type.upper()]

            return StatusEffect(
                effect_type=effect_type,
                duration_rounds=data.get("duration_rounds", 0),
                source=data.get("source", ""),
                description=data.get("description", ""),
                modifiers=data.get("modifiers", {})
            )
        except Exception as e:
            logger.error(f"Failed to deserialize status effect: {e}")
            return None

    def _deserialize_action(self, data: Dict[str, Any]) -> Optional[CombatAction]:
        """Deserialize a combat action.

        Args:
            data: Serialized action data

        Returns:
            Deserialized CombatAction or None
        """
        try:
            timestamp = datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now()

            return CombatAction(
                timestamp=timestamp,
                round_number=data.get("round_number", 1),
                actor_id=data.get("actor_id", ""),
                action_type=data.get("action_type", ""),
                target_id=data.get("target_id"),
                ap_cost=data.get("ap_cost", 0),
                roll_result=data.get("roll_result"),
                damage_dealt=data.get("damage_dealt"),
                success=data.get("success", True),
                description=data.get("description", ""),
                effects_applied=data.get("effects_applied", [])
            )
        except Exception as e:
            logger.error(f"Failed to deserialize combat action: {e}")
            return None

    def _deserialize_battlefield(self, data: Dict[str, Any]) -> Optional[BattlefieldConfig]:
        """Deserialize battlefield state.

        Args:
            data: Serialized battlefield data

        Returns:
            Deserialized BattlefieldConfig or None
        """
        try:
            return BattlefieldConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to deserialize battlefield: {e}")
            return None
