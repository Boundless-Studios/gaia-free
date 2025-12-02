"""Tests for RoomAccessGuard - Chat interface gatekeeping.

Tests the guards that protect /api/chat endpoint:
- ensure_dm_present: Validates DM has joined before actions
- ensure_player_has_character: Validates player has character before playing
"""

import uuid

import pytest
from uuid import uuid4

from db.src.connection import db_manager
from gaia_private.session.session_models import CampaignSession, RoomSeat
from gaia.api.middleware.room_access import RoomAccessGuard
from sqlalchemy import select

# Import test helpers from conftest
from test.room.conftest import (
    create_test_campaign,
    add_campaign_member,
    cleanup_campaign,
)


@pytest.fixture
def guard():
    """RoomAccessGuard instance for testing."""
    return RoomAccessGuard()


@pytest.fixture
def test_dm_id():
    """DM user ID for testing."""
    return f"dm-{uuid4().hex[:8]}"


@pytest.fixture
def test_player_id():
    """Player user ID for testing."""
    return f"player-{uuid4().hex[:8]}"


# ============================================================================
# ensure_dm_present() Tests
# ============================================================================


def test_ensure_dm_present_success(guard, test_dm_id):
    """Test: DM has joined → action allowed."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign with DM joined (room_status = 'active')
        create_test_campaign(campaign_id, test_dm_id)

        with db_manager.get_sync_session() as session:
            campaign = session.get(CampaignSession, campaign_id)
            campaign.room_status = 'active'  # DM has joined
            session.commit()

        # Test: Should not raise exception
        guard.ensure_dm_present(campaign_id)

        # If we get here, test passed
        assert True

    finally:
        cleanup_campaign(campaign_id)


def test_ensure_dm_present_waiting_for_dm(guard, test_dm_id):
    """Test: DM not joined → 409 Conflict."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign without DM joined (room_status = 'waiting_for_dm')
        create_test_campaign(campaign_id, test_dm_id)

        with db_manager.get_sync_session() as session:
            campaign = session.get(CampaignSession, campaign_id)
            campaign.room_status = 'waiting_for_dm'  # DM has NOT joined
            session.commit()

        # Test: Should raise 409 Conflict
        with pytest.raises(Exception) as exc_info:
            guard.ensure_dm_present(campaign_id)

        assert exc_info.value.status_code == 409
        assert "Waiting for DM" in exc_info.value.detail

    finally:
        cleanup_campaign(campaign_id)


def test_ensure_dm_present_campaign_not_found(guard):
    """Test: Invalid campaign ID → 404 Not Found."""
    campaign_id = "nonexistent-campaign-123"

    # Test: Should raise 404 Not Found
    with pytest.raises(Exception) as exc_info:
        guard.ensure_dm_present(campaign_id)

    assert exc_info.value.status_code == 404
    assert campaign_id in exc_info.value.detail


# ============================================================================
# ensure_player_has_character() Tests
# ============================================================================


def test_ensure_player_has_character_success(guard, test_dm_id, test_player_id):
    """Test: Player has seat + character → action allowed."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign with player seat + character
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, test_player_id, f"{test_player_id}@example.com")

        with db_manager.get_sync_session() as session:
            # Get first player seat
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()

            # Assign to player with character
            seat.owner_user_id = test_player_id
            seat.character_id = f"char-{uuid4().hex[:8]}"
            session.commit()

        # Test: Should not raise exception
        guard.ensure_player_has_character(campaign_id, test_player_id)

        # If we get here, test passed
        assert True

    finally:
        cleanup_campaign(campaign_id)


def test_ensure_player_has_character_no_seat(guard, test_dm_id, test_player_id):
    """Test: Player has no seat → 400 Bad Request."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign but player has no seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, test_player_id, f"{test_player_id}@example.com")

        # Test: Should raise 400 Bad Request
        with pytest.raises(Exception) as exc_info:
            guard.ensure_player_has_character(campaign_id, test_player_id)

        assert exc_info.value.status_code == 400
        assert "Seat must be claimed" in exc_info.value.detail

    finally:
        cleanup_campaign(campaign_id)


