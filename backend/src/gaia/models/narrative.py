"""Narrative data model for story progression."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class NarrativeInfo:
    """Narrative and story progression information."""
    narrative_id: str
    content: str
    narrative_type: str  # description, dialog, action, outcome
    speaker: Optional[str] = None  # character_id or npc_id if dialog
    scene_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "narrative_id": self.narrative_id,
            "content": self.content,
            "narrative_type": self.narrative_type,
            "speaker": self.speaker,
            "scene_id": self.scene_id,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NarrativeInfo':
        """Create from dictionary."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)