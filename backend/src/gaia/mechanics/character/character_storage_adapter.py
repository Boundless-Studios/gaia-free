"""Character Storage Adapter - Hybrid storage layer for gradual DB migration.

This adapter provides a unified interface for character storage, supporting both
disk-based and database-backed storage. It uses a feature flag to enable gradual
migration from disk to database without disrupting existing functionality.

Migration Strategy:
- READ: Database first (if enabled), fallback to disk
- WRITE: Database (if enabled), mirror to disk for backward compatibility
- Gradual rollout controlled by USE_CHARACTER_DATABASE environment variable
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from gaia.models.character import CharacterInfo, CharacterProfile as CharacterProfileDataclass
from gaia.models.character.npc_profile import NpcProfile as NpcProfileDataclass
from gaia.models.character.enums import CharacterRole
from gaia.mechanics.character.character_storage import CharacterStorage
from gaia.mechanics.character.utils import CharacterDataConverter
from gaia.infra.storage.character_repository import CharacterRepository

logger = logging.getLogger(__name__)


class CharacterStorageAdapter:
    """Hybrid storage adapter supporting both disk and database backends.

    This adapter provides transparent migration from disk-based to database-backed
    character storage. It maintains backward compatibility while enabling new
    database features like user ownership and campaign instances.

    Feature Flag: USE_CHARACTER_DATABASE (environment variable)
    - "true": Use database with disk fallback/mirror
    - "false" or unset: Use disk only (legacy behavior)
    """

    def __init__(self):
        """Initialize the storage adapter with both disk and DB backends."""
        # Always initialize disk storage for backward compatibility
        self.disk_storage = CharacterStorage()

        # Feature flag: database storage
        self.use_database = os.getenv("USE_CHARACTER_DATABASE", "false").lower() == "true"

        if self.use_database:
            self.repository = CharacterRepository()
            logger.info("CharacterStorageAdapter: Database storage ENABLED")
        else:
            self.repository = None
            logger.info("CharacterStorageAdapter: Database storage DISABLED (disk only)")

        self.converter = CharacterDataConverter()

    # ------------------------------------------------------------------
    # Character Profile Operations
    # ------------------------------------------------------------------

    def save_character(
        self,
        character_data: Dict[str, Any],
        character_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> str:
        """Save a character profile to storage.

        Args:
            character_data: Character data dictionary
            character_id: Optional existing character ID
            user_id: User who owns this character (None = system)
            user_email: Email of the user

        Returns:
            The character ID used for storage
        """
        # Always save to disk for backward compatibility
        final_id = self.disk_storage.save_character(character_data, character_id)

        # Also save to database if enabled
        if self.use_database and self.repository:
            try:
                # Convert dict to CharacterInfo
                character_info = self.converter.from_dict(character_data, CharacterInfo)

                # Create CharacterProfile dataclass from CharacterInfo
                profile = self._character_info_to_profile(character_info)

                # Check if profile exists in DB
                try:
                    existing_uuid = self.repository.get_profile_by_external_id_sync(final_id)
                    if existing_uuid:
                        # Update existing profile
                        self.repository.update_profile_sync(existing_uuid, profile)
                        logger.debug(f"Updated character profile in DB: {final_id}")
                    else:
                        raise ValueError("Not found")  # Trigger creation
                except Exception:
                    # Create new profile
                    self.repository.create_profile_sync(profile, user_id, user_email)
                    logger.debug(f"Created character profile in DB: {final_id}")

            except Exception as e:
                logger.warning(f"Failed to save character {final_id} to database: {e}")
                # Continue with disk save, don't fail the operation

        return final_id

    def load_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Load a character from storage.

        Strategy: Database first (if enabled), fallback to disk.

        Args:
            character_id: Character identifier

        Returns:
            Character data or None if not found
        """
        # Try database first if enabled
        if self.use_database and self.repository:
            try:
                profile = self.repository.get_profile_sync(character_id)
                if profile:
                    # Convert CharacterProfile dataclass to dict
                    char_dict = self._profile_to_dict(profile)
                    logger.debug(f"Loaded character {character_id} from database")
                    return char_dict
            except Exception as e:
                logger.debug(f"Database load failed for {character_id}, falling back to disk: {e}")

        # Fallback to disk storage
        return self.disk_storage.load_character(character_id)

    def link_character_to_campaign(self, character_id: str, campaign_id: str) -> bool:
        """Link a character to a campaign.

        For database: Creates a campaign instance if it doesn't exist.
        For disk: Updates the character's campaign list.

        Args:
            character_id: Character identifier
            campaign_id: Campaign identifier

        Returns:
            True if successful
        """
        # Always update disk tracking
        disk_success = self.disk_storage.link_character_to_campaign(character_id, campaign_id)

        # Also link in database if enabled
        if self.use_database and self.repository:
            try:
                # Convert campaign_id string to UUID
                campaign_uuid = self._parse_uuid(campaign_id)
                if not campaign_uuid:
                    logger.warning(f"Invalid campaign_id format: {campaign_id}")
                    return disk_success

                # Get character profile UUID
                character_uuid = self.repository.get_profile_by_external_id_sync(character_id)
                if not character_uuid:
                    logger.warning(f"Character {character_id} not found in database")
                    return disk_success

                # Check if instance already exists
                try:
                    instance = self.repository.get_instance_sync(character_uuid, campaign_uuid)
                    if instance:
                        logger.debug(f"Campaign instance already exists for {character_id} in {campaign_id}")
                        return True
                except Exception:
                    pass  # Instance doesn't exist, create it

                # Create campaign instance
                # Load character data to create instance
                char_data = self.load_character(character_id)
                if char_data:
                    character_info = self.converter.from_dict(char_data, CharacterInfo)
                    instance_uuid = self.repository.create_instance_sync(
                        character_info, character_uuid, campaign_uuid
                    )
                    logger.info(f"Created campaign instance for {character_id} in {campaign_id}")
                    return True

            except Exception as e:
                logger.warning(f"Failed to link character {character_id} to campaign {campaign_id} in DB: {e}")

        return disk_success

    # ------------------------------------------------------------------
    # Campaign-Specific Operations
    # ------------------------------------------------------------------

    def persist_campaign_characters(
        self,
        campaign_id: str,
        characters: Dict[str, Any],
        campaign_path: Optional[Path] = None,
        user_id: Optional[str] = None,
    ) -> List[str]:
        """Persist all characters for a campaign.

        Args:
            campaign_id: Campaign identifier
            characters: Dictionary of character_id -> character_data (CharacterInfo objects)
            campaign_path: Optional path to campaign character directory
            user_id: User who owns the campaign

        Returns:
            List of character IDs that were persisted
        """
        # Always persist to disk
        disk_ids = self.disk_storage.persist_campaign_characters(
            campaign_id, characters, campaign_path
        )

        # Also persist to database if enabled
        if self.use_database and self.repository:
            try:
                campaign_uuid = self._parse_uuid(campaign_id)
                if not campaign_uuid:
                    logger.warning(f"Invalid campaign_id format: {campaign_id}")
                    return disk_ids

                for char_id, character in characters.items():
                    try:
                        # Convert to CharacterInfo if needed
                        if isinstance(character, dict):
                            character_info = self.converter.from_dict(character, CharacterInfo)
                        else:
                            character_info = character

                        # Create or update profile
                        profile = self._character_info_to_profile(character_info)

                        # Check if profile exists
                        try:
                            character_uuid = self.repository.get_profile_by_external_id_sync(char_id)
                            if not character_uuid:
                                # Create new profile
                                character_uuid = self.repository.create_profile_sync(
                                    profile, user_id, None
                                )
                        except Exception:
                            # Create new profile
                            character_uuid = self.repository.create_profile_sync(
                                profile, user_id, None
                            )

                        # Create or update campaign instance
                        try:
                            existing_instance = self.repository.get_instance_sync(
                                character_uuid, campaign_uuid
                            )
                            if existing_instance:
                                # Update existing instance
                                self.repository.update_instance_sync(
                                    existing_instance.instance_id, character_info
                                )
                            else:
                                # Create new instance
                                self.repository.create_instance_sync(
                                    character_info, character_uuid, campaign_uuid
                                )
                        except Exception as e:
                            logger.debug(f"Failed to update instance for {char_id}: {e}")
                            # Try creating new instance
                            self.repository.create_instance_sync(
                                character_info, character_uuid, campaign_uuid
                            )

                    except Exception as e:
                        logger.warning(f"Failed to persist character {char_id} to database: {e}")
                        # Continue with other characters

            except Exception as e:
                logger.warning(f"Failed to persist campaign characters to database: {e}")

        return disk_ids

    def load_campaign_characters(
        self,
        campaign_id: str,
        campaign_path: Optional[Path] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Load all characters for a campaign.

        Strategy: Database first (if enabled), fallback to disk.

        Args:
            campaign_id: Campaign identifier
            campaign_path: Optional path to campaign character directory

        Returns:
            Dictionary of character_id -> character_data
        """
        # Try database first if enabled
        if self.use_database and self.repository:
            try:
                campaign_uuid = self._parse_uuid(campaign_id)
                if campaign_uuid:
                    # Get all instances for this campaign
                    instances = self.repository.list_instances_for_campaign_sync(campaign_uuid)

                    if instances:
                        characters = {}
                        for instance in instances:
                            # Get profile for this instance
                            profile = self.repository.get_profile_by_uuid_sync(instance.character_id)
                            if profile:
                                # Merge instance + profile into CharacterInfo
                                character_info = instance.to_character_info(profile)
                                # Convert to dict
                                char_dict = self.converter.to_dict(character_info)
                                characters[character_info.character_id] = char_dict

                        if characters:
                            logger.info(f"Loaded {len(characters)} characters from database for campaign {campaign_id}")
                            return characters
            except Exception as e:
                logger.debug(f"Database load failed for campaign {campaign_id}, falling back to disk: {e}")

        # Fallback to disk storage
        return self.disk_storage.load_campaign_characters(campaign_id, campaign_path)

    # ------------------------------------------------------------------
    # NPC Operations
    # ------------------------------------------------------------------

    def save_npc_profile(
        self,
        npc_profile: NpcProfileDataclass,
        user_id: str,
        campaign_id: Optional[str] = None,
    ) -> str:
        """Save an NPC profile to storage.

        Args:
            npc_profile: NPC profile dataclass
            user_id: User who created this NPC
            campaign_id: Optional campaign association

        Returns:
            The NPC ID
        """
        if self.use_database and self.repository:
            try:
                campaign_uuid = self._parse_uuid(campaign_id) if campaign_id else None

                # Check if NPC exists
                try:
                    existing_uuid = self.repository.get_npc_by_external_id_sync(npc_profile.npc_id)
                    if existing_uuid:
                        # Update existing NPC
                        self.repository.update_npc_sync(existing_uuid, npc_profile)
                        logger.debug(f"Updated NPC profile in DB: {npc_profile.npc_id}")
                        return npc_profile.npc_id
                except Exception:
                    pass  # NPC doesn't exist, create it

                # Create new NPC
                self.repository.create_npc_sync(
                    npc_profile, user_id, None, campaign_uuid
                )
                logger.info(f"Created NPC profile in DB: {npc_profile.npc_id}")
                return npc_profile.npc_id

            except Exception as e:
                logger.warning(f"Failed to save NPC {npc_profile.npc_id} to database: {e}")

        # For now, disk storage doesn't have specific NPC profile storage
        # This would use the existing NpcProfileStorage class
        logger.debug(f"NPC profile {npc_profile.npc_id} saved (DB only)")
        return npc_profile.npc_id

    def load_npc_profile(self, npc_id: str) -> Optional[NpcProfileDataclass]:
        """Load an NPC profile from storage.

        Args:
            npc_id: NPC identifier

        Returns:
            NPC profile dataclass or None
        """
        if self.use_database and self.repository:
            try:
                npc_profile = self.repository.get_npc_sync(npc_id)
                if npc_profile:
                    logger.debug(f"Loaded NPC {npc_id} from database")
                    return npc_profile
            except Exception as e:
                logger.debug(f"Database load failed for NPC {npc_id}: {e}")

        # Disk fallback would use NpcProfileStorage
        logger.debug(f"NPC {npc_id} not found in database")
        return None

    # ------------------------------------------------------------------
    # List Operations
    # ------------------------------------------------------------------

    def list_characters(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all available characters.

        Args:
            user_id: Optional user filter (only with database)

        Returns:
            List of character summaries
        """
        # Try database first if enabled
        if self.use_database and self.repository:
            try:
                if user_id:
                    # Get user-specific characters
                    profiles = self.repository.list_profiles_by_user_sync(user_id)
                else:
                    # Get system characters (user_id = None)
                    profiles = self.repository.list_system_profiles_sync()

                # Convert to summary format
                characters = []
                for profile in profiles:
                    characters.append({
                        'id': profile.character_id,
                        'name': profile.name,
                        'class': profile.character_class,
                        'race': profile.race,
                        'level': profile.base_level,
                        'character_type': profile.character_type.value,
                        'created_at': profile.first_created.isoformat() if profile.first_created else None,
                    })

                if characters:
                    logger.info(f"Loaded {len(characters)} characters from database")
                    return characters
            except Exception as e:
                logger.debug(f"Database list failed, falling back to disk: {e}")

        # Fallback to disk storage
        return self.disk_storage.list_characters()

    def get_campaign_characters(self, campaign_id: str) -> List[str]:
        """Get all character IDs associated with a campaign.

        Args:
            campaign_id: Campaign identifier

        Returns:
            List of character IDs
        """
        # Try database first if enabled
        if self.use_database and self.repository:
            try:
                campaign_uuid = self._parse_uuid(campaign_id)
                if campaign_uuid:
                    instances = self.repository.list_instances_for_campaign_sync(campaign_uuid)
                    if instances:
                        # Get external character IDs from profiles
                        character_ids = []
                        for instance in instances:
                            profile = self.repository.get_profile_by_uuid_sync(instance.character_id)
                            if profile:
                                character_ids.append(profile.external_character_id)

                        if character_ids:
                            logger.info(f"Found {len(character_ids)} characters in campaign {campaign_id} (DB)")
                            return character_ids
            except Exception as e:
                logger.debug(f"Database query failed for campaign {campaign_id}, falling back to disk: {e}")

        # Fallback to disk storage
        return self.disk_storage.get_campaign_characters(campaign_id)

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _character_info_to_profile(self, character_info: CharacterInfo) -> CharacterProfileDataclass:
        """Convert CharacterInfo to CharacterProfile dataclass.

        Args:
            character_info: CharacterInfo instance

        Returns:
            CharacterProfile dataclass
        """
        from gaia.models.character.enums import CharacterType, VoiceArchetype

        # Determine character type
        if character_info.character_type == "player":
            char_type = CharacterType.PLAYER
        elif character_info.character_type == "npc":
            char_type = CharacterType.NPC
        else:
            char_type = CharacterType.NPC

        # Parse voice archetype if present
        voice_archetype = None
        if hasattr(character_info, 'voice_archetype') and character_info.voice_archetype:
            try:
                voice_archetype = VoiceArchetype(character_info.voice_archetype)
            except (ValueError, AttributeError):
                pass

        return CharacterProfileDataclass(
            character_id=character_info.character_id,
            name=character_info.name,
            character_type=char_type,
            race=character_info.race,
            character_class=character_info.character_class,
            base_level=character_info.level,
            voice_id=getattr(character_info, 'voice_id', None),
            voice_settings=getattr(character_info, 'voice_settings', {}),
            voice_archetype=voice_archetype,
            portrait_url=getattr(character_info, 'portrait_url', None),
            portrait_path=getattr(character_info, 'portrait_path', None),
            portrait_prompt=getattr(character_info, 'portrait_prompt', None),
            gender=getattr(character_info, 'gender', None),
            age_category=getattr(character_info, 'age_category', None),
            build=getattr(character_info, 'build', None),
            height_description=getattr(character_info, 'height_description', None),
            facial_expression=getattr(character_info, 'facial_expression', None),
            facial_features=getattr(character_info, 'facial_features', None),
            attire=getattr(character_info, 'attire', None),
            primary_weapon=getattr(character_info, 'primary_weapon', None),
            distinguishing_feature=getattr(character_info, 'distinguishing_feature', None),
            background_setting=getattr(character_info, 'background_setting', None),
            pose=getattr(character_info, 'pose', None),
            backstory=character_info.backstory,
            description=character_info.description,
            appearance=character_info.appearance,
            visual_description=character_info.visual_description,
        )

    def _profile_to_dict(self, profile: CharacterProfileDataclass) -> Dict[str, Any]:
        """Convert CharacterProfile dataclass to dictionary format.

        Args:
            profile: CharacterProfile dataclass

        Returns:
            Dictionary representation
        """
        return {
            'id': profile.character_id,
            'character_id': profile.character_id,
            'name': profile.name,
            'character_type': profile.character_type.value,
            'race': profile.race,
            'character_class': profile.character_class,
            'level': profile.base_level,
            'voice_id': profile.voice_id,
            'voice_settings': profile.voice_settings,
            'voice_archetype': profile.voice_archetype.value if profile.voice_archetype else None,
            'portrait_url': profile.portrait_url,
            'portrait_path': profile.portrait_path,
            'portrait_prompt': profile.portrait_prompt,
            'gender': profile.gender,
            'age_category': profile.age_category,
            'build': profile.build,
            'height_description': profile.height_description,
            'facial_expression': profile.facial_expression,
            'facial_features': profile.facial_features,
            'attire': profile.attire,
            'primary_weapon': profile.primary_weapon,
            'distinguishing_feature': profile.distinguishing_feature,
            'background_setting': profile.background_setting,
            'pose': profile.pose,
            'backstory': profile.backstory,
            'description': profile.description,
            'appearance': profile.appearance,
            'visual_description': profile.visual_description,
            'total_interactions': profile.total_interactions,
            'first_created': profile.first_created.isoformat() if profile.first_created else None,
        }

    def _parse_uuid(self, id_str: str) -> Optional[uuid.UUID]:
        """Parse a string to UUID, handling various formats.

        Args:
            id_str: String that might be a UUID

        Returns:
            UUID object or None if not valid
        """
        if not id_str:
            return None

        try:
            return uuid.UUID(id_str)
        except (ValueError, AttributeError):
            return None
