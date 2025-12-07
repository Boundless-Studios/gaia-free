"""Tests for SceneRosterManager using the public API."""

from datetime import datetime
from typing import List

import pytest

from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia_private.session.scene.scene_roster_manager import SceneRosterManager
from gaia.models.scene_participant import SceneParticipant
from gaia.models.scene_info import SceneInfo


def make_scene_info(
    scene_id: str,
    participants: List[SceneParticipant] | None = None,
    pcs_present: List[str] | None = None,
    npcs_present: List[str] | None = None,
) -> SceneInfo:
    """Create a minimal SceneInfo for testing."""
    return SceneInfo(
        scene_id=scene_id,
        title="Test Scene",
        description="Test description",
        scene_type="narrative",
        participants=participants or [],
        pcs_present=pcs_present or [],
        npcs_present=npcs_present or [],
        objectives=[],
        metadata={},
    )


@pytest.fixture
def character_manager():
    """Provide a simple character manager stub."""
    class _Manager:
        def __init__(self):
            self.characters = {
                "pc:aragorn": CharacterInfo(
                    character_id="pc:aragorn",
                    name="Aragorn",
                    character_class="Ranger",
                    character_role=CharacterRole.PLAYER,
                    capabilities=CharacterCapability.COMBAT | CharacterCapability.NARRATIVE,
                ),
                "npc:gandalf": CharacterInfo(
                    character_id="npc:gandalf",
                    name="Gandalf",
                    character_class="Wizard",
                    character_role=CharacterRole.NPC_SUPPORT,
                    capabilities=CharacterCapability.NARRATIVE,
                ),
            }

        def get_character(self, character_id):
            return self.characters.get(character_id)

        def get_character_by_name(self, name):
            for character in self.characters.values():
                if character.name == name:
                    return character
            return None

    return _Manager()


@pytest.fixture
def roster_manager(character_manager):
    return SceneRosterManager(campaign_id="test_campaign", character_manager=character_manager)


def test_ensure_participants_populates_players(roster_manager):
    scene_info = make_scene_info("scene_001", pcs_present=["pc:aragorn"])

    roster_manager.ensure_participants(scene_info)

    participants = roster_manager.get_participants_for_scene("scene_001")
    assert len(participants) == 1
    player = participants[0]
    assert player.character_id == "pc:aragorn"
    assert player.role == CharacterRole.PLAYER
    assert player.is_present


def test_process_turn_updates_npc_roster(roster_manager):
    scene_info = make_scene_info("scene_001", npcs_present=["Goblin"])
    roster_manager.ensure_participants(scene_info)

    # NPC joins - using character_resolution (new architecture)
    updates = roster_manager.process_turn(
        scene_info,
        structured_data={
            "character_resolution": {
                "npcs": [
                    {"display_name": "Goblin"},
                    {"display_name": "Goblin Shaman"}
                ]
            }
        },
    )
    assert updates["npcs_present"] == ["npc:goblin", "npc:goblin_shaman"]
    assert updates["npcs_added"] == ["npc:goblin_shaman"]

    participants = roster_manager.get_participants_for_scene("scene_001")
    assert {p.display_name for p in participants if p.is_present} == {"Goblin", "Goblin Shaman"}

    # NPC leaves - using character_resolution
    updates = roster_manager.process_turn(
        scene_info,
        structured_data={
            "character_resolution": {
                "npcs": [
                    {"display_name": "Goblin Shaman"}
                ]
            }
        },
    )
    assert updates["npcs_present"] == ["npc:goblin_shaman"]
    assert updates["npcs_removed"] == ["npc:goblin"]

    participants = roster_manager.get_participants_for_scene("scene_001")
    assert {p.display_name for p in participants if p.is_present} == {"Goblin Shaman"}


def test_bootstrap_scene_with_existing_participants(roster_manager):
    participant = SceneParticipant(
        character_id="npc:gandalf",
        display_name="Gandalf",
        role=CharacterRole.NPC_SUPPORT,
        capabilities=CharacterCapability.NARRATIVE,
        joined_at=datetime.utcnow(),
    )
    scene_info = make_scene_info("scene_002", participants=[participant])

    roster_manager.bootstrap_scene(scene_info)

    cached = roster_manager.get_participants_for_scene("scene_002")
    assert len(cached) == 1
    assert cached[0].display_name == "Gandalf"
    assert cached[0].role == CharacterRole.NPC_SUPPORT


def test_get_participants_for_scene_returns_empty_when_unknown(roster_manager):
    assert roster_manager.get_participants_for_scene("missing_scene") == []


def test_pc_prefix_in_npcs_list_routes_to_player(roster_manager):
    """Test that PC identifiers with pc: prefix are correctly routed to player handling even if in npcs_present list."""
    # Create scene with PC identifier incorrectly placed in npcs_present
    scene_info = make_scene_info(
        "scene_003",
        pcs_present=[],
        npcs_present=["pc:aragorn"]  # PC incorrectly in NPC list
    )

    roster_manager.ensure_participants(scene_info)

    participants = roster_manager.get_participants_for_scene("scene_003")
    assert len(participants) == 1
    player = participants[0]
    assert player.character_id == "pc:aragorn"
    assert player.role == CharacterRole.PLAYER  # Should be PLAYER, not NPC_SUPPORT
    assert player.is_present


def test_npcs_present_never_contains_pc_prefix_after_ensure(roster_manager):
    """Test that after ensure_participants, npcs_present list never contains pc: prefixed IDs."""
    # Create scene with mixed PC/NPC in npcs_present
    scene_info = make_scene_info(
        "scene_004",
        pcs_present=[],
        npcs_present=["pc:aragorn", "npc:gandalf"]
    )

    roster_manager.ensure_participants(scene_info)

    # After ensure_participants, pcs_present should contain the PC
    assert "pc:aragorn" in scene_info.pcs_present or "Aragorn" in scene_info.pcs_present

    # npcs_present should NOT contain pc: prefix
    for npc_id in scene_info.npcs_present:
        assert not str(npc_id).lower().startswith("pc:"), f"Found PC identifier {npc_id} in npcs_present!"


def test_ensure_npc_never_overwrites_player_role(roster_manager):
    """Test that _ensure_npc() never overwrites existing PLAYER roles to NPC_SUPPORT."""
    # First, add a player character
    scene_info = make_scene_info("scene_005", pcs_present=["pc:aragorn"])
    roster_manager.ensure_participants(scene_info)

    participants = roster_manager.get_participants_for_scene("scene_005")
    assert len(participants) == 1
    assert participants[0].role == CharacterRole.PLAYER

    # Now try to process the same character as an NPC (simulating the bug)
    # This should NOT change the role
    roster_manager._ensure_npc(scene_info, "pc:aragorn")

    # Verify role is still PLAYER
    participants = roster_manager.get_participants_for_scene("scene_005")
    player = next(p for p in participants if p.character_id == "pc:aragorn")
    assert player.role == CharacterRole.PLAYER, "PLAYER role should never be overwritten to NPC_SUPPORT"
