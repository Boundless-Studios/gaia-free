"""Focused unit tests for RoomService edge cases and business logic.

Tests RoomService behaviors that HTTP integration tests don't reach:
- Attempting to occupy someone else's seat
- Releasing someone else's seat
- Non-DM vacating seats
- Character immutability violations
- Authorization edge cases
- Single seat enforcement
"""

import uuid
from uuid import uuid4

import pytest
from sqlalchemy import select

from db.src.connection import db_manager
from gaia_private.session.session_models import CampaignSession, RoomSeat
from gaia_private.session.room_service import RoomService

# Import test helpers
from test.room.conftest import (
    create_test_campaign,
    add_campaign_member,
    cleanup_campaign,
)


@pytest.fixture
def service():
    """RoomService instance for testing."""
    with db_manager.get_sync_session() as session:
        yield RoomService(session)


@pytest.fixture
def test_dm_id():
    """DM user ID for testing."""
    return f"dm-{uuid4().hex[:8]}"


@pytest.fixture
def test_player_ids():
    """Multiple player IDs for testing."""
    return [f"player-{i}-{uuid4().hex[:8]}" for i in range(3)]


# ============================================================================
# occupy_seat() Edge Cases
# ============================================================================


def test_occupy_seat_already_occupied_by_different_user(service, test_dm_id, test_player_ids):
    """Test: Cannot occupy a seat already owned by a different user."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        # Setup: Alice occupies a seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies seat
        service.occupy_seat(seat_id, player_alice)

        # Test: Bob tries to occupy Alice's seat → should fail
        with pytest.raises(ValueError) as exc_info:
            service.occupy_seat(seat_id, player_bob)

        assert "already occupied" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


def test_occupy_dm_seat_as_non_owner(service, test_dm_id, test_player_ids):
    """Test: Non-owner cannot occupy the DM seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]

    try:
        # Setup: Create campaign with DM seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")

        with db_manager.get_sync_session() as session:
            dm_seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "dm"
                )
            ).scalars().first()
            dm_seat_id = str(dm_seat.seat_id)

        # Test: Player tries to occupy DM seat → should fail
        with pytest.raises(ValueError) as exc_info:
            service.occupy_seat(dm_seat_id, player_alice)

        assert "only the campaign owner" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


def test_dm_seat_claim_backfills_missing_owner(service, test_dm_id):
    """Test: DM seat claim sets campaign.owner_user_id when missing."""
    campaign_id = f"legacy-camp-{uuid4().hex[:8]}"

    try:
        with db_manager.get_sync_session() as session:
            campaign = CampaignSession(
                session_id=campaign_id,
                owner_user_id=None,
                max_player_seats=4,
                room_status='waiting_for_dm',
                campaign_status='setup',
            )
            session.add(campaign)
            session.commit()

            room_service = RoomService(session)
            room_service.create_room(campaign_id, owner_user_id="", max_player_seats=4)

            dm_seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "dm"
                )
            ).scalars().first()
            dm_seat_id = str(dm_seat.seat_id)

        seat_info = service.occupy_seat(dm_seat_id, test_dm_id)

        assert seat_info.owner_user_id == test_dm_id

        with db_manager.get_sync_session() as session:
            updated_campaign = session.get(CampaignSession, campaign_id)
            assert updated_campaign.owner_user_id == test_dm_id

    finally:
        cleanup_campaign(campaign_id)


def test_occupy_player_seat_as_non_member(service, test_dm_id):
    """Test: Non-invited user cannot occupy player seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    uninvited_user = f"uninvited-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign but don't invite user
        create_test_campaign(campaign_id, test_dm_id)

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Test: Uninvited user tries to occupy seat → should fail
        with pytest.raises(ValueError) as exc_info:
            service.occupy_seat(seat_id, uninvited_user)

        assert "must be invited" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


def test_occupy_seat_single_seat_enforcement(service, test_dm_id, test_player_ids):
    """Test: Occupying new seat auto-releases previous seat (single seat per user)."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]

    try:
        # Setup: Create campaign with multiple seats
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")

        with db_manager.get_sync_session() as session:
            seats = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().all()
            seat_1_id = str(seats[0].seat_id)
            seat_2_id = str(seats[1].seat_id)

        # Alice occupies seat 1
        service.occupy_seat(seat_1_id, player_alice)

        # Verify seat 1 is occupied
        with db_manager.get_sync_session() as session:
            seat_1 = session.get(RoomSeat, uuid.UUID(seat_1_id))
            assert seat_1.owner_user_id == player_alice

        # Alice occupies seat 2
        service.occupy_seat(seat_2_id, player_alice)

        # Verify: Seat 1 auto-released, Seat 2 occupied
        with db_manager.get_sync_session() as session:
            seat_1 = session.get(RoomSeat, uuid.UUID(seat_1_id))
            seat_2 = session.get(RoomSeat, uuid.UUID(seat_2_id))

            assert seat_1.owner_user_id is None, "Seat 1 should be auto-released"
            assert seat_2.owner_user_id == player_alice, "Seat 2 should be occupied"

    finally:
        cleanup_campaign(campaign_id)


