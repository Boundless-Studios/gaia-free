"""Test that scene payloads don't iterate strings character-by-character."""

import pytest
from gaia_private.session.scene.scene_payloads import (
    StructuredScenePayload,
    SceneAnalysisPayload,
)


def test_coerce_character_list_handles_string_not_character_by_character():
    """Test that a string passed to characters doesn't get split into individual characters."""
    # This was the bug: when a string was passed where a list was expected,
    # Python's string iteration would split it into individual characters
    data = {
        "npcs": "Zephyr Nightflame (Sorcerer 2)",  # String instead of list
        "characters": "Thorin Stonefist",  # String instead of list
    }

    payload = StructuredScenePayload.from_raw(data)

    # Should have 1 NPC entry, not 29 characters from the string
    assert len(payload.npcs) == 1
    assert payload.npcs[0].display == "Zephyr Nightflame (Sorcerer 2)"

    # Should have 1 character entry, not 16 characters from the string
    assert len(payload.characters) == 1
    assert payload.characters[0].display == "Thorin Stonefist"


def test_coerce_character_list_handles_list_normally():
    """Test that lists are still processed correctly."""
    data = {
        "npcs": ["NPC One", "NPC Two"],
        "characters": ["PC One", "PC Two", "PC Three"],
    }

    payload = StructuredScenePayload.from_raw(data)

    assert len(payload.npcs) == 2
    assert payload.npcs[0].display == "NPC One"
    assert payload.npcs[1].display == "NPC Two"

    assert len(payload.characters) == 3
    assert payload.characters[0].display == "PC One"
    assert payload.characters[1].display == "PC Two"
    assert payload.characters[2].display == "PC Three"


def test_analysis_payload_handles_string_not_character_by_character():
    """Test that SceneAnalysisPayload also handles strings correctly."""
    data = {
        "players": "Player Character Name",
        "active_characters": "Active NPC Name",
        "npcs": "Guild-Receiver Aurelia Lighthand",
    }

    payload = SceneAnalysisPayload.from_raw(data)

    # Should have 1 player, not N characters
    assert len(payload.players) == 1
    assert payload.players[0].display == "Player Character Name"

    # Should have 1 active character, not N characters
    assert len(payload.active_characters) == 1
    assert payload.active_characters[0].display == "Active NPC Name"

    # Should have 1 NPC, not N characters
    assert len(payload.npcs) == 1
    assert payload.npcs[0].display == "Guild-Receiver Aurelia Lighthand"


def test_empty_and_none_values_still_work():
    """Test that empty/None values are still handled correctly."""
    data = {
        "npcs": None,
        "characters": [],
        "players": "",
    }

    payload = StructuredScenePayload.from_raw(data)

    assert len(payload.npcs) == 0
    assert len(payload.characters) == 0
    # Empty string should create 0 entries (wrapped in list, but empty string is falsy)
    assert len(payload.players) == 0


def test_mixed_types_in_list():
    """Test that mixed types in a list are handled correctly."""
    data = {
        "npcs": [
            "String NPC",
            {"name": "Dict NPC", "id": "npc:dict_npc"},
        ],
    }

    payload = StructuredScenePayload.from_raw(data)

    assert len(payload.npcs) == 2
    assert payload.npcs[0].display == "String NPC"
    assert payload.npcs[1].display == "Dict NPC"
    assert payload.npcs[1].identifier == "npc:dict_npc"
