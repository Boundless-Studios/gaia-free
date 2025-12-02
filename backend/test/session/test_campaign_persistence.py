"""Test campaign persistence functionality.

Note: These tests work with SimpleCampaignManager which requires proper
campaign directory structure. Some tests are currently skipped as they need
integration with the full campaign creation flow rather than direct directory creation.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia.utils.singleton import SingletonMeta
from gaia.models.campaign import CampaignData
from gaia.models.game_enums import GameStyle


class TestCampaignPersistence:
    """Test campaign persistence using SimpleCampaignManager."""

    @pytest.fixture(autouse=True)
    def clear_singleton(self):
        """Clear SimpleCampaignManager singleton before and after each test."""
        # Clear before test
        if SimpleCampaignManager in SingletonMeta._instances:
            manager = SingletonMeta._instances[SimpleCampaignManager]
            if hasattr(manager, '_initialized'):
                delattr(manager, '_initialized')
            del SingletonMeta._instances[SimpleCampaignManager]

        yield

        # Clear after test
        if SimpleCampaignManager in SingletonMeta._instances:
            manager = SingletonMeta._instances[SimpleCampaignManager]
            if hasattr(manager, '_initialized'):
                delattr(manager, '_initialized')
            del SingletonMeta._instances[SimpleCampaignManager]

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def campaign_manager(self, temp_dir):
        """Create a campaign manager for testing."""
        return SimpleCampaignManager(base_path=temp_dir)

    def test_save_and_load_campaign_data(self, campaign_manager, temp_dir):
        """Test saving and loading campaign data."""
        campaign_id = "test_campaign_001"

        # SimpleCampaignManager creates base_path/campaigns/{environment}/
        # Create campaign directory in the correct location
        campaign_path = campaign_manager.base_path / campaign_id
        campaign_path.mkdir(parents=True, exist_ok=True)

        # Create campaign data
        campaign_data = CampaignData(
            campaign_id=campaign_id,
            title="Test Adventure",
            description="A test campaign",
            game_style=GameStyle.BALANCED
        )

        # Save campaign data
        success = campaign_manager.save_campaign_data(campaign_id, campaign_data)
        assert success is True

        # Load campaign data
        loaded = campaign_manager.load_campaign(campaign_id)
        assert loaded is not None
        assert loaded.campaign_id == campaign_id
        assert loaded.title == "Test Adventure"
        assert loaded.description == "A test campaign"

    def test_list_campaigns(self, campaign_manager, temp_dir):
        """Test listing campaigns."""
        # Create multiple campaigns with directories
        # Note: SimpleCampaignManager only lists campaigns with IDs starting with 'campaign_'
        # Note: list_campaigns() only lists campaigns with chat history (logs/ directory exists)
        # Note: list_campaigns() parses campaign name from directory name (e.g., "campaign_001 - Title")
        for i in range(3):
            campaign_id = f"campaign_{i:03d}"
            campaign_title = f"Campaign {i}"
            # Create directory with name in format "campaign_XXX - Title"
            dir_name = f"{campaign_id} - {campaign_title}"
            campaign_path = campaign_manager.base_path / dir_name
            campaign_path.mkdir(parents=True, exist_ok=True)

            campaign_data = CampaignData(
                campaign_id=campaign_id,
                title=f"Campaign {i}",
                description=f"Test campaign {i}"
            )
            campaign_manager.save_campaign_data(campaign_id, campaign_data)

            # Save chat history to create logs/ directory (required for list_campaigns to find it)
            campaign_manager.save_campaign(campaign_id, [
                {"role": "user", "content": f"Test message for campaign {i}"}
            ])

        # List campaigns
        result = campaign_manager.list_campaigns()

        assert "campaigns" in result
        assert len(result["campaigns"]) >= 3

        # Check campaign IDs are present (SimpleCampaignManager uses session_id as name when no metadata)
        ids = [c["id"] for c in result["campaigns"]]
        assert "campaign_000" in ids
        assert "campaign_001" in ids
        assert "campaign_002" in ids

    def test_save_campaign_history(self, campaign_manager):
        """Test saving campaign chat history."""
        campaign_id = "test_history"

        # Create initial campaign data
        campaign_data = CampaignData(
            campaign_id=campaign_id,
            title="History Test"
        )
        campaign_manager.save_campaign_data(campaign_id, campaign_data)

        # Save chat history
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Welcome to the adventure!"}
        ]

        success = campaign_manager.save_campaign(campaign_id, messages)
        assert success is True

        # Load history
        loaded_history = campaign_manager.load_campaign_history(campaign_id)
        assert len(loaded_history) >= 2
        assert any(msg.get("content") == "Hello" for msg in loaded_history)

    def test_campaign_directory_structure(self, campaign_manager, temp_dir):
        """Test that campaign creates proper directory structure."""
        campaign_id = "test_structure"

        # Create campaign directory in correct location
        campaign_path = campaign_manager.base_path / campaign_id
        campaign_path.mkdir(parents=True, exist_ok=True)

        campaign_data = CampaignData(
            campaign_id=campaign_id,
            title="Structure Test"
        )
        campaign_manager.save_campaign_data(campaign_id, campaign_data)

        # Verify directory exists
        assert campaign_path.exists()
        assert campaign_path.is_dir()

        # Verify campaign_data.json exists in data directory
        data_path = campaign_path / "data"
        campaign_file = data_path / "campaign_data.json"
        assert campaign_file.exists()

    def test_load_nonexistent_campaign(self, campaign_manager):
        """Test loading a campaign that doesn't exist creates a fallback campaign."""
        loaded = campaign_manager.load_campaign("nonexistent_campaign")
        # SimpleCampaignManager now creates fallback campaigns instead of returning None
        assert loaded is not None
        assert loaded.campaign_id == "nonexistent_campaign"
        assert loaded.title == "nonexistent_campaign"  # Uses campaign_id as fallback title

    def test_list_campaigns_with_sorting(self, campaign_manager):
        """Test listing campaigns with sorting options."""
        # Create campaigns (must use 'campaign_' prefix to be listed)
        for i in range(2):
            campaign_id = f"campaign_sorted_{i:02d}"
            campaign_data = CampaignData(
                campaign_id=campaign_id,
                title=f"Sorted {i}"
            )
            campaign_manager.save_campaign_data(campaign_id, campaign_data)

        # List with ascending sort
        result_asc = campaign_manager.list_campaigns(ascending=True)
        assert "campaigns" in result_asc

        # List with descending sort
        result_desc = campaign_manager.list_campaigns(ascending=False)
        assert "campaigns" in result_desc

    def test_campaign_id_normalization_in_mark_loaded(self, campaign_manager):
        """Test that mark_campaign_loaded normalizes campaign IDs with pretty names."""
        # Create a campaign
        campaign_id = "campaign_999"
        campaign_path = campaign_manager.base_path / campaign_id
        campaign_path.mkdir(parents=True, exist_ok=True)

        campaign_data = CampaignData(
            campaign_id=campaign_id,
            title="Normalization Test"
        )
        campaign_manager.save_campaign_data(campaign_id, campaign_data)

        # Mark loaded with pretty name (as might come from directory name)
        pretty_name = "campaign_999 - Normalization Test"
        campaign_manager.mark_campaign_loaded(pretty_name)

        # Verify metadata was updated with normalized ID
        # The metadata should be stored under the bare campaign_999, not the pretty name
        metadata = campaign_manager.storage.load_metadata(campaign_id)
        assert metadata is not None
        assert "last_loaded_at" in metadata
        assert "updated_at" in metadata
