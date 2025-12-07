"""ObservationsManager - manages pending observations from secondary players."""

from typing import Dict, List, Optional

from gaia.models.pending_observations import PendingObservations
from gaia.models.player_observation import PlayerObservation


class ObservationsManager:
    """
    Manages pending observations from secondary players.

    Secondary players can submit observations instead of direct actions.
    These are collected and presented to the primary player for inclusion
    in their turn submission.
    """

    def __init__(self):
        # Map of session_id -> PendingObservations
        self._pending: Dict[str, PendingObservations] = {}

    def get_or_create_pending(
        self,
        session_id: str,
        primary_character_id: str,
        primary_character_name: str
    ) -> PendingObservations:
        """Get or create pending observations for a session."""
        if session_id not in self._pending:
            self._pending[session_id] = PendingObservations(
                session_id=session_id,
                primary_character_id=primary_character_id,
                primary_character_name=primary_character_name
            )
        else:
            # Update primary character if changed
            pending = self._pending[session_id]
            pending.primary_character_id = primary_character_id
            pending.primary_character_name = primary_character_name
        return self._pending[session_id]

    def add_observation(
        self,
        session_id: str,
        primary_character_id: str,
        primary_character_name: str,
        observer_character_id: str,
        observer_character_name: str,
        observation_text: str
    ) -> PlayerObservation:
        """
        Add an observation from a secondary player.

        Args:
            session_id: The session ID
            primary_character_id: ID of the turn-taking character
            primary_character_name: Name of the turn-taking character
            observer_character_id: ID of the observing character
            observer_character_name: Name of the observing character
            observation_text: The observation text

        Returns:
            The created PlayerObservation
        """
        pending = self.get_or_create_pending(
            session_id=session_id,
            primary_character_id=primary_character_id,
            primary_character_name=primary_character_name
        )

        return pending.add_observation(
            character_id=observer_character_id,
            character_name=observer_character_name,
            observation_text=observation_text
        )

    def get_pending_observations(self, session_id: str) -> Optional[PendingObservations]:
        """Get pending observations for a session."""
        return self._pending.get(session_id)

    def get_unincluded_observations(self, session_id: str) -> List[PlayerObservation]:
        """Get observations that haven't been included in a turn yet."""
        pending = self._pending.get(session_id)
        if pending:
            return pending.get_unincluded_observations()
        return []

    def format_observations_for_submission(self, session_id: str) -> str:
        """
        Format all unincluded observations for inclusion in primary player's submission.

        Returns:
            Formatted string to append to the primary player's input
        """
        pending = self._pending.get(session_id)
        if pending:
            return pending.format_all_for_submission()
        return ""

    def mark_all_included(self, session_id: str) -> None:
        """Mark all observations as included after primary player submits."""
        pending = self._pending.get(session_id)
        if pending:
            pending.mark_all_included()

    def clear_session(self, session_id: str) -> None:
        """Clear all observations for a session."""
        if session_id in self._pending:
            del self._pending[session_id]

    def clear_included(self, session_id: str) -> None:
        """Remove included observations from a session, keep unincluded."""
        pending = self._pending.get(session_id)
        if pending:
            pending.clear_included()


# Global instance for use across the application
_observations_manager: Optional[ObservationsManager] = None


def get_observations_manager() -> ObservationsManager:
    """Get the global observations manager instance."""
    global _observations_manager
    if _observations_manager is None:
        _observations_manager = ObservationsManager()
    return _observations_manager
