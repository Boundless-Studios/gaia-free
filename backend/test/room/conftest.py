"""Test fixtures for room testing following codebase patterns."""

import os

from dataclasses import dataclass
from typing import Optional

import pytest
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import timezone, datetime

from db.src.connection import db_manager
from gaia_private.session.session_models import CampaignSession, CampaignSessionMember, RoomSeat
from gaia_private.session.room_service import RoomService


@dataclass
class DummyUser:
    """Minimal user for testing (matches pattern from test/rest tests)."""
    user_id: Optional[str] = None
    email: Optional[str] = None


def user_dep():
    """User dependency that extracts from headers (test pattern)."""
    def _dep(req: Request) -> DummyUser:
        return DummyUser(
            user_id=req.headers.get("X-User-Id"),
            email=req.headers.get("X-User-Email"),
        )
    return _dep


def build_room_app(tmp_path) -> TestClient:
    """Build minimal FastAPI app for room testing.

    Follows pattern from test/rest/test_session_invites.py
    """
    # Isolate storage
    os.environ["CAMPAIGN_STORAGE_PATH"] = str(tmp_path)

    app = FastAPI()

    # Room state endpoint
    @app.get("/api/v2/rooms/{campaign_id}")
    def get_room_state(campaign_id: str, user: DummyUser = Depends(user_dep())):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        with db_manager.get_sync_session() as session:
            # Check access
            campaign = session.get(CampaignSession, campaign_id)
            if not campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")

            # Owner always has access, check membership for others
            if campaign.owner_user_id != user.user_id:
                from sqlalchemy import select
                member = session.execute(
                    select(CampaignSessionMember).where(
                        CampaignSessionMember.session_id == campaign_id,
                        CampaignSessionMember.user_id == user.user_id
                    )
                ).scalar_one_or_none()

                if not member:
                    raise HTTPException(status_code=403, detail="Access denied")

            room_service = RoomService(session)
            state = room_service.get_room_state(campaign_id)

            return {
                "campaign_id": state.campaign_id,
                "owner_user_id": state.owner_user_id,
                "max_player_seats": state.max_player_seats,
                "room_status": state.room_status,
                "campaign_status": state.campaign_status,
                "dm_joined_at": state.dm_joined_at,
                "seats": [s.__dict__ for s in state.seats],
                "invited_players": state.invited_players,
            }

    # Room summary endpoint
    @app.get("/api/v2/rooms/{campaign_id}/summary")
    def get_room_summary(campaign_id: str, user: DummyUser = Depends(user_dep())):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        with db_manager.get_sync_session() as session:
            campaign = session.get(CampaignSession, campaign_id)
            if not campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")

            room_service = RoomService(session)
            summary = room_service.get_room_summary(campaign_id, user.user_id)

            return {
                "campaign_id": summary.campaign_id,
                "max_player_seats": summary.max_player_seats,
                "filled_player_seats": summary.filled_player_seats,
                "room_status": summary.room_status,
                "user_seat_id": summary.user_seat_id,
                "user_character_name": summary.user_character_name,
            }

    # Occupy seat endpoint
    @app.post("/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy")
    def occupy_seat(campaign_id: str, seat_id: str, user: DummyUser = Depends(user_dep())):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        with db_manager.get_sync_session() as session:
            room_service = RoomService(session)
            try:
                seat_info = room_service.occupy_seat(seat_id, user.user_id)
                return seat_info.__dict__
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    # Release seat endpoint
    @app.post("/api/v2/rooms/{campaign_id}/seats/{seat_id}/release")
    def release_seat(campaign_id: str, seat_id: str, user: DummyUser = Depends(user_dep())):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        with db_manager.get_sync_session() as session:
            room_service = RoomService(session)
            try:
                seat_info = room_service.release_seat(seat_id, user.user_id)
                return seat_info.__dict__
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    # Vacate seat endpoint (DM only)
    @app.post("/api/v2/rooms/{campaign_id}/seats/{seat_id}/vacate")
    def vacate_seat(campaign_id: str, seat_id: str, user: DummyUser = Depends(user_dep())):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        with db_manager.get_sync_session() as session:
            campaign = session.get(CampaignSession, campaign_id)
            if not campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")

            if campaign.owner_user_id != user.user_id:
                raise HTTPException(status_code=403, detail="Only DM can vacate seats")

            room_service = RoomService(session)
            try:
                seat_info, previous_owner = room_service.vacate_seat(seat_id, user.user_id)
                return {
                    "seat": seat_info.__dict__,
                    "previous_owner": previous_owner
                }
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    # Assign character endpoint
    @app.post("/api/v2/rooms/{campaign_id}/seats/{seat_id}/assign-character")
    def assign_character(campaign_id: str, seat_id: str, payload: dict, user: DummyUser = Depends(user_dep())):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        with db_manager.get_sync_session() as session:
            room_service = RoomService(session)
            try:
                character_id = room_service.assign_character_to_seat(
                    campaign_id, seat_id, payload.get("character_data", {}), user.user_id
                )
                return {"success": True, "character_id": character_id}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    return TestClient(app)


