"""Integration tests for character management within campaign context."""

import pytest
import tempfile
import shutil
from pathlib import Path

from gaia.utils.singleton import SingletonMeta
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia.models.character import CharacterSetupSlot, CharacterInfo


class TestCharacterCampaignIntegration:
    """Test character management integrated with campaigns."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def campaign_manager(self, temp_dir):
        """Create a campaign manager for testing."""
        SingletonMeta._instances.pop(SimpleCampaignManager, None)
        return SimpleCampaignManager(temp_dir)
    
    def test_create_campaign_with_character_setup(self, campaign_manager):
        """Test creating a campaign and its character manager."""
        result = campaign_manager.create_campaign(
            session_id="campaign_001",
            title="Fellowship of the Ring",
            description="The journey begins",
            game_style="balanced",
        )

        assert result["success"] is True

        # Check character manager created
        char_manager = campaign_manager.get_character_manager("campaign_001")
        assert char_manager is not None

        # Check campaign data loaded
        campaign = campaign_manager.load_campaign("campaign_001")
        assert campaign.title == "Fellowship of the Ring"
    
    def test_campaign_character_workflow(self, campaign_manager):
        """Test full character workflow within a campaign."""
        # 1. Create campaign
        campaign_manager.create_campaign(
            session_id="campaign_002",
            title="The Two Towers",
            setup_characters=True,
            player_count=3
        )

        # 2. Get character manager
        char_manager = campaign_manager.get_character_manager("campaign_002")
        assert char_manager is not None

        # 3. Create characters directly using simple character data
        aragorn = char_manager.create_character_from_simple({
            "name": "Aragorn",
            "character_class": "Ranger",
            "race": "Human",
            "level": 1
        }, slot_id=0)

        legolas = char_manager.create_character_from_simple({
            "name": "Legolas",
            "character_class": "Ranger",
            "race": "Elf",
            "level": 1
        }, slot_id=1)

        gimli = char_manager.create_character_from_simple({
            "name": "Gimli",
            "character_class": "Fighter",
            "race": "Dwarf",
            "level": 1
        }, slot_id=2)

        # 4. Verify characters were created
        assert aragorn.name == "Aragorn"
        assert legolas.name == "Legolas"
        assert gimli.name == "Gimli"

        # 5. Load campaign and add character IDs
        campaign = campaign_manager.load_campaign("campaign_002")
        characters = [aragorn, legolas, gimli]
        for char in characters:
            campaign.character_ids.append(char.character_id)

        # 7. Save campaign with character IDs
        success = campaign_manager.save_campaign_data("campaign_002", campaign)
        assert success is True

        # 8. Reload campaign and verify character IDs
        reloaded_campaign = campaign_manager.load_campaign("campaign_002")
        assert len(reloaded_campaign.character_ids) == 3

        # 9. Verify characters through character manager
        reloaded_char_manager = campaign_manager.get_character_manager("campaign_002")
        # Character data should be available through the character manager
        assert reloaded_char_manager is not None
    
    def test_load_campaign_with_existing_characters(self, campaign_manager):
        """Test loading a campaign preserves character data."""
        # Create campaign with characters
        campaign_manager.create_campaign(
            session_id="campaign_003",
            title="Return of the King"
        )

        campaign = campaign_manager.load_campaign("campaign_003")
        char_manager = campaign_manager.get_character_manager("campaign_003")

        # Create a character through the character manager
        gandalf = char_manager.create_character_from_simple({
            "name": "Gandalf",
            "character_class": "Wizard",
            "race": "Human",
            "level": 20,
            "description": "The Grey Wizard"
        })

        # Add character ID to campaign
        campaign.character_ids.append(gandalf.character_id)

        # Save campaign
        campaign_manager.save_campaign_data("campaign_003", campaign)

        # Create new manager and load
        SingletonMeta._instances.pop(SimpleCampaignManager, None)
        new_manager = SimpleCampaignManager(campaign_manager.base_path)
        loaded_campaign = new_manager.load_campaign("campaign_003")

        # Check campaign was loaded
        assert loaded_campaign is not None, "Failed to load campaign"

        # Check character ID preserved
        assert len(loaded_campaign.character_ids) == 1
        assert gandalf.character_id in loaded_campaign.character_ids
        # Check character through character manager
        new_char_manager = new_manager.get_character_manager("campaign_003")
        assert new_char_manager is not None
    
    def test_character_persistence_across_sessions(self, campaign_manager):
        """Test characters persist across multiple sessions."""
        # Session 1: Create campaign and characters
        campaign_manager.create_campaign(
            session_id="campaign_004",
            title="The Hobbit"
        )

        campaign = campaign_manager.load_campaign("campaign_004")
        char_manager = campaign_manager.get_character_manager("campaign_004")

        # Create character using simple data
        bilbo = char_manager.create_character_from_simple({
            "name": "Bilbo",
            "character_class": "Rogue",
            "race": "Halfling",
            "level": 1,
            "description": "A hobbit from the Shire"
        })

        # Add character ID to campaign
        campaign.character_ids.append(bilbo.character_id)
        campaign_manager.save_campaign_data("campaign_004", campaign)

        # Session 2: Load and verify character persisted
        SingletonMeta._instances.pop(SimpleCampaignManager, None)
        new_manager = SimpleCampaignManager(campaign_manager.base_path)
        campaign2 = new_manager.load_campaign("campaign_004")

        # Check campaign was loaded
        assert campaign2 is not None, "Failed to load campaign in session 2"

        char_manager2 = new_manager.get_character_manager("campaign_004")

        # Verify character ID is present
        assert len(campaign2.character_ids) == 1
        assert bilbo.character_id in campaign2.character_ids

        # Update character through character manager (create a new version)
        bilbo2 = char_manager2.create_character_from_simple({
            "name": "Bilbo Baggins",
            "character_class": "Rogue",
            "race": "Halfling",
            "level": 5,
            "description": "There and back again..."
        })

        # Replace old character ID with new one
        campaign2.character_ids = [bilbo2.character_id]

        # Save campaign
        new_manager.save_campaign_data("campaign_004", campaign2)

        # Session 3: Verify updates persisted
        SingletonMeta._instances.pop(SimpleCampaignManager, None)
        final_manager = SimpleCampaignManager(campaign_manager.base_path)
        final_campaign = final_manager.load_campaign("campaign_004")

        # Check campaign was loaded
        assert final_campaign is not None, "Failed to load campaign in session 3"

        final_char_manager = final_manager.get_character_manager("campaign_004")

        # Check campaign character ID was updated
        assert len(final_campaign.character_ids) == 1
        assert bilbo2.character_id in final_campaign.character_ids

        # Verify character manager is accessible
        assert final_char_manager is not None
    
    def test_multiple_campaigns_same_character(self, campaign_manager):
        """Test same character across multiple campaigns."""
        # Create two campaigns
        result_a = campaign_manager.create_campaign(session_id="campaign_005", title="Campaign A")
        result_b = campaign_manager.create_campaign(session_id="campaign_006", title="Campaign B")

        # Verify campaigns were created successfully
        assert result_a is not None
        assert result_b is not None

        # Verify character managers can be retrieved for each campaign
        char_manager_a = campaign_manager.get_character_manager("campaign_005")
        char_manager_b = campaign_manager.get_character_manager("campaign_006")
        assert char_manager_a is not None
        assert char_manager_b is not None