def test_ensure_player_has_character_no_character(guard, test_dm_id, test_player_id):
    """Test: Player has seat but no character → 400 Bad Request."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign with player seat but NO character
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, test_player_id, f"{test_player_id}@example.com")

        with db_manager.get_sync_session() as session:
            # Get first player seat
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()

            # Assign to player WITHOUT character
            seat.owner_user_id = test_player_id
            seat.character_id = None  # No character!
            session.commit()

        # Test: Should raise 400 Bad Request
        with pytest.raises(Exception) as exc_info:
            guard.ensure_player_has_character(campaign_id, test_player_id)

        assert exc_info.value.status_code == 400
        assert "Seat requires character" in exc_info.value.detail

    finally:
        cleanup_campaign(campaign_id)


def test_ensure_player_has_character_dm_exempt(guard, test_dm_id):
    """Test: DM is exempt from character requirement → always allowed."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign where DM is the caller
        create_test_campaign(campaign_id, test_dm_id)

        # DM should NOT have a player seat or character
        with db_manager.get_sync_session() as session:
            player_seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player",
                    RoomSeat.owner_user_id == test_dm_id
                )
            ).scalars().first()

            # Verify DM has no player seat
            assert player_seat is None

        # Test: DM calling should not raise exception (exempt)
        guard.ensure_player_has_character(campaign_id, test_dm_id)

        # If we get here, test passed
        assert True

    finally:
        cleanup_campaign(campaign_id)


def test_ensure_player_has_character_no_user_id(guard, test_dm_id):
    """Test: No user_id provided → 401 Unauthorized."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign
        create_test_campaign(campaign_id, test_dm_id)

        # Test: Calling with user_id=None should raise 401
        with pytest.raises(Exception) as exc_info:
            guard.ensure_player_has_character(campaign_id, user_id=None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    finally:
        cleanup_campaign(campaign_id)


def test_ensure_player_has_character_campaign_not_found(guard, test_player_id):
    """Test: Invalid campaign ID → 404 Not Found."""
    campaign_id = "nonexistent-campaign-456"

    # Test: Should raise 404 Not Found
    with pytest.raises(Exception) as exc_info:
        guard.ensure_player_has_character(campaign_id, test_player_id)

    assert exc_info.value.status_code == 404
    assert campaign_id in exc_info.value.detail


# ============================================================================
# Integration Test: Combined Guards (Chat Flow)
# ============================================================================


def test_chat_flow_both_guards_pass(guard, test_dm_id, test_player_id):
    """Test: Complete chat flow validation - DM present + player has character."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign with DM joined and player with character
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, test_player_id, f"{test_player_id}@example.com")

        with db_manager.get_sync_session() as session:
            # Set DM as joined
            campaign = session.get(CampaignSession, campaign_id)
            campaign.room_status = 'active'

            # Give player a seat with character
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()

            seat.owner_user_id = test_player_id
            seat.character_id = f"char-{uuid4().hex[:8]}"
            session.commit()

        # Test: Both guards should pass
        guard.ensure_dm_present(campaign_id)
        guard.ensure_player_has_character(campaign_id, test_player_id)

        # If we get here, chat flow is allowed
        assert True

    finally:
        cleanup_campaign(campaign_id)


def test_chat_flow_dm_not_present(guard, test_dm_id, test_player_id):
    """Test: Chat blocked when DM not present (even if player has character)."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Player has character BUT DM not joined
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, test_player_id, f"{test_player_id}@example.com")

        with db_manager.get_sync_session() as session:
            # DM NOT joined
            campaign = session.get(CampaignSession, campaign_id)
            campaign.room_status = 'waiting_for_dm'

            # Player has character
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()

            seat.owner_user_id = test_player_id
            seat.character_id = f"char-{uuid4().hex[:8]}"
            session.commit()

        # Test: DM presence check should fail
        with pytest.raises(Exception) as exc_info:
            guard.ensure_dm_present(campaign_id)

        assert exc_info.value.status_code == 409

        # Player has character check would pass (but shouldn't reach this)
        guard.ensure_player_has_character(campaign_id, test_player_id)

    finally:
        cleanup_campaign(campaign_id)


def test_chat_flow_player_no_character(guard, test_dm_id, test_player_id):
    """Test: Chat blocked when player has no character (even if DM present)."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: DM joined BUT player has no character
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, test_player_id, f"{test_player_id}@example.com")

        with db_manager.get_sync_session() as session:
            # DM joined
            campaign = session.get(CampaignSession, campaign_id)
            campaign.room_status = 'active'

            # Player has seat but NO character
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()

            seat.owner_user_id = test_player_id
            seat.character_id = None  # No character!
            session.commit()

        # Test: DM presence check passes
        guard.ensure_dm_present(campaign_id)

        # Player character check should fail
        with pytest.raises(Exception) as exc_info:
            guard.ensure_player_has_character(campaign_id, test_player_id)

        assert exc_info.value.status_code == 400
        assert "Seat requires character" in exc_info.value.detail

    finally:
        cleanup_campaign(campaign_id)
