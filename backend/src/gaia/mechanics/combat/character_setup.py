"""Unified character setup and management for combat.

This module consolidates all character setup logic that was previously
duplicated across combat_orchestrator.py and character_extraction.py.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
import logging
import uuid

from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia.models.combat.persistence.combatant_state import CombatantState
from gaia_private.models.combat.character.combat_types import (
    CharacterSetupResult,
    ExtractedCharacters
)
from gaia_private.session.scene.scene_roster_manager import SceneRosterManager
from gaia.mechanics.combat.npc_combatant_creator import NPCCombatantCreator


logger = logging.getLogger(__name__)


class CharacterSetupManager:
    """Manages all character setup and extraction for combat."""

    # Default values for missing data
    DEFAULT_PLAYER_HP = 10
    DEFAULT_NPC_HP = 8
    DEFAULT_PLAYER_AC = 10
    DEFAULT_NPC_AC = 12
    DEFAULT_ENEMY_AC = 13
    DEFAULT_ACTION_POINTS = 3
    DEFAULT_INITIATIVE_BONUS = 0

    def __init__(self, character_manager=None, roster_manager: Optional[SceneRosterManager] = None):
        """Initialize the character setup manager.

        Args:
            character_manager: Optional character manager for database lookups
        """
        self.character_manager = character_manager
        self.roster_manager = roster_manager
        self.combatant_creator = NPCCombatantCreator(character_manager)

    def set_roster_manager(self, roster_manager: SceneRosterManager) -> None:
        self.roster_manager = roster_manager

    def _normalize_combatant_name(
        self,
        raw_name: str,
        player_names: Iterable[str]
    ) -> Tuple[str, List[str]]:
        """Return the original combatant name and generate alias options.

        The canonical name now mirrors the LLM-provided value (whitespace trimmed)
        so we can faithfully propagate whatever the model generated. We still
        derive alias strings to help downstream matching when the model
        occasionally embellishes with status text or descriptions.
        """
        if not raw_name:
            return "", []

        canonical = str(raw_name).strip()
        if not canonical:
            return "", []

        name = canonical
        alias_candidates: List[str] = []

        # Strip numbering/bullet prefixes like "2. " or "- "
        name = re.sub(r"^[\s\-]*\d+[\.\-\)\]]\s*", "", name)
        name = re.sub(r"^[\s\-]*[\*\-•]\s*", "", name)

        raw_segments = [
            segment.strip()
            for segment in re.split(r"[\n\r]+|\.\s*", name)
            if segment.strip()
        ]

        player_lookup = {p.lower() for p in player_names if p}
        status_keywords = (
            "hp",
            "ap",
            "status",
            "condition",
            "conditions",
            "unconscious",
            "wounded",
            "bloodied",
            "healthy",
            "injured",
            "defeated",
            "initiative",
            "turn ended",
        )

        filtered_segments: List[str] = []
        for segment in raw_segments:
            lowered = segment.lower()
            if any(player in lowered for player in player_lookup):
                continue
            if ":" in segment:
                left, _, right = segment.partition(":")
                if any(keyword in right.lower() for keyword in status_keywords):
                    filtered_segments.append(left.strip())
                    continue
            filtered_segments.append(segment)

        if not filtered_segments:
            filtered_segments = raw_segments or [name]

        candidate_raw = filtered_segments[-1] if len(filtered_segments) > 1 else filtered_segments[0]
        candidate = (
            re.sub(r"\s+", " ", candidate_raw)
            .replace("_", " ")
            .strip(" .;,-")
        )

        for alias in (candidate_raw.strip(), name):
            if alias:
                alias_candidates.append(alias)

        descriptive_terms = (
            " appear",
            " appears",
            " appearing",
            " seem",
            " seems",
            " seeming",
            " are ",
            " were ",
            " is ",
            " was ",
            " have ",
            " has ",
            " carrying ",
            " wielding ",
            " holding ",
            " wearing ",
            " standing ",
            " seated ",
            " sitting ",
            " crouched ",
            " crouching ",
            " looming ",
            " hovering ",
            " guarding ",
            " charging ",
            " lurching ",
            " shambling ",
            " approaching ",
            " advancing ",
        )

        lowered_candidate = candidate.lower()
        if len(candidate) > 40:
            for term in descriptive_terms:
                idx = lowered_candidate.find(term)
                if idx > 0 and idx >= 6:
                    alias_candidates.append(candidate)
                    candidate = candidate[:idx].strip(" .;,-")
                    lowered_candidate = candidate.lower()
                    break

        stop_words = {
            "appear",
            "appears",
            "appearing",
            "seated",
            "sitting",
            "standing",
            "looming",
            "hovering",
            "guarding",
            "charging",
            "lurching",
            "shambling",
            "approaching",
            "advancing",
            "holding",
            "wielding",
            "with",
        }

        words = candidate.split()
        for idx, word in enumerate(words):
            if idx >= 3 and word.lower() in stop_words:
                alias_candidates.append(candidate)
                candidate = " ".join(words[:idx]).strip(" .;,-")
                break

        candidate = re.sub(r"\s+", " ", candidate).strip(" .;,-")
        if not candidate:
            candidate = canonical

        alias_unique: List[str] = []
        for alias in alias_candidates:
            normalized_alias = re.sub(r"\s+", " ", alias.replace("_", " ")).strip(" .;,-")
            if normalized_alias and normalized_alias not in alias_unique and normalized_alias != canonical:
                alias_unique.append(normalized_alias)

        if candidate and candidate != canonical and candidate not in alias_unique:
            alias_unique.insert(0, candidate)

        return canonical, alias_unique

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

    def set_character_manager(self, character_manager) -> None:
        self.character_manager = character_manager
        self.combatant_creator.set_character_manager(character_manager)

    def setup_combat_characters(
        self,
        combat_model: Any,  # CombatInitiation model
        combat_request: Any,  # CombatInitiationRequest
        player_characters: Optional[List[CharacterInfo]] = None
    ) -> CharacterSetupResult:
        """Setup characters for combat initialization.

        Consolidates logic from combat_orchestrator._setup_combat_characters.

        Args:
            combat_model: Combat initiation model with initiative order
            combat_request: Combat initiation request with combatants
            player_characters: Optional list of player characters from database

        Returns:
            CharacterSetupResult with characters, ID mapping, and combatant data
        """
        characters: List[CharacterInfo] = []
        name_to_combatant_id: Dict[str, str] = {}
        combatants_by_name: Dict[str, CombatantState] = {}

        player_names: set[str] = {
            entry.name.strip()
            for entry in getattr(combat_model, "initiative_order", [])
            if getattr(entry, "is_player", False) and getattr(entry, "name", None)
        }
        if player_characters:
            player_names.update(
                c.name for c in player_characters
                if getattr(c, "name", None)
            )

        roster_participants = []
        if self.roster_manager and getattr(combat_model, "scene_id", None):
            roster_participants = list(self.roster_manager.get_participants_for_scene(combat_model.scene_id))

        pcs = {
            c.name: c for c in (player_characters or [])
        } if player_characters else {}

        for entry in combat_model.initiative_order:
            raw_name = entry.name if hasattr(entry, 'name') else None
            if not raw_name:
                continue

            is_player = getattr(entry, 'is_player', False)
            name = raw_name.strip()
            alias_names: List[str] = []

            if not is_player:
                canonical_name, alias_names = self._normalize_combatant_name(raw_name, player_names)
                if canonical_name:
                    name = canonical_name
            else:
                player_names.add(name)

            # Handle player characters
            if is_player:
                if name in pcs:
                    char = pcs[name]
                    characters.append(char)
                    name_to_combatant_id[name] = char.character_id

                    combatants_by_name[name] = self._character_info_to_combatant_state(char)
                # Skip player characters without database entries - they shouldn't be created as NPCs
                continue

            # Handle NPCs/enemies
            try:
                overrides = entry.model_dump() if hasattr(entry, "model_dump") else dict(entry)
                combatant_state = self.combatant_creator.ensure_combatant(
                    name,
                    overrides=overrides,
                )

                combatants_by_name[name] = combatant_state
                name_to_combatant_id[name] = combatant_state.character_id

                for alias in alias_names:
                    alias_key = alias.strip()
                    if alias_key and alias_key not in name_to_combatant_id:
                        name_to_combatant_id[alias_key] = combatant_state.character_id

                existing_character: Optional[CharacterInfo] = None
                if self.character_manager:
                    existing_character = self.character_manager.get_character(combatant_state.character_id)
                if existing_character:
                    characters.append(existing_character)
                    continue

                capabilities = CharacterCapability.NARRATIVE | CharacterCapability.SKILLS
                if combatant_state.hostile:
                    capabilities |= CharacterCapability.COMBAT

                generated_character = CharacterInfo(
                    character_id=combatant_state.character_id,
                    name=name,
                    character_class=overrides.get("class", "Enemy"),
                    hit_points_current=combatant_state.hp,
                    hit_points_max=combatant_state.max_hp,
                    armor_class=combatant_state.ac,
                    character_type='creature',
                    character_role=CharacterRole.NPC_COMBATANT,
                    capabilities=capabilities,
                )
                characters.append(generated_character)

            except Exception as exc:
                logger.warning(f"Failed to build CharacterInfo for {name}: {exc}")

        return CharacterSetupResult(
            characters=characters,
            name_to_combatant_id=name_to_combatant_id,
            combatants_by_name=combatants_by_name
        )

    def build_combatants_from_context(
        self,
        players: List[Dict[str, Any]],
        npcs: List[Dict[str, Any]],
        initiative_data: Optional[List[Dict[str, Any]]] = None,
        existing_name_mapping: Optional[Dict[str, str]] = None
    ) -> Tuple[Dict[str, CombatantState], Dict[str, str]]:
        """Build combatants from context data.

        Consolidates logic from combat_orchestrator._build_combatants_from_context.

        Args:
            players: List of player data dictionaries
            npcs: List of NPC data dictionaries
            initiative_data: Optional initiative order data
            existing_name_mapping: Optional existing name to ID mapping

        Returns:
            Tuple of (combatants_by_name, name_to_combatant_id mapping)
        """
        combatants_by_name: Dict[str, CombatantState] = {}
        name_to_combatant_id: Dict[str, str] = existing_name_mapping.copy() if existing_name_mapping else {}

        # Process players
        for player in players:
            if not isinstance(player, dict):
                continue

            name = player.get('name')
            if not name or name in combatants_by_name:
                continue

            # Build ID mapping
            if name not in name_to_combatant_id:
                char_id = player.get('character_id')
                if char_id:
                    name_to_combatant_id[name] = str(char_id)
                else:
                    slug = name.lower().replace(' ', '_')
                    name_to_combatant_id[name] = f"player_{slug}"

            # Create combatant state for player
            char_id = self._ensure_prefixed_id(name_to_combatant_id[name], is_npc=False)
            combatants_by_name[name] = CombatantState(
                character_id=char_id,
                name=name,
                initiative=player.get('initiative', 0),
                hp=player.get('hp_current', player.get('hp', self.DEFAULT_PLAYER_HP)),
                max_hp=player.get('hp_max', self.DEFAULT_PLAYER_HP),
                ac=player.get('armor_class', player.get('ac', self.DEFAULT_PLAYER_AC)),
                level=player.get('level', 1),
                is_npc=False,
                hostile=False,  # Players are never hostile
                is_conscious=True
            )

        # Process NPCs
        for npc in npcs:
            if not isinstance(npc, dict):
                continue

            name = npc.get('name')
            if not name or name in combatants_by_name:
                continue

            # Determine if hostile
            is_hostile = npc.get('hostile', True)

            # Build ID mapping
            if name not in name_to_combatant_id:
                slug = name.lower().replace(' ', '_')
                short_uuid = uuid.uuid4().hex[:4]
                name_to_combatant_id[name] = f"npc_{slug}_{short_uuid}"

            # Create combatant state for NPC
            char_id = self._ensure_prefixed_id(name_to_combatant_id[name], is_npc=True)
            combatants_by_name[name] = CombatantState(
                character_id=char_id,
                name=name,
                initiative=npc.get('initiative', 0),
                hp=npc.get('hp_current', npc.get('hp', self.DEFAULT_NPC_HP)),
                max_hp=npc.get('hp_max', self.DEFAULT_NPC_HP),
                ac=npc.get('armor_class', npc.get('ac',
                    self.DEFAULT_ENEMY_AC if is_hostile else self.DEFAULT_NPC_AC)),
                level=npc.get('level', 1),
                is_npc=True,
                hostile=is_hostile,  # Track whether NPC is hostile
                is_conscious=True
            )

        # Process initiative data if provided
        if initiative_data:
            for entry in initiative_data:
                if not isinstance(entry, dict):
                    continue

                name = entry.get('name')
                if not name or name in combatants_by_name:
                    continue

                # Determine type
                is_player = entry.get('is_player', False)

                # Build ID mapping
                if name not in name_to_combatant_id:
                    if is_player:
                        # Try to find player data
                        player_entry = next((p for p in players if p.get('name') == name), None)
                        if player_entry and player_entry.get('character_id'):
                            name_to_combatant_id[name] = str(player_entry['character_id'])
                        else:
                            name_to_combatant_id[name] = f"player_{name.lower().replace(' ', '_')}"
                    else:
                        slug = name.lower().replace(' ', '_')
                        name_to_combatant_id[name] = f"npc_{slug}_{uuid.uuid4().hex[:4]}"

                # Create combatant state with defaults
                char_id = self._ensure_prefixed_id(name_to_combatant_id[name], is_npc=not is_player)
                # Use explicit hostile flag from initiative entry - must be set by character resolution
                is_hostile = entry.get('hostile', False)
                combatants_by_name[name] = CombatantState(
                    character_id=char_id,
                    name=name,
                    initiative=0,
                    hp=self.DEFAULT_PLAYER_HP if is_player else self.DEFAULT_NPC_HP,
                    max_hp=self.DEFAULT_PLAYER_HP if is_player else self.DEFAULT_NPC_HP,
                    ac=self.DEFAULT_PLAYER_AC if is_player else self.DEFAULT_ENEMY_AC,
                    level=1,
                    is_npc=not is_player,
                    hostile=is_hostile,  # Respect explicit hostile flag from initiative data
                    is_conscious=True
                )

        return combatants_by_name, name_to_combatant_id

    def extract_characters_from_analysis(
        self,
        analysis: Dict[str, Any],
        campaign_id: Optional[str] = None
    ) -> ExtractedCharacters:
        """Extract and normalize character information from scene analysis.

        Args:
            analysis: Scene analysis dictionary with entity recognition
            campaign_id: Optional campaign identifier for database lookups

        Returns:
            ExtractedCharacters with normalized player and NPC lists
        """
        players = []
        npcs = []

        # Extract from entity recognition
        if "entity_recognition" in analysis:
            entities = analysis["entity_recognition"]

            # Extract players
            for player_data in entities.get("players", []):
                player_info = self._normalize_player_info(player_data)
                if player_info:
                    players.append(player_info)

            # Extract NPCs
            for npc_data in entities.get("npcs", []):
                npc_info = self._normalize_npc_info(npc_data)
                if npc_info:
                    npcs.append(npc_info)

        # Try to get additional info from character manager if available
        if self.character_manager and campaign_id:
            try:
                db_players = self._get_players_from_db(campaign_id)
                players = self._merge_character_lists(players, db_players)
            except Exception as e:
                logger.debug(f"Could not fetch players from DB: {e}")

        # Update the analysis dictionary
        analysis["extracted_players"] = players
        analysis["extracted_npcs"] = npcs

        return ExtractedCharacters(players=players, npcs=npcs)

    def build_name_to_id_mapping(
        self,
        combatant_states: Dict[str, Any]
    ) -> Dict[str, str]:
        """Build name to combatant ID mapping from combat session states.

        Args:
            combatant_states: Dictionary of combatant states by character ID

        Returns:
            Dictionary mapping combatant names to their character IDs
        """
        name_to_combatant_id: Dict[str, str] = {}

        for character_id, state in combatant_states.items():
            if state:
                # Handle both object and dict forms
                name = state.name if hasattr(state, 'name') else state.get('name')
                if name:
                    name_to_combatant_id[name] = character_id

        return name_to_combatant_id

    def _create_npc_character(
        self,
        name: str,
        combatant_info: Any,
        entry_data: Dict[str, Any]
    ) -> CharacterInfo:
        """Create an NPC CharacterInfo object.

        Args:
            name: Character name
            combatant_info: Combatant information object
            entry_data: Initiative entry data dictionary

        Returns:
            CharacterInfo object for the NPC
        """
        # Use CharacterInfo factory method for NPC creation if available,
        # otherwise create directly
        if hasattr(CharacterInfo, 'from_combatant_info'):
            npc_character = CharacterInfo.from_combatant_info(
                combatant_info,
                entry_data
            )
        else:
            # Create CharacterInfo manually if factory method doesn't exist
            import uuid as uuid_module
            char_id = f"npc_{name.lower().replace(' ', '_')}_{uuid_module.uuid4().hex[:4]}"

            from gaia.models.character.character_info import CharacterInfo as CI
            npc_character = CI(
                character_id=char_id,
                name=name,
                character_class=entry_data.get('class_or_creature', 'Enemy'),
                level=entry_data.get('level', 1),
                hit_points_current=entry_data.get('hp_current', entry_data.get('hp', 10)),
                hit_points_max=entry_data.get('hp_max', 10),
                armor_class=entry_data.get('armor_class', entry_data.get('ac', 12)),
                character_type='creature' if getattr(combatant_info, 'hostile', True) else 'npc'
            )

        # Add initiative modifier
        if combatant_info and hasattr(combatant_info, 'initiative_bonus'):
            npc_character.initiative_modifier = combatant_info.initiative_bonus or 0
        elif 'initiative_bonus' in entry_data:
            npc_character.initiative_modifier = entry_data['initiative_bonus'] or 0
        else:
            npc_character.initiative_modifier = 0

        return npc_character

    def _character_info_to_combatant_state(
        self,
        char: CharacterInfo
    ) -> CombatantState:
        """Convert a CharacterInfo object to CombatantState.

        Args:
            char: CharacterInfo object

        Returns:
            CombatantState object
        """
        is_npc_char = char.character_type in ('npc', 'creature')
        is_hostile = char.character_type == 'creature' or getattr(char, 'hostile', False)
        char_id = self._ensure_prefixed_id(char.character_id, is_npc=is_npc_char)
        return CombatantState(
            character_id=char_id,
            name=char.name,
            initiative=getattr(char, 'initiative_modifier', 0),
            hp=char.hit_points_current,
            max_hp=char.hit_points_max,
            ac=char.armor_class,
            level=char.level,
            is_npc=is_npc_char,
            hostile=is_hostile,
            is_conscious=True
        )

    def _extract_combatant_state(
        self,
        character: CharacterInfo,
        is_player: bool,
        is_hostile: bool = False
    ) -> CombatantState:
        """Extract combatant state from a CharacterInfo object.

        Args:
            character: CharacterInfo object
            is_player: Whether this is a player character
            is_hostile: Whether this character is hostile

        Returns:
            CombatantState object
        """
        char_id = self._ensure_prefixed_id(character.character_id, is_npc=not is_player)
        return CombatantState(
            character_id=char_id,
            name=character.name,
            initiative=getattr(character, 'initiative_modifier', 0),
            hp=character.hit_points_current,
            max_hp=character.hit_points_max,
            ac=character.armor_class,
            level=character.level,
            is_npc=not is_player,
            hostile=is_hostile,  # Now properly using the is_hostile parameter
            is_conscious=True
        )

    def _normalize_player_info(self, player_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize player information from various sources.

        Args:
            player_data: Raw player data

        Returns:
            Normalized player info or None
        """
        name = player_data.get("name")
        if not name:
            return None

        return {
            "name": name,
            "class": player_data.get("class", "Adventurer"),
            "level": player_data.get("level", 1),
            "hp_max": player_data.get("hp_max", player_data.get("max_hp", self.DEFAULT_PLAYER_HP)),
            "hp_current": player_data.get("hp_current",
                player_data.get("hp", player_data.get("hp_max", self.DEFAULT_PLAYER_HP))),
            "armor_class": player_data.get("armor_class",
                player_data.get("ac", self.DEFAULT_PLAYER_AC)),
            "initiative_bonus": player_data.get("initiative_bonus", self.DEFAULT_INITIATIVE_BONUS),
            "character_id": player_data.get("id", player_data.get("character_id"))
        }

    def _normalize_npc_info(self, npc_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize NPC information from various sources.

        Args:
            npc_data: Raw NPC data

        Returns:
            Normalized NPC info or None
        """
        name = npc_data.get("name")
        if not name:
            return None

        # Determine hostility
        hostile = npc_data.get("hostile", npc_data.get("is_hostile"))
        if hostile is None:
            # Default based on type
            npc_type = npc_data.get("type", "").lower()
            hostile = any(word in npc_type for word in ["enemy", "hostile", "monster", "bandit", "goblin"])

        return {
            "name": name,
            "type": npc_data.get("type", "NPC"),
            "level": npc_data.get("level", 1),
            "hp_max": npc_data.get("hp_max", npc_data.get("max_hp", self.DEFAULT_NPC_HP)),
            "hp_current": npc_data.get("hp_current",
                npc_data.get("hp", npc_data.get("hp_max", self.DEFAULT_NPC_HP))),
            "armor_class": npc_data.get("armor_class", npc_data.get("ac",
                self.DEFAULT_ENEMY_AC if hostile else self.DEFAULT_NPC_AC)),
            "initiative_bonus": npc_data.get("initiative_bonus", self.DEFAULT_INITIATIVE_BONUS),
            "hostile": hostile,
            "disposition": npc_data.get("disposition", "hostile" if hostile else "neutral")
        }

    def _get_players_from_db(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get player information from database.

        Args:
            campaign_id: Campaign identifier

        Returns:
            List of player information dictionaries
        """
        if not self.character_manager:
            return []

        players = []
        try:
            characters = self.character_manager.get_party_characters(campaign_id)
            for char in characters:
                players.append({
                    "name": char.name,
                    "class": char.character_class,
                    "level": char.level,
                    "hp_max": char.hit_points_max,
                    "hp_current": char.hit_points_current,
                    "armor_class": char.armor_class,
                    "initiative_bonus": char.initiative_modifier,
                    "character_id": char.character_id
                })
        except Exception as e:
            logger.debug(f"Could not fetch characters: {e}")

        return players

    def _merge_character_lists(
        self,
        extracted: List[Dict[str, Any]],
        from_db: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge character lists, preferring DB data when available.

        Args:
            extracted: Characters extracted from analysis
            from_db: Characters from database

        Returns:
            Merged character list
        """
        merged = {}

        # Add DB characters first (they have more complete data)
        for char in from_db:
            name = char.get("name")
            if name:
                merged[name.lower()] = char

        # Add extracted characters if not already present
        for char in extracted:
            name = char.get("name")
            if name and name.lower() not in merged:
                merged[name.lower()] = char

        return list(merged.values())

    def extract_missing_npcs(
        self,
        combat_session_combatants: Dict[str, Any],
        existing_npcs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract NPCs from combat session that are missing from context.

        This handles cases where NPCs exist in the combat session but weren't
        included in the initial analysis context.

        Args:
            combat_session_combatants: Combatants dictionary from combat session
            existing_npcs: List of NPCs already identified

        Returns:
            Updated list of NPCs including any missing from combat session
        """
        npcs = existing_npcs.copy()
        npc_names_in_context = {npc.get('name') for npc in npcs if npc.get('name')}

        for char_id, combatant_state in combat_session_combatants.items():
            # Check if this is an NPC not already in our context
            if (hasattr(combatant_state, 'is_npc') and
                combatant_state.is_npc and
                combatant_state.name not in npc_names_in_context):

                # Add missing NPC from combat session
                npcs.append({
                    'name': combatant_state.name,
                    'character_id': char_id,
                    'type': 'enemy' if getattr(combatant_state, 'hostile', True) else 'npc',
                    'hostile': getattr(combatant_state, 'hostile', True),
                    'hp': getattr(combatant_state, 'hit_points_current',
                                 getattr(combatant_state, 'hp', self.DEFAULT_NPC_HP)),
                    'hp_current': getattr(combatant_state, 'hit_points_current',
                                        getattr(combatant_state, 'hp', self.DEFAULT_NPC_HP)),
                    'hp_max': getattr(combatant_state, 'hit_points_max',
                                    getattr(combatant_state, 'max_hp', self.DEFAULT_NPC_HP)),
                    'ac': getattr(combatant_state, 'armor_class',
                                getattr(combatant_state, 'ac', self.DEFAULT_NPC_AC))
                })
                logger.info(f"Added NPC {combatant_state.name} from combat session with ID {char_id}")

        return npcs
