"""Integration tests for consistent participant role tracking across scene/combat/turn systems."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia.models.character.character_info import CharacterInfo
from gaia_private.session.scene.scene_roster_manager import SceneRosterManager
from gaia_private.session.scene.scene_integration import SceneIntegration
from gaia_private.session.turn_manager import TurnManager
from gaia.models.scene_info import SceneInfo
from gaia.models.turn import TurnType


class TestParticipantRoleConsistency:
    """Test that participant roles remain consistent across scene, combat, and turn systems."""

    @pytest.fixture
    def character_manager(self):
        """Create a mock character manager with test characters."""
        manager = Mock()

        # Player characters
        pc1 = CharacterInfo(
            character_id="pc:aragorn",
            name="Aragorn",
            character_class="Ranger",
            character_type="player",
            character_role=CharacterRole.PLAYER,
            capabilities=CharacterCapability.COMBAT | CharacterCapability.NARRATIVE
        )

        pc2 = CharacterInfo(
            character_id="pc:legolas",
            name="Legolas",
            character_class="Ranger",
            character_type="player",
            character_role=CharacterRole.PLAYER,
            capabilities=CharacterCapability.COMBAT | CharacterCapability.NARRATIVE
        )

        # NPC combatant
        npc_combatant = CharacterInfo(
            character_id="npc:orc_warrior",
            name="Orc Warrior",
            character_class="Fighter",
            character_type="npc",
            character_role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT
        )

        # NPC support
        npc_support = CharacterInfo(
            character_id="npc:innkeeper",
            name="Barliman",
            character_class="Commoner",
            character_type="npc",
            character_role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE
        )

        characters = {
            "pc:aragorn": pc1,
            "pc:legolas": pc2,
            "npc:orc_warrior": npc_combatant,
            "npc:innkeeper": npc_support,
        }

        manager.get_character = Mock(side_effect=lambda cid: characters.get(cid))
        manager.get_character_by_name = Mock(side_effect=lambda name: next(
            (c for c in characters.values() if c.name == name), None
        ))
        manager.get_player_characters = Mock(return_value=[pc1, pc2])

        return manager

    @pytest.fixture
    def roster_manager(self, character_manager):
        """Create roster manager."""
        return SceneRosterManager(
            campaign_id="test_campaign",
            character_manager=character_manager
        )

    @pytest.fixture
    def turn_manager(self):
        """Create turn manager."""
        campaign_manager = Mock()
        campaign_manager.get_next_turn_number = Mock(return_value=1)
        return TurnManager(campaign_manager=campaign_manager)

    def test_player_role_consistency_scene_to_turn(self, roster_manager, turn_manager):
        """Test that player role is consistent from scene to turn."""
        scene_id = "scene_001"

        # Add player to scene roster
        roster_manager.add_participant(scene_id, "pc:aragorn")

        # Verify role in roster
        role = roster_manager.lookup_role(scene_id, "pc:aragorn")
        assert role == CharacterRole.PLAYER

        # Create turn for this character
        turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="pc:aragorn",
            character_name="Aragorn",
            scene_context={"scene_id": scene_id}
        )

        # Verify turn type matches character role
        assert turn.turn_type == TurnType.PLAYER

    def test_npc_combatant_role_consistency(self, roster_manager, turn_manager):
        """Test that NPC combatant role is consistent."""
        scene_id = "scene_001"

        # Add NPC combatant to scene roster
        roster_manager.add_participant(scene_id, "npc:orc_warrior")

        # Verify role in roster
        role = roster_manager.lookup_role(scene_id, "npc:orc_warrior")
        assert role == CharacterRole.NPC_COMBATANT

        # Create turn for this NPC
        turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="npc:orc_warrior",
            character_name="Orc Warrior",
            scene_context={"scene_id": scene_id}
        )

        # Turn type should be NPC
        assert turn.turn_type == TurnType.NPC

    def test_npc_support_not_in_combat(self, roster_manager):
        """Test that support NPCs are excluded from combat roster."""
        scene_id = "scene_combat"

        # Add both combatant and support NPCs
        roster_manager.add_participant(scene_id, "npc:orc_warrior")
        roster_manager.add_participant(scene_id, "npc:innkeeper")

        # Get combat participants
        combat_participants = roster_manager.get_combat_participants(scene_id)

        # Only the combatant should be included
        combat_ids = [p.character_id for p in combat_participants]
        assert "npc:orc_warrior" in combat_ids
        assert "npc:innkeeper" not in combat_ids

    def test_mixed_participant_scene(self, roster_manager):
        """Test scene with mixed participant types."""
        scene_id = "scene_tavern"

        # Add various participants
        roster_manager.add_participant(scene_id, "pc:aragorn")  # Player
        roster_manager.add_participant(scene_id, "pc:legolas")  # Player
        roster_manager.add_participant(scene_id, "npc:innkeeper")  # Support NPC

        # Verify all participants are tracked
        all_participants = roster_manager.get_participants(scene_id)
        assert len(all_participants) == 3

        # Verify only players for player-specific operations
        players = roster_manager.get_participants_by_role(scene_id, CharacterRole.PLAYER)
        assert len(players) == 2

        # Verify support NPCs
        support = roster_manager.get_participants_by_role(scene_id, CharacterRole.NPC_SUPPORT)
        assert len(support) == 1

    def test_combat_initiation_uses_roster(self, roster_manager):
        """Test that combat initiation respects scene roster roles."""
        scene_id = "scene_combat"

        # Setup scene with players and enemies
        roster_manager.add_participant(scene_id, "pc:aragorn")
        roster_manager.add_participant(scene_id, "pc:legolas")
        roster_manager.add_participant(scene_id, "npc:orc_warrior")

        # Get combat participants
        combat_participants = roster_manager.get_combat_participants(scene_id)

        # Should include all combat-capable participants
        assert len(combat_participants) == 3

        # Verify roles
        roles = {p.character_id: p.role for p in combat_participants}
        assert roles["pc:aragorn"] == CharacterRole.PLAYER
        assert roles["pc:legolas"] == CharacterRole.PLAYER
        assert roles["npc:orc_warrior"] == CharacterRole.NPC_COMBATANT

    def test_turn_type_inference_from_roster(self, roster_manager, turn_manager):
        """Test that turn type can be inferred from roster role."""
        scene_id = "scene_001"

        # Add participants to roster
        roster_manager.add_participant(scene_id, "pc:aragorn")
        roster_manager.add_participant(scene_id, "npc:orc_warrior")

        # Get roles from roster
        player_role = roster_manager.lookup_role(scene_id, "pc:aragorn")
        npc_role = roster_manager.lookup_role(scene_id, "npc:orc_warrior")

        # Verify roles match expected turn types
        assert player_role == CharacterRole.PLAYER  # Should map to TurnType.PLAYER
        assert npc_role == CharacterRole.NPC_COMBATANT  # Should map to TurnType.NPC

    def test_participant_join_leave_tracking(self, roster_manager):
        """Test tracking when participants join and leave scenes."""
        scene_id = "scene_001"

        # Initial participants
        roster_manager.add_participant(scene_id, "pc:aragorn")
        roster_manager.add_participant(scene_id, "npc:innkeeper")

        initial = roster_manager.get_participants(scene_id)
        assert len(initial) == 2

        # New participant joins
        roster_manager.add_participant(scene_id, "npc:orc_warrior")

        # Participant leaves
        roster_manager.remove_participant(scene_id, "npc:innkeeper")

        # Get deltas
        current = roster_manager.get_participants(scene_id)
        added, removed = roster_manager.get_participant_deltas(scene_id, initial)

        assert len(added) == 1
        assert "npc:orc_warrior" in [p.character_id for p in added]

        assert len(removed) == 1
        assert "npc:innkeeper" in [p.character_id for p in removed]

    def test_capability_validation(self, roster_manager):
        """Test validating capabilities before actions."""
        scene_id = "scene_001"

        # Add participants with different capabilities
        roster_manager.add_participant(scene_id, "pc:aragorn")  # Has COMBAT
        roster_manager.add_participant(scene_id, "npc:innkeeper")  # No COMBAT

        # Validate combat capability
        assert roster_manager.has_capability(scene_id, "pc:aragorn", CharacterCapability.COMBAT)
        assert not roster_manager.has_capability(scene_id, "npc:innkeeper", CharacterCapability.COMBAT)

        # Validate narrative capability
        assert roster_manager.has_capability(scene_id, "pc:aragorn", CharacterCapability.NARRATIVE)
        assert roster_manager.has_capability(scene_id, "npc:innkeeper", CharacterCapability.NARRATIVE)

    def test_roster_snapshot_for_scene_info(self, roster_manager):
        """Test creating a roster snapshot for SceneInfo persistence."""
        scene_id = "scene_001"

        # Setup roster
        roster_manager.add_participant(scene_id, "pc:aragorn")
        roster_manager.add_participant(scene_id, "pc:legolas")
        roster_manager.add_participant(scene_id, "npc:orc_warrior")

        participants = roster_manager.get_participants(scene_id)

        # Verify we can extract IDs for legacy fields
        player_ids = [p.character_id for p in participants if p.role == CharacterRole.PLAYER]
        npc_ids = [p.character_id for p in participants if p.role != CharacterRole.PLAYER]

        assert len(player_ids) == 2
        assert len(npc_ids) == 1

    def test_dm_narrative_turn_type(self, turn_manager):
        """Test that DM gets NARRATIVE turn type."""
        turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="dm",
            character_name="Dungeon Master"
        )

        assert turn.turn_type == TurnType.NARRATIVE

    def test_character_id_prefix_fallback(self, turn_manager):
        """Test turn type inference from character_id prefix when roster unavailable."""
        # Test PC prefix
        pc_turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="pc:unknown",
            character_name="Unknown PC"
        )
        assert pc_turn.turn_type == TurnType.PLAYER

        # Test NPC prefix
        npc_turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="npc:unknown",
            character_name="Unknown NPC"
        )
        assert npc_turn.turn_type == TurnType.NPC

    def test_roster_persistence_in_scene_info(self, roster_manager):
        """Test that roster data can be persisted in SceneInfo."""
        scene_info = SceneInfo(
            scene_id="scene_001",
            title="Test Scene",
            description="A test scene",
            location_id="test_location",
            location_description="Test location desc",
            scene_type="combat",
            pcs_present=["pc:aragorn", "pc:legolas"],
            npcs_involved=["npc:orc_warrior"]
        )

        # Bootstrap roster from scene
        roster_manager.bootstrap_scene(scene_info)

        # Verify roster was populated
        participants = roster_manager.get_participants("scene_001")
        assert len(participants) >= 2  # At least the PCs
