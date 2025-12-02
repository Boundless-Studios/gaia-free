"""Well-formed data structures for combat mechanics resolution."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from gaia_private.models.combat.agent_io.fight.character_status import AgentCharacterStatus
@dataclass
class CombatMechanicsResolution:
    """Result of resolving combat mechanics for a character."""
    character_status: AgentCharacterStatus
    current_ap: Optional[int]
    max_ap: Optional[int]

    def to_tuple(self) -> tuple:
        """Convert to legacy tuple format."""
        return (self.character_status, self.current_ap, self.max_ap)


@dataclass
class CombatContext:
    """Context for combat mechanics resolution."""
    action_resolutions: List[Any] = field(default_factory=list)
    status_effects_applied: Dict[str, List[str]] = field(default_factory=dict)

    def get_authoritative_hp(self, name: str) -> Optional[Dict[str, int]]:
        """Get authoritative HP for a combatant."""
        # This would be overridden in actual implementation
        _ = name  # Suppress unused warning
        return None

    def get_authoritative_ap(self, name: str) -> Optional[Dict[str, int]]:
        """Get authoritative AP for a combatant."""
        # This would be overridden in actual implementation
        _ = name  # Suppress unused warning
        return None

    def get_net_damage(self, name: str) -> int:
        """Get net damage for a combatant."""
        # This would be overridden in actual implementation
        _ = name  # Suppress unused warning
        return 0