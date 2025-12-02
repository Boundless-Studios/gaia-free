"""Combat event logging models for debugging and analysis."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


@dataclass
class CombatEventLog:
    """Complete record of a combat interaction for debugging."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = ""  # "user_input", "agent_request", "agent_response", etc.

    # Input tracking
    user_input: Optional[str] = None
    agent_prompt: Optional[str] = None
    context_provided: Dict[str, Any] = field(default_factory=dict)

    # Processing details
    agent_name: Optional[str] = None
    model_used: Optional[str] = None
    processing_time_ms: Optional[int] = None

    # Output tracking
    agent_response: Optional[Dict] = None
    parsed_actions: List[Dict] = field(default_factory=list)
    validation_results: List[Dict] = field(default_factory=list)

    # State snapshots
    state_before: Dict[str, Any] = field(default_factory=dict)
    state_after: Dict[str, Any] = field(default_factory=dict)
    state_changes: Dict[str, Any] = field(default_factory=dict)

    # Dice rolls
    dice_rolls: List[Dict[str, Any]] = field(default_factory=list)

    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Performance metrics
    memory_usage_mb: Optional[float] = None
    token_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "user_input": self.user_input,
            "agent_prompt": self.agent_prompt,
            "context_provided": self.context_provided,
            "agent_name": self.agent_name,
            "model_used": self.model_used,
            "processing_time_ms": self.processing_time_ms,
            "agent_response": self.agent_response,
            "parsed_actions": self.parsed_actions,
            "validation_results": self.validation_results,
            "state_before": self.state_before,
            "state_after": self.state_after,
            "state_changes": self.state_changes,
            "dice_rolls": self.dice_rolls,
            "errors": self.errors,
            "warnings": self.warnings,
            "memory_usage_mb": self.memory_usage_mb,
            "token_count": self.token_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CombatEventLog':
        """Create from dictionary representation."""
        event = cls()
        for key, value in data.items():
            if key == "timestamp":
                event.timestamp = datetime.fromisoformat(value)
            elif hasattr(event, key):
                setattr(event, key, value)
        return event


@dataclass
class DiceRollLog:
    """Log entry for a dice roll."""
    roll_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    roll_type: str = ""  # "attack", "damage", "saving_throw", etc.
    expression: str = ""  # "1d20+5"
    rolls: List[int] = field(default_factory=list)  # Individual die results
    modifier: int = 0
    total: int = 0
    critical: bool = False
    fumble: bool = False
    advantage: bool = False
    disadvantage: bool = False
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "roll_id": self.roll_id,
            "timestamp": self.timestamp.isoformat(),
            "roll_type": self.roll_type,
            "expression": self.expression,
            "rolls": self.rolls,
            "modifier": self.modifier,
            "total": self.total,
            "critical": self.critical,
            "fumble": self.fumble,
            "advantage": self.advantage,
            "disadvantage": self.disadvantage,
            "context": self.context
        }


@dataclass
class CombatPerformanceMetrics:
    """Performance metrics for a combat session."""
    session_id: str
    total_events: int = 0
    total_actions: int = 0
    total_dice_rolls: int = 0
    total_errors: int = 0
    total_warnings: int = 0

    # Timing metrics (milliseconds)
    avg_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    total_processing_time_ms: float = 0.0

    # Token usage
    total_tokens_used: int = 0
    avg_tokens_per_action: float = 0.0

    # Memory usage
    peak_memory_usage_mb: float = 0.0
    avg_memory_usage_mb: float = 0.0

    # Combat statistics
    rounds_completed: int = 0
    damage_dealt_total: int = 0
    healing_done_total: int = 0
    knockouts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "total_events": self.total_events,
            "total_actions": self.total_actions,
            "total_dice_rolls": self.total_dice_rolls,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "timing": {
                "avg_response_time_ms": self.avg_response_time_ms,
                "max_response_time_ms": self.max_response_time_ms,
                "min_response_time_ms": self.min_response_time_ms,
                "total_processing_time_ms": self.total_processing_time_ms
            },
            "tokens": {
                "total_tokens_used": self.total_tokens_used,
                "avg_tokens_per_action": self.avg_tokens_per_action
            },
            "memory": {
                "peak_memory_usage_mb": self.peak_memory_usage_mb,
                "avg_memory_usage_mb": self.avg_memory_usage_mb
            },
            "combat_stats": {
                "rounds_completed": self.rounds_completed,
                "damage_dealt_total": self.damage_dealt_total,
                "healing_done_total": self.healing_done_total,
                "knockouts": self.knockouts
            }
        }