"""Playback status enumeration."""

from enum import Enum


class PlaybackStatus(str, Enum):
    """Status of audio playback."""
    PENDING = "pending"  # Request queued, not yet started
    GENERATING = "generating"  # Request is actively generating chunks
    GENERATED = "generated"  # Request chunks have been generated and are ready for playback
    COMPLETED = "completed"  # Request has finished all chunks
    PLAYED = "played"  # Individual chunk has been played
    FAILED = "failed"  # Request failed during generation or playback
