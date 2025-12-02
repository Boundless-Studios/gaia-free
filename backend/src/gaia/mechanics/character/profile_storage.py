"""Character Profile Storage - Manages persistent storage of CharacterProfiles with voice and visual data."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from gaia.models.character import CharacterProfile, CharacterInfo
from gaia.utils.singleton import SingletonMeta
from gaia_private.session.session_storage import SessionStorage
from gaia.infra.storage.campaign_store import get_campaign_store

logger = logging.getLogger(__name__)


class ProfileStorage(metaclass=SingletonMeta):
    """Manages CharacterProfile storage for voice and visual data with hybrid local+GCS storage."""

    def __init__(self, base_path: Optional[str] = None):
        """Initialize the profile storage system.

        Args:
            base_path: Base directory for storage (optional, uses CAMPAIGN_STORAGE_PATH if not provided)
        """
        # Skip initialization if already initialized (singleton pattern)
        if hasattr(self, '_initialized'):
            return

        if base_path is None:
            campaign_storage = os.getenv('CAMPAIGN_STORAGE_PATH')
            if not campaign_storage:
                raise ValueError(
                    "CAMPAIGN_STORAGE_PATH environment variable is not set. "
                    "Please set it to your campaign storage directory."
                )
            base_path = campaign_storage

        self.base_path = Path(base_path)
        self.profiles_path = self.base_path / "character_profiles"

        # Respect lazy bootstrap mode (like SessionStorage does)
        # Default behavior: eager in normal environments; lazy in Cloud Run or when explicitly requested
        bootstrap_mode = os.getenv("CAMPAIGN_STORAGE_BOOTSTRAP", "").strip().lower()
        create_dirs = bootstrap_mode not in {"lazy", "false", "0"}

        # Also check for Cloud Run environment (K_SERVICE present)
        if os.getenv("K_SERVICE") is not None:
            create_dirs = False

        if create_dirs:
            # Create directory if not in lazy mode
            try:
                self.profiles_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created character profiles directory: {self.profiles_path}")
            except (PermissionError, OSError) as exc:
                # In read-only or restricted environments, proceed without bootstrap
                logger.warning(
                    f"ProfileStorage: unable to create profiles directory ({exc}). "
                    "Proceeding without bootstrap; directory will be created lazily when needed."
                )
        else:
            logger.debug(
                "ProfileStorage: lazy bootstrap enabled; skipping directory creation"
            )

        # Initialize unified hybrid storage (local + GCS)
        self._storage = SessionStorage(str(self.base_path), ensure_legacy_dirs=True)
        self._store = get_campaign_store(self._storage)

        logger.debug(f"📁 Initialized ProfileStorage at: {self.profiles_path}")
        self._initialized = True
    
    def save_profile(self, profile: CharacterProfile) -> str:
        """Save a CharacterProfile to persistent storage.

        Args:
            profile: CharacterProfile to save

        Returns:
            The character ID used for storage
        """
        try:
            # Convert to dict for serialization
            profile_data = profile.to_dict()

            # Ensure directory exists (lazy creation)
            self.profiles_path.mkdir(parents=True, exist_ok=True)

            # Save to profiles directory (local)
            profile_file = self.profiles_path / f"{profile.character_id}.json"
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)

            # Mirror to GCS when enabled
            if self._store:
                try:
                    self._store.write_json(profile_data, "shared", f"character_profiles/{profile.character_id}.json")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Profile store mirror failed for %s: %s", profile.character_id, exc)

            return profile.character_id

        except Exception as e:
            logger.error(f"❌ Error saving character profile: {e}")
            raise
    
    def load_profile(self, character_id: str) -> Optional[CharacterProfile]:
        """Load a CharacterProfile from storage.

        Args:
            character_id: Character identifier

        Returns:
            CharacterProfile or None if not found
        """
        try:
            profile_file = self.profiles_path / f"{character_id}.json"

            # Try local file first
            if profile_file.exists():
                with open(profile_file, 'r', encoding='utf-8') as f:
                    profile_data = json.load(f)
                    profile = CharacterProfile.from_dict(profile_data)
                    logger.debug(f"📖 Loaded character profile {character_id} ({profile.name})")
                    return profile

            # Fallback to GCS
            if self._store:
                try:
                    profile_data = self._store.read_json("shared", f"character_profiles/{character_id}.json")
                    if profile_data:
                        profile = CharacterProfile.from_dict(profile_data)
                        logger.debug(f"📖 Loaded character profile {character_id} from store ({profile.name})")
                        return profile
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Profile store read failed for %s: %s", character_id, exc)

            logger.debug(f"Character profile {character_id} not found")
            return None

        except Exception as e:
            logger.error(f"❌ Error loading character profile {character_id}: {e}")
            return None
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all available character profiles.

        Returns:
            List of profile summaries
        """
        profiles = []
        seen = set()

        # List local profiles
        for profile_file in self.profiles_path.glob("*.json"):
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    profile_data = json.load(f)
                    char_id = profile_data.get('character_id', profile_file.stem)
                    seen.add(char_id)
                    profiles.append({
                        'character_id': char_id,
                        'name': profile_data.get('name', 'Unknown'),
                        'character_type': profile_data.get('character_type', 'npc'),
                        'voice_id': profile_data.get('voice_id'),
                        'portrait_path': profile_data.get('portrait_path'),
                        'total_interactions': profile_data.get('total_interactions', 0)
                    })
            except Exception as e:
                logger.error(f"Error reading profile file {profile_file}: {e}")

        # Supplement with GCS profiles not found locally
        if self._store:
            try:
                for name in self._store.list_json_prefix("shared", "character_profiles"):
                    profile_id = Path(name).stem
                    if profile_id in seen:
                        continue
                    profile_data = self._store.read_json("shared", f"character_profiles/{name}")
                    if profile_data:
                        seen.add(profile_id)
                        profiles.append({
                            'character_id': profile_data.get('character_id', profile_id),
                            'name': profile_data.get('name', 'Unknown'),
                            'character_type': profile_data.get('character_type', 'npc'),
                            'voice_id': profile_data.get('voice_id'),
                            'portrait_path': profile_data.get('portrait_path'),
                            'total_interactions': profile_data.get('total_interactions', 0)
                        })
            except Exception as exc:  # noqa: BLE001
                logger.debug("Profile store listing failed: %s", exc)

        logger.debug(f"📋 Found {len(profiles)} character profiles")
        return profiles
    
    def find_or_create_profile(self, name: str, character_info: Optional[CharacterInfo] = None) -> CharacterProfile:
        """Find an existing profile by name or create a new one.
        
        Args:
            name: Character name to search for
            character_info: Optional CharacterInfo to use if creating new profile
            
        Returns:
            Existing or newly created CharacterProfile
        """
        # Search existing profiles by name
        for profile_summary in self.list_profiles():
            if profile_summary['name'].lower() == name.lower():
                profile = self.load_profile(profile_summary['character_id'])
                if profile:
                    logger.debug(f"Found existing profile for {name}")
                    return profile
        
        # Create new profile
        from gaia.models.character import CharacterType
        from gaia.mechanics.character.character_info_generator import CharacterInfoGenerator
        
        # Generate consistent profile ID using the generator
        generator = CharacterInfoGenerator()
        character_id = f"prof_{generator.generate_character_id({'name': name})}"
        
        profile = CharacterProfile(
            character_id=character_id,
            name=name,
            character_type=CharacterType.PLAYER if character_info and character_info.character_type == "player" else CharacterType.NPC
        )
        
        self.save_profile(profile)
        logger.debug(f"Created new profile for {name}")
        return profile
    
    def update_profile_interactions(self, character_id: str) -> bool:
        """Update interaction count for a profile.
        
        Args:
            character_id: Character profile ID
            
        Returns:
            True if successful
        """
        try:
            profile = self.load_profile(character_id)
            if not profile:
                logger.debug(f"Profile {character_id} not found")
                return False
            
            profile.total_interactions += 1
            self.save_profile(profile)
            
            logger.debug(f"Updated interaction count for {character_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating profile interactions: {e}")
            return False
    
    def get_profile_by_name(self, character_name: str) -> Optional[CharacterProfile]:
        """Get a profile by character name.
        
        Args:
            character_name: Character name
            
        Returns:
            CharacterProfile if found, None otherwise
        """
        for profile_summary in self.list_profiles():
            if profile_summary['name'].lower() == character_name.lower():
                return self.load_profile(profile_summary['character_id'])
        
        return None
    
    def delete_profile(self, character_id: str) -> bool:
        """Delete a character profile.

        Args:
            character_id: ID of the profile to delete

        Returns:
            True if successful
        """
        try:
            profile_file = self.profiles_path / f"{character_id}.json"

            # Delete local file
            if profile_file.exists():
                profile_file.unlink()
                logger.debug(f"🗑️ Deleted local profile {character_id}")

            # Delete from GCS
            if self._store:
                try:
                    self._store.delete("shared", f"character_profiles/{character_id}.json")
                    logger.debug(f"Deleted profile {character_id} from store")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Profile store delete failed for %s: %s", character_id, exc)

            return True

        except Exception as e:
            logger.error(f"❌ Error deleting profile {character_id}: {e}")
            return False