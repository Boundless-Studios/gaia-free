import pytest
from unittest.mock import MagicMock, patch
from gaia_private.session.room_service import RoomService
from gaia_private.session.session_models import RoomSeat, CampaignSession
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def room_service(mock_db):
    return RoomService(mock_db)

@patch("gaia.mechanics.campaign.simple_campaign_manager.SimpleCampaignManager.get_character_manager")
def test_get_character_manager_uses_singleton(mock_get_manager, room_service):
    """Test that _get_character_manager uses SimpleCampaignManager singleton."""
    campaign_id = "campaign_123"
    mock_manager = MagicMock()
    mock_get_manager.return_value = mock_manager
    
    # Call the method
    result = room_service._get_character_manager(campaign_id)
    
    # Verify it calls the singleton method
    mock_get_manager.assert_called_with(campaign_id)
    assert result == mock_manager

@patch("gaia.mechanics.campaign.simple_campaign_manager.SimpleCampaignManager.get_character_manager")
def test_assign_character_uses_singleton(mock_get_manager, room_service):
    """Test that assign_character_to_seat uses the singleton manager."""
    campaign_id = "campaign_123"
    seat_id = "00000000-0000-0000-0000-000000000001"
    user_id = "user_123"
    
    # Mock DB setup
    mock_seat = MagicMock(spec=RoomSeat)
    mock_seat.seat_id = seat_id
    mock_seat.campaign_id = campaign_id
    mock_seat.owner_user_id = user_id
    mock_seat.character_id = None
    mock_seat.slot_index = 0
    
    mock_campaign = MagicMock(spec=CampaignSession)
    mock_campaign.owner_user_id = user_id # Making user DM/owner for permission
    
    room_service.db.get.side_effect = [mock_seat, mock_campaign]
    
    # Mock CharacterManager
    mock_char_manager = MagicMock()
    mock_character = MagicMock()
    mock_character.character_id = "char_123"
    mock_char_manager.create_character_from_simple.return_value = mock_character
    mock_get_manager.return_value = mock_char_manager
    
    # Execute
    room_service.assign_character_to_seat(campaign_id, seat_id, {"name": "Hero"}, user_id)
    
    # Verify
    mock_get_manager.assert_called_with(campaign_id)
    mock_char_manager.create_character_from_simple.assert_called()
