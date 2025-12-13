"""Turn counter service for managing authoritative turn numbers per campaign.

This service provides server-authoritative turn counters that solve message
ordering issues by replacing timestamp-based sorting with sequential counters.

Turn Structure:
- Each campaign has a monotonically increasing turn_number
- Each turn has a response_index counter for ordering within the turn:
  - 0: TURN_INPUT (player + DM input)
  - 1-N: STREAMING chunks
  - N+1: FINAL response

Persistence:
- Turn counters are persisted to DB via CampaignRepository
- In-memory cache provides fast access for hot path
- DB is source of truth on restart/recovery
"""

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TurnCounterService:
    """Manages authoritative turn counters per campaign.

    Thread-safe service that provides:
    - Atomic turn increments
    - Per-turn response index tracking
    - DB persistence for durability
    - In-memory cache for performance
    """

    def __init__(self):
        # In-memory storage: campaign_id -> turn_number
        self._turn_counters: Dict[str, int] = {}
        # In-memory storage: (campaign_id, turn_number) -> response_index
        self._response_indices: Dict[tuple, int] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Repository for DB persistence (lazy loaded)
        self._repository = None
        # Flag to enable/disable DB persistence
        self._db_enabled = True

    def _get_repository(self):
        """Lazy load repository to avoid circular imports."""
        if self._repository is None:
            try:
                from gaia.infra.storage.campaign_repository import campaign_repository
                self._repository = campaign_repository
            except ImportError:
                logger.warning("[TurnCounter] CampaignRepository not available, DB persistence disabled")
                self._db_enabled = False
        return self._repository

    async def get_current_turn(self, campaign_id: str) -> int:
        """Get the current turn number for a campaign.

        Returns 0 if no turns have been recorded yet.
        Checks in-memory cache first, falls back to DB.
        """
        async with self._lock:
            # Check in-memory cache first
            if campaign_id in self._turn_counters:
                return self._turn_counters[campaign_id]

            # Fall back to DB if available
            if self._db_enabled:
                try:
                    repo = self._get_repository()
                    if repo:
                        state = await repo.get_campaign_state(campaign_id)
                        if state:
                            turn = state.current_turn
                            self._turn_counters[campaign_id] = turn
                            logger.debug(f"[TurnCounter] Loaded turn from DB for {campaign_id}: {turn}")
                            return turn
                except Exception as e:
                    logger.warning(f"[TurnCounter] Failed to load turn from DB: {e}")

            return 0

    async def increment_turn(
        self,
        campaign_id: str,
        input_payload: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Increment and return the new turn number.

        This should be called when a new turn begins (DM submits to backend).
        Persists to DB if available.

        Args:
            campaign_id: Campaign identifier
            input_payload: Optional input data for the turn (stored in active_turn)

        Returns:
            New turn number
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

        # Persist to DB (outside lock to avoid blocking)
        if self._db_enabled:
            try:
                repo = self._get_repository()
                if repo:
                    await repo.start_turn(
                        external_campaign_id=campaign_id,
                        turn_number=new_turn,
                        input_payload=input_payload,
                    )
                    logger.debug(f"[TurnCounter] Persisted turn start to DB: {campaign_id} turn {new_turn}")
            except Exception as e:
                logger.warning(f"[TurnCounter] Failed to persist turn start to DB: {e}")

        return new_turn

    async def complete_turn(self, campaign_id: str, turn_number: int) -> None:
        """Mark a turn as completed.

        This should be called when the turn response is finalized.

        Args:
            campaign_id: Campaign identifier
            turn_number: Turn number being completed
        """
        if self._db_enabled:
            try:
                repo = self._get_repository()
                if repo:
                    await repo.complete_turn(
                        external_campaign_id=campaign_id,
                        turn_number=turn_number,
                    )
                    logger.debug(f"[TurnCounter] Persisted turn complete to DB: {campaign_id} turn {turn_number}")
            except Exception as e:
                logger.warning(f"[TurnCounter] Failed to persist turn complete to DB: {e}")

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

    async def initialize_from_db(self, campaign_id: str, environment: str) -> int:
        """Initialize turn counter from DB, creating campaign if needed.

        This should be called when a campaign is loaded to ensure the
        turn counter is in sync with the persisted state.

        Args:
            campaign_id: Campaign identifier (external/filesystem ID)
            environment: Environment (dev/staging/prod)

        Returns:
            Current turn number
        """
        if not self._db_enabled:
            return await self.get_current_turn(campaign_id)

        try:
            repo = self._get_repository()
            if repo:
                # Get or create campaign in DB
                campaign = await repo.get_or_create_campaign(
                    external_campaign_id=campaign_id,
                    environment=environment,
                )

                # Load current turn from state
                if campaign.state:
                    turn = campaign.state.current_turn
                    async with self._lock:
                        self._turn_counters[campaign_id] = turn
                    logger.info(f"[TurnCounter] Initialized from DB: {campaign_id} at turn {turn}")
                    return turn

        except Exception as e:
            logger.warning(f"[TurnCounter] Failed to initialize from DB: {e}")

        return await self.get_current_turn(campaign_id)

    async def add_turn_input_event(
        self,
        campaign_id: str,
        turn_number: int,
        active_player: Optional[Dict[str, Any]],
        observer_inputs: list,
        dm_input: Optional[Dict[str, Any]],
        combined_prompt: str,
    ) -> None:
        """Add a turn_input event to the DB.

        Args:
            campaign_id: Campaign identifier
            turn_number: Turn number
            active_player: Active player input dict
            observer_inputs: List of observer input dicts
            dm_input: DM input dict
            combined_prompt: Combined prompt string
        """
        if not self._db_enabled:
            return

        try:
            repo = self._get_repository()
            if repo:
                await repo.add_turn_input_event(
                    external_campaign_id=campaign_id,
                    turn_number=turn_number,
                    active_player=active_player,
                    observer_inputs=observer_inputs,
                    dm_input=dm_input,
                    combined_prompt=combined_prompt,
                )
                logger.info(f"[TurnCounter] ✅ Added turn_input event: {campaign_id} turn {turn_number}")
            else:
                logger.error(f"[TurnCounter] ❌ Repository not available for turn_input event: {campaign_id}")
        except Exception as e:
            logger.error(f"[TurnCounter] ❌ Failed to add turn_input event for {campaign_id} turn {turn_number}: {e}", exc_info=True)

    async def add_assistant_response_event(
        self,
        campaign_id: str,
        turn_number: int,
        content: Dict[str, Any],
    ) -> None:
        """Add an assistant response event to the DB.

        Args:
            campaign_id: Campaign identifier
            turn_number: Turn number
            content: Response content
        """
        if not self._db_enabled:
            return

        try:
            repo = self._get_repository()
            if repo:
                # Get next event index for the turn
                event_index = await repo.get_next_event_index(campaign_id, turn_number)
                await repo.add_assistant_response_event(
                    external_campaign_id=campaign_id,
                    turn_number=turn_number,
                    content=content,
                    event_index=event_index,
                )
                logger.info(f"[TurnCounter] ✅ Added assistant event: {campaign_id} turn {turn_number}")
            else:
                logger.error(f"[TurnCounter] ❌ Repository not available for assistant event: {campaign_id}")
        except Exception as e:
            logger.error(f"[TurnCounter] ❌ Failed to add assistant event for {campaign_id} turn {turn_number}: {e}", exc_info=True)

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
