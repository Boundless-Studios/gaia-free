"""Tests for the Visual Narrator scene agent and scene image set management."""

import pytest
from datetime import datetime
from typing import Dict, Any

from gaia.infra.image.scene_image_set import (
    SceneImage,
    SceneImageSet,
    SceneImageSetManager,
    get_scene_image_set_manager,
)


# ============================================================================
# Scene Image Set Tests
# ============================================================================


class TestSceneImage:
    """Tests for the SceneImage dataclass."""

    def test_scene_image_creation(self):
        """Test creating a scene image with default values."""
        image = SceneImage(
            image_type="location_ambiance",
            description="A dimly lit tavern",
        )

        assert image.image_type == "location_ambiance"
        assert image.description == "A dimly lit tavern"
        assert image.status == "pending"
        assert image.image_path is None
        assert image.image_url is None
        assert image.error is None

    def test_scene_image_to_dict(self):
        """Test converting scene image to dictionary."""
        image = SceneImage(
            image_type="moment_focus",
            description="A hero raises their sword",
            status="complete",
            image_url="/api/images/test.png",
        )

        result = image.to_dict()

        assert result["type"] == "moment_focus"
        assert result["description"] == "A hero raises their sword"
        assert result["status"] == "complete"
        assert result["image_url"] == "/api/images/test.png"


class TestSceneImageSet:
    """Tests for the SceneImageSet dataclass."""

    def test_scene_image_set_creation(self):
        """Test creating a scene image set."""
        images = [
            SceneImage(image_type="location_ambiance", description="Tavern"),
            SceneImage(image_type="background_detail", description="Patrons"),
            SceneImage(image_type="moment_focus", description="Map"),
        ]

        image_set = SceneImageSet(
            set_id="test-id",
            campaign_id="campaign_123",
            turn_number=5,
            images=images,
        )

        assert image_set.set_id == "test-id"
        assert image_set.campaign_id == "campaign_123"
        assert image_set.turn_number == 5
        assert image_set.status == "generating"
        assert len(image_set.images) == 3

    def test_scene_image_set_update_status_all_complete(self):
        """Test status updates to complete when all images complete."""
        images = [
            SceneImage(image_type="location_ambiance", description="A", status="complete"),
            SceneImage(image_type="background_detail", description="B", status="complete"),
            SceneImage(image_type="moment_focus", description="C", status="complete"),
        ]

        image_set = SceneImageSet(
            set_id="test-id",
            campaign_id="campaign_123",
            turn_number=1,
            images=images,
        )

        image_set.update_status()

        assert image_set.status == "complete"
        assert image_set.completed_at is not None

    def test_scene_image_set_update_status_some_failed(self):
        """Test status updates to failed when some images fail."""
        images = [
            SceneImage(image_type="location_ambiance", description="A", status="complete"),
            SceneImage(image_type="background_detail", description="B", status="failed"),
            SceneImage(image_type="moment_focus", description="C", status="complete"),
        ]

        image_set = SceneImageSet(
            set_id="test-id",
            campaign_id="campaign_123",
            turn_number=1,
            images=images,
        )

        image_set.update_status()

        assert image_set.status == "failed"

    def test_scene_image_set_get_image(self):
        """Test getting a specific image by type."""
        images = [
            SceneImage(image_type="location_ambiance", description="A"),
            SceneImage(image_type="background_detail", description="B"),
            SceneImage(image_type="moment_focus", description="C"),
        ]

        image_set = SceneImageSet(
            set_id="test-id",
            campaign_id="campaign_123",
            turn_number=1,
            images=images,
        )

        result = image_set.get_image("background_detail")

        assert result is not None
        assert result.description == "B"

    def test_scene_image_set_get_image_not_found(self):
        """Test getting a non-existent image type."""
        image_set = SceneImageSet(
            set_id="test-id",
            campaign_id="campaign_123",
            turn_number=1,
            images=[],
        )

        result = image_set.get_image("location_ambiance")

        assert result is None


