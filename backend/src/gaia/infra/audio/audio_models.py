"""SQLAlchemy models for audio playback state tracking.

DEPRECATED: Import from gaia.infra.audio.models instead.
This file is maintained for backward compatibility.
"""

from gaia.infra.audio.models import (
    PlaybackStatus,
    AudioPlaybackRequest,
    AudioChunk,
    UserAudioQueue,
)
from db.src.db_utils import _uuid_column

__all__ = [
    "PlaybackStatus",
    "AudioPlaybackRequest",
    "AudioChunk",
    "UserAudioQueue",
    "_uuid_column",
]
