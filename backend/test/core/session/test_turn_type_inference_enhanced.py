"""Tests for roster-aware turn type inference."""

from typing import List

import pytest

from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.enums import CharacterRole
from gaia_private.session.turn_manager import TurnManager
from gaia_private.session.scene.scene_roster_manager import SceneRosterManager
from gaia.models.scene_participant import SceneParticipant
from gaia.models.scene_info import SceneInfo
from gaia.models.turn import TurnType


def make_scene_info(scene_id: str, participants: List[SceneParticipant]) -> SceneInfo:
    return SceneInfo(
        scene_id=scene_id,
        title="Turn Type Test",
        description="",
        location_id="loc",
        location_description="loc",
        scene_type="narrative",
        participants=participants,
        objectives=[],
        narrative_notes=[],
        metadata={},
    )


@pytest.fixture
def character_manager():
    class _Manager:
        def __init__(self):
            self.characters = {
                "pc:hero": CharacterInfo(
                    character_id="pc:hero",
                    name="Hero",
                    character_class="Fighter",
                    character_role=CharacterRole.PLAYER,
                ),
                "npc:villain": CharacterInfo(
                    character_id="npc:villain",
                    name="Villain",
                    character_class="Wizard",
                    character_role=CharacterRole.NPC_COMBATANT,
                ),
                "npc:guide": CharacterInfo(
                    character_id="npc:guide",
                    name="Guide",
                    character_class="Commoner",
                    character_role=CharacterRole.NPC_SUPPORT,
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
    return SceneRosterManager("test_campaign", character_manager=character_manager)


@pytest.fixture
def turn_manager():
    manager = TurnManager()
    return manager


def register_lookup(turn_manager: TurnManager, roster_manager: SceneRosterManager):
    def lookup(campaign_id: str, scene_id: str | None, character_id: str):
        if not scene_id:
            return None
        participants = roster_manager.get_participants_for_scene(scene_id)
        lowered = character_id.lower()
        for participant in participants:
            if participant.character_id and participant.character_id.lower() == lowered:
                return TurnType.PLAYER if participant.role == CharacterRole.PLAYER else TurnType.NPC
            if participant.display_name.lower() == lowered:
                return TurnType.PLAYER if participant.role == CharacterRole.PLAYER else TurnType.NPC
        return None

    turn_manager.set_roster_lookup(lookup)


def add_scene(roster_manager: SceneRosterManager, scene_id: str, participants: List[SceneParticipant]):
    scene_info = make_scene_info(scene_id, participants)
    roster_manager.bootstrap_scene(scene_info)


def test_player_turn_type_from_roster(turn_manager, roster_manager):
    register_lookup(turn_manager, roster_manager)
    add_scene(
        roster_manager,
        "scene_001",
        [
            SceneParticipant(
                character_id="pc:hero",
                display_name="Hero",
                role=CharacterRole.PLAYER,
            )
        ],
    )

    turn = turn_manager.create_turn(
        campaign_id="test_campaign",
        character_id="pc:hero",
        character_name="Hero",
        scene_context={"scene_id": "scene_001"},
    )

    assert turn.turn_type == TurnType.PLAYER


def test_npc_turn_type_from_roster(turn_manager, roster_manager):
    register_lookup(turn_manager, roster_manager)
    add_scene(
        roster_manager,
        "scene_002",
        [
            SceneParticipant(
                character_id="npc:villain",
                display_name="Villain",
                role=CharacterRole.NPC_COMBATANT,
            )
        ],
    )

    turn = turn_manager.create_turn(
        campaign_id="test_campaign",
        character_id="npc:villain",
        character_name="Villain",
        scene_context={"scene_id": "scene_002"},
    )

    assert turn.turn_type == TurnType.NPC


def test_support_npc_turn_type(turn_manager, roster_manager):
    register_lookup(turn_manager, roster_manager)
    add_scene(
        roster_manager,
        "scene_003",
        [
            SceneParticipant(
                character_id="npc:guide",
                display_name="Guide",
                role=CharacterRole.NPC_SUPPORT,
            )
        ],
    )

    turn = turn_manager.create_turn(
        campaign_id="test_campaign",
        character_id="npc:guide",
        character_name="Guide",
        scene_context={"scene_id": "scene_003"},
    )

    assert turn.turn_type == TurnType.NPC


def test_fallback_when_not_in_roster(turn_manager, roster_manager):
    register_lookup(turn_manager, roster_manager)
    add_scene(
        roster_manager,
        "scene_004",
        [
            SceneParticipant(
                character_id="pc:hero",
                display_name="Hero",
                role=CharacterRole.PLAYER,
            )
        ],
    )

    turn = turn_manager.create_turn(
        campaign_id="test_campaign",
        character_id="npc:unknown",
        character_name="Unknown",
        scene_context={"scene_id": "scene_004"},
    )

    assert turn.turn_type == TurnType.NPC


def test_dm_turn_type_unchanged(turn_manager):
    turn = turn_manager.create_turn(
        campaign_id="test_campaign",
        character_id="dm",
        character_name="Narrator",
    )

    assert turn.turn_type == TurnType.NARRATIVE


def test_explicit_override_preserved(turn_manager, roster_manager):
    register_lookup(turn_manager, roster_manager)
    add_scene(
        roster_manager,
        "scene_005",
        [
            SceneParticipant(
                character_id="npc:villain",
                display_name="Villain",
                role=CharacterRole.NPC_COMBATANT,
            )
        ],
    )

    turn = turn_manager.create_turn(
        campaign_id="test_campaign",
        character_id="npc:villain",
        character_name="Villain",
        turn_type=TurnType.NARRATIVE,
        scene_context={"scene_id": "scene_005"},
    )

    assert turn.turn_type == TurnType.NARRATIVE
