"""Shared dataclasses and helpers for scene participant tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from gaia.models.character.enums import CharacterRole, CharacterCapability


@dataclass
class SceneParticipant:
    """Represents a character or entity participating in a scene."""

    character_id: Optional[str]
    display_name: str
    role: CharacterRole = CharacterRole.NPC_SUPPORT
    capabilities: CharacterCapability = CharacterCapability.NONE
    is_present: bool = True
    joined_at: datetime = field(default_factory=datetime.utcnow)
    left_at: Optional[datetime] = None
    source: Optional[str] = None  # e.g., "dm", "combat_initiator"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize participant for persistence."""
        return {
            "character_id": self.character_id,
            "display_name": self.display_name,
            "role": self.role.value,
            "capabilities": int(self.capabilities),
            "is_present": self.is_present,
            "joined_at": self.joined_at.isoformat(),
            "left_at": self.left_at.isoformat() if self.left_at else None,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneParticipant":
        """Deserialize participant from stored representation."""
        role_value = data.get("role", CharacterRole.NPC_SUPPORT.value)
        try:
            role = role_value if isinstance(role_value, CharacterRole) else CharacterRole(role_value)
        except ValueError:
            role = CharacterRole.NPC_SUPPORT

        capabilities_value = data.get("capabilities", 0)
        if isinstance(capabilities_value, CharacterCapability):
            capabilities = capabilities_value
        elif isinstance(capabilities_value, int):
            capabilities = CharacterCapability(capabilities_value)
        elif isinstance(capabilities_value, list):
            flag = CharacterCapability.NONE
            for value in capabilities_value:
                if isinstance(value, str):
                    try:
                        flag |= CharacterCapability[value.upper()]
                    except KeyError:
                        continue
                elif isinstance(value, int):
                    flag |= CharacterCapability(value)
            capabilities = flag
        else:
            capabilities = CharacterCapability.NONE

        joined_at = data.get("joined_at")
        if isinstance(joined_at, str):
            joined_at = datetime.fromisoformat(joined_at)
        elif not isinstance(joined_at, datetime):
            joined_at = datetime.utcnow()

        left_at = data.get("left_at")
        if isinstance(left_at, str):
            left_at = datetime.fromisoformat(left_at)
        elif not isinstance(left_at, datetime):
            left_at = None

        return cls(
            character_id=data.get("character_id"),
            display_name=data.get("display_name", "Unknown"),
            role=role,
            capabilities=capabilities,
            is_present=data.get("is_present", True),
            joined_at=joined_at,
            left_at=left_at,
            source=data.get("source"),
            metadata=data.get("metadata", {}) or {},
        )

    def mark_departed(self, timestamp: Optional[datetime] = None) -> None:
        """Mark participant as no longer present."""
        self.is_present = False
        self.left_at = timestamp or datetime.utcnow()

    def restore(self, timestamp: Optional[datetime] = None) -> None:
        """Mark participant as present again."""
        self.is_present = True
        self.joined_at = timestamp or datetime.utcnow()
        self.left_at = None
