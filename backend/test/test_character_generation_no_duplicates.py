"""Test to verify character generation doesn't create duplicates."""

import pytest
from unittest.mock import patch
from gaia.api.routes.campaign_generation import PreGeneratedContent
from gaia.utils.singleton import SingletonMeta


@pytest.fixture
def mock_pregen_characters():
    """Create mock character data for testing."""
    return [
        {"name": "Thorin Ironforge", "race": "Dwarf", "character_class": "Fighter"},
        {"name": "Elara Moonwhisper", "race": "Elf", "character_class": "Wizard"},
        {"name": "Grok Stonefist", "race": "Orc", "character_class": "Barbarian"},
        {"name": "Lyra Brightwind", "race": "Human", "character_class": "Cleric"},
        {"name": "Zephyr Shadowblade", "race": "Halfling", "character_class": "Rogue"},
    ]


def test_get_random_characters_no_duplicates_when_enough_available(mock_pregen_characters):
    """Test that we get unique characters when enough are available."""
    # Reset singleton and inject mock data
    SingletonMeta._instances.pop(PreGeneratedContent, None)

    with patch.object(PreGeneratedContent, '_load_content'):
        pregen = PreGeneratedContent()
        pregen.characters = mock_pregen_characters.copy()

        # Request fewer characters than available (3 out of 5)
        count = 3
        characters = pregen.get_random_characters(count)

        assert len(characters) == count

        # Check for duplicates by comparing character names
        names = [char.get('name') for char in characters]
        assert len(names) == len(set(names)), f"Found duplicate characters: {names}"


def test_get_random_characters_no_duplicates_when_cycling_needed(mock_pregen_characters):
    """Test that we don't get immediate duplicates when cycling through characters."""
    # Reset singleton and inject mock data
    SingletonMeta._instances.pop(PreGeneratedContent, None)

    with patch.object(PreGeneratedContent, '_load_content'):
        pregen = PreGeneratedContent()
        pregen.characters = mock_pregen_characters.copy()

        # Request more characters than available to trigger cycling logic
        available_count = len(mock_pregen_characters)  # 5
        request_count = available_count + 3  # Request 8 (3 more than available)

        characters = pregen.get_random_characters(request_count)

        assert len(characters) == request_count

        # When cycling, we should use each character before repeating
        # So the first N characters should all be unique
        names = [char.get('name') for char in characters]
        first_cycle = names[:available_count]

        # First cycle should have all unique characters
        assert len(first_cycle) == len(set(first_cycle)), \
            f"First cycle has duplicates: {first_cycle}"

        # Verify we got the expected distribution
        name_counts = {}
        for name in names:
            name_counts[name] = name_counts.get(name, 0) + 1

        # No character should appear more than twice (since we requested available + 3)
        max_count = max(name_counts.values())
        assert max_count <= 2, f"Character appeared {max_count} times: {name_counts}"


def test_get_random_characters_with_exclude_indices(mock_pregen_characters):
    """Test that excluded indices are properly respected."""
    # Reset singleton and inject mock data
    SingletonMeta._instances.pop(PreGeneratedContent, None)

    with patch.object(PreGeneratedContent, '_load_content'):
        pregen = PreGeneratedContent()
        pregen.characters = mock_pregen_characters.copy()

        # Exclude first character (index 0)
        exclude_indices = {0}
        characters = pregen.get_random_characters(2, exclude_indices)

        assert len(characters) == 2

        # Verify excluded character is not in results
        excluded_name = mock_pregen_characters[0].get('name')
        result_names = [char.get('name') for char in characters]
        assert excluded_name not in result_names, \
            f"Excluded character '{excluded_name}' appeared in results"

        # Verify no duplicates
        assert len(result_names) == len(set(result_names)), \
            f"Found duplicate characters: {result_names}"


def test_get_random_characters_cycling_distribution(mock_pregen_characters):
    """Test that cycling provides even distribution of characters."""
    # Reset singleton and inject mock data
    SingletonMeta._instances.pop(PreGeneratedContent, None)

    with patch.object(PreGeneratedContent, '_load_content'):
        pregen = PreGeneratedContent()
        pregen.characters = mock_pregen_characters.copy()

        # Request exactly double the available characters
        available_count = len(mock_pregen_characters)  # 5
        request_count = available_count * 2  # 10

        characters = pregen.get_random_characters(request_count)

        assert len(characters) == request_count

        # Count occurrences of each character
        names = [char.get('name') for char in characters]
        name_counts = {}
        for name in names:
            name_counts[name] = name_counts.get(name, 0) + 1

        # Each character should appear exactly twice
        for name, count in name_counts.items():
            assert count == 2, \
                f"Character '{name}' appeared {count} times instead of 2: {name_counts}"
