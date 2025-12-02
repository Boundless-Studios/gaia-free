"""Utilities for determining hostile combatants during routing."""

from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)


class HostileExtractionService:
    """Encapsulates how we derive hostile combatants from scene analysis."""

    def extract_hostiles(
        self,
        analysis: Dict[str, Any],
        analysis_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Return hostiles referenced in the current routing context.

        Checks multiple sources:
        1. Explicit 'hostiles' in analysis_context
        2. NPCs marked with hostile=True
        3. Scene participants with hostile roles (npc_combatant, enemy)

        Args:
            analysis: Scene analysis dictionary
            analysis_context: Full context including NPCs, scene data

        Returns:
            List of hostile NPC dictionaries
        """
        # Debug logging
        logger.info(f"🔍 extract_hostiles called")
        logger.info(f"  - analysis_context keys: {list(analysis_context.keys())}")
        logger.info(f"  - current_scene present: {'current_scene' in analysis_context}")
        if 'current_scene' in analysis_context:
            scene = analysis_context['current_scene']
            logger.info(f"  - current_scene type: {type(scene)}")
            if isinstance(scene, dict):
                logger.info(f"  - current_scene keys: {list(scene.keys())}")
                logger.info(f"  - participants count: {len(scene.get('participants', []))}")
                if scene.get('participants'):
                    for p in scene['participants'][:2]:  # Log first 2
                        logger.info(f"  - participant: {p.get('display_name')} role={p.get('role')}")

        # First check explicit hostiles (already determined)
        hostiles = analysis_context.get("hostiles", [])
        if hostiles:
            if isinstance(hostiles, dict):
                return [hostiles]
            if isinstance(hostiles, list):
                return [h for h in hostiles if isinstance(h, (dict, str))]

        # Fallback: Extract from NPCs marked as hostile
        npcs = analysis_context.get("npcs", [])
        if isinstance(npcs, list):
            hostile_npcs = [npc for npc in npcs if isinstance(npc, dict) and npc.get('hostile', False)]
            if hostile_npcs:
                logger.info(f"🎯 Extracted {len(hostile_npcs)} hostile NPCs: {[n.get('name') for n in hostile_npcs]}")
                return hostile_npcs

        # Check scene participants for npc_combatant or enemy roles
        current_scene = analysis_context.get("current_scene", {})
        participants = current_scene.get("participants", [])
        if isinstance(participants, list):
            hostile_roles = ["npc_combatant", "enemy"]
            hostile_participants = [
                p for p in participants
                if isinstance(p, dict) and p.get("role") in hostile_roles
            ]
            if hostile_participants:
                logger.info(f"🎯 Extracted {len(hostile_participants)} hostile participants from scene: {[p.get('display_name') for p in hostile_participants]}")
                # Convert participants to NPC format by matching with NPCs list
                hostile_character_ids = {p.get("character_id") for p in hostile_participants}
                matched_npcs = [npc for npc in npcs if isinstance(npc, dict) and npc.get("character_id") in hostile_character_ids]
                if matched_npcs:
                    return matched_npcs
                # If no matching NPCs found, return the participants themselves
                return hostile_participants

        logger.warning(f"⚠️ No hostiles found - npcs: {len(npcs)}, participants: {len(participants)}")
        return []