class TestSceneImageSetManager:
    """Tests for the SceneImageSetManager."""

    @pytest.fixture
    def manager(self):
        """Create a fresh manager for each test."""
        return SceneImageSetManager()

    def test_create_set(self, manager):
        """Test creating a new scene image set."""
        descriptions = {
            "location_ambiance": "A dark cave",
            "background_detail": "Stalactites hanging",
            "moment_focus": "A treasure chest",
        }

        result = manager.create_set(
            campaign_id="campaign_123",
            turn_number=5,
            descriptions=descriptions,
        )

        assert result.campaign_id == "campaign_123"
        assert result.turn_number == 5
        assert result.status == "generating"
        assert len(result.images) == 3

        # Verify each image was created correctly
        location = result.get_image("location_ambiance")
        assert location is not None
        assert location.description == "A dark cave"
        assert location.status == "pending"

    def test_get_set(self, manager):
        """Test retrieving a set by ID."""
        descriptions = {"location_ambiance": "Test"}
        created = manager.create_set("campaign_1", 1, descriptions)

        result = manager.get_set(created.set_id)

        assert result is not None
        assert result.set_id == created.set_id

    def test_get_set_not_found(self, manager):
        """Test retrieving a non-existent set."""
        result = manager.get_set("nonexistent-id")

        assert result is None

    def test_get_latest_set(self, manager):
        """Test getting the most recent set for a campaign."""
        descriptions = {"location_ambiance": "Test"}

        # Create multiple sets
        manager.create_set("campaign_1", 1, descriptions)
        manager.create_set("campaign_1", 2, descriptions)
        latest = manager.create_set("campaign_1", 3, descriptions)

        result = manager.get_latest_set("campaign_1")

        assert result is not None
        assert result.set_id == latest.set_id
        assert result.turn_number == 3

    def test_get_latest_set_no_sets(self, manager):
        """Test getting latest set when none exist."""
        result = manager.get_latest_set("nonexistent_campaign")

        assert result is None

    def test_get_campaign_sets(self, manager):
        """Test getting multiple sets for a campaign."""
        descriptions = {"location_ambiance": "Test"}

        # Create multiple sets
        for i in range(5):
            manager.create_set("campaign_1", i + 1, descriptions)

        result = manager.get_campaign_sets("campaign_1", limit=3)

        assert len(result) == 3
        # Most recent first
        assert result[0].turn_number == 5
        assert result[1].turn_number == 4
        assert result[2].turn_number == 3

    def test_update_image(self, manager):
        """Test updating an image within a set."""
        descriptions = {
            "location_ambiance": "Test",
            "background_detail": "Test2",
            "moment_focus": "Test3",
        }
        image_set = manager.create_set("campaign_1", 1, descriptions)

        result = manager.update_image(
            set_id=image_set.set_id,
            image_type="location_ambiance",
            status="complete",
            image_url="/api/images/test.png",
        )

        assert result is not None
        image = result.get_image("location_ambiance")
        assert image.status == "complete"
        assert image.image_url == "/api/images/test.png"

    def test_update_image_triggers_set_status_update(self, manager):
        """Test that updating all images updates set status."""
        descriptions = {
            "location_ambiance": "A",
            "background_detail": "B",
            "moment_focus": "C",
        }
        image_set = manager.create_set("campaign_1", 1, descriptions)

        # Complete all images
        for image_type in ["location_ambiance", "background_detail", "moment_focus"]:
            manager.update_image(
                set_id=image_set.set_id,
                image_type=image_type,
                status="complete",
                image_url=f"/api/images/{image_type}.png",
            )

        result = manager.get_set(image_set.set_id)
        assert result.status == "complete"

    def test_cleanup_old_sets(self, manager):
        """Test that old sets are cleaned up when limit exceeded."""
        # Set a low max for testing
        original_max = SceneImageSetManager.MAX_SETS_PER_CAMPAIGN
        SceneImageSetManager.MAX_SETS_PER_CAMPAIGN = 3

        try:
            descriptions = {"location_ambiance": "Test"}

            # Create more sets than the limit
            set_ids = []
            for i in range(5):
                s = manager.create_set("campaign_1", i + 1, descriptions)
                set_ids.append(s.set_id)

            # Old sets should be cleaned up
            assert manager.get_set(set_ids[0]) is None
            assert manager.get_set(set_ids[1]) is None

            # Recent sets should still exist
            assert manager.get_set(set_ids[2]) is not None
            assert manager.get_set(set_ids[3]) is not None
            assert manager.get_set(set_ids[4]) is not None

        finally:
            SceneImageSetManager.MAX_SETS_PER_CAMPAIGN = original_max


class TestGlobalManager:
    """Tests for the global singleton manager."""

    def test_get_scene_image_set_manager_returns_singleton(self):
        """Test that get_scene_image_set_manager returns the same instance."""
        manager1 = get_scene_image_set_manager()
        manager2 = get_scene_image_set_manager()

        assert manager1 is manager2


# ============================================================================
# Visual Narrator Agent Tests (Integration)
# ============================================================================


