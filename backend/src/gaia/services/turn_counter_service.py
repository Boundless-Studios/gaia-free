"""Turn counter service for managing authoritative turn numbers per campaign.

This service provides server-authoritative turn counters that solve message
ordering issues by replacing timestamp-based sorting with sequential counters.

Turn Structure:
- Each campaign has a monotonically increasing turn_number
- Each turn has a response_index counter for ordering within the turn:
  - 0: TURN_INPUT (player + DM input)
  - 1-N: STREAMING chunks
  - N+1: FINAL response
"""

import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TurnCounterService:
    """Manages authoritative turn counters per campaign.

    Thread-safe service that provides:
    - Atomic turn increments
    - Per-turn response index tracking
    - Optional persistence integration
    """

    def __init__(self):
        # In-memory storage: campaign_id -> turn_number
        self._turn_counters: Dict[str, int] = {}
        # In-memory storage: (campaign_id, turn_number) -> response_index
        self._response_indices: Dict[tuple, int] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def get_current_turn(self, campaign_id: str) -> int:
        """Get the current turn number for a campaign.

        Returns 0 if no turns have been recorded yet.
        """
        async with self._lock:
            return self._turn_counters.get(campaign_id, 0)

    async def increment_turn(self, campaign_id: str) -> int:
        """Increment and return the new turn number.

        This should be called when a new turn begins (DM submits to backend).
        """
        async with self._lock:
            current = self._turn_counters.get(campaign_id, 0)
            new_turn = current + 1
            self._turn_counters[campaign_id] = new_turn
            # Reset response index for the new turn
            self._response_indices[(campaign_id, new_turn)] = 0
            logger.info(
                f"[TurnCounter] Incremented turn for {campaign_id}: {current} -> {new_turn}"
            )
            return new_turn

    async def get_next_response_index(
        self, campaign_id: str, turn_number: int
    ) -> int:
        """Get and increment the response index for a turn.

        Response indices are used to order messages within a turn:
        - 0: TURN_INPUT
        - 1+: STREAMING chunks and FINAL response
        """
        async with self._lock:
            key = (campaign_id, turn_number)
            current = self._response_indices.get(key, 0)
            self._response_indices[key] = current + 1
            return current

    async def set_turn_number(self, campaign_id: str, turn_number: int) -> None:
        """Set the turn number directly (used for loading from persistence).

        This should only be called during campaign initialization to restore
        the turn counter from persisted state.
        """
        async with self._lock:
            self._turn_counters[campaign_id] = turn_number
            logger.info(
                f"[TurnCounter] Set turn number for {campaign_id}: {turn_number}"
            )

    async def reset_campaign(self, campaign_id: str) -> None:
        """Reset all counters for a campaign (for testing or cleanup)."""
        async with self._lock:
            self._turn_counters.pop(campaign_id, None)
            # Clean up all response indices for this campaign
            keys_to_remove = [
                key for key in self._response_indices if key[0] == campaign_id
            ]
            for key in keys_to_remove:
                del self._response_indices[key]
            logger.info(f"[TurnCounter] Reset all counters for {campaign_id}")


# Singleton instance
turn_counter_service = TurnCounterService()
