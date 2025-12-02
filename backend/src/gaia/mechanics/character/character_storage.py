"""
Character Storage System - Manages persistent storage of characters across campaigns
"""
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from gaia.utils.singleton import SingletonMeta
from gaia_private.session.session_storage import SessionStorage
from gaia.infra.storage.campaign_store import get_campaign_store

logger = logging.getLogger(__name__)


class CharacterStorage(metaclass=SingletonMeta):
    """Manages character storage with unique identifiers and cross-campaign support."""
    
    def __init__(self, base_path: Optional[str] = None):
        """Initialize the character storage system.
        
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
        self.environment = os.getenv("ENVIRONMENT_NAME", "default") or "default"
        self.characters_path = self.base_path / "characters"
        self.pregenerated_path = self.base_path / "pregenerated"
        self.pregenerated_characters_path = self.pregenerated_path / "characters"
        self.pregenerated_campaigns_path = self.pregenerated_path / "campaigns"
        self.legacy_pregenerated_path = (
            self.base_path / "campaigns" / self.environment / "pregenerated"
        )
        
        # Create directories if they don't exist
        self.characters_path.mkdir(parents=True, exist_ok=True)
        self.pregenerated_characters_path.mkdir(parents=True, exist_ok=True)
        self.pregenerated_campaigns_path.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"📁 Initialized CharacterStorage with base path: {self.base_path}")
        self._initialized = True
        # Unified campaign store (local + GCS hybrid) for campaign-scoped character state
        self._session_storage = SessionStorage(str(self.base_path), ensure_legacy_dirs=True)
        self._store = get_campaign_store(self._session_storage)
    
    
    def save_character(self, character_data: Dict[str, Any], character_id: Optional[str] = None) -> str:
        """Save a character to persistent storage.
        
        Args:
            character_data: Character data to save
            character_id: Optional existing character ID (if None, generates new ID)
            
        Returns:
            The character ID used for storage
        """
        try:
            # Use provided ID or generate new one using the generator
            if not character_id:
                from gaia.mechanics.character.character_info_generator import CharacterInfoGenerator
                generator = CharacterInfoGenerator()
                character_id = generator.generate_character_id(character_data)
            final_id = character_id
            
            # Add metadata
            character_data['id'] = final_id
            character_data['last_modified'] = datetime.now().isoformat()
            
            # Save to characters directory
            char_file = self.characters_path / f"{final_id}.json"
            with open(char_file, 'w', encoding='utf-8') as f:
                json.dump(character_data, f, indent=2, ensure_ascii=False, default=str)
            
            return final_id
            
        except Exception as e:
            logger.error(f"❌ Error saving character: {e}")
            raise
    
    def load_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Load a character from storage.
        
        Args:
            character_id: Character identifier
            
        Returns:
            Character data or None if not found
        """
        try:
            char_file = self.characters_path / f"{character_id}.json"
            
            if char_file.exists():
                with open(char_file, 'r', encoding='utf-8') as f:
                    character_data = json.load(f)
                    logger.info(f"📖 Loaded character {character_id}")
                    return character_data
            
            logger.warning(f"⚠️ Character {character_id} not found")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error loading character {character_id}: {e}")
            return None
    
    def list_characters(self) -> List[Dict[str, Any]]:
        """List all available characters.
        
        Returns:
            List of character summaries
        """
        characters = []
        
        for char_file in self.characters_path.glob("*.json"):
            try:
                with open(char_file, 'r', encoding='utf-8') as f:
                    char_data = json.load(f)
                    characters.append({
                        'id': char_data.get('id', char_file.stem),
                        'name': char_data.get('name', 'Unknown'),
                        'class': char_data.get('class', 'Unknown'),
                        'race': char_data.get('race', 'Unknown'),
                        'level': char_data.get('level', 1),
                        'last_modified': char_data.get('last_modified'),
                        'campaigns': char_data.get('campaigns', [])
                    })
            except Exception as e:
                logger.error(f"Error reading character file {char_file}: {e}")
        
        logger.info(f"📋 Found {len(characters)} characters")
        return characters
    
    def link_character_to_campaign(self, character_id: str, campaign_id: str) -> bool:
        """Link a character to a campaign (for tracking purposes).
        
        Args:
            character_id: Character identifier
            campaign_id: Campaign identifier
            
        Returns:
            True if successful
        """
        try:
            # Load character
            character_data = self.load_character(character_id)
            if not character_data:
                logger.error(f"Character {character_id} not found")
                return False
            
            # Add campaign to character's campaign list
            if 'campaigns' not in character_data:
                character_data['campaigns'] = []
            
            if campaign_id not in character_data['campaigns']:
                character_data['campaigns'].append(campaign_id)
                character_data['last_campaign'] = campaign_id
                
                # Save updated character
                self.save_character(character_data, character_id=character_id)
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error linking character to campaign: {e}")
            return False
    
    def get_campaign_characters(self, campaign_id: str) -> List[str]:
        """Get all character IDs associated with a campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            List of character IDs
        """
        character_ids = []
        
        for char_summary in self.list_characters():
            if campaign_id in char_summary.get('campaigns', []):
                character_ids.append(char_summary['id'])
        
        return character_ids

    # ------------------------------------------------------------------ #
    # Pregenerated content helpers
    # ------------------------------------------------------------------ #
    def _migrate_legacy_pregenerated(self, category: str) -> None:
        """Copy legacy pregenerated files into the new layout if needed."""
        legacy_root = self.legacy_pregenerated_path / category
        if not legacy_root.exists():
            return
        
        destination = self.pregenerated_path / category
        destination.mkdir(parents=True, exist_ok=True)
        migrated = False
        
        for legacy_file in legacy_root.glob("*.json"):
            target_file = destination / legacy_file.name
            if target_file.exists():
                continue
            try:
                shutil.copy2(legacy_file, target_file)
                migrated = True
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "⚠️ Failed to migrate legacy pregenerated file %s: %s",
                    legacy_file,
                    exc,
                )
        if migrated:
            logger.info(
                "📦 Migrated legacy pregenerated %s from %s to %s",
                category,
                legacy_root,
                destination,
            )
    
    def _resolve_pregenerated_category(self, category: str) -> Path:
        """Return the directory containing pregenerated assets for a category."""
        destination = self.pregenerated_path / category
        destination.mkdir(parents=True, exist_ok=True)
        
        if not any(destination.glob("*.json")) and self.legacy_pregenerated_path.exists():
            self._migrate_legacy_pregenerated(category)
        
        return destination
    
    def load_pregenerated_characters(self) -> List[Dict[str, Any]]:
        """Load pre-generated character templates from the pregenerated directory.
        
        Returns:
            List of pre-generated character data
        """
        characters = []
        pregen_chars_path = self._resolve_pregenerated_category("characters")
        
        if not pregen_chars_path.exists():
            logger.info("No pre-generated characters directory found")
            return characters
        
        for char_file in pregen_chars_path.glob("*.json"):
            try:
                with open(char_file, 'r', encoding='utf-8') as f:
                    char_data = json.load(f)
                    # Don't set an ID - let it be generated when saved
                    if 'id' in char_data:
                        del char_data['id']
                    characters.append(char_data)
                    logger.info(f"📖 Loaded pre-generated character: {char_data.get('name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error loading pre-generated character {char_file}: {e}")
        
        return characters
    
    def persist_campaign_characters(self, campaign_id: str, characters: Dict[str, Any], 
                                   campaign_path: Optional[Path] = None) -> List[str]:
        """Persist all characters for a campaign.
        
        Dual persistence strategy:
        1. Save to global storage (base character template)
        2. Save to campaign directory (campaign-specific state)
        
        Args:
            campaign_id: Campaign identifier
            characters: Dictionary of character_id -> character_data
            campaign_path: Optional path to campaign character directory
            
        Returns:
            List of character IDs that were persisted
        """
        from gaia.mechanics.character.utils import CharacterDataConverter
        converter = CharacterDataConverter()
        persisted_ids = []
        
        for char_id, character in characters.items():
            # Convert character to dict if needed
            char_dict = converter.to_dict(character)
            
            # Save to global character storage (base template)
            self.save_character(char_dict, character_id=char_id)
            self.link_character_to_campaign(char_id, campaign_id)
            persisted_ids.append(char_id)
            
            # Also save campaign-specific character state if path provided
            if campaign_path:
                campaign_path.mkdir(parents=True, exist_ok=True)
                char_file = campaign_path / f"{char_id}.json"
                with open(char_file, 'w', encoding='utf-8') as f:
                    json.dump(char_dict, f, indent=2, ensure_ascii=False, default=str)
                logger.debug(f"Saved campaign-specific state for {char_id} to {char_file}")
                # Mirror campaign-specific character state via unified store (GCS when enabled)
                if self._store:
                    try:
                        self._store.write_json(char_dict, campaign_id, f"data/characters/{char_id}.json")
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Character store mirror failed for %s: %s", char_id, exc)
        
        logger.info(f"Persisted {len(characters)} characters for campaign {campaign_id}")
        return persisted_ids
    
    def load_campaign_characters(self, campaign_id: str, campaign_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
        """Load all characters for a campaign.
        
        Loading strategy supports campaign-specific character states:
        1. First check campaign-specific character directory (contains campaign state)
        2. Fallback to global character storage for base character data
        
        Args:
            campaign_id: Campaign identifier
            campaign_path: Optional path to campaign character directory
            
        Returns:
            Dictionary of character_id -> character_data
        """
        characters = {}
        
        # First try to load from campaign-specific directory if provided
        if campaign_path and campaign_path.exists():
            for char_file in campaign_path.glob("*.json"):
                if char_file.name == "character_summary.json":
                    continue  # Skip summary file if it exists
                
                try:
                    with open(char_file, 'r', encoding='utf-8') as f:
                        char_data = json.load(f)
                    char_id = char_data.get('character_id', char_file.stem)
                    characters[char_id] = char_data
                    logger.debug(f"Loaded campaign-specific character {char_id} from {char_file}")
                except Exception as e:
                    logger.error(f"Error loading character from {char_file}: {e}")
        
        # If no campaign-specific characters, check unified store for campaign state
        if not characters and self._store:
            try:
                object_names = self._store.list_json_prefix(campaign_id, "data/characters")
                for name in object_names:
                    payload = self._store.read_json(campaign_id, f"data/characters/{name}")
                    if isinstance(payload, dict):
                        char_id = payload.get('character_id') or Path(name).stem
                        characters[char_id] = payload
                        logger.debug(f"Loaded character {char_id} from object store")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load campaign characters from object store: %s", exc)

        # If still empty, load from global storage as a final fallback
        if not characters:
            character_ids = self.get_campaign_characters(campaign_id)
            for char_id in character_ids:
                char_data = self.load_character(char_id)
                if char_data:
                    characters[char_id] = char_data
                    logger.debug(f"Loaded character {char_id} from global storage")
        
        return characters
    
    def load_pregenerated_campaigns(self) -> List[Dict[str, Any]]:
        """Load pre-generated campaign templates from the pregenerated directory.
        
        Returns:
            List of pre-generated campaign data
        """
        campaigns = []
        pregen_campaigns_path = self._resolve_pregenerated_category("campaigns")
        
        if not pregen_campaigns_path.exists():
            logger.info("No pre-generated campaigns directory found")
            return campaigns
        
        for campaign_file in pregen_campaigns_path.glob("*.json"):
            try:
                with open(campaign_file, 'r', encoding='utf-8') as f:
                    campaign_data = json.load(f)
                    campaigns.append(campaign_data)
                    logger.info(f"📖 Loaded pre-generated campaign: {campaign_data.get('name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Error loading pre-generated campaign {campaign_file}: {e}")
        
        return campaigns
