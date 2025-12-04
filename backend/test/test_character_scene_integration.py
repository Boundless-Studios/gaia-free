"""Test that characters are automatically added to current scene."""

import pytest
import asyncio
import json
import uuid

from gaia_private.agents.tools.formatters.character_updater import update_character
from gaia_private.agents.tools.persistence_hooks import get_persistence_hook
from gaia.infra.storage.enhanced_scene_manager import EnhancedSceneManager
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia.utils.singleton import SingletonMeta
from gaia.models.scene_info import SceneInfo
from datetime import datetime

# Import the hooks module to reset global state
import gaia_private.agents.tools.persistence_hooks as hooks_module


def reset_persistence_hook():
    """Reset the global persistence hook instance to ensure test isolation."""
    hooks_module._hook_instance = None


@pytest.mark.asyncio
async def test_character_added_to_current_scene():
    """Test that newly created characters are automatically added to the current scene."""

    # Reset global hook state for test isolation
    reset_persistence_hook()

    # Setup
    SingletonMeta._instances.pop(SimpleCampaignManager, None)
    campaign_manager = SimpleCampaignManager()
    test_campaign_id = "test_char_scene_integration"

    # Cleanup any existing campaign from previous test runs
    try:
        campaign_manager.delete_campaign(test_campaign_id)
    except:
        pass

    # Create a test campaign
    campaign = campaign_manager.create_campaign(
        session_id=test_campaign_id,
        title="Test Campaign"
    )

    # Create a scene with unique ID
    scene_manager = EnhancedSceneManager(campaign_id=test_campaign_id)
    unique_scene_id = f"test_scene_{uuid.uuid4().hex[:8]}"
    scene_info = SceneInfo(
        scene_id=unique_scene_id,
        title="Test Scene",
        description="A test scene",
        location_id="test_location",
        location_description="Test Location",
        scene_type="social",
        objectives=["Test objective"],
        npcs_involved=[],
        npcs_present=[],
        pcs_present=["test_pc"],
        timestamp=datetime.now()
    )
    scene_id = scene_manager.create_scene(scene_info)

    # Set the scene as current in the campaign
    campaign = campaign_manager.load_campaign(test_campaign_id)
    campaign.current_scene_id = scene_id
    campaign_manager.save_campaign_data(test_campaign_id, campaign)

    # Enable persistence hooks
    hook = get_persistence_hook()
    hook.set_session(test_campaign_id)
    hook.enable()

    # Create a character with add_to_current_scene=True (default)
    result = update_character(
        name="Test NPC",
        class_type="Warrior",
        race="Human",
        level=5,
        hp=45,
        max_hp=45,
        ac=16,
        add_to_current_scene=True
    )

    # Manually invoke the persistence hook
    await hook.on_character_update("character_updater", {}, result)

    # Verify the character was created
    campaign = campaign_manager.load_campaign(test_campaign_id)
    char_manager = campaign_manager.get_character_manager(test_campaign_id)
    assert any(char.name == "Test NPC" for char in char_manager.characters.values()), "Character should be created"

    # Verify the character was added to the scene
    assert campaign.current_scene_id is not None, "Campaign should have a current scene"

    # Create a fresh scene manager to avoid cache issues
    fresh_scene_manager = EnhancedSceneManager(campaign_id=test_campaign_id)
    updated_scene = fresh_scene_manager.get_scene(campaign.current_scene_id)
    assert updated_scene is not None, "Scene should exist"
    # Character IDs are prefixed with "npc:" and lowercased
    assert any("test_npc" in npc_id.lower() or "test npc" in npc_id.lower() for npc_id in updated_scene.npcs_added), \
        f"Character should be in npcs_added. npcs_added={updated_scene.npcs_added}"

    # Cleanup
    campaign_manager.delete_campaign(test_campaign_id)


@pytest.mark.asyncio
async def test_character_not_added_when_disabled():
    """Test that characters are NOT added to scene when add_to_current_scene=False."""

    # Reset global hook state for test isolation
    reset_persistence_hook()

    # Setup
    SingletonMeta._instances.pop(SimpleCampaignManager, None)
    campaign_manager = SimpleCampaignManager()
    test_campaign_id = "test_char_scene_no_add"

    # Cleanup any existing campaign from previous test runs
    try:
        campaign_manager.delete_campaign(test_campaign_id)
    except:
        pass

    # Create a test campaign
    campaign = campaign_manager.create_campaign(
        session_id=test_campaign_id,
        title="Test Campaign No Add"
    )

    # Create a scene with unique ID
    scene_manager = EnhancedSceneManager(campaign_id=test_campaign_id)
    unique_scene_id = f"test_scene_{uuid.uuid4().hex[:8]}"
    scene_info = SceneInfo(
        scene_id=unique_scene_id,
        title="Test Scene 2",
        description="Another test scene",
        location_id="test_location_2",
        location_description="Test Location 2",
        scene_type="social",
        objectives=["Test objective"],
        npcs_involved=[],
        npcs_present=[],
        pcs_present=["test_pc"],
        timestamp=datetime.now()
    )
    scene_id = scene_manager.create_scene(scene_info)

    # Set the scene as current in the campaign
    campaign = campaign_manager.load_campaign(test_campaign_id)
    campaign.current_scene_id = scene_id
    campaign_manager.save_campaign_data(test_campaign_id, campaign)

    # Enable persistence hooks
    hook = get_persistence_hook()
    hook.set_session(test_campaign_id)
    hook.enable()

    # Create a character with add_to_current_scene=False
    result = update_character(
        name="Future NPC",
        class_type="Rogue",
        race="Elf",
        level=3,
        hp=24,
        max_hp=24,
        ac=14,
        add_to_current_scene=False
    )

    # Manually invoke the persistence hook
    await hook.on_character_update("character_updater", {}, result)

    # Verify the character was created
    campaign = campaign_manager.load_campaign(test_campaign_id)
    char_manager = campaign_manager.get_character_manager(test_campaign_id)
    assert any(char.name == "Future NPC" for char in char_manager.characters.values()), "Character should be created"

    # Verify the character was NOT added to the scene
    assert campaign.current_scene_id is not None, "Campaign should have a current scene"

    # Create a fresh scene manager to avoid cache issues
    fresh_scene_manager2 = EnhancedSceneManager(campaign_id=test_campaign_id)
    updated_scene = fresh_scene_manager2.get_scene(campaign.current_scene_id)
    assert updated_scene is not None, "Scene should exist"
    assert "Future NPC" not in updated_scene.npcs_added, f"Character should NOT be in npcs_added. npcs_added={updated_scene.npcs_added}"

    # Cleanup
    campaign_manager.delete_campaign(test_campaign_id)


if __name__ == "__main__":
    print("Running character scene integration tests...")
    asyncio.run(test_character_added_to_current_scene())
    asyncio.run(test_character_not_added_when_disabled())
    print("\n✅ All tests passed!")
