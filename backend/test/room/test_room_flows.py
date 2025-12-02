"""Room flow tests following codebase patterns.

Tests the complete room flow using minimal FastAPI app approach
from test/rest/test_session_invites.py pattern.
"""

import pytest
from uuid import uuid4

from test.room.conftest import create_test_campaign, add_campaign_member, cleanup_campaign
from db.src.connection import db_manager
from gaia_private.session.session_models import RoomSeat
from sqlalchemy import select


def test_dm_creates_campaign_and_gets_state(client, test_dm_id):
    """Test: DM creates campaign and retrieves room state."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Create campaign with seats
        create_test_campaign(campaign_id, test_dm_id, max_seats=4)

        # DM gets room state
        r = client.get(
            f"/api/v2/rooms/{campaign_id}",
            headers={"X-User-Id": test_dm_id}
        )

        assert r.status_code == 200
        data = r.json()

        assert data["campaign_id"] == campaign_id
        assert data["owner_user_id"] == test_dm_id
        assert data["max_player_seats"] == 4
        assert data["room_status"] == "waiting_for_dm"
        assert len(data["seats"]) == 5  # 1 DM + 4 player

        dm_seats = [s for s in data["seats"] if s["seat_type"] == "dm"]
        player_seats = [s for s in data["seats"] if s["seat_type"] == "player"]

        assert len(dm_seats) == 1
        assert len(player_seats) == 4

    finally:
        cleanup_campaign(campaign_id)


def test_unauthenticated_access_denied(client):
    """Test: Unauthenticated requests are rejected."""
    campaign_id = "any-campaign"

    r = client.get(f"/api/v2/rooms/{campaign_id}")
    assert r.status_code == 401


def test_non_member_access_denied(client, test_dm_id, test_player_ids):
    """Test: Non-members cannot access campaign."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        create_test_campaign(campaign_id, test_dm_id)

        # Uninvited player tries to access
        r = client.get(
            f"/api/v2/rooms/{campaign_id}",
            headers={"X-User-Id": "intruder-999"}
        )

        assert r.status_code == 403

    finally:
        cleanup_campaign(campaign_id)


def test_owner_always_has_access(client, test_dm_id):
    """Test: Campaign owner always has access without explicit membership."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        create_test_campaign(campaign_id, test_dm_id)

        r = client.get(
            f"/api/v2/rooms/{campaign_id}",
            headers={"X-User-Id": test_dm_id}
        )

        assert r.status_code == 200
        assert r.json()["owner_user_id"] == test_dm_id

    finally:
        cleanup_campaign(campaign_id)


def test_member_can_access(client, test_dm_id, test_player_ids):
    """Test: Invited members can access campaign."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        r = client.get(
            f"/api/v2/rooms/{campaign_id}",
            headers={"X-User-Id": player_id}
        )

        assert r.status_code == 200

    finally:
        cleanup_campaign(campaign_id)


def test_player_occupies_seat(client, test_dm_id, test_player_ids):
    """Test: Player occupies an available seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        # Get first player seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Player occupies seat
        r = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        assert r.status_code == 200
        data = r.json()

        assert data["owner_user_id"] == player_id
        assert data["status"] == "claimed"
        assert data["character_id"] is None

    finally:
        cleanup_campaign(campaign_id)


def test_uninvited_player_cannot_occupy_seat(client, test_dm_id):
    """Test: Uninvited player cannot occupy seats."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    uninvited_player = "uninvited-999"

    try:
        create_test_campaign(campaign_id, test_dm_id)

        # Get a seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Uninvited player tries to occupy
        r = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": uninvited_player}
        )

        assert r.status_code == 400
        assert "must be invited" in r.json()["detail"]

    finally:
        cleanup_campaign(campaign_id)


def test_assign_character_to_seat(client, test_dm_id, test_player_ids, sample_character_data):
    """Test: Player creates character on their seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        # Get and occupy seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Occupy seat
        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        # Assign character
        r = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": player_id},
            json={"character_data": sample_character_data}
        )

        assert r.status_code == 200
        data = r.json()

        assert data["success"] is True
        assert data["character_id"] is not None

        # Verify character is bound to seat
        with db_manager.get_sync_session() as session:
            from uuid import UUID
            seat = session.get(RoomSeat, UUID(seat_id))
            assert seat.character_id == data["character_id"]
            assert seat.owner_user_id == player_id

    finally:
        cleanup_campaign(campaign_id)


def test_character_immutability(client, test_dm_id, test_player_ids, sample_character_data):
    """Test: Character cannot be changed once assigned."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        # Get and occupy seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Occupy and assign character
        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": player_id},
            json={"character_data": sample_character_data}
        )

        # Try to assign another character
        new_character = {**sample_character_data, "name": "Another Hero"}

        r = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": player_id},
            json={"character_data": new_character}
        )

        assert r.status_code == 400
        assert "already has character" in r.json()["detail"]

    finally:
        cleanup_campaign(campaign_id)