@pytest.fixture
def client(tmp_path):
    """Test client with room endpoints (follows codebase pattern)."""
    return build_room_app(tmp_path)


@pytest.fixture
def test_dm_id():
    """Test DM user ID."""
    return "test-dm-456"


@pytest.fixture
def test_player_ids():
    """Test player IDs."""
    return [
        "test-player-alice",
        "test-player-bob",
        "test-player-carol",
        "test-player-dave",
    ]


@pytest.fixture
def sample_character_data():
    """Sample character data for testing."""
    return {
        "name": "Test Hero",
        "race": "Human",
        "class": "Fighter",
        "level": 1,
        "background": "Soldier",
        "alignment": "Lawful Good",
        "gender": "male",
        "build": "athletic",
        "facial_expression": "determined",
        "personality": "Brave and honorable",
        "appearance": "Tall with short dark hair",
        "backstory": "A former soldier",
    }


def create_test_campaign(campaign_id: str, owner_user_id: str, max_seats: int = 4):
    """Helper to create a test campaign with seats."""
    with db_manager.get_sync_session() as session:
        # Create campaign
        campaign = CampaignSession(
            session_id=campaign_id,
            owner_user_id=owner_user_id,
            created_at=datetime.now(timezone.utc),
            max_player_seats=max_seats,
            room_status='waiting_for_dm',
            campaign_status='setup',
        )
        session.add(campaign)
        session.commit()

        # Create seats
        room_service = RoomService(session)
        room_service.create_room(campaign_id, owner_user_id, max_seats)


def add_campaign_member(campaign_id: str, user_id: str, email: str):
    """Helper to add a member to a campaign."""
    with db_manager.get_sync_session() as session:
        member = CampaignSessionMember(
            session_id=campaign_id,
            user_id=user_id,
            email=email,
            normalized_email=email.lower(),
            joined_at=datetime.now(timezone.utc),
        )
        session.add(member)
        session.commit()


def cleanup_campaign(campaign_id: str):
    """Helper to clean up a test campaign."""
    with db_manager.get_sync_session() as session:
        # Delete seats
        from sqlalchemy import select
        seats = session.execute(
            select(RoomSeat).where(RoomSeat.campaign_id == campaign_id)
        ).scalars().all()
        for seat in seats:
            session.delete(seat)

        # Delete members
        members = session.execute(
            select(CampaignSessionMember).where(
                CampaignSessionMember.session_id == campaign_id
            )
        ).scalars().all()
        for member in members:
            session.delete(member)

        # Delete campaign
        campaign = session.get(CampaignSession, campaign_id)
        if campaign:
            session.delete(campaign)

        session.commit()

    # Clean up filesystem directory
    import shutil
    from pathlib import Path

    campaign_storage_path = os.environ.get("CAMPAIGN_STORAGE_PATH", "campaign_storage")
    campaign_dir = Path(campaign_storage_path) / campaign_id

    if campaign_dir.exists():
        try:
            shutil.rmtree(campaign_dir)
        except Exception as e:
            # Log but don't fail - this is cleanup
            print(f"Warning: Failed to remove campaign directory {campaign_dir}: {e}")
