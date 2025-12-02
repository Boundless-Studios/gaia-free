"""Unit tests for CharacterManager (character registry)."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from gaia.mechanics.character.character_manager import CharacterManager
from gaia.models.character import CharacterInfo, CharacterProfile
from gaia.utils.singleton import SingletonMeta
from gaia.mechanics.character.character_storage import CharacterStorage


class TestCharacterManager:
    """Test CharacterManager functionality."""

    @pytest.fixture(autouse=True)
    def clear_singleton(self):
        """Clear CharacterStorage singleton before and after each test."""
        # Clear before test
        if CharacterStorage in SingletonMeta._instances:
            storage = SingletonMeta._instances[CharacterStorage]
            if hasattr(storage, '_initialized'):
                delattr(storage, '_initialized')
            del SingletonMeta._instances[CharacterStorage]

        yield

        # Clear after test
        if CharacterStorage in SingletonMeta._instances:
            storage = SingletonMeta._instances[CharacterStorage]
            if hasattr(storage, '_initialized'):
                delattr(storage, '_initialized')
            del SingletonMeta._instances[CharacterStorage]

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def char_manager(self, temp_dir):
        """Create a character manager for testing."""
        # Initialize CharacterStorage with temp path first
        CharacterStorage(base_path=temp_dir)

        # Then create manager
        return CharacterManager(campaign_id="test_campaign")

    def test_create_character_from_simple(self, char_manager, temp_dir):
        """Test creating character from simple data."""
        simple_char = {
            "name": "Aragorn",
            "class": "Ranger",
            "race": "Human",
            "level": 5,
            "backstory": "A ranger from the North"
        }

        character = char_manager.create_character_from_simple(simple_char)

        assert character is not None
        assert character.name == "Aragorn"
        assert character.character_class == "Ranger"
        assert character.race == "Human"
        assert character.level == 5
        assert character.character_id is not None
        assert character.voice_id is not None  # Should auto-assign

    def test_add_and_get_character(self, char_manager):
        """Test adding and retrieving a character."""
        # Create a character
        character = CharacterInfo(
            character_id="char_001",
            name="Legolas",
            character_class="Ranger",
            race="Elf",
            level=8,
            voice_id="test_voice"
        )

        # Add character
        char_manager.add_character(character)

        # Get character by ID
        retrieved = char_manager.get_character("char_001")
        assert retrieved is not None
        assert retrieved.name == "Legolas"
        assert retrieved.character_id == "char_001"

    def test_get_character_by_name(self, char_manager):
        """Test finding character by name."""
        # Add a character
        character = CharacterInfo(
            character_id="char_002",
            name="Gimli",
            character_class="Fighter",
            race="Dwarf"
        )
        char_manager.add_character(character)

        # Find by exact name
        found = char_manager.get_character_by_name("Gimli")
        assert found is not None
        assert found.character_id == "char_002"

        # Find by different case
        found_lower = char_manager.get_character_by_name("gimli")
        assert found_lower is not None
        assert found_lower.name == "Gimli"

        # Not found
        not_found = char_manager.get_character_by_name("Sauron")
        assert not_found is None

    def test_get_all_characters(self, char_manager):
        """Test getting all characters."""
        # Add multiple characters
        char1 = CharacterInfo(
            character_id="char_003",
            name="Frodo",
            character_class="Rogue"
        )
        char2 = CharacterInfo(
            character_id="char_004",
            name="Sam",
            character_class="Fighter"
        )

        char_manager.add_character(char1)
        char_manager.add_character(char2)

        # Get all characters
        all_chars = char_manager.get_all_characters()
        assert len(all_chars) >= 2  # May have others from previous tests
        char_names = [c.name for c in all_chars]
        assert "Frodo" in char_names
        assert "Sam" in char_names

    def test_get_player_characters(self, char_manager):
        """Test getting only player characters."""
        # Add player character
        player = CharacterInfo(
            character_id="char_005",
            name="Gandalf",
            character_class="Wizard",
            character_type="player"
        )

        # Add NPC character (if character_type is supported)
        npc = CharacterInfo(
            character_id="char_006",
            name="Saruman",
            character_class="Wizard",
            character_type="npc"
        )

        char_manager.add_character(player)
        char_manager.add_character(npc)

        # Get only player characters
        players = char_manager.get_player_characters()

        # Should filter to only player type
        player_names = [c.name for c in players]
        assert "Gandalf" in player_names

    def test_update_character_from_dm(self, char_manager):
        """Test updating character via DM update."""
        # Create initial character
        character = CharacterInfo(
            character_id="char_007",
            name="Boromir",
            character_class="Fighter",
            level=5,
            hit_points_current=50,
            hit_points_max=50
        )
        char_manager.add_character(character)

        # Update via DM update using character_updates structure
        dm_update = {
            "character_updates": {
                "char_007": {
                    "hit_points_current": 35,
                    "status_effects": ["wounded"]
                }
            }
        }

        char_manager.update_character_from_dm(dm_update)

        # Verify update
        updated = char_manager.get_character("char_007")
        assert updated.hit_points_current == 35

    def test_character_manager_initialization(self):
        """Test that CharacterManager initializes correctly."""
        manager = CharacterManager(campaign_id="test_init")

        assert manager.campaign_id == "test_init"
        assert manager.characters is not None
        assert manager.translator is not None
        assert manager.storage is not None
        assert manager.updater is not None
        assert manager.profile_manager is not None
        assert manager.voice_pool is not None

    def test_get_character_context_for_dm(self, char_manager):
        """Test getting character context for DM."""
        # Add some characters
        char1 = CharacterInfo(
            character_id="char_008",
            name="Merry",
            character_class="Rogue",
            level=3
        )
        char2 = CharacterInfo(
            character_id="char_009",
            name="Pippin",
            character_class="Bard",
            level=3
        )

        char_manager.add_character(char1)
        char_manager.add_character(char2)

        # Get context for DM
        context = char_manager.get_character_context_for_dm()

        assert context is not None
        assert isinstance(context, dict)
        # Should contain information about characters
        # Exact structure depends on implementation
