"""Connection status enumeration."""

from enum import Enum


class ConnectionStatus(str, Enum):
    """Status of a WebSocket connection."""
    CONNECTED = "connected"  # Currently active
    DISCONNECTED = "disconnected"  # Cleanly closed
    FAILED = "failed"  # Error/timeout
    SUPERSEDED = "superseded"  # Replaced by newer connection
