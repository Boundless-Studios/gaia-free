"""
Admin endpoints for inspecting and managing scenes stored in the database.

Provides read-only access to scene data for debugging and administration.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from db.src import get_async_db
from gaia.models.scene_db import Scene
from gaia.models.scene_entity_db import SceneEntity
from gaia.api.routes.admin import require_super_admin

router = APIRouter(
    prefix="/api/admin/scenes",
    tags=["admin-scenes"],
    dependencies=[Depends(require_super_admin)]
)


class SceneEntityResponse(BaseModel):
    """Response model for scene entity data."""
    scene_entity_id: str
    entity_id: str
    entity_type: str
    is_present: bool
    role: Optional[str]
    joined_at: Optional[str]
    left_at: Optional[str]
    entity_metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class SceneSummary(BaseModel):
    """Summary view of a scene for list endpoints."""
    scene_id: str
    campaign_id: str
    title: str
    scene_type: str
    in_combat: bool
    is_deleted: bool
    scene_timestamp: str
    entity_count: int


class SceneDetail(BaseModel):
    """Detailed view of a scene."""
    scene_id: str
    campaign_id: str
    title: str
    description: str
    scene_type: str

    # Narrative data
    objectives: List[str]
    outcomes: List[str]

    # Status
    duration_turns: int

    # Turn management
    turn_order: List[str]
    current_turn_index: int
    in_combat: bool
    combat_data: Optional[Dict[str, Any]]

    # Display names and metadata
    scene_metadata: Dict[str, Any]

    # Soft delete
    is_deleted: bool
    deleted_at: Optional[str]

    # Timestamps
    scene_timestamp: str
    last_updated: Optional[str]
    created_at: str
    updated_at: str

    # Entities
    entities: List[SceneEntityResponse]


class SceneStats(BaseModel):
    """Statistics about scenes in the database."""
    total_scenes: int
    active_scenes: int
    deleted_scenes: int
    scenes_by_type: Dict[str, int]
    campaigns_with_scenes: int


@router.get("/stats", response_model=SceneStats)
async def get_scene_stats(db=Depends(get_async_db)) -> SceneStats:
    """Get statistics about scenes in the database."""
    # Total scenes
    total_result = await db.execute(select(func.count(Scene.scene_id)))
    total_scenes = total_result.scalar() or 0

    # Active vs deleted
    active_result = await db.execute(
        select(func.count(Scene.scene_id)).where(Scene.is_deleted == False)
    )
    active_scenes = active_result.scalar() or 0
    deleted_scenes = total_scenes - active_scenes

    # By type
    type_result = await db.execute(
        select(Scene.scene_type, func.count(Scene.scene_id))
        .where(Scene.is_deleted == False)
        .group_by(Scene.scene_type)
    )
    scenes_by_type = {row[0]: row[1] for row in type_result.all()}

    # Unique campaigns
    campaign_result = await db.execute(
        select(func.count(func.distinct(Scene.campaign_id)))
        .where(Scene.is_deleted == False)
    )
    campaigns_with_scenes = campaign_result.scalar() or 0

    return SceneStats(
        total_scenes=total_scenes,
        active_scenes=active_scenes,
        deleted_scenes=deleted_scenes,
        scenes_by_type=scenes_by_type,
        campaigns_with_scenes=campaigns_with_scenes,
    )


@router.get("", response_model=List[SceneSummary])
async def list_scenes(
    campaign_id: Optional[UUID] = None,
    scene_type: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_async_db),
) -> List[SceneSummary]:
    """List scenes with optional filtering."""
    query = select(Scene).options(selectinload(Scene.entities))

    # Apply filters
    if campaign_id:
        query = query.where(Scene.campaign_id == campaign_id)
    if scene_type:
        query = query.where(Scene.scene_type == scene_type)
    if not include_deleted:
        query = query.where(Scene.is_deleted == False)

    # Order and paginate
    query = query.order_by(Scene.scene_timestamp.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    scenes = result.scalars().all()

    return [
        SceneSummary(
            scene_id=scene.scene_id,
            campaign_id=str(scene.campaign_id),
            title=scene.title,
            scene_type=scene.scene_type,
            in_combat=scene.in_combat,
            is_deleted=scene.is_deleted,
            scene_timestamp=scene.scene_timestamp.isoformat(),
            entity_count=len(scene.entities),
        )
        for scene in scenes
    ]


@router.get("/campaign/{campaign_id}", response_model=List[SceneSummary])
async def list_scenes_by_campaign(
    campaign_id: UUID,
    include_deleted: bool = False,
    limit: int = Query(default=50, le=200),
    db=Depends(get_async_db),
) -> List[SceneSummary]:
    """List all scenes for a specific campaign."""
    return await list_scenes(
        campaign_id=campaign_id,
        include_deleted=include_deleted,
        limit=limit,
        offset=0,
        db=db,
    )


@router.get("/{scene_id}", response_model=SceneDetail)
async def get_scene(
    scene_id: str,
    db=Depends(get_async_db),
) -> SceneDetail:
    """Get detailed information about a specific scene."""
    query = (
        select(Scene)
        .where(Scene.scene_id == scene_id)
        .options(selectinload(Scene.entities))
    )
    result = await db.execute(query)
    scene = result.scalar_one_or_none()

    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_id} not found"
        )

    entities = [
        SceneEntityResponse(
            scene_entity_id=str(e.scene_entity_id),
            entity_id=e.entity_id,
            entity_type=e.entity_type,
            is_present=e.is_present,
            role=e.role,
            joined_at=e.joined_at.isoformat() if e.joined_at else None,
            left_at=e.left_at.isoformat() if e.left_at else None,
            entity_metadata=e.entity_metadata or {},
        )
        for e in scene.entities
    ]

    return SceneDetail(
        scene_id=scene.scene_id,
        campaign_id=str(scene.campaign_id),
        title=scene.title,
        description=scene.description,
        scene_type=scene.scene_type,
        objectives=scene.objectives or [],
        outcomes=scene.outcomes or [],
        duration_turns=scene.duration_turns,
        turn_order=scene.turn_order or [],
        current_turn_index=scene.current_turn_index,
        in_combat=scene.in_combat,
        combat_data=scene.combat_data,
        scene_metadata=scene.scene_metadata or {},
        is_deleted=scene.is_deleted,
        deleted_at=scene.deleted_at.isoformat() if scene.deleted_at else None,
        scene_timestamp=scene.scene_timestamp.isoformat(),
        last_updated=scene.last_updated.isoformat() if scene.last_updated else None,
        created_at=scene.created_at.isoformat(),
        updated_at=scene.updated_at.isoformat(),
        entities=entities,
    )


@router.get("/{scene_id}/entities", response_model=List[SceneEntityResponse])
async def get_scene_entities(
    scene_id: str,
    entity_type: Optional[str] = None,
    present_only: bool = False,
    db=Depends(get_async_db),
) -> List[SceneEntityResponse]:
    """Get entities in a scene with optional filtering."""
    query = select(SceneEntity).where(SceneEntity.scene_id == scene_id)

    if entity_type:
        query = query.where(SceneEntity.entity_type == entity_type)
    if present_only:
        query = query.where(SceneEntity.is_present == True)

    result = await db.execute(query)
    entities = result.scalars().all()

    if not entities:
        # Check if scene exists
        scene_result = await db.execute(
            select(Scene.scene_id).where(Scene.scene_id == scene_id)
        )
        if not scene_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scene {scene_id} not found"
            )

    return [
        SceneEntityResponse(
            scene_entity_id=str(e.scene_entity_id),
            entity_id=e.entity_id,
            entity_type=e.entity_type,
            is_present=e.is_present,
            role=e.role,
            joined_at=e.joined_at.isoformat() if e.joined_at else None,
            left_at=e.left_at.isoformat() if e.left_at else None,
            entity_metadata=e.entity_metadata or {},
        )
        for e in entities
    ]


@router.delete("/{scene_id}")
async def soft_delete_scene(
    scene_id: str,
    db=Depends(get_async_db),
) -> Dict[str, str]:
    """Soft delete a scene (mark as deleted)."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(Scene).where(Scene.scene_id == scene_id)
    )
    scene = result.scalar_one_or_none()

    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_id} not found"
        )

    if scene.is_deleted:
        return {"message": f"Scene {scene_id} was already deleted"}

    scene.is_deleted = True
    scene.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": f"Scene {scene_id} soft deleted successfully"}


@router.post("/{scene_id}/restore")
async def restore_scene(
    scene_id: str,
    db=Depends(get_async_db),
) -> Dict[str, str]:
    """Restore a soft-deleted scene."""
    result = await db.execute(
        select(Scene).where(Scene.scene_id == scene_id)
    )
    scene = result.scalar_one_or_none()

    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_id} not found"
        )

    if not scene.is_deleted:
        return {"message": f"Scene {scene_id} is not deleted"}

    scene.is_deleted = False
    scene.deleted_at = None
    await db.commit()

    return {"message": f"Scene {scene_id} restored successfully"}
