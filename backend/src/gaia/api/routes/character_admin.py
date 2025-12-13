"""
Admin endpoints for inspecting and managing characters stored in the database.

Provides read-only access to character data for debugging and administration.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from db.src import get_async_db
from gaia.models.character_db import CharacterProfile
from gaia.models.character_instance_db import CharacterCampaignInstance
from gaia.models.npc_profile_db import NpcProfile
from gaia.api.routes.admin import require_super_admin
from gaia.api.schemas.admin.character_responses import (
    CharacterProfileResponse,
    CharacterDetailResponse,
    CharacterStatsResponse,
    CharacterListResponse,
    NpcProfileResponse,
    NpcDetailResponse,
    NpcListResponse,
    CampaignInstanceInfo,
)

router = APIRouter(
    prefix="/api/admin/characters",
    tags=["admin-characters"],
    dependencies=[Depends(require_super_admin)]
)


@router.get("/stats", response_model=CharacterStatsResponse)
async def get_character_stats(db=Depends(get_async_db)) -> CharacterStatsResponse:
    """Get statistics about characters in the database."""

    # Total profiles
    total_profiles_result = await db.execute(select(func.count(CharacterProfile.character_id)))
    total_profiles = total_profiles_result.scalar() or 0

    # Total instances
    total_instances_result = await db.execute(select(func.count(CharacterCampaignInstance.instance_id)))
    total_instances = total_instances_result.scalar() or 0

    # Total NPCs
    total_npcs_result = await db.execute(select(func.count(NpcProfile.npc_id)))
    total_npcs = total_npcs_result.scalar() or 0

    # By character type
    player_result = await db.execute(
        select(func.count(CharacterProfile.character_id))
        .where(CharacterProfile.character_type == "player")
        .where(CharacterProfile.is_deleted == False)
    )
    player_characters = player_result.scalar() or 0

    npc_result = await db.execute(
        select(func.count(CharacterProfile.character_id))
        .where(CharacterProfile.character_type == "npc")
        .where(CharacterProfile.is_deleted == False)
    )
    npc_characters = npc_result.scalar() or 0

    # By ownership
    system_result = await db.execute(
        select(func.count(CharacterProfile.character_id))
        .where(CharacterProfile.created_by_user_id.is_(None))
        .where(CharacterProfile.is_deleted == False)
    )
    system_characters = system_result.scalar() or 0

    user_result = await db.execute(
        select(func.count(CharacterProfile.character_id))
        .where(CharacterProfile.created_by_user_id.isnot(None))
        .where(CharacterProfile.is_deleted == False)
    )
    user_characters = user_result.scalar() or 0

    # By status
    active_result = await db.execute(
        select(func.count(CharacterProfile.character_id))
        .where(CharacterProfile.is_deleted == False)
    )
    active_characters = active_result.scalar() or 0

    deleted_result = await db.execute(
        select(func.count(CharacterProfile.character_id))
        .where(CharacterProfile.is_deleted == True)
    )
    deleted_characters = deleted_result.scalar() or 0

    # Campaign distribution
    # Average characters per campaign
    campaign_counts = await db.execute(
        select(
            CharacterCampaignInstance.campaign_id,
            func.count(CharacterCampaignInstance.instance_id).label('count')
        )
        .where(CharacterCampaignInstance.is_deleted == False)
        .group_by(CharacterCampaignInstance.campaign_id)
    )
    campaign_count_list = [(row.campaign_id, row.count) for row in campaign_counts.all()]

    characters_per_campaign_avg = 0.0
    most_active_campaign_id = None
    most_active_campaign_count = 0

    if campaign_count_list:
        characters_per_campaign_avg = sum(count for _, count in campaign_count_list) / len(campaign_count_list)
        most_active = max(campaign_count_list, key=lambda x: x[1])
        most_active_campaign_id = str(most_active[0]) if most_active[0] else None
        most_active_campaign_count = most_active[1]

    return CharacterStatsResponse(
        total_profiles=total_profiles,
        total_instances=total_instances,
        total_npcs=total_npcs,
        player_characters=player_characters,
        npc_characters=npc_characters,
        system_characters=system_characters,
        user_characters=user_characters,
        active_characters=active_characters,
        deleted_characters=deleted_characters,
        characters_per_campaign_avg=characters_per_campaign_avg,
        most_active_campaign_id=most_active_campaign_id,
        most_active_campaign_count=most_active_campaign_count,
    )


@router.get("", response_model=CharacterListResponse)
async def list_characters(
    user_id: Optional[str] = None,
    character_type: Optional[str] = None,
    campaign_id: Optional[UUID] = None,
    include_deleted: bool = False,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_async_db),
) -> CharacterListResponse:
    """List character profiles with optional filtering.

    Args:
        user_id: Filter by user who created the character
        character_type: Filter by character type (player/npc)
        campaign_id: Filter by campaign ID (shows characters with instances in this campaign)
        include_deleted: Include soft-deleted characters
        limit: Maximum number of results
        offset: Pagination offset
        db: Database session

    Returns:
        CharacterListResponse with filtered characters
    """
    # Build base query
    if campaign_id:
        # Filter by campaign - join through instances
        query = (
            select(CharacterProfile)
            .join(CharacterCampaignInstance, CharacterProfile.character_id == CharacterCampaignInstance.character_id)
            .where(CharacterCampaignInstance.campaign_id == campaign_id)
        )
    else:
        query = select(CharacterProfile)

    # Apply filters
    if user_id:
        query = query.where(CharacterProfile.created_by_user_id == user_id)

    if character_type:
        query = query.where(CharacterProfile.character_type == character_type)

    if not include_deleted:
        query = query.where(CharacterProfile.is_deleted == False)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    characters = result.scalars().all()

    # Convert to response models
    character_responses = [CharacterProfileResponse.from_model(char) for char in characters]

    return CharacterListResponse(
        characters=character_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{character_id}", response_model=CharacterDetailResponse)
async def get_character(
    character_id: UUID,
    db=Depends(get_async_db),
) -> CharacterDetailResponse:
    """Get detailed information about a character including all campaign instances.

    Args:
        character_id: UUID of the character profile
        db: Database session

    Returns:
        CharacterDetailResponse with full character data

    Raises:
        HTTPException: 404 if character not found
    """
    # Load character profile
    profile_result = await db.execute(
        select(CharacterProfile).where(CharacterProfile.character_id == character_id)
    )
    profile = profile_result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found"
        )

    # Load all campaign instances for this character
    instances_result = await db.execute(
        select(CharacterCampaignInstance)
        .where(CharacterCampaignInstance.character_id == character_id)
        .where(CharacterCampaignInstance.is_deleted == False)
    )
    instances = instances_result.scalars().all()

    return CharacterDetailResponse.from_model(profile, instances)


@router.delete("/{character_id}")
async def soft_delete_character(
    character_id: UUID,
    db=Depends(get_async_db),
) -> Dict[str, Any]:
    """Soft delete a character profile.

    Args:
        character_id: UUID of the character profile
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: 404 if character not found
    """
    # Load character
    profile_result = await db.execute(
        select(CharacterProfile).where(CharacterProfile.character_id == character_id)
    )
    profile = profile_result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found"
        )

    # Soft delete
    profile.soft_delete()
    await db.commit()

    return {
        "success": True,
        "message": f"Character {character_id} soft deleted",
        "character_id": str(character_id),
    }


@router.post("/{character_id}/restore")
async def restore_character(
    character_id: UUID,
    db=Depends(get_async_db),
) -> Dict[str, Any]:
    """Restore a soft-deleted character profile.

    Args:
        character_id: UUID of the character profile
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: 404 if character not found
    """
    # Load character
    profile_result = await db.execute(
        select(CharacterProfile).where(CharacterProfile.character_id == character_id)
    )
    profile = profile_result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found"
        )

    # Restore
    profile.restore()
    await db.commit()

    return {
        "success": True,
        "message": f"Character {character_id} restored",
        "character_id": str(character_id),
    }


# NPC Endpoints

@router.get("/npcs/list", response_model=NpcListResponse)
async def list_npcs(
    user_id: Optional[str] = None,
    campaign_id: Optional[UUID] = None,
    include_deleted: bool = False,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_async_db),
) -> NpcListResponse:
    """List NPC profiles with optional filtering.

    Args:
        user_id: Filter by DM user ID
        campaign_id: Filter by campaign ID
        include_deleted: Include soft-deleted NPCs
        limit: Maximum number of results
        offset: Pagination offset
        db: Database session

    Returns:
        NpcListResponse with filtered NPCs
    """
    # Build query
    query = select(NpcProfile)

    # Apply filters
    if user_id:
        query = query.where(NpcProfile.created_by_user_id == user_id)

    if campaign_id:
        query = query.where(NpcProfile.campaign_id == campaign_id)

    if not include_deleted:
        query = query.where(NpcProfile.is_deleted == False)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    npcs = result.scalars().all()

    # Convert to response models
    npc_responses = [NpcProfileResponse.from_model(npc) for npc in npcs]

    return NpcListResponse(
        npcs=npc_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/npcs/{npc_id}", response_model=NpcDetailResponse)
async def get_npc(
    npc_id: UUID,
    db=Depends(get_async_db),
) -> NpcDetailResponse:
    """Get detailed information about an NPC.

    Args:
        npc_id: UUID of the NPC profile
        db: Database session

    Returns:
        NpcDetailResponse with full NPC data

    Raises:
        HTTPException: 404 if NPC not found
    """
    # Load NPC
    npc_result = await db.execute(
        select(NpcProfile).where(NpcProfile.npc_id == npc_id)
    )
    npc = npc_result.scalar_one_or_none()

    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC {npc_id} not found"
        )

    return NpcDetailResponse.from_model(npc)


@router.post("/npcs/{npc_id}/promote")
async def promote_npc_to_character(
    npc_id: UUID,
    db=Depends(get_async_db),
) -> Dict[str, Any]:
    """Promote an NPC to a full character profile.

    Args:
        npc_id: UUID of the NPC profile
        db: Database session

    Returns:
        Success message with new character ID

    Raises:
        HTTPException: 404 if NPC not found, 400 if already promoted
    """
    # Load NPC
    npc_result = await db.execute(
        select(NpcProfile).where(NpcProfile.npc_id == npc_id)
    )
    npc = npc_result.scalar_one_or_none()

    if not npc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NPC {npc_id} not found"
        )

    if npc.promoted_to_character_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"NPC {npc_id} already promoted to character {npc.promoted_to_character_id}"
        )

    # TODO: Implement NPC promotion logic
    # This would create a CharacterProfile from the NPC data
    # and update the NPC with the promotion details

    return {
        "success": False,
        "message": "NPC promotion not yet implemented",
        "npc_id": str(npc_id),
    }
