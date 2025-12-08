"""Factory helpers for promoting NPC participants into combatants."""

from __future__ import annotations

import logging
import uuid
from typing import Dict, Optional

from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.enums import CharacterCapability, CharacterRole
from gaia.models.character.npc_profile import NpcProfile
from gaia.models.combat.persistence.combatant_state import CombatantState

logger = logging.getLogger(__name__)


class NPCCombatantCreator:
    """Creates combatant records from roster participants or profiles."""

    DEFAULT_HP = 12
    DEFAULT_AC = 13
    DEFAULT_LEVEL = 1

    def __init__(self, character_manager: Optional[object] = None) -> None:
        self.character_manager = character_manager

    def set_character_manager(self, character_manager: object) -> None:
        self.character_manager = character_manager

    # ------------------------------------------------------------------
    # Combatant creation
    # ------------------------------------------------------------------
    def ensure_combatant(
        self,
        name: str,
        profile: Optional[NpcProfile] = None,
        overrides: Optional[Dict[str, int]] = None,
    ) -> CombatantState:
        character = self._lookup_character(name)
        if character:
            return self._combatant_from_character(character)

        if profile and profile.has_full_sheet and self.character_manager:
            character = self._lookup_character(profile.display_name)
            if character:
                return self._combatant_from_character(character)

        hit_points = overrides.get("hp") if overrides else None
        armor_class = overrides.get("ac") if overrides else None
        level = overrides.get("level") if overrides else None

        # Generate temp ID with npc: prefix
        temp_id = self._generate_temp_id(name)

        return CombatantState(
            character_id=temp_id,
            name=name,
            initiative=overrides.get("initiative", 0) if overrides else 0,
            hp=hit_points or self.DEFAULT_HP,
            max_hp=hit_points or self.DEFAULT_HP,
            ac=armor_class or self.DEFAULT_AC,
            level=level or self.DEFAULT_LEVEL,
            is_npc=True,
            hostile=overrides.get("hostile", False) if overrides else False,  # Must be explicitly set
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _lookup_character(self, identifier: str) -> Optional[CharacterInfo]:
        if not self.character_manager:
            return None
        try:
            character = self.character_manager.get_character(identifier)
            if character:
                return character
        except Exception:
            logger.debug("Combatant lookup by id failed", exc_info=True)
        try:
            return self.character_manager.get_character_by_name(identifier)
        except Exception:
            logger.debug("Combatant lookup by name failed", exc_info=True)
            return None

    def _combatant_from_character(self, character: CharacterInfo) -> CombatantState:
        is_npc = character.character_role != CharacterRole.PLAYER
        prefixed_id = self._ensure_prefixed_id(character.character_id, is_npc)

        return CombatantState(
            character_id=prefixed_id,
            name=character.name,
            initiative=character.initiative_modifier or 0,
            hp=character.hit_points_current,
            max_hp=character.hit_points_max,
            ac=character.armor_class,
            level=character.level,
            is_npc=is_npc,
            hostile=character.character_role not in (CharacterRole.PLAYER, CharacterRole.NPC_SUPPORT),
        )

    def _generate_temp_id(self, name: str) -> str:
        slug = name.lower().replace(" ", "_")
        return f"npc:{slug}"

    def _ensure_prefixed_id(self, character_id: str, is_npc: bool) -> str:
        """Ensure character ID has the proper pc: or npc: prefix."""
        if not character_id:
            return character_id

        # Check if already prefixed
        if character_id.startswith("pc:") or character_id.startswith("npc:"):
            return character_id

        # Add appropriate prefix
        prefix = "npc:" if is_npc else "pc:"
        return f"{prefix}{character_id}"

