"""Tests for character assignment to seats during campaign initialization.

These tests verify that campaign_service.initialize_campaign correctly assigns
pre-created characters to room seats in the database.
"""

import uuid
from uuid import uuid4

import pytest
from sqlalchemy import select

from db.src.connection import db_manager
from gaia_private.session.session_models import CampaignSession, RoomSeat
from gaia.api.routes.campaigns import CampaignService, CampaignInitializeRequest, CharacterSlotRequest

# Import test helpers
from test.room.conftest import (
    create_test_campaign,
    cleanup_campaign,
)


@pytest.fixture
def campaign_service():
    """Create a campaign service instance for testing."""
    from gaia_private.orchestration.orchestrator import Orchestrator
    orchestrator = Orchestrator()
    service = CampaignService(orchestrator)
    return service


@pytest.fixture
def test_dm_id():
    """DM user ID for testing."""
    return f"dm-{uuid4().hex[:8]}"


# ============================================================================
# Integration Tests - Call initialize_campaign and verify DB
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_campaign_assigns_characters_to_seats(campaign_service, test_dm_id):
    """Test: initialize_campaign assigns characters to seats by slot_id in the DATABASE."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign with room structure
        create_test_campaign(campaign_id, test_dm_id, max_seats=2)

        # Verify seats start empty
        with db_manager.get_sync_session() as session:
            stmt = select(RoomSeat).where(
                RoomSeat.campaign_id == campaign_id,
                RoomSeat.seat_type == 'player'
            ).order_by(RoomSeat.slot_index)
            seats_before = list(session.execute(stmt).scalars().all())

            assert len(seats_before) == 2, "Should have 2 player seats"
            assert seats_before[0].slot_index == 0, "First seat should be slot 0"
            assert seats_before[1].slot_index == 1, "Second seat should be slot 1"
            assert all(s.character_id is None for s in seats_before), "Seats should start empty"

        # Initialize campaign with 2 characters in explicit slots
        character_slots = [
            CharacterSlotRequest(
                slot_id=0,  # Explicitly slot 0
                use_pregenerated=False,
                character_data={
                    "name": "Warrior Zero",
                    "character_class": "Fighter",
                    "race": "Human",
                    "level": 1,
                    "description": "Should go to slot 0",
                    "backstory": "Slot zero fighter",
                    "gender": "male",
                    "facial_expression": "determined",
                    "build": "muscular"
                }
            ),
            CharacterSlotRequest(
                slot_id=1,  # Explicitly slot 1
                use_pregenerated=False,
                character_data={
                    "name": "Wizard One",
                    "character_class": "Wizard",
                    "race": "Elf",
                    "level": 1,
                    "description": "Should go to slot 1",
                    "backstory": "Slot one wizard",
                    "gender": "female",
                    "facial_expression": "wise",
                    "build": "slender"
                }
            )
        ]

        init_request = CampaignInitializeRequest(
            campaign_id=campaign_id,
            campaign_info={
                "title": "Test Campaign",
                "description": "Testing character-to-seat mapping",
                "setting": "Fantasy",
                "theme": "Adventure"
            },
            use_pregenerated_campaign=False,
            character_slots=character_slots
        )

        # Call initialize_campaign - this should assign characters to seats
        result = await campaign_service.initialize_campaign(init_request)
        assert result.get("success"), "Campaign initialization should succeed"

        # CRITICAL: Verify characters are assigned to seats IN THE DATABASE
        with db_manager.get_sync_session() as session:
            stmt = select(RoomSeat).where(
                RoomSeat.campaign_id == campaign_id,
                RoomSeat.seat_type == 'player'
            ).order_by(RoomSeat.slot_index)
            seats_after = list(session.execute(stmt).scalars().all())

            # Verify both seats have characters
            assert len(seats_after) == 2, "Should still have 2 player seats"

            # CRITICAL ASSERTIONS: Check database has character_id
            assert seats_after[0].character_id is not None, \
                f"Slot 0 (slot_index={seats_after[0].slot_index}) should have character_id in DB"
            assert seats_after[1].character_id is not None, \
                f"Slot 1 (slot_index={seats_after[1].slot_index}) should have character_id in DB"

            # Verify they're different characters
            assert seats_after[0].character_id != seats_after[1].character_id, \
                "Each seat should have a different character"

            print(f"✓ Slot 0 has character: {seats_after[0].character_id}")
            print(f"✓ Slot 1 has character: {seats_after[1].character_id}")

    finally:
        cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_initialize_campaign_empty_slots_leave_seats_empty(campaign_service, test_dm_id):
    """Test: initialize_campaign with no characters leaves seats empty in DATABASE."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        create_test_campaign(campaign_id, test_dm_id, max_seats=2)

        # Initialize with NO characters
        init_request = CampaignInitializeRequest(
            campaign_id=campaign_id,
            campaign_info={
                "title": "Empty Campaign",
                "description": "No pre-created characters",
                "setting": "Fantasy",
                "theme": "Adventure"
            },
            use_pregenerated_campaign=False,
            character_slots=[]  # Empty!
        )

        result = await campaign_service.initialize_campaign(init_request)
        assert result.get("success"), "Campaign initialization should succeed"

        # Verify seats remain empty in DATABASE
        with db_manager.get_sync_session() as session:
            stmt = select(RoomSeat).where(
                RoomSeat.campaign_id == campaign_id,
                RoomSeat.seat_type == 'player'
            )
            seats = list(session.execute(stmt).scalars().all())

            assert len(seats) == 2, "Should have 2 player seats"
            assert all(s.character_id is None for s in seats), \
                "All seats should remain empty in DB when no characters created"

    finally:
        cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_initialize_campaign_partial_assignment(campaign_service, test_dm_id):
    """Test: initialize_campaign with some characters fills only those slots in DATABASE."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        create_test_campaign(campaign_id, test_dm_id, max_seats=3)

        # Initialize with only slot 1 character (skip slot 0 and 2)
        character_slots = [
            CharacterSlotRequest(
                slot_id=1,  # Only middle slot
                use_pregenerated=False,
                character_data={
                    "name": "Middle Character",
                    "character_class": "Rogue",
                    "race": "Halfling",
                    "level": 1,
                    "description": "Only in slot 1",
                    "backstory": "Middle slot only",
                    "gender": "male",
                    "facial_expression": "sly",
                    "build": "small"
                }
            )
        ]

        init_request = CampaignInitializeRequest(
            campaign_id=campaign_id,
            campaign_info={
                "title": "Partial Campaign",
                "description": "One character in middle slot",
                "setting": "Fantasy",
                "theme": "Adventure"
            },
            use_pregenerated_campaign=False,
            character_slots=character_slots
        )

        result = await campaign_service.initialize_campaign(init_request)
        assert result.get("success"), "Campaign initialization should succeed"

        # Verify only slot 1 has character in DATABASE
        with db_manager.get_sync_session() as session:
            stmt = select(RoomSeat).where(
                RoomSeat.campaign_id == campaign_id,
                RoomSeat.seat_type == 'player'
            ).order_by(RoomSeat.slot_index)
            seats = list(session.execute(stmt).scalars().all())

            assert len(seats) == 3, "Should have 3 player seats"
            assert seats[0].character_id is None, "Slot 0 should be empty in DB"
            assert seats[1].character_id is not None, "Slot 1 should have character in DB"
            assert seats[2].character_id is None, "Slot 2 should be empty in DB"

    finally:
        cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_initialize_campaign_slot_index_mapping(campaign_service, test_dm_id):
    """Test: Characters map to correct seats based on slot_id."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        create_test_campaign(campaign_id, test_dm_id, max_seats=3)

        # Create characters with specific slot_ids out of order
        character_slots = [
            CharacterSlotRequest(
                slot_id=2,  # Last slot
                use_pregenerated=False,
                character_data={
                    "name": "Last Character",
                    "character_class": "Wizard",
                    "race": "Elf",
                    "level": 1,
                    "description": "Should go to slot 2",
                    "backstory": "Last slot",
                    "gender": "female",
                    "facial_expression": "wise",
                    "build": "slender"
                }
            ),
            CharacterSlotRequest(
                slot_id=0,  # First slot
                use_pregenerated=False,
                character_data={
                    "name": "First Character",
                    "character_class": "Fighter",
                    "race": "Human",
                    "level": 1,
                    "description": "Should go to slot 0",
                    "backstory": "First slot",
                    "gender": "male",
                    "facial_expression": "determined",
                    "build": "muscular"
                }
            )
        ]

        init_request = CampaignInitializeRequest(
            campaign_id=campaign_id,
            campaign_info={
                "title": "Slot Mapping Test",
                "description": "Test slot_id to slot_index mapping",
                "setting": "Fantasy",
                "theme": "Adventure"
            },
            use_pregenerated_campaign=False,
            character_slots=character_slots
        )

        result = await campaign_service.initialize_campaign(init_request)
        assert result.get("success"), "Campaign initialization should succeed"

        # Verify characters mapped to correct slots
        with db_manager.get_sync_session() as session:
            stmt = select(RoomSeat).where(
                RoomSeat.campaign_id == campaign_id,
                RoomSeat.seat_type == 'player'
            ).order_by(RoomSeat.slot_index)
            seats = list(session.execute(stmt).scalars().all())

            assert seats[0].slot_index == 0 and seats[0].character_id is not None, \
                "Slot 0 should have First Character"
            assert seats[1].slot_index == 1 and seats[1].character_id is None, \
                "Slot 1 should be empty"
            assert seats[2].slot_index == 2 and seats[2].character_id is not None, \
                "Slot 2 should have Last Character"

    finally:
        cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_initialize_campaign_dm_seat_unaffected(campaign_service, test_dm_id):
    """Test: Character assignment doesn't affect DM seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        create_test_campaign(campaign_id, test_dm_id, max_seats=2)

        character_slots = [
            CharacterSlotRequest(
                slot_id=0,
                use_pregenerated=False,
                character_data={
                    "name": "Test Character",
                    "character_class": "Fighter",
                    "race": "Human",
                    "level": 1,
                    "description": "Test",
                    "backstory": "Test",
                    "gender": "male",
                    "facial_expression": "neutral",
                    "build": "average"
                }
            )
        ]

        init_request = CampaignInitializeRequest(
            campaign_id=campaign_id,
            campaign_info={
                "title": "DM Seat Test",
                "description": "DM seat should remain untouched",
                "setting": "Fantasy",
                "theme": "Adventure"
            },
            use_pregenerated_campaign=False,
            character_slots=character_slots
        )

        result = await campaign_service.initialize_campaign(init_request)
        assert result.get("success"), "Campaign initialization should succeed"

        # Verify DM seat remains empty
        with db_manager.get_sync_session() as session:
            dm_seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == 'dm'
                )
            ).scalar_one()

            assert dm_seat.character_id is None, "DM seat should remain empty in DB"
            assert dm_seat.owner_user_id is None, "DM seat should have no owner"

    finally:
        cleanup_campaign(campaign_id)
