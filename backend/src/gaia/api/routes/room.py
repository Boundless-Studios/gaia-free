"""Game room management API endpoints."""

import logging
from dataclasses import asdict
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth.src.flexible_auth import optional_auth
from auth.src.models import User
from db.src.connection import db_manager
from sqlalchemy import select

from gaia_private.session.room_service import RoomService
from gaia_private.session.session_models import CampaignSession, CampaignSessionMember, RoomSeat
from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/rooms", tags=["room"])


class AssignCharacterRequest(BaseModel):
    character_data: dict


class VacateRequest(BaseModel):
    notify_user: bool | None = True


def _require_user_id(current_user: Optional[User]) -> str:
    if not current_user or not hasattr(current_user, "user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return str(current_user.user_id)


def _ensure_room_access(db_session, campaign_id: str, user_id: str) -> None:
    campaign = db_session.get(CampaignSession, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    if campaign.owner_user_id == user_id:
        return

    member = (
        db_session.execute(
            select(CampaignSessionMember).where(
                CampaignSessionMember.session_id == campaign_id,
                CampaignSessionMember.user_id == user_id,
            )
        )
        .scalars()
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="Invite required to access this room")


def _get_room_service():
    with db_manager.get_sync_session() as sync_db:
        yield sync_db, RoomService(sync_db)


def _validate_seat(sync_db, campaign_id: str, seat_id: str) -> RoomSeat:
    try:
        seat_uuid = UUID(seat_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid seat_id") from exc
    seat = sync_db.get(RoomSeat, seat_uuid)
    if not seat or seat.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail=f"Seat {seat_id} not found in campaign {campaign_id}")
    return seat


def _sync_connection_seat(campaign_id: str, user_id: Optional[str], seat_id: Optional[str]) -> None:
    if not user_id:
        return
    try:
        from gaia.connection.connection_registry import connection_registry
        if connection_registry.db_enabled:
            connection_registry.update_user_seat(campaign_id, user_id, seat_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to sync connection seat (campaign=%s user=%s): %s", campaign_id, user_id, exc)


@router.get("/summaries")
async def list_room_summaries(
    role: str = "player",
    current_user: Optional[User] = optional_auth(),
):
    """List room summaries for campaigns the user can access."""
    user_id = _require_user_id(current_user)
    if role not in ("player", "dm"):
        raise HTTPException(status_code=400, detail="Unsupported role")

    try:
        with db_manager.get_sync_session() as sync_db:
            room_service = RoomService(sync_db)
            summaries = room_service.list_room_summaries_for_user(user_id)
            return {"summaries": [asdict(summary) for summary in summaries]}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error listing room summaries: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{campaign_id}")
async def get_room_state(
    campaign_id: str,
    current_user: Optional[User] = optional_auth(),
):
    """Get complete room state with seat information."""
    user_id = _require_user_id(current_user)

    try:
        with db_manager.get_sync_session() as sync_db:
            _ensure_room_access(sync_db, campaign_id, user_id)
            room_service = RoomService(sync_db)
            return room_service.get_room_state(campaign_id)
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Failed to get room state: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error getting room state: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{campaign_id}/summary")
async def get_room_summary(
    campaign_id: str,
    current_user: Optional[User] = optional_auth(),
):
    """Get lightweight room summary for PlayerSession modal."""
    user_id = _require_user_id(current_user)
    try:
        with db_manager.get_sync_session() as sync_db:
            _ensure_room_access(sync_db, campaign_id, user_id)
            room_service = RoomService(sync_db)
            return room_service.get_room_summary(campaign_id, user_id)
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Failed to get room summary: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error getting room summary: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{campaign_id}/seats")
async def list_seats(
    campaign_id: str,
    current_user: Optional[User] = optional_auth(),
):
    """List all seats for a campaign with their current state."""
    user_id = _require_user_id(current_user)
    try:
        with db_manager.get_sync_session() as sync_db:
            _ensure_room_access(sync_db, campaign_id, user_id)
            room_service = RoomService(sync_db)
            state = room_service.get_room_state(campaign_id)
            return {
                "campaign_id": state.campaign_id,
                "seats": state.seats,
                "summary": {
                    "total_seats": len(state.seats),
                    "dm_seats": sum(1 for s in state.seats if s.seat_type == "dm"),
                    "player_seats": sum(1 for s in state.seats if s.seat_type == "player"),
                    "occupied_seats": sum(1 for s in state.seats if s.owner_user_id is not None),
                    "available_seats": sum(1 for s in state.seats if s.owner_user_id is None),
                },
            }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error listing seats: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{campaign_id}/seats/{seat_id}")
async def get_seat(
    campaign_id: str,
    seat_id: str,
    current_user: Optional[User] = optional_auth(),
):
    """Get details of a specific seat."""
    user_id = _require_user_id(current_user)
    try:
        with db_manager.get_sync_session() as sync_db:
            _ensure_room_access(sync_db, campaign_id, user_id)
            seat = _validate_seat(sync_db, campaign_id, seat_id)
            room_service = RoomService(sync_db)
            return room_service._serialize_single_seat(seat)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error getting seat: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{campaign_id}/seats/{seat_id}/occupy")
async def occupy_seat(
    campaign_id: str,
    seat_id: str,
    request: Request,
    current_user: Optional[User] = optional_auth(),
):
    """Occupy a seat (claim it for yourself)."""
    user_id = _require_user_id(current_user)
    owner_was_claimed = False
    new_owner = None
    previous_campaign_owner: Optional[str] = None
    previous_seat_owner: Optional[str] = None
    try:
        with db_manager.get_sync_session() as sync_db:
            _ensure_room_access(sync_db, campaign_id, user_id)
            campaign = sync_db.get(CampaignSession, campaign_id)
            previous_campaign_owner = campaign.owner_user_id if campaign else None
            room_service = RoomService(sync_db)
            seat = _validate_seat(sync_db, campaign_id, seat_id)
            previous_seat_owner = seat.owner_user_id
            seat_info = room_service.occupy_seat(seat_id, user_id)
            if campaign:
                new_owner = campaign.owner_user_id
                owner_was_claimed = bool(not previous_campaign_owner and new_owner)

        from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

        await campaign_broadcaster.broadcast_seat_updated(
            campaign_id,
            seat_info.__dict__,
        )
        _sync_connection_seat(campaign_id, seat_info.owner_user_id, seat_info.seat_id)
        await campaign_broadcaster.handle_seat_change(
            campaign_id,
            seat_info.seat_id,
            previous_seat_owner,
            seat_info.owner_user_id,
        )
        if owner_was_claimed:
            session_registry = getattr(request.app.state, "session_registry", None)
            if session_registry:
                session_registry.register_session(
                    campaign_id,
                    new_owner,
                    owner_email=getattr(current_user, "email", None),
                )
        return seat_info
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Failed to occupy seat: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error occupying seat: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{campaign_id}/seats/{seat_id}/release")
async def release_seat(
    campaign_id: str,
    seat_id: str,
    current_user: Optional[User] = optional_auth(),
):
    """Release a seat (clears owner_user_id)."""
    user_id = _require_user_id(current_user)
    try:
        with db_manager.get_sync_session() as sync_db:
            _ensure_room_access(sync_db, campaign_id, user_id)
            room_service = RoomService(sync_db)
            seat_info = room_service.release_seat(seat_id, user_id)

        from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

        await campaign_broadcaster.broadcast_seat_updated(
            campaign_id,
            seat_info.__dict__,
        )
        _sync_connection_seat(campaign_id, user_id, None)
        await campaign_broadcaster.handle_seat_change(
            campaign_id,
            seat_info.seat_id,
            user_id,
            None,
        )
        return seat_info
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Failed to release seat: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error releasing seat: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{campaign_id}/seats/{seat_id}/vacate")
async def vacate_seat(
    campaign_id: str,
    seat_id: str,
    request: VacateRequest,
    current_user: Optional[User] = optional_auth(),
):
    """DM-only: force-vacate a seat."""
    user_id = _require_user_id(current_user)
    try:
        with db_manager.get_sync_session() as sync_db:
            campaign = sync_db.get(CampaignSession, campaign_id)
            if not campaign:
                raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
            if campaign.owner_user_id != user_id:
                raise HTTPException(status_code=403, detail="Only DM can vacate seats")

            seat = _validate_seat(sync_db, campaign_id, seat_id)
            room_service = RoomService(sync_db)
            seat_info, previous_owner = room_service.vacate_seat(str(seat.seat_id), user_id)

        from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

        await campaign_broadcaster.broadcast_seat_updated(
            campaign_id,
            seat_info.__dict__,
        )
        _sync_connection_seat(campaign_id, previous_owner, None)
        await campaign_broadcaster.handle_seat_change(
            campaign_id,
            seat_info.seat_id,
            previous_owner,
            None,
        )
        if request.notify_user and previous_owner:
            await campaign_broadcaster.broadcast_player_vacated(
                campaign_id,
                seat_info.seat_id,
                previous_owner,
            )

        return {"seat": seat_info, "previous_owner": previous_owner}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error vacating seat: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{campaign_id}/seats/{seat_id}/assign-character")
async def assign_character(
    campaign_id: str,
    seat_id: str,
    request: AssignCharacterRequest,
    current_user: Optional[User] = optional_auth(),
):
    """Create and assign a character to a seat."""
    user_id = _require_user_id(current_user)
    try:
        seat_info = None
        character_id = None
        with db_manager.get_sync_session() as sync_db:
            _ensure_room_access(sync_db, campaign_id, user_id)
            seat = _validate_seat(sync_db, campaign_id, seat_id)
            room_service = RoomService(sync_db)
            character_id = room_service.assign_character_to_seat(
                campaign_id=campaign_id,
                seat_id=str(seat.seat_id),
                character_data=request.character_data,
                user_id=user_id,
            )
            seat_info = room_service._serialize_single_seat(seat)

        from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

        await campaign_broadcaster.broadcast_seat_updated(
            campaign_id,
            seat_info.__dict__,
        )
        await campaign_broadcaster.broadcast_seat_character_update(
            campaign_id,
            seat_info.seat_id,
            character_id,
        )

        return {"success": True, "character_id": character_id}
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Failed to assign character: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error assigning character: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{campaign_id}/start")
async def start_campaign(
    campaign_id: str,
    current_user: Optional[User] = optional_auth(),
):
    """Start a campaign with characters from seats."""
    user_id = _require_user_id(current_user)
    logger.info("Start campaign requested | campaign_id=%s user_id=%s", campaign_id, user_id)
    try:
        with db_manager.get_sync_session() as sync_db:
            campaign = sync_db.get(CampaignSession, campaign_id)
            if not campaign:
                raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
            if campaign.owner_user_id != user_id:
                raise HTTPException(status_code=403, detail="Only campaign owner can start the campaign")
            if campaign.room_status != "active":
                raise HTTPException(status_code=400, detail="DM must join the room before starting campaign")
            if campaign.campaign_status == "active":
                raise HTTPException(status_code=409, detail="Campaign already active")

            seats_with_characters = list(
                sync_db.execute(
                    select(RoomSeat).where(
                        RoomSeat.campaign_id == campaign_id,
                        RoomSeat.seat_type == "player",
                        RoomSeat.character_id.isnot(None),
                    )
                ).scalars()
            )
            if not seats_with_characters:
                raise HTTPException(
                    status_code=400,
                    detail="At least one player seat must have a character before starting",
                )
            logger.info(
                "Validated start prerequisites | campaign_id=%s seat_count=%d status=%s room_status=%s",
                campaign_id,
                len(seats_with_characters),
                campaign.campaign_status,
                campaign.room_status,
            )

        from gaia.api.app import campaign_service as main_campaign_service

        if not main_campaign_service:
            raise HTTPException(status_code=500, detail="Campaign service not initialized")

        # Start the campaign (this updates DB status and creates async task)
        result = await main_campaign_service.start_campaign_from_seats(campaign_id)
        logger.info(
            "CampaignService.start_campaign_from_seats returned | campaign_id=%s initializing=%s keys=%s",
            campaign_id,
            result.get("initializing"),
            sorted(result.keys()),
        )

        # Now broadcast campaign_started AFTER method returns but BEFORE async task streams
        # This ensures frontend receives the event before narrative chunks arrive
        from datetime import datetime, timezone as tz
        from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster

        with db_manager.get_sync_session() as sync_db:
            campaign = sync_db.get(CampaignSession, campaign_id)
            if campaign:
                payload = {
                    "campaign_id": campaign_id,
                    "started_at": campaign.started_at.isoformat() if campaign.started_at else datetime.now(tz.utc).isoformat(),
                    "campaign_status": campaign.campaign_status,
                    "room_status": campaign.room_status,
                    "character_count": len(seats_with_characters),
                }
                logger.info(
                    "Broadcasting room.campaign_started | campaign_id=%s payload_keys=%s",
                    campaign_id,
                    sorted(payload.keys()),
                )
                await campaign_broadcaster.broadcast_campaign_started(
                    campaign_id,
                    payload,
                )
                logger.info(
                    "Campaign started broadcast sent | campaign_id=%s - frontend ready for streaming",
                    campaign_id,
                )

        return result
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to start campaign: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start campaign: {exc}")
