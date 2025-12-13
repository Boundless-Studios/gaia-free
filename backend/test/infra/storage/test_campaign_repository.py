"""Tests for CampaignRepository turn event persistence.

Validates that:
1. Campaigns are auto-created when first turn event is added
2. Turn input events are persisted correctly
3. Assistant response events are persisted correctly
4. Turn events can be retrieved for a campaign
5. Turn counter service integrates with repository
"""

import uuid
import pytest
from datetime import datetime, timezone
from typing import Dict, Any

from gaia.infra.storage.campaign_repository import CampaignRepository
from gaia.services.turn_counter_service import TurnCounterService
from gaia.models.turn_event_db import TurnEventType, TurnEventRole


class TestCampaignRepositoryTurnEvents:
    """Test suite for CampaignRepository turn event operations."""

    @pytest.fixture
    def repository(self):
        """Create a CampaignRepository instance."""
        return CampaignRepository()

    @pytest.fixture
    def turn_counter(self):
        """Create a TurnCounterService instance."""
        return TurnCounterService()

    @pytest.fixture
    def test_campaign_id(self):
        """Generate a unique test campaign ID."""
        return f"test_campaign_{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def sample_turn_input(self) -> Dict[str, Any]:
        """Create sample turn input data."""
        return {
            "active_player": {
                "character_id": "char_001",
                "character_name": "Thorin",
                "text": "I attack the goblin!",
                "input_type": "action",
            },
            "observer_inputs": [
                {
                    "character_id": "char_002",
                    "character_name": "Elara",
                    "text": "I cast healing word on Thorin",
                    "input_type": "action",
                }
            ],
            "dm_input": {
                "text": "The goblin snarls in response",
            },
            "combined_prompt": "Thorin: I attack the goblin!\nElara: I cast healing word on Thorin\nDM: The goblin snarls in response",
        }

    @pytest.fixture
    def sample_assistant_response(self) -> Dict[str, Any]:
        """Create sample assistant response data."""
        return {
            "narrative": "Thorin's axe cleaves through the air, striking the goblin.",
            "dice_rolls": [{"roll": "1d20+5", "result": 18, "type": "attack"}],
            "effects": ["goblin takes 8 damage"],
        }

    @pytest.mark.asyncio
    async def test_campaign_auto_created_on_first_event(
        self, repository, test_campaign_id, sample_turn_input
    ):
        """Test that campaign is auto-created when first turn event is added."""
        # Verify campaign doesn't exist yet
        campaign = await repository.get_campaign_by_external_id(test_campaign_id)
        assert campaign is None

        # Add turn event - should auto-create campaign
        event = await repository.add_turn_input_event(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            active_player=sample_turn_input["active_player"],
            observer_inputs=sample_turn_input["observer_inputs"],
            dm_input=sample_turn_input["dm_input"],
            combined_prompt=sample_turn_input["combined_prompt"],
        )

        assert event is not None
        assert event.turn_number == 1
        assert event.event_index == 0
        assert event.type == TurnEventType.TURN_INPUT

        # Verify campaign was created
        campaign = await repository.get_campaign_by_external_id(test_campaign_id)
        assert campaign is not None
        assert campaign.external_campaign_id == test_campaign_id

        # Cleanup
        await self._cleanup_campaign(repository, test_campaign_id)

    @pytest.mark.asyncio
    async def test_turn_input_event_content_persisted(
        self, repository, test_campaign_id, sample_turn_input
    ):
        """Test that turn input content is correctly persisted."""
        # Add turn input event
        event = await repository.add_turn_input_event(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            active_player=sample_turn_input["active_player"],
            observer_inputs=sample_turn_input["observer_inputs"],
            dm_input=sample_turn_input["dm_input"],
            combined_prompt=sample_turn_input["combined_prompt"],
        )

        assert event is not None
        assert event.content is not None

        # Verify content structure
        content = event.content
        assert content["active_player"]["character_name"] == "Thorin"
        assert len(content["observer_inputs"]) == 1
        assert content["observer_inputs"][0]["character_name"] == "Elara"
        assert content["dm_input"]["text"] == "The goblin snarls in response"
        assert "combined_prompt" in content

        # Cleanup
        await self._cleanup_campaign(repository, test_campaign_id)

    @pytest.mark.asyncio
    async def test_assistant_response_event_persisted(
        self, repository, test_campaign_id, sample_turn_input, sample_assistant_response
    ):
        """Test that assistant response events are correctly persisted."""
        # First add turn input
        await repository.add_turn_input_event(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            active_player=sample_turn_input["active_player"],
            observer_inputs=sample_turn_input["observer_inputs"],
            dm_input=sample_turn_input["dm_input"],
            combined_prompt=sample_turn_input["combined_prompt"],
        )

        # Add assistant response
        event = await repository.add_assistant_response_event(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            content=sample_assistant_response,
            event_index=1,
        )

        assert event is not None
        assert event.turn_number == 1
        assert event.event_index == 1
        assert event.type == TurnEventType.ASSISTANT
        assert event.role == TurnEventRole.ASSISTANT
        assert event.content["narrative"] == sample_assistant_response["narrative"]

        # Cleanup
        await self._cleanup_campaign(repository, test_campaign_id)

    @pytest.mark.asyncio
    async def test_get_turn_events_returns_ordered_events(
        self, repository, test_campaign_id, sample_turn_input, sample_assistant_response
    ):
        """Test that get_turn_events returns events in correct order."""
        # Add turn 1 events
        await repository.add_turn_input_event(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            active_player=sample_turn_input["active_player"],
            observer_inputs=[],
            dm_input=None,
            combined_prompt="Turn 1 input",
        )
        await repository.add_assistant_response_event(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            content={"narrative": "Turn 1 response"},
            event_index=1,
        )

        # Add turn 2 events
        await repository.add_turn_input_event(
            external_campaign_id=test_campaign_id,
            turn_number=2,
            active_player=sample_turn_input["active_player"],
            observer_inputs=[],
            dm_input=None,
            combined_prompt="Turn 2 input",
        )
        await repository.add_assistant_response_event(
            external_campaign_id=test_campaign_id,
            turn_number=2,
            content={"narrative": "Turn 2 response"},
            event_index=1,
        )

        # Retrieve events
        events = await repository.get_turn_events(
            external_campaign_id=test_campaign_id, limit=100
        )

        assert len(events) == 4

        # Verify order: turn 1 input, turn 1 response, turn 2 input, turn 2 response
        assert events[0].turn_number == 1
        assert events[0].event_index == 0
        assert events[0].type == TurnEventType.TURN_INPUT

        assert events[1].turn_number == 1
        assert events[1].event_index == 1
        assert events[1].type == TurnEventType.ASSISTANT

        assert events[2].turn_number == 2
        assert events[2].event_index == 0

        assert events[3].turn_number == 2
        assert events[3].event_index == 1

        # Cleanup
        await self._cleanup_campaign(repository, test_campaign_id)

    @pytest.mark.asyncio
    async def test_get_turn_events_filter_by_turn_number(
        self, repository, test_campaign_id, sample_turn_input
    ):
        """Test filtering turn events by turn number."""
        # Add events for multiple turns
        for turn_num in [1, 2, 3]:
            await repository.add_turn_input_event(
                external_campaign_id=test_campaign_id,
                turn_number=turn_num,
                active_player=sample_turn_input["active_player"],
                observer_inputs=[],
                dm_input=None,
                combined_prompt=f"Turn {turn_num} input",
            )

        # Get only turn 2 events
        events = await repository.get_turn_events(
            external_campaign_id=test_campaign_id,
            turn_number=2,
        )

        assert len(events) == 1
        assert events[0].turn_number == 2

        # Cleanup
        await self._cleanup_campaign(repository, test_campaign_id)

    @pytest.mark.asyncio
    async def test_get_turn_events_empty_campaign(self, repository):
        """Test get_turn_events returns empty list for non-existent campaign."""
        events = await repository.get_turn_events(
            external_campaign_id="non_existent_campaign_12345",
        )
        assert events == []

    @pytest.mark.asyncio
    async def test_campaign_state_tracks_current_turn(
        self, repository, test_campaign_id
    ):
        """Test that campaign state tracks current turn number."""
        # Create campaign
        await repository.get_or_create_campaign(
            external_campaign_id=test_campaign_id,
            environment="dev",
        )

        # Use get_campaign_state which properly loads state
        state = await repository.get_campaign_state(test_campaign_id)
        assert state is not None
        assert state.current_turn == 0

        # Start turn 1
        result = await repository.start_turn(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            input_payload={"test": "data"},
        )
        assert result is True

        # Verify state updated
        state = await repository.get_campaign_state(test_campaign_id)
        assert state.current_turn == 1
        assert state.active_turn["is_processing"] is True

        # Complete turn 1
        result = await repository.complete_turn(
            external_campaign_id=test_campaign_id,
            turn_number=1,
        )
        assert result is True

        # Verify state updated
        state = await repository.get_campaign_state(test_campaign_id)
        assert state.active_turn["is_processing"] is False

        # Cleanup
        await self._cleanup_campaign(repository, test_campaign_id)

    @pytest.mark.asyncio
    async def test_turn_counter_service_integration(
        self, repository, turn_counter, test_campaign_id, sample_turn_input
    ):
        """Test TurnCounterService integration with repository."""
        # Initialize from DB (should create campaign)
        turn = await turn_counter.initialize_from_db(test_campaign_id, "dev")
        assert turn == 0

        # Increment turn
        new_turn = await turn_counter.increment_turn(
            campaign_id=test_campaign_id,
            input_payload={"test": "data"},
        )
        assert new_turn == 1

        # Add turn input event
        await turn_counter.add_turn_input_event(
            campaign_id=test_campaign_id,
            turn_number=1,
            active_player=sample_turn_input["active_player"],
            observer_inputs=sample_turn_input["observer_inputs"],
            dm_input=sample_turn_input["dm_input"],
            combined_prompt=sample_turn_input["combined_prompt"],
        )

        # Verify event was persisted
        events = await repository.get_turn_events(
            external_campaign_id=test_campaign_id,
            turn_number=1,
        )
        assert len(events) == 1
        assert events[0].type == TurnEventType.TURN_INPUT

        # Add assistant response
        await turn_counter.add_assistant_response_event(
            campaign_id=test_campaign_id,
            turn_number=1,
            content={"narrative": "Test response"},
        )

        # Complete turn
        await turn_counter.complete_turn(test_campaign_id, 1)

        # Verify all events
        events = await repository.get_turn_events(
            external_campaign_id=test_campaign_id,
        )
        assert len(events) == 2

        # Cleanup
        await self._cleanup_campaign(repository, test_campaign_id)

    @pytest.mark.asyncio
    async def test_get_next_event_index(self, repository, test_campaign_id):
        """Test get_next_event_index returns correct indices."""
        # Create campaign and add first event
        await repository.add_turn_input_event(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            active_player=None,
            observer_inputs=[],
            dm_input=None,
            combined_prompt="Test",
        )

        # Next index should be 1
        next_index = await repository.get_next_event_index(test_campaign_id, 1)
        assert next_index == 1

        # Add another event
        await repository.add_assistant_response_event(
            external_campaign_id=test_campaign_id,
            turn_number=1,
            content={"test": "response"},
            event_index=1,
        )

        # Next index should be 2
        next_index = await repository.get_next_event_index(test_campaign_id, 1)
        assert next_index == 2

        # New turn should start at 0
        next_index = await repository.get_next_event_index(test_campaign_id, 2)
        assert next_index == 0

        # Cleanup
        await self._cleanup_campaign(repository, test_campaign_id)

    async def _cleanup_campaign(self, repository: CampaignRepository, campaign_id: str):
        """Helper to cleanup test campaign and its events."""
        try:
            from gaia.models.campaign_db import Campaign
            from gaia.models.turn_event_db import TurnEvent
            from sqlalchemy import delete

            async with repository.db_manager.get_async_session() as session:
                # Get campaign UUID
                campaign = await repository.get_campaign_by_external_id(campaign_id)
                if campaign:
                    # Delete turn events first (FK constraint)
                    await session.execute(
                        delete(TurnEvent).where(
                            TurnEvent.campaign_id == campaign.campaign_id
                        )
                    )
                    # Delete campaign (cascades to state)
                    await session.execute(
                        delete(Campaign).where(
                            Campaign.campaign_id == campaign.campaign_id
                        )
                    )
                    await session.commit()
        except Exception:
            pass  # Ignore cleanup errors


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
