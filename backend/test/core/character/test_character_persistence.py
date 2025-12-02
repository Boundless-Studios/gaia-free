"""Unit tests for character persistence manager.

Strategy: Work around singleton pattern by:
1. Clearing singleton instance after each test
2. Using unique temp directories per test
3. Testing actual persistence functionality without per-test isolation issues
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path

from gaia.mechanics.character.character_storage import CharacterStorage
from gaia.utils.singleton import SingletonMeta


class TestCharacterPersistence:
    """Test character persistence functionality."""

    @pytest.fixture(autouse=True)
    def clear_singleton(self):
        """Clear singleton instance before and after each test."""
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
    def char_storage(self, temp_dir):
        """Create a character storage instance for testing."""
        return CharacterStorage(base_path=temp_dir)

    def test_save_and_load_character(self, char_storage):
        """Test saving and loading a character."""
        # Create character data
        character_data = {
            "name": "Aragorn",
            "character_class": "Ranger",
            "level": 5,
            "race": "Human"
        }

        # Save character
        char_id = char_storage.save_character(character_data)
        assert char_id is not None

        # Verify file exists
        char_file = char_storage.characters_path / f"{char_id}.json"
        assert char_file.exists()

        # Load character
        loaded_char = char_storage.load_character(char_id)
        assert loaded_char is not None
        assert loaded_char["name"] == "Aragorn"
        assert loaded_char["character_class"] == "Ranger"
        assert loaded_char["id"] == char_id
        assert "last_modified" in loaded_char

    def test_save_character_with_provided_id(self, char_storage):
        """Test saving character with a provided ID."""
        character_data = {
            "name": "Legolas",
            "character_class": "Ranger"
        }

        custom_id = "custom_char_001"
        saved_id = char_storage.save_character(character_data, character_id=custom_id)

        assert saved_id == custom_id

        # Verify can load by custom ID
        loaded = char_storage.load_character(custom_id)
        assert loaded["name"] == "Legolas"

    def test_list_all_characters(self, char_storage):
        """Test listing all saved characters."""
        # Create multiple characters
        chars = [
            {"name": "Gimli", "character_class": "Fighter"},
            {"name": "Gandalf", "character_class": "Wizard"},
            {"name": "Frodo", "character_class": "Rogue"}
        ]

        saved_ids = []
        for char_data in chars:
            char_id = char_storage.save_character(char_data)
            saved_ids.append(char_id)

        # List all characters (correct method name is list_characters)
        all_chars = char_storage.list_characters()

        assert len(all_chars) >= 3  # At least our 3 characters
        char_names = [c["name"] for c in all_chars]
        assert "Gimli" in char_names
        assert "Gandalf" in char_names
        assert "Frodo" in char_names

    def test_update_existing_character(self, char_storage):
        """Test updating an existing character."""
        # Create character
        character_data = {
            "name": "Boromir",
            "character_class": "Fighter",
            "level": 5
        }
        char_id = char_storage.save_character(character_data)

        # Update character by saving with same ID
        updated_data = {
            "name": "Boromir",
            "character_class": "Fighter",
            "level": 8,  # Level up!
            "new_ability": "Shield Bash"
        }
        char_storage.save_character(updated_data, character_id=char_id)

        # Verify update
        loaded = char_storage.load_character(char_id)
        assert loaded["level"] == 8
        assert loaded["new_ability"] == "Shield Bash"

    def test_character_persistence_across_instances(self, temp_dir):
        """Test that characters persist across storage instances (singleton behavior)."""
        # Create first instance and save character
        storage1 = CharacterStorage(base_path=temp_dir)
        character_data = {"name": "Pippin", "character_class": "Rogue"}
        char_id = storage1.save_character(character_data)

        # Storage is a singleton, so getting it again should return same instance
        storage2 = CharacterStorage(base_path=temp_dir)
        assert storage2 is storage1  # Same instance

        # But files should persist on disk
        char_file = Path(temp_dir) / "characters" / f"{char_id}.json"
        assert char_file.exists()

        # Verify can load from file directly
        with open(char_file, 'r') as f:
            file_data = json.load(f)
        assert file_data["name"] == "Pippin"

    def test_pregenerated_character_storage(self, char_storage):
        """Test storing pregenerated characters."""
        # Verify pregenerated path exists
        assert char_storage.pregenerated_path.exists()

        # Create pregenerated character
        pregen_data = {
            "name": "Pregenerated Warrior",
            "character_class": "Fighter",
            "level": 1,
            "preset": True
        }

        # Save to pregenerated directory
        pregen_file = char_storage.pregenerated_path / "warrior_template.json"
        with open(pregen_file, 'w') as f:
            json.dump(pregen_data, f, indent=2)

        assert pregen_file.exists()

        # Verify can read it back
        with open(pregen_file, 'r') as f:
            loaded = json.load(f)
        assert loaded["name"] == "Pregenerated Warrior"
        assert loaded["preset"] is True