# ============================================================================
# release_seat() Edge Cases
# ============================================================================


def test_release_someone_elses_seat(service, test_dm_id, test_player_ids):
    """Test: Cannot release a seat owned by a different user."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        # Setup: Alice occupies a seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies seat
        service.occupy_seat(seat_id, player_alice)

        # Test: Bob tries to release Alice's seat → should fail
        with pytest.raises(ValueError) as exc_info:
            service.release_seat(seat_id, player_bob)

        assert "only release your own seat" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


def test_release_unoccupied_seat(service, test_dm_id, test_player_ids):
    """Test: Cannot release a seat that's not yours (empty seat)."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]

    try:
        # Setup: Empty seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Test: Alice tries to release empty seat → should fail
        with pytest.raises(ValueError) as exc_info:
            service.release_seat(seat_id, player_alice)

        assert "only release your own seat" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


# ============================================================================
# vacate_seat() Edge Cases
# ============================================================================


def test_vacate_seat_non_dm_cannot_vacate(service, test_dm_id, test_player_ids):
    """Test: Non-DM players cannot vacate seats."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        # Setup: Alice occupies a seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies seat
        service.occupy_seat(seat_id, player_alice)

        # Test: Bob (non-DM) tries to vacate Alice's seat → should fail
        with pytest.raises(ValueError) as exc_info:
            service.vacate_seat(seat_id, player_bob)

        assert "only dm" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


def test_vacate_seat_returns_previous_owner(service, test_dm_id, test_player_ids):
    """Test: vacate_seat returns previous owner for notifications."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]

    try:
        # Setup: Alice occupies a seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies seat
        service.occupy_seat(seat_id, player_alice)

        # Test: DM vacates seat and gets previous owner
        seat_info, previous_owner = service.vacate_seat(seat_id, test_dm_id)

        assert previous_owner == player_alice, "Should return previous owner"
        assert seat_info.owner_user_id is None, "Seat should now be vacant"

    finally:
        cleanup_campaign(campaign_id)


# ============================================================================
# assign_character_to_seat() Edge Cases
# ============================================================================


def test_assign_character_to_already_assigned_seat(service, test_dm_id, test_player_ids):
    """Test: Cannot reassign character to seat (immutability)."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]

    try:
        # Setup: Alice occupies seat with character
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies seat
        service.occupy_seat(seat_id, player_alice)

        # Alice creates first character
        character_data_1 = {"name": "First Character", "class": "Warrior"}
        service.assign_character_to_seat(campaign_id, seat_id, character_data_1, player_alice)

        # Test: Alice tries to create second character → should fail (immutable)
        character_data_2 = {"name": "Second Character", "class": "Mage"}
        with pytest.raises(ValueError) as exc_info:
            service.assign_character_to_seat(campaign_id, seat_id, character_data_2, player_alice)

        assert "already has character" in str(exc_info.value).lower()
        assert "immutable" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


def test_assign_character_to_unclaimed_seat(service, test_dm_id, test_player_ids):
    """Test: Cannot assign character to unclaimed seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]

    try:
        # Setup: Seat exists but not claimed
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)
            # Verify seat is unclaimed
            assert seat.owner_user_id is None

        # Test: Alice tries to assign character to unclaimed seat → should fail
        character_data = {"name": "Test Character", "class": "Warrior"}
        with pytest.raises(ValueError) as exc_info:
            service.assign_character_to_seat(campaign_id, seat_id, character_data, player_alice)

        assert "must be claimed" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


