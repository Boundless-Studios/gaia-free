"""Campaign and character generation logic separated from API endpoints."""

import random
import logging
from typing import Any, Dict, List, Optional

from gaia.utils.singleton import SingletonMeta
from gaia.infra.storage.campaign_object_store import (
    PregeneratedFetchResult,
    get_pregenerated_content_store,
)

logger = logging.getLogger(__name__)


def is_valid_character_name(name: str) -> bool:
    """Check if a character name is valid (not a placeholder or malformed)."""
    if not name or not isinstance(name, str):
        return False

    name = name.strip()

    # Reject invalid names
    if (
        len(name) < 2 or
        name.lower().startswith('unnamed') or
        'tool_call' in name.lower() or
        '<' in name or '>' in name or  # Reject XML/HTML tags
        not any(c.isalpha() for c in name)  # Must have at least one letter
    ):
        return False

    return True


class PreGeneratedContent(metaclass=SingletonMeta):
    """Handles loading and serving pre-generated content."""
    
    def __init__(self):
        self.campaigns: List[Dict[str, Any]] = []
        self.characters: List[Dict[str, Any]] = []
        self._campaigns_mtime: Optional[float] = None
        self._characters_mtime: Optional[float] = None
        self._load_content(force=False)  # Check GCS first, then fall back to local
    
    def _maybe_reload(self) -> None:
        """Reload pregenerated content if files changed since last load."""
        self._load_content(force=False)
    
    def _load_content(self, *, force: bool = False) -> None:
        """Load pre-generated content from the shared storage abstraction."""
        store = get_pregenerated_content_store()

        def apply_result(
            filename: str,
            result: PregeneratedFetchResult,
            *,
            data_attr: str,
            mtime_attr: str,
            payload_key: str,
            label: str,
        ) -> None:
            payload: Dict[str, Any] = result.payload if isinstance(result.payload, dict) else {}
            values = payload.get(payload_key, [])
            if not isinstance(values, list):
                values = []

            if result.source == "gcs":
                setattr(self, data_attr, values)
                setattr(self, mtime_attr, result.local_mtime)
                logger.info("✅ Loaded %s pre-generated %s from GCS", len(values), label)
                return

            if result.source == "local":
                if result.checked_remote:
                    logger.info(
                        "ℹ️ No pregenerated %s found in object store; using local fallback",
                        label,
                    )
                setattr(self, data_attr, values)
                setattr(self, mtime_attr, result.local_mtime)
                logger.info(
                    "✅ Loaded %s pre-generated %s from local file: %s",
                    len(values),
                    label,
                    store.local_path(filename),
                )
                return

            if result.source == "unchanged":
                setattr(self, mtime_attr, result.local_mtime)
                logger.debug(
                    "Pregenerated %s unchanged; keeping %s cached entries",
                    label,
                    len(getattr(self, data_attr)),
                )
                return

            if result.checked_remote:
                logger.info(
                    "ℹ️ No pregenerated %s found in object store; local cache unavailable",
                    label,
                )

            if force or getattr(self, mtime_attr) is not None or getattr(self, data_attr):
                logger.warning(
                    "⚠️ No pregenerated %s found at %s",
                    label,
                    store.local_path(filename),
                )

            setattr(self, data_attr, [])
            setattr(self, mtime_attr, result.local_mtime)

        campaigns_result = store.fetch_json(
            "campaigns.json",
            previous_local_mtime=self._campaigns_mtime,
            force_local=force,
        )
        apply_result(
            "campaigns.json",
            campaigns_result,
            data_attr="campaigns",
            mtime_attr="_campaigns_mtime",
            payload_key="campaigns",
            label="campaigns",
        )

        characters_result = store.fetch_json(
            "characters.json",
            previous_local_mtime=self._characters_mtime,
            force_local=force,
        )
        apply_result(
            "characters.json",
            characters_result,
            data_attr="characters",
            mtime_attr="_characters_mtime",
            payload_key="characters",
            label="characters",
        )
    
    def get_random_campaign(self, style: Optional[str] = None) -> Dict[str, Any]:
        """Get a random pre-generated campaign, optionally filtered by style."""
        self._maybe_reload()
        if not self.campaigns:
            return self._get_default_campaign()
        
        campaigns = self.campaigns
        if style:
            filtered = [c for c in campaigns if c.get("style", "").lower() == style.lower()]
            if filtered:
                campaigns = filtered
        
        return random.choice(campaigns)
    
    def get_random_character(self) -> Dict[str, Any]:
        """Get a random pre-generated character."""
        self._maybe_reload()
        if not self.characters:
            return self._get_default_character()

        return random.choice(self.characters)

    def get_all_characters(self) -> List[Dict[str, Any]]:
        """Get all pre-generated characters with valid names."""
        self._maybe_reload()
        # Filter out characters with invalid names
        valid_characters = [
            char for char in self.characters
            if is_valid_character_name(char.get('name', ''))
        ]
        return valid_characters.copy()

    def get_character_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific pre-generated character by name."""
        self._maybe_reload()
        for char in self.characters:
            if char.get("name", "").lower() == name.lower():
                return char.copy()
        return None

    def get_random_characters(self, count: int, exclude_indices: Optional[set] = None) -> List[Dict[str, Any]]:
        """Get multiple random pre-generated characters without duplicates."""
        self._maybe_reload()
        if not self.characters:
            return [self._get_default_character() for _ in range(count)]

        exclude_indices = exclude_indices or set()
        available_indices = [i for i in range(len(self.characters)) if i not in exclude_indices]

        if len(available_indices) >= count:
            # We have enough unique characters
            selected_indices = random.sample(available_indices, count)
            return [self.characters[i].copy() for i in selected_indices]
        else:
            # Not enough unique characters, cycle through all available characters
            # to ensure we use each character before repeating any
            result = []
            selected_indices = list(available_indices)
            random.shuffle(selected_indices)

            # Keep cycling through shuffled indices until we have enough characters
            while len(result) < count:
                for idx in selected_indices:
                    if len(result) >= count:
                        break
                    result.append(self.characters[idx].copy())

            return result
    
    def _get_default_campaign(self) -> Dict[str, Any]:
        """Return a default campaign structure."""
        return {
            "title": "The Adventure Begins",
            "description": "A new campaign full of mystery and adventure awaits your heroes.",
            "setting": "A realm of magic and danger",
            "theme": "Epic fantasy adventure",
            "starting_location": "The town of Beginner's Rest",
            "main_conflict": "Dark forces gather in the shadows",
            "key_npcs": [
                "Mayor Aldrin - The town leader",
                "Mage Elara - A knowledgeable wizard",
                "Guard Captain Rex - The town protector"
            ],
            "potential_quests": [
                "Clear the goblin caves",
                "Find the missing merchant",
                "Investigate the haunted ruins"
            ]
        }
    
    def _get_default_character(self) -> Dict[str, Any]:
        """Return a default character structure."""
        return {
            "name": "Adventurer",
            "character_class": "Fighter",
            "race": "Human",
            "level": 1,
            "description": "A brave adventurer ready for challenges",
            "backstory": "An adventurer with a mysterious past",
            "stats": {
                "strength": 10,
                "dexterity": 10,
                "constitution": 10,
                "intelligence": 10,
                "wisdom": 10,
                "charisma": 10
            }
        }


class CampaignInitializer:
    """Handles campaign initialization logic."""
    
    def __init__(self, pregen_content: PreGeneratedContent):
        self.pregen = pregen_content
    
    def build_initial_prompt(self, campaign_info: Dict[str, Any], characters: List[Dict[str, Any]]) -> str:
        """Build the comprehensive initial prompt for starting a campaign."""
        title = campaign_info.get("title", "The Adventure")
        
        prompt = f"""Welcome to "{title}"! 

