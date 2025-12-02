import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from gaia_private.agents.tools.persistence_hooks import ToolPersistenceHook
from gaia.models.campaign import CampaignData
from gaia.models.character import CharacterInfo


class DummyCharacterManager:
    def __init__(self, characters):
        self.characters = characters
        self.converter = SimpleNamespace(to_dict=lambda obj: {"character_id": obj.character_id})
        self.storage = SimpleNamespace(
            save_character=MagicMock(),
            link_character_to_campaign=MagicMock(),
        )

    def update_npc_profile_from_structured(self, *_args, **_kwargs):
        return True

    def ensure_npc_profile(self, *_args, **_kwargs):
        return True


class DummyCampaignManager:
    def __init__(self, campaign, character_manager):
        self._campaign = campaign
        self._character_manager = character_manager
        self.saved_payloads = []

    def load_campaign(self, _campaign_id):
        return self._campaign

    def get_character_manager(self, _campaign_id):
        return self._character_manager

    def save_campaign_data(self, _campaign_id, payload):
        self.saved_payloads.append(payload)
        self._campaign = payload
        return True


@pytest.mark.asyncio
async def test_on_character_update_does_not_duplicate_existing_players():
    # Arrange existing player character
    campaign = CampaignData(campaign_id="campaign_140", character_ids=["pc:silas_vex"])
    existing_player = CharacterInfo(
        character_id="pc:silas_vex",
        name="Silas Vex",
        character_class="Wizard",
        character_type="player",
    )
    character_manager = DummyCharacterManager({"pc:silas_vex": existing_player})
    campaign_manager = DummyCampaignManager(campaign, character_manager)

    hook = ToolPersistenceHook()
    hook.current_session_id = "campaign_140"
    hook.campaign_manager = campaign_manager

    params = {"name": "Silas Vex"}
    result = {
        "character": {
            "name": "Silas Vex",
            "class": "Warlock",
            "race": "Changeling",
            "hp": 13,
            "max_hp": 13,
            "ac": 15,
        },
        "update_mode": "create",  # DM requested create, but player already exists
        "add_to_current_scene": False,
    }

    # Act
    await hook.on_character_update("character_updater", params, result)

    # Assert: original player updated, no duplicate added
    assert campaign.character_ids == ["pc:silas_vex"]
    assert set(character_manager.characters.keys()) == {"pc:silas_vex"}
    assert existing_player.character_class == "Warlock"
    character_manager.storage.save_character.assert_called_once()


@pytest.mark.asyncio
async def test_on_character_update_creates_npc_with_standard_prefix():
    campaign = CampaignData(campaign_id="campaign_147", character_ids=[])
    character_manager = DummyCharacterManager({})
    campaign_manager = DummyCampaignManager(campaign, character_manager)

    hook = ToolPersistenceHook()
    hook.current_session_id = "campaign_147"
    hook.campaign_manager = campaign_manager

    result = {
        "character": {
            "name": "Gull-Winged Aarakocra Clerk",
            "class": "Cleric",
            "race": "Aarakocra",
            "hp": 8,
            "max_hp": 8,
            "ac": 12,
        },
        "update_mode": "create",
        "add_to_current_scene": False,
    }

    await hook.on_character_update("character_updater", {"name": "Gull-Winged Aarakocra Clerk"}, result)

    assert len(character_manager.characters) == 1
    new_id = next(iter(character_manager.characters.keys()))
    assert new_id.startswith("npc:")
    assert campaign.character_ids == [new_id]
    assert character_manager.characters[new_id].character_type == "npc"
    save_payload = character_manager.storage.save_character.call_args.args[0]
    assert save_payload["character_id"] == new_id


@pytest.mark.asyncio
async def test_on_character_update_creates_player_with_pc_prefix():
    campaign = CampaignData(campaign_id="campaign_200", character_ids=[])
    character_manager = DummyCharacterManager({})
    campaign_manager = DummyCampaignManager(campaign, character_manager)

    hook = ToolPersistenceHook()
    hook.current_session_id = "campaign_200"
    hook.campaign_manager = campaign_manager

    result = {
        "character": {
            "name": "Seren the Bold",
            "class": "Paladin",
            "race": "Human",
            "hp": 14,
            "max_hp": 14,
            "ac": 18,
            "is_player": True,
        },
        "update_mode": "create",
        "add_to_current_scene": False,
    }

    await hook.on_character_update("character_updater", {"name": "Seren the Bold"}, result)

    assert len(character_manager.characters) == 1
    new_id = next(iter(character_manager.characters.keys()))
    assert new_id.startswith("pc:")
    assert character_manager.characters[new_id].character_type == "player"
    assert campaign.character_ids == [new_id]
    save_payload = character_manager.storage.save_character.call_args.args[0]
    assert save_payload["character_id"] == new_id
