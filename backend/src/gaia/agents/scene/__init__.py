"""Scene-related agents - re-exports from gaia_private."""

# All scene agents are now in gaia_private - re-export for backward compatibility
from gaia_private.agents.scene import (
    ActivePlayerOptionsAgent,
    ObservingPlayerOptionsAgent,
    PlayerOptionsAgent,  # Alias for ObservingPlayerOptionsAgent
)

__all__ = [
    "ActivePlayerOptionsAgent",
    "ObservingPlayerOptionsAgent",
    "PlayerOptionsAgent",
]
