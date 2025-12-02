"""Character Manager - Primary interface for character management operations."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import json

from gaia.models.character import CharacterInfo, CharacterProfile
from gaia.models.character.enums import CharacterRole
from gaia.models.character.npc_profile import NpcProfile
from gaia.mechanics.character.character_translator import CharacterTranslator
from gaia.mechanics.character.character_storage import CharacterStorage
from gaia.mechanics.character.character_updater import CharacterUpdater
from gaia.mechanics.character.profile_manager import ProfileManager
from gaia.mechanics.character.voice_pool import VoicePool
from gaia.mechanics.character.utils import CharacterDataConverter, PathResolver
from gaia.mechanics.character.npc_updater import NpcUpdater
from gaia.mechanics.character.npc_profile_storage import NpcProfileStorage
from gaia_private.extraction.character_resolution import CharacterExtractorResult
from gaia.models.campaign import CampaignData
from gaia.models.npc import NPCInfo
from gaia.infra.storage.campaign_store import get_campaign_store

logger = logging.getLogger(__name__)


class CharacterManager:
    """Primary interface for managing characters in campaigns.

    This class coordinates between various character subsystems:
    - CharacterStorage: Handles persistence and loading
    - CharacterUpdater: Handles character state updates
    - CharacterTranslator: Handles format conversions
    - ProfileManager: Manages character profiles (identity, portraits, enrichment)
    - VoicePool: Manages voice assignments
    """
    
    def __init__(self, campaign_id: str):
        """Initialize the character manager for a specific campaign.
        
        Args:
            campaign_id: The ID of the campaign this manager is associated with
        """
        self.campaign_id = campaign_id
        self.characters: Dict[str, CharacterInfo] = {}  # character_id -> CharacterInfo
        
        # Initialize subsystems
        self.translator = CharacterTranslator()
        self.storage = CharacterStorage()
        self.updater = CharacterUpdater()
        self.profile_manager = ProfileManager()
        self.voice_pool = VoicePool()
        self.converter = CharacterDataConverter()
        self.path_resolver = PathResolver(campaign_id)
        self.npc_profile_storage = NpcProfileStorage()
        self.npc_updater = NpcUpdater(self.npc_profile_storage)

        # Unified campaign store (local + GCS) based on campaign manager's storage
        try:
            self._store = get_campaign_store(self.path_resolver.campaign_manager.storage)
        except Exception:
            self._store = None

        # Load existing characters
        self._load_characters()
    
    def _load_characters(self):
        """Load existing characters from storage for this campaign."""
        try:
            # Get campaign-specific character path
            characters_path = self.path_resolver.get_characters_path()

            # Load characters using storage module
            characters_dict = self.storage.load_campaign_characters(
                self.campaign_id,
                campaign_path=characters_path
            )

            # Convert loaded data to CharacterInfo objects
            for char_id, char_data in characters_dict.items():
                character = self.converter.from_dict(char_data, CharacterInfo)
                self.characters[char_id] = character

            if characters_dict:
                logger.info(f"Loaded {len(characters_dict)} characters for campaign {self.campaign_id}")

        except Exception as e:
            logger.warning(f"Could not load characters for campaign {self.campaign_id}: {e}", exc_info=True)
    
    def create_character_from_simple(self, simple_char: Dict[str, Any], slot_id: Optional[int] = None) -> CharacterInfo:
        """Create a full CharacterInfo from simple character data.
        
        Args:
            simple_char: Simple character dictionary from frontend or pre-generated data
            slot_id: Optional slot ID for the character
            
        Returns:
            Created CharacterInfo object
        """
        # Use translator to create CharacterInfo
        character_info = self.translator.simple_to_character_info(simple_char, slot_id)
        
        # Save character to persistent storage
        char_dict = self.converter.to_dict(character_info)
        stored_id = self.storage.save_character(char_dict)
        character_info.character_id = stored_id
        
        # Link character to campaign
        self.storage.link_character_to_campaign(stored_id, self.campaign_id)
        
        # Also save to campaign-specific directory for campaign state
        characters_path = self.path_resolver.get_characters_path()
        if characters_path:
            characters_path.mkdir(parents=True, exist_ok=True)
            char_file = characters_path / f"{stored_id}.json"
            with open(char_file, 'w', encoding='utf-8') as f:
                json.dump(char_dict, f, indent=2, ensure_ascii=False, default=str)
            # Mirror campaign character state via store when available
            if self._store is not None:
                try:
                    self._store.write_json(char_dict, self.campaign_id, f"data/characters/{stored_id}.json")
                except Exception as exc:
                    logger.warning("Character store mirror failed for %s: %s", stored_id, exc)
        
        # Create or update character profile with full metadata (including visual data)
        profile_id = self.profile_manager.ensure_profile_exists(character_info)

        # Set profile_id on character_info (link to profile)
        if not hasattr(character_info, 'profile_id') or not character_info.profile_id:
            character_info.profile_id = profile_id

        # Load the profile to check voice assignment
        profile = self.profile_manager.get_profile(profile_id)

        # Assign voice if not already assigned
        if not profile.voice_id:
            # Determine archetype based on character data
            from gaia.mechanics.character.character_info_generator import CharacterInfoGenerator
            generator = CharacterInfoGenerator()
            archetype = generator.determine_voice_archetype(char_dict)

            # Assign voice with determined archetype
            voice_id, voice_archetype = self.voice_pool.assign_voice(profile, archetype)
            profile.voice_id = voice_id
            profile.voice_archetype = voice_archetype
            self.profile_manager.storage.save_profile(profile)

            # Invalidate cache after profile update
            self.profile_manager.invalidate_cache(profile_id)

            # Update character_info with voice
            character_info.voice_id = voice_id
            character_info.voice_settings = profile.voice_settings
        else:
            # Use existing voice from profile
            character_info.voice_id = profile.voice_id
            character_info.voice_settings = profile.voice_settings

        # Update interaction count
        self.profile_manager.update_profile_interactions(profile.character_id)
        
        # Add to manager's character collection
        self.add_character(character_info)
        logger.info(f"Created and stored character: {character_info.name} (ID: {stored_id}, Voice: {profile.voice_id})")
        return character_info
    
    def create_characters_from_slots(
        self,
        character_slots: List[Dict[str, Any]]
    ) -> List[Tuple[CharacterInfo, Optional[int]]]:
        """Create multiple characters from slot data.

        Automatically detects NPCs vs PCs based on 'hostile' flag or 'character_type' field.

        Args:
            character_slots: List of character slot dictionaries

        Returns:
            List of tuples (CharacterInfo, slot_id) preserving the slot
        """
        from gaia.models.character.enums import CharacterRole

        characters: List[Tuple[CharacterInfo, Optional[int]]] = []
        for idx, char_dict in enumerate(character_slots):
            if char_dict:  # Skip empty slots
                slot_id = char_dict.get('slot_id')
                translator_slot = slot_id if slot_id is not None else idx
                character_info = self.create_character_from_simple(char_dict, slot_id=translator_slot)

                # Detect if this should be an NPC based on hostile flag or explicit type
                is_npc = char_dict.get('hostile', False) or char_dict.get('character_type') == 'npc'

                if is_npc:
                    character_info.character_type = "npc"
                    character_info.character_role = CharacterRole.NPC_COMBATANT
                else:
                    character_info.character_type = "player"
                    character_info.character_role = CharacterRole.PLAYER

                characters.append((character_info, slot_id))
        return characters

    def add_character(self, character: CharacterInfo):
        """Add a character to the manager.
        
        Args:
            character: CharacterInfo object to add
        """
        self.characters[character.character_id] = character
        character.last_interaction = datetime.now()

    # ------------------------------------------------------------------
    # NPC profile helpers
    # ------------------------------------------------------------------

    def ensure_npc_profile(
        self,
        name: str,
        role: CharacterRole = CharacterRole.NPC_SUPPORT,
    ) -> NpcProfile:
        """Ensure an NPC profile exists for the given name."""
        return self.npc_updater.ensure_profile(name, role)

    def update_npc_profile_from_structured(
        self,
        name: str,
        structured_data: Dict[str, Any],
    ) -> NpcProfile:
        """Update an NPC profile using structured agent output."""
        return self.npc_updater.update_from_structured(name, structured_data)

    def promote_npc_to_character(self, profile: NpcProfile) -> None:
        """Mark an NPC profile as promoted to a full character."""
        self.npc_updater.promote_to_character(profile)
    
    def sync_npcs_from_extractor(
        self,
        campaign_data: CampaignData,
        extractor_result: Optional[CharacterExtractorResult],
        *,
        scene_id: Optional[str] = None,
    ) -> Tuple[int, int]:
        """Apply extractor NPC output to campaign data.

        Returns:
            Tuple of (added_count, updated_count).
        """
        if not campaign_data or not extractor_result:
            return (0, 0)

        npcs_added = 0
        npcs_updated = 0

        def _append_note(notes: List[str], note: Optional[str]) -> None:
            if not note:
                return
            if note not in notes:
                notes.append(note)

        # Existing NPC references (character_resolution.npcs / monsters)
        for npc_ref in getattr(extractor_result, "npcs", []) or []:
            npc_id = getattr(npc_ref, "character_id", None)
            if not npc_id:
                continue

            existing_npc = campaign_data.npcs.get(npc_id)
            if existing_npc:
                if scene_id:
                    _append_note(existing_npc.notes, f"Last seen: {scene_id}")
                npcs_updated += 1
                continue

            new_npc = NPCInfo(
                npc_id=npc_id,
                name=getattr(npc_ref, "display_name", "") or npc_id,
                role=getattr(npc_ref, "role", "") or "unknown",
                description="",
                location=scene_id or "",
                disposition="neutral",
                notes=[f"First seen: {scene_id}"] if scene_id else [],
            )
            campaign_data.npcs[npc_id] = new_npc
            npcs_added += 1

        # New characters discovered in this scene
        for placeholder in getattr(extractor_result, "new_characters", []) or []:
            npc_id = getattr(placeholder, "temporary_id", None)
            if not npc_id:
                continue

            existing_npc = campaign_data.npcs.get(npc_id)
            if existing_npc:
                if scene_id:
                    _append_note(existing_npc.notes, f"Last seen: {scene_id}")
                npcs_updated += 1
                continue

            prototype = getattr(placeholder, "prototype", None) or {}
            description = prototype.get("description", "")
            disposition = prototype.get("disposition", "neutral")

            notes: List[str] = []
            if scene_id:
                notes.append(f"First seen: {scene_id}")
            rationale = getattr(placeholder, "rationale", "")
            if rationale:
                notes.append(f"Rationale: {rationale}")

            new_npc = NPCInfo(
                npc_id=npc_id,
                name=getattr(placeholder, "display_name", "") or npc_id,
                role=getattr(placeholder, "role", "") or "unknown",
                description=description,
                location=scene_id or prototype.get("location", ""),
                disposition=disposition or "neutral",
                notes=notes,
            )
            campaign_data.npcs[npc_id] = new_npc
            npcs_added += 1

        return npcs_added, npcs_updated
    
    def get_character(self, character_id: str) -> Optional[CharacterInfo]:
        """Get a character by ID.

        Checks in-memory cache first, then falls back to loading from storage.
        This ensures characters are accessible even if _load_characters() failed
        during initialization.

        Args:
            character_id: The character's ID

        Returns:
            CharacterInfo if found, None otherwise
        """
        # Check in-memory cache first
        character = self.characters.get(character_id)
        if character:
            return character

        # Fall back to loading from storage
        try:
            char_data = self.storage.load_character(character_id)
            if char_data:
                character = self.converter.from_dict(char_data, CharacterInfo)
                # Cache for future lookups
                self.characters[character_id] = character
                logger.info(f"Loaded character {character_id} from storage (cache miss)")
                return character
        except Exception as e:
            logger.warning(f"Failed to load character {character_id} from storage: {e}")

        return None
    
    def get_character_details(
        self,
        character_id: str,
        *,
        include_alignment: bool = True,
        include_voice: bool = True,
    ) -> Dict[str, Any]:
        """Return lightweight character details for contextual usage."""
        character = self.get_character(character_id)
        if not character:
            return {}

        raw_name = getattr(character, "name", None) or character_id
        display_name = raw_name
        if display_name == character_id and ":" in character_id:
            display_name = character_id.split(":", 1)[1]
        if display_name == character_id:
            display_name = display_name.replace("_", " ").title()

        details: Dict[str, Any] = {
            "name": display_name,
            "personality_traits": list(character.personality_traits),
            "backstory": character.backstory,
            "description": character.description,
            "character_class": character.character_class,
            "race": character.race,
        }
        if include_alignment and character.alignment:
            details["alignment"] = character.alignment
        if include_voice and character.voice_id:
            details["voice_id"] = character.voice_id
        return details
    
    def get_character_by_name(self, name: str) -> Optional[CharacterInfo]:
        """Get a character by name (case-insensitive).
        
        Args:
            name: The character's name
            
        Returns:
            CharacterInfo if found, None otherwise
        """
        name_lower = name.lower()
        for char in self.characters.values():
            if char.name.lower() == name_lower:
                return char
        return None
    
    def get_all_characters(self) -> List[CharacterInfo]:
        """Get all characters.
        
        Returns:
            List of all CharacterInfo objects
        """
        return list(self.characters.values())
    
    def get_player_characters(self) -> List[CharacterInfo]:
        """Get only player characters (not NPCs).
        
        Returns:
            List of player CharacterInfo objects
        """
        return [char for char in self.characters.values() 
                if char.character_type == "player"]
    
    # Character Update Methods (delegating to CharacterUpdater)
    
    def update_character_from_dm(self, dm_update: Dict[str, Any]):
        """Update character information based on DM response.
        
        Args:
            dm_update: Dictionary containing character updates from DM
        """
        # Update specific characters if mentioned
        if "character_updates" in dm_update:
            for char_id, updates in dm_update["character_updates"].items():
                if char_id in self.characters:
                    self.updater.apply_updates(self.characters[char_id], updates)
        
        # Character parsing from DM narrative removed; extractor handles roster resolution
    
    def apply_damage(self, character_name: str, damage: int, damage_type: Optional[str] = None):
        """Apply damage to a character.
        
        Args:
            character_name: Name of the character
            damage: Amount of damage
            damage_type: Optional damage type
        """
        character = self.get_character_by_name(character_name)
        if character:
            self.updater.apply_combat_damage(character, damage, damage_type)
    
    def apply_healing(self, character_name: str, healing: int, source: Optional[str] = None):
        """Apply healing to a character.
        
        Args:
            character_name: Name of the character
            healing: Amount of healing
            source: Optional source of healing
        """
        character = self.get_character_by_name(character_name)
        if character:
            self.updater.apply_healing(character, healing, source)
    
    def level_up_character(self, character_name: str):
        """Level up a character.
        
        Args:
            character_name: Name of the character to level up
        """
        character = self.get_character_by_name(character_name)
        if character:
            self.updater.level_up(character)
    
    # Persistence Methods (delegating to CharacterStorage)
    
    def persist_characters(self):
        """Persist all characters to storage for this campaign.
        
        Returns:
            List of character IDs that were persisted
        """
        characters_path = self.path_resolver.get_characters_path()
        return self.storage.persist_campaign_characters(
            self.campaign_id,
            self.characters,
            campaign_path=characters_path
        )
    
    def persist_to_campaign(self, campaign_data):
        """Persist character IDs to campaign data.
        
        Args:
            campaign_data: Campaign data object to persist characters to
        """
        character_ids = list(self.characters.keys())
        campaign_data.character_ids = character_ids
        logger.info("Persisted %d character IDs to campaign data", len(character_ids))

        # Immediately persist the updated campaign data to disk/storage when available
        try:
            campaign_manager = self.path_resolver.campaign_manager
            if hasattr(campaign_manager, "save_campaign_data"):
                campaign_manager.save_campaign_data(self.campaign_id, campaign_data)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to persist campaign data for %s after character update: %s",
                self.campaign_id,
                exc,
            )
    
    # Context and Summary Methods
    
    def get_character_context_for_dm(self) -> Dict[str, Any]:
        """Get character context formatted for the Dungeon Master.
        
        Returns:
            Dictionary containing all character information for DM context
        """
        player_chars = self.get_player_characters()
        
        context = {
            "party_size": len(player_chars),
            "characters": []
        }
        
        for char in player_chars:
            char_summary = {
                "name": char.name,
                "class": char.character_class,
                "race": char.race,
                "level": char.level,
                "hp": f"{char.hit_points_current}/{char.hit_points_max}",
                "ac": char.armor_class,
                "status": char.status.value,
                "location": char.location,
                "key_items": [item.name for item in char.inventory.values() 
                             if item.item_type in ["weapon", "artifact", "quest"]],
                "backstory": char.backstory[:200] if char.backstory else "No backstory"
            }
            
            # Add abilities summary
            if char.abilities:
                char_summary["abilities"] = [ability.name for ability in char.abilities.values()]
            
            context["characters"].append(char_summary)
        
        # Create a narrative summary
        context["summary"] = self._create_party_summary(player_chars)
        
        return context
    
    def _create_party_summary(self, characters: List[CharacterInfo]) -> str:
        """Create a narrative summary of the party.
        
        Args:
            characters: List of player characters
            
        Returns:
            Narrative summary string
        """
        if not characters:
            return "No party members present."
        
        names = [char.name for char in characters]
        classes = [f"{char.name} the {char.race} {char.character_class}" for char in characters]
        
        summary = f"The party consists of {len(characters)} members: {', '.join(classes)}. "
        
        # Add status information
        injured = [char.name for char in characters if char.status.value != "healthy"]
        if injured:
            summary += f"Currently injured: {', '.join(injured)}. "
        
        # Add level range
        levels = [char.level for char in characters]
        if levels:
            summary += f"Party levels range from {min(levels)} to {max(levels)}."
        
        return summary
    
    # Serialization Methods
    
    def to_json(self) -> str:
        """Serialize all characters to JSON.
        
        Returns:
            JSON string of all characters
        """
        characters_dict = {
            char_id: self.converter.to_dict(char)
            for char_id, char in self.characters.items()
        }
        return json.dumps(characters_dict, indent=2, default=str)
    
    def from_json(self, json_str: str):
        """Load characters from JSON.
        
        Args:
            json_str: JSON string containing character data
        """
        try:
            characters_dict = json.loads(json_str)
            self.characters.clear()
            
            for char_id, char_data in characters_dict.items():
                character = self.converter.from_dict(char_data, CharacterInfo)
                self.characters[char_id] = character
            
            logger.info(f"Loaded {len(self.characters)} characters from JSON")
        except Exception as e:
            logger.error(f"Error loading characters from JSON: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the managed characters.

        Returns:
            Dictionary containing character statistics
        """
        from gaia.models.character import CharacterStatus
        player_chars = self.get_player_characters()

        return {
            "total_characters": len(self.characters),
            "player_characters": len(player_chars),
            "npcs": len(self.characters) - len(player_chars),
            "average_level": sum(c.level for c in player_chars) / len(player_chars) if player_chars else 0,
            "party_health": {
                "healthy": len([c for c in player_chars if c.status == CharacterStatus.HEALTHY]),
                "injured": len([c for c in player_chars if c.status == CharacterStatus.INJURED]),
                "affected": len([c for c in player_chars if c.status == CharacterStatus.AFFECTED]),
                "unconscious": len([c for c in player_chars if c.status == CharacterStatus.UNCONSCIOUS]),
                "dead": len([c for c in player_chars if c.status == CharacterStatus.DEAD])
            }
        }

    # ------------------------------------------------------------------
    # Profile Management Methods (Delegated to ProfileManager)
    # ------------------------------------------------------------------

    def get_enriched_character(self, character_id: str) -> 'EnrichedCharacter':
        """Get character with profile data merged (enriched view).

        Delegates to ProfileManager for profile loading and enrichment.

        Args:
            character_id: The character's ID

        Returns:
            EnrichedCharacter with merged identity and campaign state

        Raises:
            ValueError: If character not found
        """
        character_info = self.get_character(character_id)
        if not character_info:
            raise ValueError(f"Character {character_id} not found in campaign")

        return self.profile_manager.enrich_character(character_info)

    async def generate_character_portrait(
        self,
        character_id: str,
        custom_additions: Optional[str] = None,
        character_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate portrait for a character.

        Delegates to ProfileManager for portrait generation.

        Args:
            character_id: ID of the character to generate portrait for
            custom_additions: Optional custom prompt additions
            character_data: Optional character data for non-persisted characters (during setup)

        Returns:
            Dictionary with success status and portrait information
        """
        character_info = self.get_character(character_id)
        return await self.profile_manager.generate_portrait(
            character_id=character_id,
            character_info=character_info,
            custom_additions=custom_additions,
            character_data=character_data,
            session_id=self.campaign_id
        )

    def update_character_visuals(
        self,
        character_id: str,
        visual_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update character visual metadata.

        Delegates to ProfileManager for visual updates.

        Args:
            character_id: ID of the character to update
            visual_data: Dictionary of visual fields to update

        Returns:
            Dictionary with success status and updated character data
        """
        if not self.get_character(character_id):
            return {"success": False, "error": "Character not found"}

        return self.profile_manager.update_character_visuals(character_id, visual_data)

    def get_character_portrait(self, character_id: str) -> Dict[str, Any]:
        """Get portrait information for a character.

        Delegates to ProfileManager for portrait retrieval.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with portrait information
        """
        if not self.get_character(character_id):
            return {"success": False, "error": "Character not found"}

        return self.profile_manager.get_portrait(character_id)
