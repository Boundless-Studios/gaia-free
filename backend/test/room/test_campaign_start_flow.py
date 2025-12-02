"""Tests for deferred campaign start behavior driven by room seats."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from db.src.connection import db_manager
from gaia_private.session.room_service import RoomService
from gaia_private.session.session_models import RoomSeat
from gaia.api.routes.campaigns import CampaignService
from gaia.mechanics.campaign.simple_campaign_manager import SimpleCampaignManager
from gaia.utils.singleton import SingletonMeta
from test.room.conftest import (
    create_test_campaign,
    add_campaign_member,
    cleanup_campaign,
)


@pytest.fixture
def campaign_service(tmp_path, monkeypatch):
    """CampaignService backed by an isolated storage directory."""
    storage_root = tmp_path / "campaigns"
    storage_root.mkdir()
    SingletonMeta.clear_instance(SimpleCampaignManager)
    orchestrator = type(
        "OrchestratorStub",
        (),
        {"campaign_manager": SimpleCampaignManager(base_path=str(storage_root))},
    )()
    return CampaignService(orchestrator)


@pytest.mark.asyncio
async def test_start_campaign_requires_seat_characters(campaign_service, test_dm_id):
    """Starting a campaign without any seat characters should fail."""
    campaign_id = f"start-test-{uuid4().hex[:8]}"

    try:
        create_test_campaign(campaign_id, test_dm_id)

        with pytest.raises(HTTPException) as exc_info:
            await campaign_service.start_campaign_from_seats(
                campaign_id,
                campaign_info={"title": "Empty Seats", "description": "No heroes yet."},
            )

        assert exc_info.value.status_code == 400
        assert "No characters found" in exc_info.value.detail
    finally:
        cleanup_campaign(campaign_id)


@pytest.mark.asyncio
async def test_start_campaign_uses_room_seat_characters(
    campaign_service,
    test_dm_id,
    test_player_ids,
    sample_character_data,
    monkeypatch,
):
    """Start flow should build the opening prompt from seat-bound characters."""
    campaign_id = f"start-flow-{uuid4().hex[:8]}"
    player_alice = test_player_ids[0]
    player_bob = test_player_ids[1]

    try:
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_alice, f"{player_alice}@example.com")
        add_campaign_member(campaign_id, player_bob, f"{player_bob}@example.com")

        # Occupy two seats and assign characters
        with db_manager.get_sync_session() as session:
            seats = (
                session.execute(
                    select(RoomSeat)
                    .where(
                        RoomSeat.campaign_id == campaign_id,
                        RoomSeat.seat_type == "player",
                    )
                    .order_by(RoomSeat.slot_index)
                )
                .scalars()
                .all()
            )
            seat_alice = str(seats[0].seat_id)
            seat_bob = str(seats[1].seat_id)

            room_service = RoomService(session)
            room_service.occupy_seat(seat_alice, player_alice)
            room_service.occupy_seat(seat_bob, player_bob)

            room_service.assign_character_to_seat(
                campaign_id,
                seat_alice,
                {**sample_character_data, "name": "Aria Swiftblade"},
                player_alice,
            )
            room_service.assign_character_to_seat(
                campaign_id,
                seat_bob,
                {**sample_character_data, "name": "Borin Ironforge"},
                player_bob,
            )

        captured = {}

        async def fake_generate(self, cid, prompt, info, characters):
            captured["campaign_id"] = cid
            captured["prompt"] = prompt
            captured["info"] = info
            captured["characters"] = characters

        monkeypatch.setattr(
            CampaignService, "_generate_first_turn_async", fake_generate, raising=False
        )

        created_tasks = []
        original_create_task = asyncio.create_task

        def track_task(coro):
            task = original_create_task(coro)
            created_tasks.append(task)
            return task

        monkeypatch.setattr(asyncio, "create_task", track_task)

        result = await campaign_service.start_campaign_from_seats(
            campaign_id,
            campaign_info={
                "title": "Legends of Emberfall",
                "description": "A looming threat gathers on the horizon.",
                "starting_location": "Emberfall Keep",
            },
        )

        assert result["success"] is True
        assert "initializing" in result and result["initializing"] is True

        # Ensure the async hook ran
        if created_tasks:
            await asyncio.gather(*created_tasks)

        assert captured["campaign_id"] == campaign_id
        assert {"Aria Swiftblade", "Borin Ironforge"} == {
            char.get("name") for char in captured["characters"]
        }
        assert "Legends of Emberfall" in captured["prompt"]
        assert "Emberfall Keep" in captured["prompt"]
    finally:
        cleanup_campaign(campaign_id)
