"""Response type enumeration for turn-based messages."""

from enum import Enum


class ResponseType(str, Enum):
    """Types of responses within a turn.

    Each turn can have multiple responses with different types:
    - TURN_INPUT: The structured input from players and DM at the start of a turn
    - STREAMING: In-progress narrative chunks during LLM generation
    - FINAL: The complete DM response after generation finishes
    - SYSTEM: System-generated messages (errors, status updates)
    - PRIVATE: Future use for DM-to-player whispers
    """
    TURN_INPUT = "turn_input"
    STREAMING = "streaming"
    FINAL = "final"
    SYSTEM = "system"
    PRIVATE = "private"
