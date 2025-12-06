"""Gaia agents package - re-exports agents from gaia_private."""

# All agents are now in gaia_private - re-export for backward compatibility
from gaia_private.agents.scene import (
    ActivePlayerOptionsAgent,
    ObservingPlayerOptionsAgent,
)

__all__ = [
    "ActivePlayerOptionsAgent",
    "ObservingPlayerOptionsAgent",
]
