"""
API routes for game preferences management

Provides CRUD endpoints for:
- DM Preferences (per-user settings for dungeon masters)
- Player Preferences (per-user settings for players)
- Campaign Settings (per-campaign configuration)
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.src import get_async_db, DMPreferences, PlayerPreferences, CampaignSettings
from auth.src.middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class DMPreferencesUpdate(BaseModel):
    """Request schema for updating DM preferences"""
    preferred_dm_model: Optional[str] = Field(None, max_length=100)
    preferred_npc_model: Optional[str] = Field(None, max_length=100)
    preferred_combat_model: Optional[str] = Field(None, max_length=100)
    show_dice_rolls: Optional[bool] = None
    auto_generate_portraits: Optional[bool] = None
    auto_scene_image_generation: Optional[bool] = None
    auto_audio_playback: Optional[bool] = None
    default_difficulty: Optional[str] = Field(None, max_length=50)
    enable_critical_success: Optional[bool] = None
    enable_critical_failure: Optional[bool] = None


class DMPreferencesResponse(BaseModel):
    """Response schema for DM preferences"""
    preference_id: UUID
    user_id: UUID
    preferred_dm_model: Optional[str]
    preferred_npc_model: Optional[str]
    preferred_combat_model: Optional[str]
    show_dice_rolls: bool
    auto_generate_portraits: bool
    auto_scene_image_generation: bool
    auto_audio_playback: bool
    default_difficulty: str
    enable_critical_success: bool
    enable_critical_failure: bool

    class Config:
        from_attributes = True


class PlayerPreferencesUpdate(BaseModel):
    """Request schema for updating player preferences"""
    enable_audio: Optional[bool] = None
    audio_volume: Optional[int] = Field(None, ge=0, le=100)
    enable_background_music: Optional[bool] = None
    enable_sound_effects: Optional[bool] = None
    enable_turn_notifications: Optional[bool] = None
    enable_combat_notifications: Optional[bool] = None


class PlayerPreferencesResponse(BaseModel):
    """Response schema for player preferences"""
    preference_id: UUID
    user_id: UUID
    enable_audio: bool
    audio_volume: int
    enable_background_music: bool
    enable_sound_effects: bool
    enable_turn_notifications: bool
    enable_combat_notifications: bool

    class Config:
        from_attributes = True


class CampaignSettingsUpdate(BaseModel):
    """Request schema for updating campaign settings"""
    tone: Optional[str] = Field(None, max_length=50)
    pace: Optional[str] = Field(None, max_length=50)
    difficulty: Optional[str] = Field(None, max_length=50)
    max_players: Optional[int] = Field(None, ge=1, le=12)
    min_players: Optional[int] = Field(None, ge=1, le=12)
    allow_pvp: Optional[bool] = None
    dm_model: Optional[str] = Field(None, max_length=100)
    npc_model: Optional[str] = Field(None, max_length=100)
    combat_model: Optional[str] = Field(None, max_length=100)
    narration_model: Optional[str] = Field(None, max_length=100)


class CampaignSettingsResponse(BaseModel):
    """Response schema for campaign settings"""
    settings_id: UUID
    campaign_id: UUID
    tone: str
    pace: str
    difficulty: str
    max_players: int
    min_players: int
    allow_pvp: bool
    dm_model: Optional[str]
    npc_model: Optional[str]
    combat_model: Optional[str]
    narration_model: Optional[str]

    class Config:
        from_attributes = True


# =============================================================================
# DM Preferences Endpoints
# =============================================================================

@router.get("/dm", response_model=DMPreferencesResponse)
async def get_dm_preferences(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_async_db),
) -> DMPreferencesResponse:
    """Get DM preferences for the current user. Creates default if not exists."""
    result = await db.execute(
        select(DMPreferences).where(DMPreferences.user_id == current_user.user_id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Create default preferences
        prefs = DMPreferences(user_id=current_user.user_id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
        logger.info(f"Created default DM preferences for user {current_user.user_id}")

    return DMPreferencesResponse.model_validate(prefs)


@router.put("/dm", response_model=DMPreferencesResponse)
async def update_dm_preferences(
    updates: DMPreferencesUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_async_db),
) -> DMPreferencesResponse:
    """Update DM preferences for the current user. Creates if not exists."""
    result = await db.execute(
        select(DMPreferences).where(DMPreferences.user_id == current_user.user_id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = DMPreferences(user_id=current_user.user_id)
        db.add(prefs)

    # Apply updates (only non-None values)
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(prefs, field, value)

    await db.commit()
    await db.refresh(prefs)
    logger.info(f"Updated DM preferences for user {current_user.user_id}")

    return DMPreferencesResponse.model_validate(prefs)


# =============================================================================
# Player Preferences Endpoints
# =============================================================================

@router.get("/player", response_model=PlayerPreferencesResponse)
async def get_player_preferences(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_async_db),
) -> PlayerPreferencesResponse:
    """Get player preferences for the current user. Creates default if not exists."""
    result = await db.execute(
        select(PlayerPreferences).where(PlayerPreferences.user_id == current_user.user_id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Create default preferences
        prefs = PlayerPreferences(user_id=current_user.user_id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
        logger.info(f"Created default player preferences for user {current_user.user_id}")

    return PlayerPreferencesResponse.model_validate(prefs)


@router.put("/player", response_model=PlayerPreferencesResponse)
async def update_player_preferences(
    updates: PlayerPreferencesUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_async_db),
) -> PlayerPreferencesResponse:
    """Update player preferences for the current user. Creates if not exists."""
    result = await db.execute(
        select(PlayerPreferences).where(PlayerPreferences.user_id == current_user.user_id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = PlayerPreferences(user_id=current_user.user_id)
        db.add(prefs)

    # Apply updates (only non-None values)
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(prefs, field, value)

    await db.commit()
    await db.refresh(prefs)
    logger.info(f"Updated player preferences for user {current_user.user_id}")

    return PlayerPreferencesResponse.model_validate(prefs)


# =============================================================================
# Campaign Settings Endpoints
# =============================================================================

@router.get("/campaign/{campaign_id}", response_model=CampaignSettingsResponse)
async def get_campaign_settings(
    campaign_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_async_db),
) -> CampaignSettingsResponse:
    """Get settings for a campaign. Creates default if not exists."""
    # TODO: Add permission check - user must be DM or player in campaign

    result = await db.execute(
        select(CampaignSettings).where(CampaignSettings.campaign_id == campaign_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings
        settings = CampaignSettings(campaign_id=campaign_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        logger.info(f"Created default campaign settings for campaign {campaign_id}")

    return CampaignSettingsResponse.model_validate(settings)


@router.put("/campaign/{campaign_id}", response_model=CampaignSettingsResponse)
async def update_campaign_settings(
    campaign_id: UUID,
    updates: CampaignSettingsUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_async_db),
) -> CampaignSettingsResponse:
    """Update settings for a campaign. Creates if not exists."""
    # TODO: Add permission check - user must be DM of campaign

    result = await db.execute(
        select(CampaignSettings).where(CampaignSettings.campaign_id == campaign_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = CampaignSettings(campaign_id=campaign_id)
        db.add(settings)

    # Apply updates (only non-None values)
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)
    logger.info(f"Updated campaign settings for campaign {campaign_id}")

    return CampaignSettingsResponse.model_validate(settings)
