"""Profile Updater - Handles business logic transformations for CharacterProfiles."""

from typing import Dict, Any, Optional
import logging

from gaia.models.character import CharacterProfile, CharacterInfo
from gaia.models.character.enriched_character import EnrichedCharacter

logger = logging.getLogger(__name__)


class ProfileUpdater:
    """Handles pure business logic transformations for character profiles.

    This class contains no I/O operations - it only transforms data.
    Storage operations are delegated to ProfileStorage.
    Orchestration is handled by ProfileManager.
    """

    def sync_from_character_info(self, profile: CharacterProfile, character_info: CharacterInfo) -> None:
        """Synchronize profile data from CharacterInfo.

        Copies identity, visual metadata, descriptions, and voice data from
        CharacterInfo to CharacterProfile. This is used during character creation
        and profile updates to ensure the profile reflects the latest character data.

        Args:
            profile: CharacterProfile to update (modified in place)
            character_info: CharacterInfo source data
        """
        # Update basic identity (including name to handle slot character changes)
        profile.name = character_info.name
        profile.race = character_info.race
        profile.character_class = character_info.character_class
        profile.base_level = character_info.level

        # Copy visual metadata if present (copy even if None or empty to reflect source data)
        if hasattr(character_info, 'gender'):
            profile.gender = character_info.gender
        if hasattr(character_info, 'age_category'):
            profile.age_category = character_info.age_category
        if hasattr(character_info, 'build'):
            profile.build = character_info.build
        if hasattr(character_info, 'height_description'):
            profile.height_description = character_info.height_description
        if hasattr(character_info, 'facial_expression'):
            profile.facial_expression = character_info.facial_expression
        if hasattr(character_info, 'facial_features'):
            profile.facial_features = character_info.facial_features
        if hasattr(character_info, 'attire'):
            profile.attire = character_info.attire
        if hasattr(character_info, 'primary_weapon'):
            profile.primary_weapon = character_info.primary_weapon
        if hasattr(character_info, 'distinguishing_feature'):
            profile.distinguishing_feature = character_info.distinguishing_feature
        if hasattr(character_info, 'background_setting'):
            profile.background_setting = character_info.background_setting
        if hasattr(character_info, 'pose'):
            profile.pose = character_info.pose

        # Copy portrait data if present (copy even if None or empty to reflect source data)
        if hasattr(character_info, 'portrait_url'):
            profile.portrait_url = character_info.portrait_url
        if hasattr(character_info, 'portrait_path'):
            profile.portrait_path = character_info.portrait_path
        if hasattr(character_info, 'portrait_prompt'):
            profile.portrait_prompt = character_info.portrait_prompt

        # Copy descriptions (only update if source has non-empty value)
        if hasattr(character_info, 'backstory') and character_info.backstory:
            profile.backstory = character_info.backstory
        if hasattr(character_info, 'description') and character_info.description:
            profile.description = character_info.description
        if hasattr(character_info, 'appearance') and character_info.appearance:
            profile.appearance = character_info.appearance
        if hasattr(character_info, 'visual_description') and character_info.visual_description:
            profile.visual_description = character_info.visual_description

        # Copy voice data (only update if source has non-None value)
        if hasattr(character_info, 'voice_id') and character_info.voice_id:
            profile.voice_id = character_info.voice_id
        if hasattr(character_info, 'voice_settings') and character_info.voice_settings:
            profile.voice_settings = character_info.voice_settings

        logger.debug(f"Synced profile {profile.character_id} from CharacterInfo")

    def update_visual_fields(self, profile: CharacterProfile, visual_data: Dict[str, Any]) -> None:
        """Update visual metadata fields in a profile.

        Args:
            profile: CharacterProfile to update (modified in place)
            visual_data: Dictionary of visual fields to update
        """
        visual_fields = [
            'gender', 'age_category', 'build', 'height_description',
            'facial_expression', 'facial_features', 'attire',
            'primary_weapon', 'distinguishing_feature',
            'background_setting', 'pose'
        ]

        updated_fields = []
        for field in visual_fields:
            if field in visual_data:
                setattr(profile, field, visual_data[field])
                updated_fields.append(field)
                logger.debug(f"Updated {field} in profile {profile.character_id}")

        if updated_fields:
            logger.info(f"Updated {len(updated_fields)} visual fields in profile {profile.character_id}")

    def create_enriched_character(
        self,
        character_info: CharacterInfo,
        profile: CharacterProfile
    ) -> EnrichedCharacter:
        """Merge CharacterInfo and CharacterProfile into enriched view.

        This creates a complete view combining identity (from profile) and
        campaign state (from character_info) for API responses.

        Args:
            character_info: Campaign-specific character state
            profile: Global character identity

        Returns:
            EnrichedCharacter with merged data
        """
        return EnrichedCharacter.from_character_and_profile(character_info, profile)

    def increment_interactions(self, profile: CharacterProfile) -> None:
        """Increment the interaction counter for a profile.

        Args:
            profile: CharacterProfile to update (modified in place)
        """
        profile.total_interactions += 1
        logger.debug(f"Incremented interactions for profile {profile.character_id} to {profile.total_interactions}")
