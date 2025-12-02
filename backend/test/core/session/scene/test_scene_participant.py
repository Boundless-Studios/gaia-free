"""Unit tests for SceneParticipant model and related functionality."""

import pytest
from datetime import datetime

from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia.models.scene_participant import SceneParticipant


class TestSceneParticipant:
    """Test SceneParticipant data model."""

    def test_create_player_participant(self):
        """Test creating a player character participant."""
        participant = SceneParticipant(
            character_id="pc:aragorn",
            display_name="Aragorn",
            role=CharacterRole.PLAYER,
            capabilities=CharacterCapability.COMBAT | CharacterCapability.NARRATIVE,
            is_present=True
        )

        assert participant.character_id == "pc:aragorn"
        assert participant.display_name == "Aragorn"
        assert participant.role == CharacterRole.PLAYER
        assert participant.is_present is True
        assert participant.capabilities & CharacterCapability.COMBAT
        assert participant.capabilities & CharacterCapability.NARRATIVE

    def test_create_npc_combatant_participant(self):
        """Test creating an NPC combatant participant."""
        participant = SceneParticipant(
            character_id="npc:goblin_1",
            display_name="Goblin Scout",
            role=CharacterRole.NPC_COMBATANT,
            capabilities=CharacterCapability.COMBAT,
            is_present=True
        )

        assert participant.role == CharacterRole.NPC_COMBATANT
        assert participant.capabilities & CharacterCapability.COMBAT
        assert not participant.capabilities & CharacterCapability.NARRATIVE

    def test_create_npc_support_participant(self):
        """Test creating a narrative-only NPC participant."""
        participant = SceneParticipant(
            character_id="npc:innkeeper",
            display_name="Barliman Butterbur",
            role=CharacterRole.NPC_SUPPORT,
            capabilities=CharacterCapability.NARRATIVE,
            is_present=True
        )

        assert participant.role == CharacterRole.NPC_SUPPORT
        assert participant.capabilities & CharacterCapability.NARRATIVE
        assert not participant.capabilities & CharacterCapability.COMBAT

    def test_participant_join_timestamp(self):
        """Test participant tracks when they joined."""
        participant = SceneParticipant(
            character_id="pc:test",
            display_name="Test Character",
            role=CharacterRole.PLAYER
        )

        assert participant.joined_at is not None
        assert isinstance(participant.joined_at, datetime)

    def test_participant_leave(self):
        """Test marking a participant as leaving."""
        participant = SceneParticipant(
            character_id="pc:test",
            display_name="Test Character",
            role=CharacterRole.PLAYER,
            is_present=True
        )

        # Mark as left
        participant.is_present = False
        participant.left_at = datetime.now()

        assert participant.is_present is False
        assert participant.left_at is not None

    def test_participant_to_dict(self):
        """Test serializing participant to dictionary."""
        participant = SceneParticipant(
            character_id="pc:gandalf",
            display_name="Gandalf",
            role=CharacterRole.PLAYER,
            capabilities=CharacterCapability.COMBAT | CharacterCapability.NARRATIVE,
            is_present=True
        )

        data = participant.to_dict()

        assert data["character_id"] == "pc:gandalf"
        assert data["display_name"] == "Gandalf"
        assert data["role"] == "player"
        assert data["is_present"] is True
        assert "joined_at" in data
        assert isinstance(data["capabilities"], int)

    def test_participant_from_dict(self):
        """Test deserializing participant from dictionary."""
        data = {
            "character_id": "npc:orc_1",
            "display_name": "Orc Warrior",
            "role": "npc_combatant",
            "capabilities": int(CharacterCapability.COMBAT),
            "is_present": True,
            "joined_at": datetime.now().isoformat()
        }

        participant = SceneParticipant.from_dict(data)

        assert participant.character_id == "npc:orc_1"
        assert participant.display_name == "Orc Warrior"
        assert participant.role == CharacterRole.NPC_COMBATANT
        assert participant.is_present is True
        assert CharacterCapability.COMBAT in participant.capabilities

    def test_participant_capability_checks(self):
        """Test checking if participant has specific capabilities."""
        participant = SceneParticipant(
            character_id="pc:test",
            display_name="Test",
            role=CharacterRole.PLAYER,
            capabilities=CharacterCapability.COMBAT | CharacterCapability.INVENTORY
        )

        # Check has_capability helper if it exists, otherwise check directly
        assert participant.capabilities & CharacterCapability.COMBAT
        assert participant.capabilities & CharacterCapability.INVENTORY
        assert not participant.capabilities & CharacterCapability.NARRATIVE

    def test_participant_equality(self):
        """Test comparing participants for equality."""
        p1 = SceneParticipant(
            character_id="pc:test",
            display_name="Test",
            role=CharacterRole.PLAYER
        )

        p2 = SceneParticipant(
            character_id="pc:test",
            display_name="Test",
            role=CharacterRole.PLAYER
        )

        # Same character_id should be considered same participant
        assert p1.character_id == p2.character_id

    def test_participant_without_character_id(self):
        """Test creating participant with only display name."""
        participant = SceneParticipant(
            character_id=None,
            display_name="Mysterious Stranger",
            role=CharacterRole.NPC_SUPPORT,
            is_present=True
        )

        assert participant.character_id is None
        assert participant.display_name == "Mysterious Stranger"

    def test_multiple_capabilities(self):
        """Test participant with multiple capabilities."""
        participant = SceneParticipant(
            character_id="pc:versatile",
            display_name="Versatile Hero",
            role=CharacterRole.PLAYER,
            capabilities=(
                CharacterCapability.COMBAT |
                CharacterCapability.NARRATIVE |
                CharacterCapability.INVENTORY |
                CharacterCapability.SKILLS
            )
        )

        # Verify all capabilities are present
        assert participant.capabilities & CharacterCapability.COMBAT
        assert participant.capabilities & CharacterCapability.NARRATIVE
        assert participant.capabilities & CharacterCapability.INVENTORY
        assert participant.capabilities & CharacterCapability.SKILLS

    def test_participant_round_trip_serialization(self):
        """Test full round-trip serialization."""
        original = SceneParticipant(
            character_id="pc:bilbo",
            display_name="Bilbo Baggins",
            role=CharacterRole.PLAYER,
            capabilities=CharacterCapability.NARRATIVE | CharacterCapability.INVENTORY,
            is_present=True
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = SceneParticipant.from_dict(data)

        # Verify all fields match
        assert restored.character_id == original.character_id
        assert restored.display_name == original.display_name
        assert restored.role == original.role
        assert restored.is_present == original.is_present
        assert restored.capabilities == original.capabilities
