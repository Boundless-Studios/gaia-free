"""
SQLAlchemy models for user preferences and campaign settings

These models provide user-specific preferences for DMs and players,
as well as campaign-level configuration settings.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column, String, Boolean, Integer, ForeignKey,
    CheckConstraint, JSON, UUID
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.src.base import BaseModel


class DMPreferences(BaseModel):
    """Dungeon Master user preferences model"""

    __tablename__ = "dm_preferences"
    __table_args__ = (
        {"schema": "game"}
    )

    preference_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Model configuration
    preferred_dm_model: Mapped[Optional[str]] = mapped_column(String(100))
    preferred_npc_model: Mapped[Optional[str]] = mapped_column(String(100))
    preferred_combat_model: Mapped[Optional[str]] = mapped_column(String(100))

    # UI/Display preferences
    show_dice_rolls: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_generate_portraits: Mapped[bool] = mapped_column(Boolean, default=True)
    narration_style: Mapped[str] = mapped_column(String(50), default="balanced")

    # Gameplay preferences
    default_difficulty: Mapped[str] = mapped_column(String(50), default="medium")
    enable_critical_success: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_critical_failure: Mapped[bool] = mapped_column(Boolean, default=True)

    # Metadata
    preferences_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    def __repr__(self):
        return f"<DMPreferences(user_id={self.user_id}, dm_model={self.preferred_dm_model})>"


class PlayerPreferences(BaseModel):
    """Player user preferences model"""

    __tablename__ = "player_preferences"
    __table_args__ = (
        CheckConstraint(
            "audio_volume >= 0 AND audio_volume <= 100",
            name="check_audio_volume_range"
        ),
        {"schema": "game"}
    )

    preference_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Display preferences
    theme: Mapped[str] = mapped_column(String(50), default="dark")
    font_size: Mapped[str] = mapped_column(String(20), default="medium")
    show_animations: Mapped[bool] = mapped_column(Boolean, default=True)

    # Audio preferences
    enable_audio: Mapped[bool] = mapped_column(Boolean, default=True)
    audio_volume: Mapped[int] = mapped_column(Integer, default=80)
    enable_background_music: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_sound_effects: Mapped[bool] = mapped_column(Boolean, default=True)

    # Notification preferences
    enable_turn_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_combat_notifications: Mapped[bool] = mapped_column(Boolean, default=True)

    # Metadata
    preferences_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    def __repr__(self):
        return f"<PlayerPreferences(user_id={self.user_id}, theme={self.theme})>"


class CampaignSettings(BaseModel):
    """Campaign-level settings model"""

    __tablename__ = "campaign_settings"
    __table_args__ = (
        {"schema": "game"}
    )

    settings_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    campaign_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game.campaigns.campaign_id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Campaign style and tone
    tone: Mapped[str] = mapped_column(String(50), default="balanced")
    pace: Mapped[str] = mapped_column(String(50), default="medium")
    difficulty: Mapped[str] = mapped_column(String(50), default="medium")

    # Player configuration
    max_players: Mapped[int] = mapped_column(Integer, default=6)
    min_players: Mapped[int] = mapped_column(Integer, default=1)
    allow_pvp: Mapped[bool] = mapped_column(Boolean, default=False)

    # Model configuration for this campaign
    dm_model: Mapped[Optional[str]] = mapped_column(String(100))
    npc_model: Mapped[Optional[str]] = mapped_column(String(100))
    combat_model: Mapped[Optional[str]] = mapped_column(String(100))
    narration_model: Mapped[Optional[str]] = mapped_column(String(100))

    # Gameplay rules
    allow_homebrew: Mapped[bool] = mapped_column(Boolean, default=False)
    use_milestone_leveling: Mapped[bool] = mapped_column(Boolean, default=True)
    starting_level: Mapped[int] = mapped_column(Integer, default=1)
    max_level: Mapped[int] = mapped_column(Integer, default=20)

    # Session settings
    session_length_minutes: Mapped[int] = mapped_column(Integer, default=180)
    breaks_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Metadata
    settings_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    def __repr__(self):
        return f"<CampaignSettings(campaign_id={self.campaign_id}, tone={self.tone}, pace={self.pace})>"
