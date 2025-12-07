"""Integration tests for scene database storage.

Tests the scene storage flow:
1. Create a scene with a campaign UUID
2. Verify scene is stored in the database
3. Verify scene can be retrieved
4. Verify NPC/PC lists are computed correctly from scene entities

Note: No FK constraint on campaign_id - campaigns aren't in DB yet.
"""

import uuid
import pytest
from datetime import datetime, timezone

from gaia.infra.storage.scene_repository import SceneRepository
from gaia.models.scene_info import SceneInfo
from gaia.models.scene_participant import SceneParticipant
from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia.models.scene_db import Scene
from db.src.connection import db_manager


class TestSceneDBIntegration:
    """Integration tests for scene database storage."""

    @pytest.fixture
    def scene_repository(self):
        """Create a scene repository for testing."""
        return SceneRepository()

    @pytest.fixture
    def campaign_uuid(self):
        """Generate a campaign UUID for testing."""
        return uuid.uuid4()

    def _cleanup_scene(self, scene_id: str):
        """Helper to clean up test scenes."""
        with db_manager.get_sync_session() as session:
            scene = session.get(Scene, scene_id)
            if scene:
                scene.is_deleted = True
                session.commit()

    def test_create_scene_stores_in_db(self, scene_repository, campaign_uuid):
        """Test that creating a scene stores it in the database."""
        scene_id = f"test_scene_{uuid.uuid4().hex[:8]}"
        scene_info = SceneInfo(
            scene_id=scene_id,
            title="Tavern Encounter",
            description="The party enters a bustling tavern",
            scene_type="social",
            objectives=["Meet the contact", "Gather information"],
            participants=[
                SceneParticipant(
                    character_id="npc_bartender",
                    display_name="Barkeep Marcus",
                    role=CharacterRole.NPC_SUPPORT,
                    capabilities=CharacterCapability.NARRATIVE | CharacterCapability.COMBAT,
                    is_present=True,
                    joined_at=datetime.now(timezone.utc),
                ),
                SceneParticipant(
                    character_id="pc_hero",
                    display_name="Thorin Ironforge",
                    role=CharacterRole.PLAYER,
                    capabilities=CharacterCapability.NARRATIVE | CharacterCapability.COMBAT,
                    is_present=True,
                    joined_at=datetime.now(timezone.utc),
                ),
            ],
            metadata={"location": "tavern_001"},
            timestamp=datetime.now(timezone.utc),
        )

        try:
            # Create scene in database
            created_id = scene_repository.create_scene_sync(scene_info, campaign_uuid)
            assert created_id == scene_id

            # Verify scene exists in database
            with db_manager.get_sync_session() as session:
                db_scene = session.get(Scene, scene_id)
                assert db_scene is not None, "Scene should exist in database"
                assert db_scene.title == "Tavern Encounter"
                assert db_scene.campaign_id == campaign_uuid
                assert db_scene.scene_type == "social"

                # Verify scene entities were created
                assert len(db_scene.entities) == 2
                entity_ids = [e.entity_id for e in db_scene.entities]
                assert "npc_bartender" in entity_ids
                assert "pc_hero" in entity_ids
        finally:
            self._cleanup_scene(scene_id)

    def test_retrieve_scene_from_db(self, scene_repository, campaign_uuid):
        """Test that scenes can be retrieved from the database."""
        scene_id = f"test_scene_{uuid.uuid4().hex[:8]}"
        scene_info = SceneInfo(
            scene_id=scene_id,
            title="Forest Clearing",
            description="A peaceful clearing in the forest",
            scene_type="exploration",
            objectives=["Find the hidden path"],
            participants=[
                SceneParticipant(
                    character_id="pc_ranger",
                    display_name="Elara the Ranger",
                    role=CharacterRole.PLAYER,
                    capabilities=CharacterCapability.NARRATIVE,
                    is_present=True,
                    joined_at=datetime.now(timezone.utc),
                ),
            ],
            metadata={"location": "forest_001"},
            timestamp=datetime.now(timezone.utc),
        )

        try:
            # Create scene
            scene_repository.create_scene_sync(scene_info, campaign_uuid)

            # Retrieve scene
            retrieved = scene_repository.get_scene_sync(scene_id)
            assert retrieved is not None
            assert retrieved.scene_id == scene_id
            assert retrieved.title == "Forest Clearing"
            assert retrieved.scene_type == "exploration"
            assert len(retrieved.participants) == 1
            assert retrieved.participants[0].character_id == "pc_ranger"
        finally:
            self._cleanup_scene(scene_id)

    def test_scene_entities_computed_correctly(self, scene_repository, campaign_uuid):
        """Test that NPC/PC lists are computed correctly from scene entities."""
        scene_id = f"test_scene_{uuid.uuid4().hex[:8]}"
        scene_info = SceneInfo(
            scene_id=scene_id,
            title="Mixed Party Scene",
            description="A scene with NPCs and PCs",
            scene_type="social",
            participants=[
                SceneParticipant(
                    character_id="npc_guard",
                    display_name="Guard Captain",
                    role=CharacterRole.NPC_SUPPORT,
                    capabilities=CharacterCapability.NARRATIVE,
                    is_present=True,
                    joined_at=datetime.now(timezone.utc),
                ),
                SceneParticipant(
                    character_id="npc_merchant",
                    display_name="Merchant",
                    role=CharacterRole.NPC_SUPPORT,
                    capabilities=CharacterCapability.NARRATIVE,
                    is_present=False,  # Not present
                    joined_at=datetime.now(timezone.utc),
                    left_at=datetime.now(timezone.utc),
                ),
                SceneParticipant(
                    character_id="pc_fighter",
                    display_name="Fighter",
                    role=CharacterRole.PLAYER,
                    capabilities=CharacterCapability.NARRATIVE,
                    is_present=True,
                    joined_at=datetime.now(timezone.utc),
                ),
            ],
            metadata={"location": "location_001"},
            timestamp=datetime.now(timezone.utc),
        )

        try:
            # Create and retrieve scene
            scene_repository.create_scene_sync(scene_info, campaign_uuid)
            retrieved = scene_repository.get_scene_sync(scene_id)

            assert retrieved is not None

            # Verify NPC/PC lists are computed correctly
            assert "npc_guard" in retrieved.npcs_involved
            assert "npc_merchant" in retrieved.npcs_involved
            assert "npc_guard" in retrieved.npcs_present
            assert "npc_merchant" not in retrieved.npcs_present  # Left the scene
            assert "npc_merchant" in retrieved.npcs_removed
            assert "pc_fighter" in retrieved.pcs_present
        finally:
            self._cleanup_scene(scene_id)