@pytest.fixture
def sample_analysis_context() -> Dict[str, Any]:
    """Provide sample analysis context with character visuals."""
    return {
        "previous_scenes": [
            {
                "narrative": "The party enters an ancient stone chamber. Dust motes dance in shafts of light from cracks in the ceiling."
            }
        ],
        "active_characters": [
            {
                "name": "Thorin Ironforge",
                "race": "Dwarf",
                "character_class": "Fighter",
                "gender": "Male",
                "build": "Stocky",
                "facial_features": "Braided grey beard, battle scars",
                "attire": "Plate armor with clan insignia",
                "primary_weapon": "Warhammer",
                "distinguishing_feature": "Eyepatch over left eye",
                "facial_expression": "Determined",
                "pose": "Ready stance",
            },
            {
                "name": "Elara Moonwhisper",
                "race": "Elf",
                "character_class": "Wizard",
                "gender": "Female",
                "build": "Slender",
                "visual_description": "Tall elven woman with silver hair and violet eyes",
                "attire": "Flowing blue robes with silver embroidery",
                "primary_weapon": "Crystal-topped staff",
            },
        ],
        "current_turn": {
            "character_name": "Thorin Ironforge",
            "personality_traits": ["Brave", "Protective"],
        },
    }


class TestVisualNarratorResult:
    """Tests for the VisualNarratorResult dataclass."""

    def test_to_dict(self):
        """Test converting result to dictionary."""
        from gaia_private.agents.scene.visual_narrator_agent import VisualNarratorResult

        result = VisualNarratorResult(
            location_ambiance="A dark tavern",
            background_detail="Patrons in shadows",
            moment_focus="A map on the table",
        )

        d = result.to_dict()

        assert d["location_ambiance"] == "A dark tavern"
        assert d["background_detail"] == "Patrons in shadows"
        assert d["moment_focus"] == "A map on the table"

    def test_to_image_prompts(self):
        """Test converting result to image generation prompts."""
        from gaia_private.agents.scene.visual_narrator_agent import VisualNarratorResult

        result = VisualNarratorResult(
            location_ambiance="Location desc",
            background_detail="Background desc",
            moment_focus="Moment desc",
        )

        prompts = result.to_image_prompts()

        assert prompts["scene"] == "Location desc"
        assert prompts["scene_background"] == "Background desc"
        assert prompts["moment"] == "Moment desc"


class TestVisualNarratorCharacterFormatting:
    """Tests for character visual formatting in the agent."""

    def test_format_character_visual_full_details(self, sample_analysis_context):
        """Test formatting a character with full visual details."""
        from gaia_private.agents.scene.visual_narrator_agent import VisualNarratorAgent

        agent = VisualNarratorAgent()
        char = sample_analysis_context["active_characters"][0]  # Thorin

        result = agent._format_character_visual(char)

        assert "Thorin Ironforge" in result
        assert "Dwarf" in result
        assert "Fighter" in result
        assert "Warhammer" in result
        assert "Eyepatch" in result

    def test_format_character_visual_with_visual_description(self, sample_analysis_context):
        """Test formatting a character with visual_description field."""
        from gaia_private.agents.scene.visual_narrator_agent import VisualNarratorAgent

        agent = VisualNarratorAgent()
        char = sample_analysis_context["active_characters"][1]  # Elara

        result = agent._format_character_visual(char)

        assert "Elara Moonwhisper" in result
        assert "silver hair" in result
        assert "violet eyes" in result

    def test_build_character_visuals_multiple_characters(self, sample_analysis_context):
        """Test building character visuals for multiple characters."""
        from gaia_private.agents.scene.visual_narrator_agent import VisualNarratorAgent

        agent = VisualNarratorAgent()

        result = agent._build_character_visuals(sample_analysis_context)

        assert "Thorin Ironforge" in result
        assert "Elara Moonwhisper" in result

    def test_build_character_visuals_empty(self):
        """Test building character visuals with no characters."""
        from gaia_private.agents.scene.visual_narrator_agent import VisualNarratorAgent

        agent = VisualNarratorAgent()

        result = agent._build_character_visuals({"active_characters": []})

        assert "No characters" in result


class TestVisualNarratorSceneExtraction:
    """Tests for scene description extraction."""

    def test_extract_scene_description(self, sample_analysis_context):
        """Test extracting scene description from context."""
        from gaia_private.agents.scene.visual_narrator_agent import VisualNarratorAgent

        result = VisualNarratorAgent._extract_scene_description(sample_analysis_context)

        assert "ancient stone chamber" in result
        assert "Dust motes" in result

    def test_extract_scene_description_empty(self):
        """Test extracting scene description with empty context."""
        from gaia_private.agents.scene.visual_narrator_agent import VisualNarratorAgent

        result = VisualNarratorAgent._extract_scene_description({})

        assert result == ""
