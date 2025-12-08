"""Profile Manager - Orchestrates character profile operations with caching."""

from typing import Dict, Any, Optional
import logging
from pathlib import Path

from gaia.models.character import CharacterProfile, CharacterInfo
from gaia.models.character.enriched_character import EnrichedCharacter
from gaia.models.character.enums import CharacterType
from gaia.mechanics.character.profile_storage import ProfileStorage
from gaia.mechanics.character.profile_updater import ProfileUpdater
from gaia.infra.image.image_metadata import get_metadata_manager

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages character profile operations with caching and orchestration.

    This class coordinates between ProfileStorage (I/O) and ProfileUpdater (business logic),
    providing caching for performance and high-level orchestration for complex operations
    like portrait generation and profile enrichment.
    """

    def __init__(self):
        """Initialize the profile manager."""
        self.storage = ProfileStorage()
        self.updater = ProfileUpdater()
        self._cache: Dict[str, CharacterProfile] = {}

    # ------------------------------------------------------------------
    # Cache Management
    # ------------------------------------------------------------------

    def get_profile(self, profile_id: str) -> CharacterProfile:
        """Load character profile with caching.

        Args:
            profile_id: The profile ID to load

        Returns:
            CharacterProfile from storage

        Raises:
            ValueError: If profile not found
        """
        # Check cache first
        if profile_id in self._cache:
            return self._cache[profile_id]

        # Load from storage
        profile = self.storage.load_profile(profile_id)
        if not profile:
            raise ValueError(f"Profile {profile_id} not found")

        # Cache for future use
        self._cache[profile_id] = profile
        logger.debug(f"Profile {profile_id} loaded from storage and cached")
        return profile

    def invalidate_cache(self, profile_id: str) -> None:
        """Remove a profile from the cache.

        Args:
            profile_id: The profile ID to invalidate
        """
        if profile_id in self._cache:
            self._cache.pop(profile_id)
            logger.debug(f"Invalidated cache for profile {profile_id}")

    # ------------------------------------------------------------------
    # Profile Lifecycle
    # ------------------------------------------------------------------

    def ensure_profile_exists(self, character_info: CharacterInfo) -> str:
        """Ensure a CharacterProfile exists for this character, create if needed.

        This is used during character creation to ensure every character has a profile.
        Updates existing profiles with new data from CharacterInfo.

        Args:
            character_info: The character to ensure profile for

        Returns:
            The profile_id (character_id)
        """
        # Try to find existing profile
        profile_exists = False
        try:
            profile = self.get_profile(character_info.character_id)
            logger.info(f"Found existing profile for {character_info.name}, updating with latest data")
            profile_exists = True
        except ValueError:
            # Profile doesn't exist, create it
            logger.info(f"Creating new profile for {character_info.name}")

            # Determine character type
            character_type = CharacterType.PLAYER if character_info.character_type == "player" else CharacterType.NPC

            # Create profile using find_or_create_profile from storage
            profile = self.storage.find_or_create_profile(
                name=character_info.name,
                character_info=character_info
            )

            # Set character_id and character_type explicitly
            profile.character_id = character_info.character_id
            profile.character_type = character_type

        # Update profile with data from CharacterInfo (works for both new and existing profiles)
        self.updater.sync_from_character_info(profile, character_info)

        # Save profile
        self.storage.save_profile(profile)

        # Cache the profile
        self._cache[profile.character_id] = profile

        return profile.character_id

    # ------------------------------------------------------------------
    # Visual Metadata Operations
    # ------------------------------------------------------------------

    def update_visual_metadata(self, profile_id: str, visual_data: Dict[str, Any]) -> None:
        """Update visual metadata in CharacterProfile.

        Args:
            profile_id: The profile ID to update
            visual_data: Dictionary of visual fields to update

        Raises:
            ValueError: If profile not found
        """
        # Load profile (with caching)
        profile = self.get_profile(profile_id)

        # Update visual fields using updater
        self.updater.update_visual_fields(profile, visual_data)

        # Save profile
        self.storage.save_profile(profile)

        # Invalidate cache so next load gets fresh data
        self.invalidate_cache(profile_id)

        logger.info(f"Updated visual metadata for profile {profile_id}")

    def update_character_visuals(
        self,
        character_id: str,
        visual_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update character visual metadata.

        Args:
            character_id: ID of the character to update
            visual_data: Dictionary of visual fields to update

        Returns:
            Dictionary with success status and updated character data
        """
        try:
            # Get profile_id (use character_id as profile_id until migration)
            profile_id = character_id

            # Ensure profile exists
            try:
                self.get_profile(profile_id)
            except ValueError:
                return {"success": False, "error": "Profile not found"}

            # Update visual metadata in profile
            self.update_visual_metadata(profile_id, visual_data)

            return {
                "success": True,
                "character_id": character_id,
                "profile_id": profile_id,
                "updated_fields": list(visual_data.keys())
            }

        except Exception as e:
            logger.error(f"Failed to update visual metadata: {e}")
            return {
                "success": False,
                "error": f"Failed to update visual metadata: {str(e)}"
            }

    # ------------------------------------------------------------------
    # Portrait Generation
    # ------------------------------------------------------------------

    async def generate_portrait(
        self,
        character_id: str,
        character_info: Optional[CharacterInfo] = None,
        custom_additions: Optional[str] = None,
        character_data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate portrait for a character.

        Args:
            character_id: ID of the character to generate portrait for
            character_info: Optional CharacterInfo object (if character exists in manager)
            custom_additions: Optional custom prompt additions
            character_data: Optional character data for non-persisted characters (during setup)
            session_id: Session/campaign ID for storage

        Returns:
            Dictionary with success status and portrait information
        """
        from gaia.mechanics.character.portrait_generator import CharacterPortraitGenerator

        # If character_info not provided, try to build from character_data
        if not character_info and character_data:
            try:
                # Build temporary CharacterInfo from slot data
                character_info = CharacterInfo(
                    character_id=character_id,
                    name=character_data.get('name', 'Unknown'),
                    character_class=character_data.get('character_class', 'Fighter'),
                    race=character_data.get('race', 'Human'),
                    level=character_data.get('level', 1),
                    gender=character_data.get('gender'),
                    age_category=character_data.get('age_category'),
                    build=character_data.get('build'),
                    height_description=character_data.get('height_description'),
                    facial_expression=character_data.get('facial_expression'),
                    facial_features=character_data.get('facial_features'),
                    attire=character_data.get('attire'),
                    primary_weapon=character_data.get('primary_weapon'),
                    distinguishing_feature=character_data.get('distinguishing_feature'),
                    background_setting=character_data.get('background_setting'),
                    pose=character_data.get('pose'),
                    # Include text descriptions from character data
                    backstory=character_data.get('backstory', ''),
                    description=character_data.get('description', ''),
                    appearance=character_data.get('appearance', ''),
                    visual_description=character_data.get('visual_description', '')
                )
            except Exception as e:
                logger.error(f"Failed to build CharacterInfo from data: {e}")
                return {"success": False, "error": f"Invalid character data: {str(e)}"}

        if not character_info:
            return {"success": False, "error": "Character not found and no character data provided"}

        portrait_gen = CharacterPortraitGenerator()
        result = await portrait_gen.generate_portrait(
            character_info=character_info,
            session_id=session_id or "default",
            custom_additions=custom_additions
        )

        if result.get("success"):
            # Save portrait to CharacterProfile
            try:
                # Get profile_id (use character_id as profile_id until migration)
                profile_id = getattr(character_info, 'profile_id', character_id)

                # Ensure profile exists
                try:
                    profile = self.get_profile(profile_id)
                except ValueError:
                    # Profile doesn't exist, create it
                    profile_id = self.ensure_profile_exists(character_info)
                    profile = self.get_profile(profile_id)

                # Update profile with portrait data
                # Use proxy_url if available (from artifact store), otherwise fall back to image_url
                profile.portrait_url = result.get("proxy_url") or result.get("image_url")
                profile.portrait_path = result.get("local_path")
                profile.portrait_prompt = result.get("prompt")

                # Save profile
                self.storage.save_profile(profile)

                # Invalidate cache
                self.invalidate_cache(profile_id)

            except Exception as e:
                logger.error(f"Failed to save portrait to profile: {e}")
                # Don't fail the whole operation, portrait was generated successfully

            # Persist metadata so /api/images can resolve via storage_path
            try:
                metadata_manager = get_metadata_manager()
                campaign_ref = session_id or getattr(character_info, "campaign_id", None) or "default"

                storage_filename = result.get("storage_filename")
                if not storage_filename:
                    if result.get("storage_path"):
                        storage_filename = Path(str(result["storage_path"])).name
                    elif result.get("local_path"):
                        storage_filename = Path(str(result["local_path"])).name

                if storage_filename:
                    result.setdefault("storage_filename", storage_filename)
                    metadata_payload = {
                        "prompt": result.get("prompt"),
                        "type": result.get("type", "portrait"),
                        "service": result.get("service"),
                        "style": result.get("style"),
                        "original_prompt": result.get("original_prompt"),
                        "proxy_url": result.get("proxy_url") or result.get("image_url"),
                        "storage_path": result.get("storage_path"),
                        "storage_bucket": result.get("storage_bucket"),
                        "local_path": result.get("local_path"),
                        "gcs_uploaded": result.get("gcs_uploaded"),
                        "mime_type": result.get("mime_type"),
                        "model": result.get("model"),
                        "character_id": character_id,
                    }
                    metadata_manager.save_metadata(
                        storage_filename,
                        metadata_payload,
                        campaign_id=campaign_ref,
                    )
            except Exception as exc:
                logger.warning("Failed to persist portrait metadata for %s: %s", character_id, exc)

        return result

    def get_portrait(self, character_id: str) -> Dict[str, Any]:
        """Get portrait information for a character from their profile.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with portrait information from CharacterProfile
        """
        # Get portrait from CharacterProfile
        try:
            profile_id = character_id
            profile = self.get_profile(profile_id)

            return {
                "success": True,
                "character_id": character_id,
                "portrait_url": profile.portrait_url,
                "portrait_path": profile.portrait_path,
                "has_portrait": bool(profile.portrait_url or profile.portrait_path)
            }
        except ValueError:
            # Profile not found, return empty portrait info
            return {
                "success": True,
                "character_id": character_id,
                "portrait_url": None,
                "portrait_path": None,
                "has_portrait": False
            }

    # ------------------------------------------------------------------
    # Character Enrichment
    # ------------------------------------------------------------------

    def enrich_character(self, character_info: CharacterInfo) -> EnrichedCharacter:
        """Get character with profile data merged (enriched view).

        This loads both the campaign-specific CharacterInfo and the global
        CharacterProfile, then merges them into an EnrichedCharacter for API responses.

        Args:
            character_info: The character's campaign state

        Returns:
            EnrichedCharacter with merged identity and campaign state

        Raises:
            ValueError: If profile not found
        """
        # Get profile_id (for now, use character_id as profile_id until migration adds profile_id field)
        profile_id = getattr(character_info, 'profile_id', character_info.character_id)

        # Load profile (with caching)
        profile = self.get_profile(profile_id)

        # Merge into enriched view using updater
        return self.updater.create_enriched_character(character_info, profile)

    # ------------------------------------------------------------------
    # Interaction Tracking
    # ------------------------------------------------------------------

    def update_profile_interactions(self, character_id: str) -> bool:
        """Update interaction count for a profile.

        Args:
            character_id: Character profile ID

        Returns:
            True if successful
        """
        try:
            profile = self.get_profile(character_id)
            self.updater.increment_interactions(profile)
            self.storage.save_profile(profile)
            self.invalidate_cache(character_id)
            logger.debug(f"Updated interaction count for {character_id}")
            return True
        except ValueError:
            logger.debug(f"Profile {character_id} not found")
            return False
        except Exception as e:
            logger.error(f"❌ Error updating profile interactions: {e}")
            return False
