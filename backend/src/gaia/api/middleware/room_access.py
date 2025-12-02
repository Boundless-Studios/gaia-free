"""Utilities for enforcing game room access rules on mutating endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select

from db.src.connection import db_manager
from gaia_private.session.session_models import CampaignSession, RoomSeat


class RoomAccessGuard:
    """Provides DM/Player gatekeeping helpers for gameplay endpoints.

    Currently applied to:
      - `/api/chat` (primary turn submission endpoint)

    TODO:
      - Apply to `/api/chat/compat`, campaign action routes, audio triggers,
        and websocket handlers once those flows adopt the room API.
    """


    def ensure_dm_present(self, campaign_id: str) -> None:
        """Ensure the DM has joined the room before allowing actions."""
        with db_manager.get_sync_session() as session:
            campaign = session.get(CampaignSession, campaign_id)
            if not campaign:
                raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
            if campaign.room_status != "active":
                raise HTTPException(status_code=409, detail="Waiting for DM")

    def ensure_player_has_character(
        self,
        campaign_id: str,
        user_id: Optional[str],
    ) -> None:
        """Ensure the caller owns a seat with a bound character."""
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        with db_manager.get_sync_session() as session:
            campaign = session.get(CampaignSession, campaign_id)
            if not campaign:
                raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

            if campaign.owner_user_id == user_id:
                return  # DM is exempt

            seat = (
                session.execute(
                    select(RoomSeat).where(
                        RoomSeat.campaign_id == campaign_id,
                        RoomSeat.seat_type == "player",
                        RoomSeat.owner_user_id == user_id,
                    )
                )
                .scalars()
                .first()
            )

            if not seat:
                raise HTTPException(status_code=400, detail="Seat must be claimed before playing")
            if not seat.character_id:
                raise HTTPException(status_code=400, detail="Seat requires character")