=== CAMPAIGN OVERVIEW ===
{campaign_info.get("description", "An epic adventure awaits")}

=== SETTING ===
{campaign_info.get("setting", "A fantasy realm filled with adventure")}

=== THEME & TONE ===
{campaign_info.get("theme", "Classic fantasy adventure")}

=== STARTING LOCATION ===
{campaign_info.get("starting_location", "A tavern in a small town")}

=== CENTRAL CONFLICT ===
{campaign_info.get("main_conflict", "An emerging threat to the realm")}"""

        # Add key NPCs if available
        key_npcs = campaign_info.get("key_npcs", [])
        if key_npcs:
            prompt += f"\n\n=== KEY NPCS ===\n" + "\n".join(key_npcs)
        
        # Add potential quests if available
        potential_quests = campaign_info.get("potential_quests", [])
        if potential_quests:
            prompt += f"\n\n=== POTENTIAL QUEST HOOKS ===\n" + "\n".join(potential_quests)
        
        # Add character information
        if characters:
            prompt += f"\n\n=== THE ADVENTURERS ===\nWe have {len(characters)} brave souls ready to begin their journey:\n"
            
            for char in characters:
                char_desc = f"- {char.get('name', 'Unknown')} ({char.get('race', 'Human')} {char.get('character_class', 'Adventurer')}, Level {char.get('level', 1)})"
                
                if char.get('description'):
                    char_desc += f"\n  Description: {char['description']}"
                if char.get('backstory'):
                    char_desc += f"\n  Backstory: {char['backstory']}"
                
                prompt += char_desc + "\n\n"
        
        # Add instructions for the DM
        prompt += f"""
=== YOUR TASK ===
Please set the opening scene for our campaign at {campaign_info.get('starting_location', 'an appropriate starting location')}. 
Describe where our adventurers begin their journey, how they might know each other or meet, and present the initial hook that will draw them into adventure. 
Make sure to reference the central conflict and potentially introduce one of the key NPCs or quest hooks."""
        
        return prompt
