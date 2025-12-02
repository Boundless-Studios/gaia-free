"""Unit tests for the turn mechanism implementation."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from gaia.models.turn import (
    Turn, TurnAction, TurnResult, 
    TurnType, TurnStatus, ActionType
)
from gaia_private.session.turn_manager import TurnManager
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia_private.agents.dungeon_master import DungeonMasterRunContext


class TestTurnModel:
    """Test the Turn data model."""
    
    def test_turn_creation(self):
        """Test creating a Turn object."""
        turn = Turn(
            turn_id="test_001",
            campaign_id="campaign_1",
            turn_number=1,
            character_id="player_1",
            character_name="user_1",
            turn_type=TurnType.PLAYER,
            status=TurnStatus.ACTIVE
        )

        assert turn.turn_id == "test_001"
        assert turn.campaign_id == "campaign_1"
        assert turn.turn_number == 1
        assert turn.character_id == "player_1"
        assert turn.character_name == "user_1"
        assert turn.turn_type == TurnType.PLAYER
        assert turn.status == TurnStatus.ACTIVE
        assert turn.available_actions == []
        assert turn.selected_action is None
    
    def test_turn_to_dict(self):
        """Test converting Turn to dictionary."""
        action = TurnAction(
            action_id="attack",
            action_type=ActionType.ATTACK,
            name="Attack",
            description="Attack an enemy"
        )
        
        turn = Turn(
            turn_id="test_001",
            campaign_id="campaign_1",
            turn_number=1,
            character_id="player_1",
            available_actions=[action]
        )
        
        turn_dict = turn.to_dict()

        assert turn_dict["turn_id"] == "test_001"
        assert turn_dict["campaign_id"] == "campaign_1"
        assert turn_dict["turn_number"] == 1
        assert turn_dict["character_id"] == "player_1"
        assert turn_dict["turn_type"] == "player"
        assert turn_dict["status"] in ["active", "completed"]
        assert len(turn_dict["available_actions"]) == 1
        assert turn_dict["available_actions"][0]["action_id"] == "attack"
    
    def test_turn_from_dict(self):
        """Test creating Turn from dictionary."""
        turn_dict = {
            "turn_id": "test_001",
            "campaign_id": "campaign_1",
            "turn_number": 1,
            "character_id": "player_1",
            "player_id": "user_1",
            "turn_type": "player",
            "status": "active",
            "available_actions": [
                {
                    "action_id": "examine"
                }
            ]
        }
        
        turn = Turn.from_dict(turn_dict)
        
        assert turn.turn_id == "test_001"
        assert turn.campaign_id == "campaign_1"
        assert turn.turn_number == 1
        assert turn.character_id == "player_1"
        assert turn.turn_type == TurnType.PLAYER
        assert turn.status == TurnStatus.ACTIVE
        assert turn.character_name == "user_1"
        assert len(turn.available_actions) == 1
        assert turn.available_actions[0].action_id == "examine"
    
    def test_turn_complete(self):
        """Test completing a turn."""
        turn = Turn(
            turn_id="test_001",
            campaign_id="campaign_1",
            turn_number=1,
            character_id="player_1",
            status=TurnStatus.ACTIVE
        )

        action_result = {"success": True, "damage": 10}
        turn.complete(action_result)

        assert turn.status == TurnStatus.COMPLETED
        assert turn.action_result == action_result


class TestTurnAction:
    """Test the TurnAction model."""
    
    def test_action_creation(self):
        """Test creating a TurnAction."""
        action = TurnAction(
            action_id="move",
            action_type=ActionType.MOVE,
            name="Move",
            description="Move to a new location",
            targets=["north", "south", "east", "west"]
        )
        
        assert action.action_id == "move"
        assert action.action_type == ActionType.MOVE
        assert action.name == "Move"
        assert action.description == "Move to a new location"
        assert action.targets == ["north", "south", "east", "west"]
    
    def test_action_to_dict(self):
        """Test converting TurnAction to dictionary."""
        action = TurnAction(
            action_id="dialog",
            action_type=ActionType.DIALOG,
            name="Speak",
            description="Talk to NPC"
        )
        
        action_dict = action.to_dict()

        assert action_dict["action_id"] == "dialog"
        assert action_dict["action_type"] == "dialog"
        assert action_dict["name"] == "Speak"
        assert action_dict["description"] == "Talk to NPC"
    
    def test_action_from_dict(self):
        """Test creating TurnAction from dictionary."""
        action_dict = {
            "action_id": "search"
        }

        action = TurnAction.from_dict(action_dict)

        assert action.action_id == "search"


class TestTurnManager:
    """Test the TurnManager class."""
    
    @pytest.fixture
    def mock_campaign_manager(self):
        """Create a mock campaign manager."""
        from gaia.models.campaign import CampaignData

        manager = Mock(spec=SimpleCampaignManager)
        manager.get_next_turn_number.return_value = 1
        manager.save_turn.return_value = True
        manager.get_current_turn.return_value = None
        manager.load_campaign_turns.return_value = []

        # Create a proper CampaignData object for turn order management
        campaign_data = CampaignData(
            campaign_id="test_campaign",
            turn_order=[],  # Empty initially, will be set by tests
            current_turn_index=0
        )
        manager.load_campaign.return_value = campaign_data
        manager.save_campaign_data.return_value = True

        return manager
    
    @pytest.fixture
    def turn_manager(self, mock_campaign_manager):
        """Create a TurnManager with mocked dependencies."""
        return TurnManager(campaign_manager=mock_campaign_manager)
    
    def test_create_turn(self, turn_manager, mock_campaign_manager):
        """Test creating a new turn."""
        campaign_id = "test_campaign"
        character_id = "test_character"
        character_name = "test_player"
        
        turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id=character_id,
            character_name=character_name
        )

        assert turn.campaign_id == campaign_id
        assert turn.character_id == character_id
        assert turn.character_name == character_name
        assert turn.turn_number == 1
        assert turn.turn_type == TurnType.PLAYER
        assert turn.status == TurnStatus.ACTIVE
        # Available actions are populated externally by combat_state_manager
        assert turn.available_actions == []

        # Check that campaign manager was called
        mock_campaign_manager.get_next_turn_number.assert_called_once_with(campaign_id)
    
    def test_create_turn_with_scene_context(self, turn_manager, mock_campaign_manager):
        """Test creating a turn with scene context."""
        scene_context = {
            "scene_id": "tavern_1",
            "scene_type": "social",
            "npcs": ["innkeeper", "patron"]
        }
        
        turn = turn_manager.create_turn(
            campaign_id="test_campaign",
            character_id="test_character",
            scene_context=scene_context
        )
        
        assert turn.scene_id == "tavern_1"
        assert turn.scene_type == "social"
        assert turn.context["npcs"] == ["innkeeper", "patron"]
        # Available actions are populated externally by combat_state_manager
        assert turn.available_actions == []
    
    def test_start_turn(self, turn_manager, mock_campaign_manager):
        """Test starting a turn - turns are already active on creation."""
        turn = Turn(
            turn_id="test_001",
            campaign_id="test_campaign",
            turn_number=1,
            character_id="test_character",
            status=TurnStatus.ACTIVE
        )

        started_turn = turn_manager.start_turn(turn)

        assert started_turn.status == TurnStatus.ACTIVE
        assert turn_manager.active_turns["test_campaign"] == started_turn
        mock_campaign_manager.save_turn.assert_called_once()
    
    # test_execute_action_* removed - action execution is now handled by combat_state_manager
    
    def test_complete_turn(self, turn_manager, mock_campaign_manager):
        """Test completing a turn."""
        turn = Turn(
            turn_id="test_001",
            campaign_id="test_campaign",
            turn_number=1,
            character_id="test_character",
            status=TurnStatus.ACTIVE
        )
        
        turn_manager.active_turns["test_campaign"] = turn
        
        completed_turn = turn_manager.complete_turn(turn)
        
        assert completed_turn.status == TurnStatus.COMPLETED
        assert "test_campaign" not in turn_manager.active_turns
        mock_campaign_manager.save_turn.assert_called_once()
    
    def test_get_current_turn_active(self, turn_manager):
        """Test getting current active turn."""
        turn = Turn(
            turn_id="test_001",
            campaign_id="test_campaign",
            turn_number=1,
            character_id="test_character",
            status=TurnStatus.ACTIVE
        )
        
        turn_manager.active_turns["test_campaign"] = turn
        
        current = turn_manager.get_current_turn("test_campaign")
        
        assert current == turn
    
    def test_get_current_turn_from_persistence(self, turn_manager, mock_campaign_manager):
        """Test getting current turn from persistence."""
        turn_data = {
            "turn_id": "test_001",
            "campaign_id": "test_campaign",
            "turn_number": 1,
            "character_id": "test_character",
            "status": "active",
            "turn_type": "player",
            "available_actions": []
        }
        
        mock_campaign_manager.get_current_turn.return_value = turn_data
        
        current = turn_manager.get_current_turn("test_campaign")
        
        assert current is not None
        assert current.turn_id == "test_001"
        assert current.status == TurnStatus.ACTIVE
        assert turn_manager.active_turns["test_campaign"] == current
    
    def test_get_turn_history(self, turn_manager, mock_campaign_manager):
        """Test getting turn history."""
        turn_data_list = [
            {
                "turn_id": f"turn_{i}",
                "campaign_id": "test_campaign",
                "turn_number": i,
                "character_id": "test_character",
                "status": "completed",
                "turn_type": "player",
                "available_actions": []
            }
            for i in range(1, 4)
        ]
        
        mock_campaign_manager.load_campaign_turns.return_value = turn_data_list
        
        history = turn_manager.get_turn_history("test_campaign", limit=5)
        
        assert len(history) == 3
        assert history[0].turn_number == 1
        assert history[1].turn_number == 2
        assert history[2].turn_number == 3
        
        mock_campaign_manager.load_campaign_turns.assert_called_once_with("test_campaign", 5)


# TestActionGeneration removed - action generation is now handled externally
# by combat_state_manager, not by TurnManager


class TestCampaignRunnerIntegration:
    """Test integration with CampaignRunner."""
    
    @pytest.mark.asyncio
    async def test_run_turn_creates_turn(self):
        """Test that run_turn creates and manages a turn."""
        from gaia_private.session.campaign_runner import CampaignRunner
        from gaia_private.session.history_manager import ConversationHistoryManager
        
        # Mock dependencies
        history_manager = Mock(spec=ConversationHistoryManager)
        history_manager.get_full_history.return_value = []
        history_manager.get_recent_history = Mock(return_value=[])
        history_manager.add_message = Mock()
        
        from gaia.models.campaign import CampaignData

        campaign_manager = Mock(spec=SimpleCampaignManager)
        campaign_manager.get_next_turn_number.return_value = 1
        campaign_manager.save_turn.return_value = True
        campaign_manager.get_current_turn.return_value = None
        campaign_manager.list_campaigns.return_value = {"campaigns": []}
        campaign_manager.get_campaign_data_path.return_value = None
        campaign_manager.load_campaign_history.return_value = []  # Empty history

        # Create a proper CampaignData object for turn order management
        campaign_data = CampaignData(
            campaign_id="test_campaign",
            turn_order=[],
            current_turn_index=0
        )
        campaign_manager.load_campaign.return_value = campaign_data
        campaign_manager.save_campaign_data.return_value = True
        
        game_config = {"setting": "fantasy"}
        
        # Create CampaignRunner
        runner = CampaignRunner(
            history_manager=history_manager,
            current_game_config=game_config,
            campaign_manager=campaign_manager
        )

        # Mock character manager to avoid iteration errors
        mock_character_manager = Mock()
        mock_character_manager.get_player_characters = Mock(return_value=[])
        mock_character_manager.get_character = Mock(return_value=None)  # Return None to avoid Mock iteration errors
        mock_character_manager.get_character_by_name = Mock(return_value=None)
        mock_character_manager.update_character_from_dm = Mock()
        mock_character_manager.persist_characters = Mock()
        runner._get_character_manager = Mock(return_value=mock_character_manager)

        # Mock the smart router and DM
        runner.smart_router = AsyncMock()
        runner.smart_router.analyze_and_route = AsyncMock(return_value=None)
        runner.smart_router.last_parallel_analysis = {
            "scene_type": {
                "primary_type": "exploration",
                "confidence": 0.9
            }
        }
        runner.smart_router.force_story_advancement = False
        
        # Mock the DM result as an agent Result object
        mock_dm_result = Mock()
        mock_dm_result.new_items = []  # Empty items (ResponseHandler expects this)
        mock_dm_result.final_output = {
            "player_response": "You see a dimly lit room.",
            "narrative": "The room is dusty.",
            "turn": "What do you do?",
            "status": "Exploring"
        }
        mock_run_context = DungeonMasterRunContext()
        mock_run_context.finalize(mock_dm_result.final_output)
        runner.run_dungeon_master = AsyncMock(return_value=(mock_dm_result, mock_run_context))
        
        # Run a turn
        result = await runner.run_turn(
            user_input="I enter the dungeon",
            campaign_id="test_campaign"
        )
        
        # Check that turn was created
        assert runner.turn_manager is not None

        # Check that structured_data includes turn_info
        assert "structured_data" in result
        assert "turn_info" in result["structured_data"]

        turn_info = result["structured_data"]["turn_info"]
        assert "turn_id" in turn_info
        assert "turn_number" in turn_info
        assert "available_actions" in turn_info
        # Available actions are populated externally by combat_state_manager

        # Verify turn was saved
        campaign_manager.save_turn.assert_called()


class TestAPIEndpoints:
    """Test the API endpoints for turn management."""
    
    @pytest.mark.asyncio
    async def test_get_current_turn_endpoint(self):
        """Test the get_current_turn API endpoint."""
        from gaia.api.routes.internal import get_current_turn
        
        # Mock the orchestrator
        with patch('gaia.api.routes.internal.get_orchestrator') as mock_get_orch:
            mock_orchestrator = Mock()
            mock_turn_manager = Mock()
            
            # Setup mock turn
            mock_turn = Turn(
                turn_id="test_001",
                campaign_id="test_campaign",
                turn_number=1,
                character_id="test_character",
                status=TurnStatus.ACTIVE
            )
            
            mock_turn_manager.get_current_turn.return_value = mock_turn
            mock_orchestrator.campaign_runner.turn_manager = mock_turn_manager
            mock_get_orch.return_value = mock_orchestrator
            
            # Call endpoint
            result = await get_current_turn(
                campaign_id="test_campaign",
                admin_user={"id": "admin"}
            )
            
            assert result["success"] is True
            assert "turn" in result
            assert result["turn"]["turn_id"] == "test_001"
    
    @pytest.mark.asyncio
    async def test_get_turn_history_endpoint(self):
        """Test the get_turn_history API endpoint."""
        from gaia.api.routes.internal import get_turn_history
        
        with patch('gaia.api.routes.internal.get_orchestrator') as mock_get_orch:
            mock_orchestrator = Mock()
            mock_turn_manager = Mock()
            
            # Setup mock turns
            mock_turns = [
                Turn(
                    turn_id=f"turn_{i}",
                    campaign_id="test_campaign",
                    turn_number=i,
                    character_id="test_character",
                    status=TurnStatus.COMPLETED
                )
                for i in range(1, 4)
            ]
            
            mock_turn_manager.get_turn_history.return_value = mock_turns
            mock_orchestrator.campaign_runner.turn_manager = mock_turn_manager
            mock_get_orch.return_value = mock_orchestrator
            
            # Call endpoint
            result = await get_turn_history(
                campaign_id="test_campaign",
                limit=10,
                admin_user={"id": "admin"}
            )
            
            assert result["success"] is True
            assert "turns" in result
            assert len(result["turns"]) == 3
            assert result["total_count"] == 3
    
    @pytest.mark.asyncio
    async def test_execute_turn_action_endpoint(self):
        """Test the execute_turn_action API endpoint."""
        from gaia.api.routes.internal import execute_turn_action, ExecuteActionRequest
        
        with patch('gaia.api.routes.internal.get_orchestrator') as mock_get_orch:
            mock_orchestrator = Mock()
            mock_turn_manager = Mock()
            
            # Setup mock turn and action
            mock_action = TurnAction(
                action_id="examine",
                action_type=ActionType.EXAMINE,
                name="Examine",
                description="Look closely"
            )
            
            mock_turn = Turn(
                turn_id="test_001",
                campaign_id="test_campaign",
                turn_number=1,
                character_id="test_character",
                status=TurnStatus.ACTIVE,
                available_actions=[mock_action]
            )
            
            mock_result = TurnResult(
                turn=mock_turn,
                success=True,
                message="You examine the door",
                state_changes={}
            )
            
            mock_turn_manager.get_current_turn.return_value = mock_turn
            mock_turn_manager.execute_action.return_value = mock_result
            mock_turn_manager.complete_turn.return_value = mock_turn
            mock_orchestrator.campaign_runner.turn_manager = mock_turn_manager
            mock_get_orch.return_value = mock_orchestrator
            
            # Call endpoint
            request = ExecuteActionRequest(
                action_id="examine",
                parameters={"target": "door"}
            )
            
            result = await execute_turn_action(
                campaign_id="test_campaign",
                request=request,
                admin_user={"id": "admin"}
            )
            
            assert result["success"] is True
            assert result["turn_id"] == "test_001"
            assert result["message"] == "You examine the door"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
