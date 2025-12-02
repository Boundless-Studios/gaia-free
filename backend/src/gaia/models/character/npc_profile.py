"""Profile metadata for NPCs that may not have full character sheets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from gaia.models.character.enums import CharacterRole, CharacterCapability


@dataclass
class NpcProfile:
    """Lightweight narrative profile for non-player characters."""

    npc_id: str
    display_name: str
    role: CharacterRole = CharacterRole.NPC_SUPPORT
    description: str = ""
    tags: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    has_full_sheet: bool = False
    capabilities: CharacterCapability = CharacterCapability.NARRATIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def mark_updated(self) -> None:
        """Refresh the profile's updated timestamp."""
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the profile for persistence."""
        return {
            "npc_id": self.npc_id,
            "display_name": self.display_name,
            "role": self.role.value,
            "description": self.description,
            "tags": list(self.tags),
            "relationships": dict(self.relationships),
            "notes": list(self.notes),
            "has_full_sheet": self.has_full_sheet,
            "capabilities": int(self.capabilities),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NpcProfile":
        """Deserialize an NPC profile from stored representation."""
        role_value = data.get("role", CharacterRole.NPC_SUPPORT.value)
        try:
            role = role_value if isinstance(role_value, CharacterRole) else CharacterRole(role_value)
        except ValueError:
            role = CharacterRole.NPC_SUPPORT

        capabilities_value = data.get("capabilities", CharacterCapability.NARRATIVE)
        if isinstance(capabilities_value, CharacterCapability):
            capabilities = capabilities_value
        elif isinstance(capabilities_value, int):
            capabilities = CharacterCapability(capabilities_value)
        elif isinstance(capabilities_value, list):
            flag = CharacterCapability.NONE
            for entry in capabilities_value:
                if isinstance(entry, str):
                    try:
                        flag |= CharacterCapability[entry.upper()]
                    except KeyError:
                        continue
                elif isinstance(entry, int):
                    flag |= CharacterCapability(entry)
            capabilities = flag if flag != CharacterCapability.NONE else CharacterCapability.NARRATIVE
        else:
            capabilities = CharacterCapability.NARRATIVE

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif not isinstance(created_at, datetime):
            created_at = datetime.utcnow()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif not isinstance(updated_at, datetime):
            updated_at = datetime.utcnow()

        return cls(
            npc_id=data.get("npc_id", ""),
            display_name=data.get("display_name", "Unknown"),
            role=role,
            description=data.get("description", ""),
            tags=data.get("tags", []) or [],
            relationships=data.get("relationships", {}) or {},
            notes=data.get("notes", []) or [],
            has_full_sheet=data.get("has_full_sheet", False),
            capabilities=capabilities,
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get("metadata", {}) or {},
        )
