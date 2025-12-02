"""Initialize room seats for campaigns that don't have them yet.

This runs during application startup after SessionRegistry seeds campaigns
from the filesystem into the database.
"""

import logging
from typing import Optional

from sqlalchemy import select
from db.src.connection import db_manager
from gaia_private.session.session_models import CampaignSession, RoomSeat
from gaia_private.session.room_service import RoomService

try:
    from gaia_private.session.session_registry import SessionRegistry
except Exception:  # noqa: BLE001
    SessionRegistry = None  # type: ignore[misc]

logger = logging.getLogger(__name__)


def _get_player_count_from_metadata(campaign_id: str) -> Optional[int]:
    """Try to determine player count from campaign metadata.

    Args:
        campaign_id: The campaign identifier

    Returns:
        Number of players if found, None otherwise
    """
    try:
        from pathlib import Path
        import os

        base_path = os.getenv("CAMPAIGN_STORAGE_PATH")
        if not base_path:
            return None

        # Try to load metadata from campaign storage
        storage_path = Path(base_path) / campaign_id / "metadata.json"
        if storage_path.exists():
            import json
            with open(storage_path, 'r') as f:
                metadata = json.load(f)
                # Check for player_count in world_settings or max_player_seats
                if "max_player_seats" in metadata:
                    return metadata["max_player_seats"]
                if "world_settings" in metadata:
                    ws = metadata["world_settings"]
                    if "player_count" in ws:
                        return ws["player_count"]

        # Try counting character files
        characters_dir = Path(base_path) / campaign_id / "data" / "characters"
        if characters_dir.exists():
            char_files = list(characters_dir.glob("*.json"))
            if char_files:
                return len(char_files)

    except Exception as e:
        logger.debug(f"Could not determine player count for {campaign_id}: {e}")

    return None


async def initialize_campaign_rooms() -> dict:
    """Initialize room seats for campaigns that were seeded from filesystem.

    This function:
    1. Finds all campaigns without room seats
    2. Determines player count from campaign metadata (defaults to 4)
    3. Creates room structure (1 DM seat + N player seats)

    Returns:
        Dict with statistics about initialization
    """
    if not db_manager.sync_engine:
        logger.warning("Database not available, skipping room initialization")
        return {"skipped": True, "reason": "Database not available"}

    try:
        registry = None
        if SessionRegistry:
            try:
                registry = SessionRegistry()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "SessionRegistry unavailable during room initialization; "
                    "owner backfill skipped: %s",
                    exc,
                )

        stats = {
            "campaigns_checked": 0,
            "campaigns_initialized": 0,
            "seats_created": 0,
            "errors": 0,
        }

        with db_manager.get_sync_session() as session:
            # Find campaigns without any seats using a simple query
            stmt = select(CampaignSession.session_id).where(
                ~CampaignSession.session_id.in_(
                    select(RoomSeat.campaign_id).distinct()
                )
            )
            campaign_ids_without_seats = session.execute(stmt).scalars().all()
            stats["campaigns_checked"] = len(campaign_ids_without_seats)

            # Now fetch the full campaign objects for those IDs
            campaigns_without_seats = []
            if campaign_ids_without_seats:
                campaigns_without_seats = session.query(CampaignSession).filter(
                    CampaignSession.session_id.in_(campaign_ids_without_seats)
                ).all()

            if not campaigns_without_seats:
                logger.info("All campaigns already have room seats")
                return stats

            logger.info(f"Found {len(campaigns_without_seats)} campaigns without seats, initializing...")

            room_service = RoomService(session)

            for campaign in campaigns_without_seats:
                try:
                    campaign_id = campaign.session_id
                    resolved_owner_id = campaign.owner_user_id

                    # Determine player count
                    player_count = _get_player_count_from_metadata(campaign_id)
                    if player_count is None:
                        player_count = 4  # Default fallback

                    # Set max_player_seats if not already set
                    if campaign.max_player_seats is None:
                        campaign.max_player_seats = player_count

                    # Set room_status - always waiting for DM initially
                    if campaign.room_status is None:
                        campaign.room_status = "waiting_for_dm"

                    # Set campaign_status for campaigns seeded from filesystem
                    if campaign.campaign_status is None:
                        # All campaigns that exist in the filesystem are active campaigns
                        # They were created, played, and persisted to files
                        # Only brand-new API-created campaigns should be 'setup'
                        campaign.campaign_status = "active"

                    # Backfill missing owner from session registry metadata
                    if not resolved_owner_id and registry:
                        meta = registry.get_metadata(campaign_id)
                        owner_candidate = (meta or {}).get("owner_user_id")
                        if owner_candidate:
                            resolved_owner_id = owner_candidate
                            campaign.owner_user_id = owner_candidate

                    # Create room structure
                    owner_user_id = resolved_owner_id or ""
                    max_seats = campaign.max_player_seats or player_count
                    room_service.create_room(
                        campaign_id=campaign_id,
                        owner_user_id=owner_user_id,
                        max_player_seats=max_seats,
                    )

                    stats["campaigns_initialized"] += 1
                    # 1 DM seat + N player seats
                    stats["seats_created"] += (1 + max_seats)

                    logger.debug(
                        f"Initialized room for {campaign_id}: "
                        f"{campaign.max_player_seats or player_count} player seats"
                    )

                except Exception as e:
                    logger.error(f"Failed to initialize room for {campaign.session_id}: {e}")
                    stats["errors"] += 1

            session.commit()

            logger.info(
                f"Room initialization complete: "
                f"{stats['campaigns_initialized']} campaigns, "
                f"{stats['seats_created']} seats created"
            )

            return stats

    except Exception as e:
        logger.error(f"Room initialization failed: {e}", exc_info=True)
        return {"error": str(e)}
