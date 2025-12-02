"""Turn data model for explicit turn management in D&D campaigns."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class TurnType(Enum):
    """Types of turns in the game."""
    PLAYER = "player"  # Player character turn
    NPC = "npc"  # Non-player character turn
    ENVIRONMENTAL = "environmental"  # Environmental effects
    NARRATIVE = "narrative"  # Story progression


class TurnStatus(Enum):
    """Status of a turn."""
    ACTIVE = "active"  # Turn in progress
    COMPLETED = "completed"  # Turn finished


class ActionType(Enum):
    """Types of actions available during a turn."""
    # Combat Actions
    MOVE = "move"
    ATTACK = "attack"
    CAST_SPELL = "cast_spell"
    USE_ABILITY = "use_ability"
    DEFEND = "defend"
    
    # Interaction Actions
    DIALOG = "dialog"
    EXAMINE = "examine"
    USE_ITEM = "use_item"
    TRADE = "trade"
    
    # Exploration Actions
    EXPLORE = "explore"
    SEARCH = "search"
    TRAVEL = "travel"
    REST = "rest"
    
    # Meta Actions
    PASS = "pass"
    END_TURN = "end_turn"


@dataclass
class TurnAction:
    """Represents an available action during a turn."""
    action_id: str  # Unique identifier
    action_type: Optional[ActionType] = None  # Type of action
    name: Optional[str] = None  # Display name
    description: Optional[str] = None  # What the action does
    
    # Optional fields
    targets: List[str] = field(default_factory=list)  # Valid targets
    requirements: Dict[str, Any] = field(default_factory=dict)  # Prerequisites
    cost: Optional[Dict[str, int]] = None  # Resource costs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {"action_id": self.action_id}
        if self.action_type:
            result["action_type"] = self.action_type.value
        if self.name:
            result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.targets:
            result["targets"] = self.targets
        if self.requirements:
            result["requirements"] = self.requirements
        if self.cost:
            result["cost"] = self.cost
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TurnAction':
        """Create from dictionary."""
        if isinstance(data, str):
            return cls(action_id=data)

        if not isinstance(data, dict):
            raise ValueError(f"Unsupported TurnAction data: {data}")

        action_id = data.get("action_id") or data.get("id")
        if not action_id:
            raise ValueError("TurnAction data missing 'action_id'")

        action_type = data.get("action_type")
        if isinstance(action_type, str):
            try:
                action_type = ActionType(action_type)
            except ValueError:
                action_type = None
        elif not isinstance(action_type, ActionType):
            action_type = None

        return cls(
            action_id=action_id,
            action_type=action_type,
            name=data.get("name"),
            description=data.get("description"),
            targets=data.get("targets", []) or [],
            requirements=data.get("requirements", {}) or {},
            cost=data.get("cost")
        )


@dataclass
class Turn:
    """Represents a single turn in the game."""
    # Identity
    turn_id: str  # Unique identifier
    campaign_id: str  # Associated campaign
    turn_number: int  # Sequential turn number in campaign
    
    # Ownership
    character_id: str  # Character taking the turn (DM/NPC/PC)
    character_name: Optional[str] = None  # Display name of acting character
    turn_type: TurnType = TurnType.PLAYER  # Type of turn
    
    # Status
    status: TurnStatus = TurnStatus.ACTIVE  # Current status
    
    # Scene context
    scene_id: Optional[str] = None  # Current scene
    scene_type: Optional[str] = None  # Type of scene
    
    # Actions - can be either list of action IDs (compact) or TurnAction objects (verbose)
    available_actions: List[Any] = field(default_factory=list)  # What can be done
    selected_action: Optional[TurnAction] = None  # What was chosen
    action_result: Optional[Dict[str, Any]] = None  # Result of the action
    
    # Turn linking
    previous_turn_id: Optional[str] = None  # Link to previous turn
    next_turn_id: Optional[str] = None  # Link to next turn (set when transitioning)

    # Generic context
    context: Dict[str, Any] = field(default_factory=dict)  # Flexible context data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "turn_id": self.turn_id,
            "campaign_id": self.campaign_id,
            "turn_number": self.turn_number,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "turn_type": self.turn_type.value,
            "status": self.status.value,
            "scene_id": self.scene_id,
            "scene_type": self.scene_type,
            "available_actions": [
                action.to_dict() if hasattr(action, 'to_dict') else action
                for action in self.available_actions
            ],
            "selected_action": self.selected_action.to_dict() if self.selected_action else None,
            "action_result": self.action_result,
            "previous_turn_id": self.previous_turn_id,
            "next_turn_id": self.next_turn_id,
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Turn':
        """Create from dictionary."""
        # Make a copy to avoid mutating original
        data = dict(data)

        # Convert enums
        if isinstance(data.get("turn_type"), str):
            data["turn_type"] = TurnType(data["turn_type"])
        if isinstance(data.get("status"), str):
            data["status"] = TurnStatus(data["status"])

        # Backward compatibility: map legacy player_id -> character_name
        if "character_name" not in data and "player_id" in data:
            data["character_name"] = data.pop("player_id")

        # Convert actions - keep as strings if they're strings (compact format)
        if "available_actions" in data:
            data["available_actions"] = [
                TurnAction.from_dict(action) if isinstance(action, dict)
                else action  # Keep strings as strings
                for action in data["available_actions"]
            ]
        if data.get("selected_action") and isinstance(data["selected_action"], dict):
            data["selected_action"] = TurnAction.from_dict(data["selected_action"])

        return cls(**data)
    
    def complete(self, action_result: Optional[Dict[str, Any]] = None):
        """Mark the turn as completed."""
        self.status = TurnStatus.COMPLETED
        if action_result:
            self.action_result = action_result

    def is_active(self) -> bool:
        """Check if turn is currently active."""
        return self.status == TurnStatus.ACTIVE

    def is_complete(self) -> bool:
        """Check if turn is complete."""
        return self.status == TurnStatus.COMPLETED


@dataclass
class TurnResult:
    """Result of executing a turn."""
    turn: Turn  # The completed turn
    success: bool  # Whether the action succeeded
    message: str  # Description of what happened
    
    # Effects
    state_changes: Dict[str, Any] = field(default_factory=dict)  # Changes to game state
    next_character_id: Optional[str] = None  # Who goes next
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "turn": self.turn.to_dict(),
            "success": self.success,
            "message": self.message,
            "state_changes": self.state_changes,
            "next_character_id": self.next_character_id
        }
