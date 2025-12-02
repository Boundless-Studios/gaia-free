"""Quest data model."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class QuestInfo:
    """Information about a quest."""
    quest_id: str
    title: str
    description: str
    status: str = "active"  # active, completed, failed, abandoned
    objectives: List[str] = field(default_factory=list)
    rewards: List[str] = field(default_factory=list)
    giver_npc: Optional[str] = None
    location: Optional[str] = None
    deadline: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "quest_id": self.quest_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "objectives": self.objectives,
            "rewards": self.rewards,
            "giver_npc": self.giver_npc,
            "location": self.location,
            "deadline": self.deadline,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestInfo':
        """Create from dictionary."""
        return cls(**data)