"""Unit tests for SceneRepository sync methods.

Tests the database storage layer for scenes without going through
the scene_creator agent. Validates that:
1. Scenes can be created with sync methods
2. Scenes can be retrieved after creation
3. Scene updates work correctly
"""

import uuid
import pytest
from datetime import datetime, timezone

from gaia.infra.storage.scene_repository import SceneRepository
from gaia.models.scene_info import SceneInfo
from gaia.models.scene_participant import SceneParticipant
from gaia.models.character.enums import CharacterRole, CharacterCapability
from gaia.models.scene_db import Scene


class TestSceneRepositorySync:
    """Test suite for SceneRepository sync methods."""

    @pytest.fixture
    def repository(self):
        """Create a SceneRepository instance."""
        return SceneRepository()

    @pytest.fixture
    def campaign_uuid(self):
        """Generate a test campaign UUID."""
        return uuid.uuid4()

    @pytest.fixture
    def sample_scene_info(self):
        """Create a sample SceneInfo for testing."""
        scene_id = f"test_scene_{uuid.uuid4().hex[:8]}"
        return SceneInfo(
            scene_id=scene_id,
            title="Test Tavern Scene",
            description="The party enters a dimly lit tavern",
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
                    capabilities=CharacterCapability.NARRATIVE | CharacterCapability.COMBAT | CharacterCapability.INVENTORY,
                    is_present=True,
                    joined_at=datetime.now(timezone.utc),
                ),
            ],
            npcs_involved=["npc_bartender"],
            npcs_present=["npc_bartender"],
            pcs_present=["pc_hero"],
            metadata={
                "location": {
                    "id": "tavern_001",
                    "description": "A cozy tavern with a roaring fireplace",
                }
            },
            timestamp=datetime.now(timezone.utc),
        )

    def test_create_scene_sync_success(self, repository, campaign_uuid, sample_scene_info):
        """Test that create_scene_sync successfully stores a scene."""
        # Act
        result_id = repository.create_scene_sync(sample_scene_info, campaign_uuid)

        # Assert
        assert result_id == sample_scene_info.scene_id

        # Verify we can retrieve it
        retrieved = repository.get_scene_sync(sample_scene_info.scene_id)
        assert retrieved is not None
        assert retrieved.scene_id == sample_scene_info.scene_id
        assert retrieved.title == sample_scene_info.title
        assert retrieved.description == sample_scene_info.description

        # Cleanup
        self._cleanup_scene(repository, sample_scene_info.scene_id)

    def test_create_scene_sync_with_participants(self, repository, campaign_uuid, sample_scene_info):
        """Test that participants are correctly stored."""
        # Act
        repository.create_scene_sync(sample_scene_info, campaign_uuid)

        # Verify
        retrieved = repository.get_scene_sync(sample_scene_info.scene_id)
        assert retrieved is not None
        assert len(retrieved.participants) == 2

        # Check participant details
        participant_ids = [p.character_id for p in retrieved.participants]
        assert "npc_bartender" in participant_ids
        assert "pc_hero" in participant_ids

        # Cleanup
        self._cleanup_scene(repository, sample_scene_info.scene_id)

    def test_create_scene_sync_duplicate_raises(self, repository, campaign_uuid, sample_scene_info):
        """Test that creating a duplicate scene raises ValueError."""
        # Create first scene
        repository.create_scene_sync(sample_scene_info, campaign_uuid)

        # Attempt to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            repository.create_scene_sync(sample_scene_info, campaign_uuid)

        # Cleanup
        self._cleanup_scene(repository, sample_scene_info.scene_id)

    def test_get_scene_sync_not_found(self, repository):
        """Test that get_scene_sync returns None for non-existent scenes."""
        result = repository.get_scene_sync("nonexistent_scene_12345")
        assert result is None

    def test_update_scene_sync_outcomes(self, repository, campaign_uuid, sample_scene_info):
        """Test updating scene outcomes."""
        # Create scene
        repository.create_scene_sync(sample_scene_info, campaign_uuid)

        # Update outcomes
        new_outcomes = ["Party made a new ally", "Secret information revealed"]
        result = repository.update_scene_sync(
            sample_scene_info.scene_id,
            {"outcomes": new_outcomes}
        )

        assert result is True

        # Verify update
        retrieved = repository.get_scene_sync(sample_scene_info.scene_id)
        assert retrieved is not None
        assert retrieved.outcomes == new_outcomes

        # Cleanup
        self._cleanup_scene(repository, sample_scene_info.scene_id)

    def test_update_scene_sync_not_found(self, repository):
        """Test that update_scene_sync returns False for non-existent scenes."""
        result = repository.update_scene_sync(
            "nonexistent_scene_12345",
            {"outcomes": ["test"]}
        )
        assert result is False

    def test_update_scene_sync_immutable_field_raises(self, repository, campaign_uuid, sample_scene_info):
        """Test that updating immutable fields raises ValueError."""
        # Create scene
        repository.create_scene_sync(sample_scene_info, campaign_uuid)

        # Attempt to update immutable field
        with pytest.raises(ValueError, match="Cannot update immutable fields"):
            repository.update_scene_sync(
                sample_scene_info.scene_id,
                {"title": "New Title"}  # title is immutable
            )

        # Cleanup
        self._cleanup_scene(repository, sample_scene_info.scene_id)

    def test_get_recent_scenes_sync(self, repository, campaign_uuid):
        """Test retrieving recent scenes for a campaign."""
        # Create multiple scenes
        scene_ids = []
        for i in range(3):
            scene_info = SceneInfo(
                scene_id=f"test_recent_{uuid.uuid4().hex[:8]}",
                title=f"Test Scene {i}",
                description=f"Description {i}",
                scene_type="exploration",
                timestamp=datetime.now(timezone.utc),
            )
            repository.create_scene_sync(scene_info, campaign_uuid)
            scene_ids.append(scene_info.scene_id)

        # Get recent scenes
        recent = repository.get_recent_scenes_sync(campaign_uuid, limit=5)

        assert len(recent) >= 3
        recent_ids = [s.scene_id for s in recent]
        for scene_id in scene_ids:
            assert scene_id in recent_ids

        # Cleanup
        for scene_id in scene_ids:
            self._cleanup_scene(repository, scene_id)

    def test_scene_with_empty_scene_id_flow(self, repository, campaign_uuid):
        """Test the flow where scene_id starts empty and gets assigned.

        This simulates what scene_creator does: passing scene_id=""
        which should be assigned by EnhancedSceneManager before calling
        the repository.
        """
        # Create a SceneInfo with a generated scene_id (simulating what
        # EnhancedSceneManager._generate_scene_id would do)
        generated_id = f"scene_001_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        scene_info = SceneInfo(
            scene_id=generated_id,  # This would be assigned by EnhancedSceneManager
            title="Generated Scene",
            description="A scene with auto-generated ID",
            scene_type="exploration",
            timestamp=datetime.now(timezone.utc),
        )

        # Act
        result_id = repository.create_scene_sync(scene_info, campaign_uuid)

        # Assert
        assert result_id == generated_id

        # Verify retrieval
        retrieved = repository.get_scene_sync(generated_id)
        assert retrieved is not None
        assert retrieved.title == "Generated Scene"

        # Cleanup
        self._cleanup_scene(repository, generated_id)

    def _cleanup_scene(self, repository, scene_id: str):
        """Helper to cleanup test scenes using soft delete."""
        try:
            # Use sync session directly for cleanup
            with repository.db_manager.get_sync_session() as session:
                scene = session.get(Scene, scene_id)
                if scene:
                    scene.is_deleted = True
                    session.commit()
        except Exception:
            pass  # Ignore cleanup errors
