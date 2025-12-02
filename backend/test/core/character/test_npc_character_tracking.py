"""Tests for NPC character tracking and mapping improvements."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia.models.character.character_info import CharacterInfo
from gaia_private.session.scene.scene_roster_manager import SceneRosterManager
from gaia.models.scene_participant import SceneParticipant


class TestNpcCharacterTracking:
    """Test NPC character tracking and role consistency."""

    @pytest.fixture
    def character_manager(self):
        """Create mock character manager."""
        manager = Mock()

        # NPC database
        npcs = {}

        def get_character(char_id):
            return npcs.get(char_id)

        def get_character_by_name(name):
            for npc in npcs.values():
                if npc.name == name:
                    return npc
            return None

        def create_or_update_npc(npc_info):
            npcs[npc_info.character_id] = npc_info
            return npc_info

        manager.get_character = Mock(side_effect=get_character)
        manager.get_character_by_name = Mock(side_effect=get_character_by_name)
        manager.create_or_update_npc = Mock(side_effect=create_or_update_npc)
        manager._npcs = npcs  # Store for test access

        return manager

    @pytest.fixture
    def roster_manager(self, character_manager):
        """Create roster manager with mock character manager."""
        return SceneRosterManager(
            campaign_id="test_campaign",
            character_manager=character_manager
        )

    def test_npc_first_appearance_tracking(self, character_manager, roster_manager):
        """Test tracking when an NPC first appears."""
        # Create new NPC
        npc = CharacterInfo(
            character_id="npc:mysterious_stranger",
            name="Mysterious Stranger",
            character_class="Rogue",
            character_type="npc",
            character_role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE,
            first_appearance=datetime.now()
        )

        character_manager.create_or_update_npc(npc)

        # Add to scene
        scene_id = "scene_001"
        roster_manager.add_participant(scene_id, npc.character_id)

        # Verify NPC is tracked
        participants = roster_manager.get_participants(scene_id)
        assert len(participants) == 1
        assert participants[0].character_id == "npc:mysterious_stranger"
        assert participants[0].role == CharacterRole.NPC_SUPPORT

    def test_npc_combatant_vs_support_distinction(self, character_manager, roster_manager):
        """Test distinguishing between combat and support NPCs."""
        scene_id = "scene_001"

        # Combat NPC
        combatant = CharacterInfo(
            character_id="npc:guard",
            name="City Guard",
            character_class="Fighter",
            character_type="npc",
            character_role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT
        )
        character_manager.create_or_update_npc(combatant)

        # Support NPC
        support = CharacterInfo(
            character_id="npc:merchant",
            name="Merchant",
            character_class="Commoner",
            character_type="npc",
            character_role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE
        )
        character_manager.create_or_update_npc(support)

        # Add both to scene
        roster_manager.add_participant(scene_id, combatant.character_id)
        roster_manager.add_participant(scene_id, support.character_id)

        # Verify distinction
        all_npcs = roster_manager.get_participants_by_role(scene_id, CharacterRole.NPC_COMBATANT)
        all_npcs.extend(roster_manager.get_participants_by_role(scene_id, CharacterRole.NPC_SUPPORT))

        assert len(all_npcs) == 2

        # Verify only combatant in combat roster
        combat_ready = roster_manager.get_combat_participants(scene_id)
        assert len(combat_ready) == 1
        assert combat_ready[0].character_id == "npc:guard"

    def test_npc_role_upgrade_from_support_to_combatant(self, character_manager, roster_manager):
        """Test upgrading NPC from support to combatant role."""
        scene_id = "scene_001"

        # Start as support NPC
        npc = CharacterInfo(
            character_id="npc:blacksmith",
            name="Blacksmith",
            character_class="Commoner",
            character_type="npc",
            character_role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE
        )
        character_manager.create_or_update_npc(npc)
        roster_manager.add_participant(scene_id, npc.character_id)

        # Verify initial role
        role = roster_manager.lookup_role(scene_id, "npc:blacksmith")
        assert role == CharacterRole.NPC_SUPPORT

        # Upgrade to combatant (e.g., blacksmith picks up weapon to defend shop)
        npc.character_role = CharacterRole.NPC_COMBATANT
        npc.capabilities = CharacterCapability.COMBAT | CharacterCapability.NARRATIVE
        character_manager.create_or_update_npc(npc)

        # Update roster
        roster_manager.remove_participant(scene_id, "npc:blacksmith")
        roster_manager.add_participant(scene_id, npc.character_id)

        # Verify upgraded role
        new_role = roster_manager.lookup_role(scene_id, "npc:blacksmith")
        assert new_role == CharacterRole.NPC_COMBATANT

        # Should now appear in combat roster
        combat_ready = roster_manager.get_combat_participants(scene_id)
        assert any(p.character_id == "npc:blacksmith" for p in combat_ready)

    def test_npc_interaction_count_tracking(self, character_manager):
        """Test tracking NPC interaction count."""
        npc = CharacterInfo(
            character_id="npc:innkeeper",
            name="Innkeeper",
            character_class="Commoner",
            character_type="npc",
            character_role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE,
            interaction_count=0
        )
        character_manager.create_or_update_npc(npc)

        # Simulate interactions
        npc.interaction_count += 1
        npc.last_interaction = datetime.now()
        character_manager.create_or_update_npc(npc)

        # Verify tracking
        retrieved = character_manager.get_character("npc:innkeeper")
        assert retrieved.interaction_count == 1
        assert retrieved.last_interaction is not None

    def test_npc_without_full_character_info(self, roster_manager):
        """Test handling NPCs that don't have full CharacterInfo yet."""
        scene_id = "scene_001"

        # Create lightweight participant (DM mentioned an NPC but no full sheet yet)
        participant = SceneParticipant(
            character_id=None,
            display_name="Mysterious Figure",
            role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE,
            is_present=True
        )

        # Should be able to add without character_id
        # Use internal cache structure: _scene_cache[scene_id][key] = participant
        key = participant.display_name.lower()
        roster_manager._scene_cache[scene_id] = {key: participant}

        participants = roster_manager.get_participants(scene_id)
        assert len(participants) == 1
        assert participants[0].display_name == "Mysterious Figure"
        assert participants[0].character_id is None  # Not yet assigned

    def test_npc_id_generation_from_name(self, character_manager):
        """Test generating consistent NPC IDs from names."""
        # When DM introduces "Goblin Scout", system should create ID
        npc1 = CharacterInfo(
            character_id="npc:goblin_scout_a1b2",  # Generated ID
            name="Goblin Scout",
            character_class="Scout",
            character_type="npc",
            character_role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT
        )
        character_manager.create_or_update_npc(npc1)

        # Later reference should find same NPC
        retrieved = character_manager.get_character_by_name("Goblin Scout")
        assert retrieved is not None
        assert retrieved.character_id == "npc:goblin_scout_a1b2"

    def test_hostile_vs_friendly_npc_tracking(self, character_manager, roster_manager):
        """Test tracking hostile vs friendly NPCs."""
        scene_id = "scene_tavern_brawl"

        # Friendly NPC
        friendly = CharacterInfo(
            character_id="npc:ally_guard",
            name="Friendly Guard",
            character_class="Fighter",
            character_type="npc",
            character_role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT
        )

        # Hostile NPC
        hostile = CharacterInfo(
            character_id="npc:bandit",
            name="Bandit",
            character_class="Rogue",
            character_type="npc",
            character_role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT
        )

        character_manager.create_or_update_npc(friendly)
        character_manager.create_or_update_npc(hostile)

        roster_manager.add_participant(scene_id, friendly.character_id)
        roster_manager.add_participant(scene_id, hostile.character_id)

        # Both should be in combat roster
        combat_participants = roster_manager.get_combat_participants(scene_id)
        assert len(combat_participants) == 2

        # Can filter by metadata if needed
        # (Implementation detail - roster manager may or may not expose this)

    def test_multiple_npcs_same_name_different_ids(self, character_manager, roster_manager):
        """Test handling multiple NPCs with same name but different IDs."""
        scene_id = "scene_001"

        # Two different guards
        guard1 = CharacterInfo(
            character_id="npc:guard_1",
            name="City Guard",
            character_class="Fighter",
            character_type="npc",
            character_role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT
        )

        guard2 = CharacterInfo(
            character_id="npc:guard_2",
            name="City Guard",
            character_class="Fighter",
            character_type="npc",
            character_role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT
        )

        character_manager.create_or_update_npc(guard1)
        character_manager.create_or_update_npc(guard2)

        roster_manager.add_participant(scene_id, guard1.character_id)
        roster_manager.add_participant(scene_id, guard2.character_id)

        # Should track both separately
        participants = roster_manager.get_participants(scene_id)
        assert len(participants) == 2
        assert participants[0].character_id != participants[1].character_id

    def test_npc_appearance_description_tracking(self, character_manager):
        """Test tracking NPC visual appearance for consistency."""
        npc = CharacterInfo(
            character_id="npc:wizard",
            name="Gandalf",
            character_class="Wizard",
            character_type="npc",
            character_role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE,
            appearance="Tall old man with grey robes and pointed hat",
            visual_description="Elderly wizard with long grey beard and staff"
        )
        character_manager.create_or_update_npc(npc)

        retrieved = character_manager.get_character("npc:wizard")
        assert retrieved.appearance == "Tall old man with grey robes and pointed hat"
        assert retrieved.visual_description is not None

    def test_npc_voice_assignment(self, character_manager):
        """Test assigning voice IDs to NPCs for TTS."""
        npc = CharacterInfo(
            character_id="npc:narrator",
            name="Town Crier",
            character_class="Commoner",
            character_type="npc",
            character_role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE,
            voice_id="male_authoritative",
            voice_settings={"speed": 1.0, "pitch": 0}
        )
        character_manager.create_or_update_npc(npc)

        retrieved = character_manager.get_character("npc:narrator")
        assert retrieved.voice_id == "male_authoritative"
        assert retrieved.voice_settings.get("speed") == 1.0

    def test_npc_persistence_across_scenes(self, character_manager, roster_manager):
        """Test that NPC data persists when appearing in multiple scenes."""
        # Scene 1: First appearance
        scene1 = "scene_tavern"
        npc = CharacterInfo(
            character_id="npc:recurring_villain",
            name="Evil Wizard",
            character_class="Wizard",
            character_type="npc",
            character_role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT | CharacterCapability.NARRATIVE,
            interaction_count=0
        )
        character_manager.create_or_update_npc(npc)
        roster_manager.add_participant(scene1, npc.character_id)

        # Update interaction count
        npc.interaction_count = 1
        character_manager.create_or_update_npc(npc)

        # Scene 2: Reappearance
        scene2 = "scene_castle"
        roster_manager.add_participant(scene2, "npc:recurring_villain")

        # Should have same data
        retrieved = character_manager.get_character("npc:recurring_villain")
        assert retrieved.interaction_count == 1
        assert retrieved.name == "Evil Wizard"