def test_character_rotation(client, test_dm_id, test_player_ids, sample_character_data):
    """Test: DM vacates seat, then different player occupies with character persisting."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        # Get seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies and creates character
        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_alice}
        )

        r1 = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": player_alice},
            json={"character_data": sample_character_data}
        )
        character_id = r1.json()["character_id"]

        # DM vacates Alice's seat (required for character rotation)
        r_vacate = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/vacate",
            headers={"X-User-Id": test_dm_id}
        )
        assert r_vacate.status_code == 200
        assert r_vacate.json()["previous_owner"] == player_alice

        # Bob occupies the now-vacant seat
        r2 = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_bob}
        )

        assert r2.status_code == 200
        data = r2.json()

        assert data["owner_user_id"] == player_bob
        assert data["character_id"] == character_id  # Character persists across rotation

    finally:
        cleanup_campaign(campaign_id)


def test_dm_vacates_player_seat(client, test_dm_id, test_player_ids, sample_character_data):
    """Test: DM vacates a player seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        # Get and occupy seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Player occupies and creates character
        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        r1 = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": player_id},
            json={"character_data": sample_character_data}
        )
        character_id = r1.json()["character_id"]

        # DM vacates seat
        r2 = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/vacate",
            headers={"X-User-Id": test_dm_id}
        )

        assert r2.status_code == 200
        data = r2.json()

        assert data["previous_owner"] == player_id
        assert data["seat"]["owner_user_id"] is None
        assert data["seat"]["character_id"] == character_id  # Character remains

    finally:
        cleanup_campaign(campaign_id)


def test_non_dm_cannot_vacate_seat(client, test_dm_id, test_player_ids):
    """Test: Non-DM player cannot vacate seats."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        # Get and occupy seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        # Alice occupies seat
        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_alice}
        )

        # Bob (not DM) tries to vacate
        r = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/vacate",
            headers={"X-User-Id": player_bob}
        )

        assert r.status_code == 403
        assert "Only DM" in r.json()["detail"]

    finally:
        cleanup_campaign(campaign_id)


def test_room_summary(client, test_dm_id, test_player_ids, sample_character_data):
    """Test: Room summary provides lightweight data."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        # Get summary before seat occupation
        r1 = client.get(
            f"/api/v2/rooms/{campaign_id}/summary",
            headers={"X-User-Id": player_id}
        )

        assert r1.status_code == 200
        data1 = r1.json()

        assert data1["campaign_id"] == campaign_id
        assert data1["max_player_seats"] == 4
        assert data1["filled_player_seats"] == 0
        assert data1["user_seat_id"] is None

        # Player occupies seat and creates character
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": player_id},
            json={"character_data": sample_character_data}
        )

        # Get summary after
        r2 = client.get(
            f"/api/v2/rooms/{campaign_id}/summary",
            headers={"X-User-Id": player_id}
        )

        assert r2.status_code == 200
        data2 = r2.json()

        assert data2["filled_player_seats"] == 1
        assert data2["user_seat_id"] == seat_id
        assert data2["user_character_name"] == sample_character_data["name"]

    finally:
        cleanup_campaign(campaign_id)


def test_player_can_only_hold_one_seat(client, test_dm_id, test_player_ids):
    """Test: Player can only hold one seat at a time."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        # Get two seats
        with db_manager.get_sync_session() as session:
            seats = list(session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                ).limit(2)
            ).scalars())
            seat_1_id = str(seats[0].seat_id)
            seat_2_id = str(seats[1].seat_id)

        # Occupy first seat
        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_1_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        # Occupy second seat - should release first
        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_2_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        # Verify first seat released
        with db_manager.get_sync_session() as session:
            from uuid import UUID
            seat_1 = session.get(RoomSeat, UUID(seat_1_id))
            seat_2 = session.get(RoomSeat, UUID(seat_2_id))

            assert seat_1.owner_user_id is None
            assert seat_2.owner_user_id == player_id

    finally:
        cleanup_campaign(campaign_id)


def test_release_seat(client, test_dm_id, test_player_ids):
    """Test: Player releases their own seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        # Get and occupy seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        # Release seat
        r = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/release",
            headers={"X-User-Id": player_id}
        )

        assert r.status_code == 200
        data = r.json()

        assert data["owner_user_id"] is None

    finally:
        cleanup_campaign(campaign_id)


def test_character_assignment_requires_ownership(client, test_dm_id, test_player_ids, sample_character_data):
    """Test: Only seat owner or DM can assign character to a seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        # Alice occupies a seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "player"
                )
            ).scalars().first()
            seat_id = str(seat.seat_id)

        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_alice}
        )

        # Bob tries to assign character to Alice's seat (should fail)
        r1 = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": player_bob},
            json={"character_data": sample_character_data}
        )

        assert r1.status_code == 400
        assert "Only the seat owner or DM can assign a character" in r1.json()["detail"]

        # Alice can assign character to her own seat (should succeed)
        r2 = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": player_alice},
            json={"character_data": sample_character_data}
        )

        assert r2.status_code == 200
        character_id = r2.json()["character_id"]
        assert character_id is not None

        # Verify character immutability - even DM cannot reassign
        r3 = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character",
            headers={"X-User-Id": test_dm_id},
            json={"character_data": {"name": "Different Character"}}
        )

        assert r3.status_code == 400
        assert "already has character" in r3.json()["detail"]

        # Test DM can assign to unclaimed seat
        with db_manager.get_sync_session() as session:
            dm_seat = session.execute(
                select(RoomSeat).where(
                    RoomSeat.campaign_id == campaign_id,
                    RoomSeat.seat_type == "dm"
                )
            ).scalar_one()
            dm_seat_id = str(dm_seat.seat_id)

        # DM occupies DM seat
        client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{dm_seat_id}/occupy",
            headers={"X-User-Id": test_dm_id}
        )

        # DM can assign character to their own seat
        r4 = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{dm_seat_id}/assign-character",
            headers={"X-User-Id": test_dm_id},
            json={"character_data": {"name": "DM Character"}}
        )

        assert r4.status_code == 200

    finally:
        cleanup_campaign(campaign_id)