def test_assign_character_non_owner_non_dm(service, test_dm_id, test_player_ids):
    """Test: Non-owner, non-DM cannot assign character to seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        # Setup: Alice occupies seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies seat
        service.occupy_seat(seat_id, player_alice)

        # Test: Bob (not owner, not DM) tries to assign character → should fail
        character_data = {"name": "Bob's Character", "class": "Rogue"}
        with pytest.raises(ValueError) as exc_info:
            service.assign_character_to_seat(campaign_id, seat_id, character_data, player_bob)

        assert "only the seat owner or dm" in str(exc_info.value).lower()

    finally:
        cleanup_campaign(campaign_id)


def test_assign_character_dm_can_assign_to_any_seat(service, test_dm_id, test_player_ids):
    """Test: DM can assign character to any claimed seat (DM override)."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]

    try:
        # Setup: Alice occupies seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies seat
        service.occupy_seat(seat_id, player_alice)

        # Test: DM assigns character to Alice's seat (DM override)
        character_data = {"name": "DM-Created Character", "class": "Paladin"}
        character_id = service.assign_character_to_seat(campaign_id, seat_id, character_data, test_dm_id)

        assert character_id is not None

        # Verify character was assigned
        with db_manager.get_sync_session() as session:
            seat = session.get(RoomSeat, uuid.UUID(seat_id))
            assert seat.character_id == character_id

    finally:
        cleanup_campaign(campaign_id)


# ============================================================================
# create_room() Edge Cases
# ============================================================================


def test_create_room_nonexistent_campaign(service):
    """Test: Cannot create room for non-existent campaign."""
    nonexistent_campaign_id = f"nonexistent-{uuid4().hex[:8]}"
    fake_dm_id = f"dm-{uuid4().hex[:8]}"

    # Test: Creating room for non-existent campaign → should fail
    with pytest.raises(ValueError) as exc_info:
        service.create_room(nonexistent_campaign_id, fake_dm_id, max_player_seats=4)

    assert "not found" in str(exc_info.value).lower()


def test_create_room_correct_seat_counts(service, test_dm_id):
    """Test: create_room creates correct number of seats (1 DM + N player)."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Setup: Create campaign manually WITHOUT seats
        from datetime import datetime, timezone
        with db_manager.get_sync_session() as session:
            campaign = CampaignSession(
                session_id=campaign_id,
                owner_user_id=test_dm_id,
                created_at=datetime.now(timezone.utc),
                max_player_seats=None,
                room_status=None,
                campaign_status=None,
            )
            session.add(campaign)
            session.commit()

        # Test: Create room with 3 player seats
        service.create_room(campaign_id, test_dm_id, max_player_seats=3)

        # Verify: 1 DM seat + 3 player seats
        with db_manager.get_sync_session() as session:
            all_seats = session.execute(
                select(RoomSeat).where(RoomSeat.campaign_id == campaign_id)
            ).scalars().all()

            dm_seats = [s for s in all_seats if s.seat_type == "dm"]
            player_seats = [s for s in all_seats if s.seat_type == "player"]

            assert len(dm_seats) == 1, "Should have exactly 1 DM seat"
            assert len(player_seats) == 3, "Should have 3 player seats"
            assert dm_seats[0].slot_index is None, "DM seat should have no slot_index"
            assert [s.slot_index for s in player_seats] == [0, 1, 2], "Player seats should have sequential indices"

    finally:
        cleanup_campaign(campaign_id)


# ============================================================================
# get_room_summary() Edge Cases
# ============================================================================


def test_get_room_summary_user_not_in_campaign(service, test_dm_id, test_player_ids):
    """Test: Summary for user not in campaign shows no user seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    outside_user = f"outside-{uuid4().hex[:8]}"

    try:
        # Setup: Alice has a seat
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")

        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()

        # Alice occupies seat
        service.occupy_seat(str(seat.seat_id), player_alice)

        # Test: Outside user requests summary
        summary = service.get_room_summary(campaign_id, outside_user)

        assert summary.filled_player_seats == 1, "Should show 1 filled seat"
        assert summary.user_seat_id is None, "Outside user should have no seat"
        assert summary.user_character_name is None, "Outside user should have no character"

    finally:
        cleanup_campaign(campaign_id)


def test_get_room_summary_correct_filled_count(service, test_dm_id, test_player_ids):
    """Test: Summary correctly counts filled seats."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        # Setup: 2 players occupy seats
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        with db_manager.get_sync_session() as session:
            seats = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().all()

        # Alice and Bob occupy seats
        service.occupy_seat(str(seats[0].seat_id), player_alice)
        service.occupy_seat(str(seats[1].seat_id), player_bob)

        # Test: Summary shows correct count
        summary = service.get_room_summary(campaign_id, player_alice)

        assert summary.filled_player_seats == 2, "Should show 2 filled seats"
        assert summary.max_player_seats == 4, "Should show max 4 seats"

    finally:
        cleanup_campaign(campaign_id)
