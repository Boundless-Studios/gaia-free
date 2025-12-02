"""Test script to verify NPC extraction logging."""

import logging
from gaia_private.session.scene.scene_updater import SceneUpdater
from gaia_private.session.scene.scene_payloads import (
    SceneAnalysisPayload,
    StructuredScenePayload,
)

# Set up logging to see DEBUG messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

def test_npc_logging_with_string_bug():
    """Test that demonstrates the logging when a string is incorrectly passed."""
    print("\n" + "="*80)
    print("TEST: String passed instead of list (the bug scenario)")
    print("="*80 + "\n")

    # Simulate the bug: a string where a list is expected
    analysis_data = {
        "scene_type": {"primary_type": "narrative"},
        "game_state": {"location": "Port Verity"},
        "players": [
            {"name": "Zephyr Nightflame", "id": "pc:zephyr_nightflame", "role": "player"}
        ],
        "active_characters": "Zephyr Nightflame (Sorcerer 2)",  # BUG: String instead of list
        "npcs": [],
    }

    structured_data = {
        "narrative": "Test narrative",
        "npcs": [],
        "characters": "Guild-Receiver Aurelia",  # BUG: String instead of list
        "pcs_present": ["pc:zephyr_nightflame"],
    }

    updater = SceneUpdater()
    scene_info = updater.create_from_analysis(
        analysis=analysis_data,
        structured_data=structured_data,
        campaign_id="test_campaign",
    )

    print(f"\n📊 Results:")
    print(f"  NPCs Involved: {scene_info.npcs_involved}")
    print(f"  NPCs Count: {len(scene_info.npcs_involved)}")
    print(f"  PCs Present: {scene_info.pcs_present}")


def test_npc_logging_correct_format():
    """Test with correct list format."""
    print("\n" + "="*80)
    print("TEST: Correct list format")
    print("="*80 + "\n")

    analysis_data = {
        "scene_type": {"primary_type": "narrative"},
        "game_state": {"location": "Port Verity"},
        "players": [
            {"name": "Zephyr Nightflame", "id": "pc:zephyr_nightflame", "role": "player"}
        ],
        "active_characters": [
            {"name": "Zephyr Nightflame", "id": "pc:zephyr_nightflame", "role": "player"},
            {"name": "Guild-Receiver Aurelia", "id": "npc:aurelia", "role": "npc"}
        ],
        "npcs": [
            {"name": "Merchant Boris", "id": "npc:boris"}
        ],
    }

    structured_data = {
        "narrative": "Test narrative",
        "npcs": [
            {"name": "Guard Captain", "id": "npc:guard_captain"}
        ],
        "characters": [
            {"name": "Zephyr Nightflame", "id": "pc:zephyr_nightflame", "role": "player"},
            {"name": "Guild-Receiver Aurelia", "id": "npc:aurelia", "role": "npc"}
        ],
        "pcs_present": ["pc:zephyr_nightflame"],
    }

    updater = SceneUpdater()
    scene_info = updater.create_from_analysis(
        analysis=analysis_data,
        structured_data=structured_data,
        campaign_id="test_campaign",
    )

    print(f"\n📊 Results:")
    print(f"  NPCs Involved: {scene_info.npcs_involved}")
    print(f"  NPCs Count: {len(scene_info.npcs_involved)}")
    print(f"  PCs Present: {scene_info.pcs_present}")


if __name__ == "__main__":
    test_npc_logging_with_string_bug()
    test_npc_logging_correct_format()
