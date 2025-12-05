"""
Player Options Service - handles personalized options generation for multiple players.

This service coordinates generating options for each connected player:
- Active player (turn-taker): Uses ActivePlayerOptionsAgent with action-oriented prompt
- Secondary players: Uses PlayerOptionsAgent with discovery-focused prompt
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from gaia.models.player_options import (
    PersonalizedPlayerOptions,
    CharacterOptions,
    PendingObservations,
    PlayerObservation
)
from gaia.agents.scene.active_player_options_agent import ActivePlayerOptionsAgent

logger = logging.getLogger(__name__)


@dataclass
class ConnectedPlayer:
    """Represents a player connected to the session."""
    character_id: str
    character_name: str
    user_id: Optional[str] = None
    seat_id: Optional[str] = None
    is_dm: bool = False


class PlayerOptionsService:
    """
    Service for generating personalized options for all connected players.

    Usage:
        service = PlayerOptionsService()
        options = await service.generate_all_player_options(
            connected_players=[...],
            active_character_id="char_123",
            scene_narrative="The dragon breathes fire...",
            previous_char_name="Gandalf"
        )
    """

    def __init__(self):
        self._active_agent = ActivePlayerOptionsAgent()
        # Lazy-load the passive agent from gaia_private
        self._passive_agent = None

    def _get_passive_agent(self):
        """Get or create the passive PlayerOptionsAgent (from gaia_private)."""
        if self._passive_agent is None:
            try:
                from gaia_private.agents.scene.player_options_agent import PlayerOptionsAgent
                self._passive_agent = PlayerOptionsAgent()
            except ImportError:
                logger.warning(
                    "PlayerOptionsAgent not available from gaia_private, "
                    "using ActivePlayerOptionsAgent for all players"
                )
                # Fallback: use active agent for all
                self._passive_agent = self._active_agent
        return self._passive_agent

    async def generate_all_player_options(
        self,
        connected_players: List[ConnectedPlayer],
        active_character_id: str,
        scene_narrative: str,
        previous_char_name: str = "the previous player",
        character_contexts: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        parallel: bool = True
    ) -> PersonalizedPlayerOptions:
        """
        Generate personalized options for all connected players.

        Args:
            connected_players: List of connected player characters
            active_character_id: ID of the turn-taking character
            scene_narrative: What just happened in the scene
            previous_char_name: Name of the character who just acted
            character_contexts: Optional map of char_id to context string
            model: Optional model override
            parallel: Whether to generate options in parallel (default True)

        Returns:
            PersonalizedPlayerOptions with options for each player
        """
        if not connected_players:
            logger.warning("[PlayerOptionsService] No connected players provided")
            return PersonalizedPlayerOptions(
                active_character_id=active_character_id,
                scene_narrative=scene_narrative,
                generated_at=datetime.now()
            )

        character_contexts = character_contexts or {}

        # Filter out DM from options generation
        player_characters = [p for p in connected_players if not p.is_dm]

        if not player_characters:
            logger.info("[PlayerOptionsService] No player characters to generate options for")
            return PersonalizedPlayerOptions(
                active_character_id=active_character_id,
                scene_narrative=scene_narrative,
                generated_at=datetime.now()
            )

        result = PersonalizedPlayerOptions(
            active_character_id=active_character_id,
            scene_narrative=scene_narrative,
            generated_at=datetime.now()
        )

        if parallel:
            # Generate all options in parallel
            tasks = []
            for player in player_characters:
                is_active = player.character_id == active_character_id
                context = character_contexts.get(player.character_id, "")
                tasks.append(
                    self._generate_single_player_options(
                        player=player,
                        is_active=is_active,
                        scene_narrative=scene_narrative,
                        previous_char_name=previous_char_name,
                        character_context=context,
                        model=model
                    )
                )

            # Wait for all options to be generated
            options_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for player, opts_result in zip(player_characters, options_results):
                if isinstance(opts_result, Exception):
                    logger.error(
                        f"[PlayerOptionsService] Error generating options for {player.character_name}: {opts_result}"
                    )
                    # Add empty options on error
                    result.add_character_options(
                        character_id=player.character_id,
                        character_name=player.character_name,
                        options=[],
                        is_active=(player.character_id == active_character_id)
                    )
                elif isinstance(opts_result, CharacterOptions):
                    result.characters[player.character_id] = opts_result
        else:
            # Generate sequentially
            for player in player_characters:
                is_active = player.character_id == active_character_id
                context = character_contexts.get(player.character_id, "")
                try:
                    char_options = await self._generate_single_player_options(
                        player=player,
                        is_active=is_active,
                        scene_narrative=scene_narrative,
                        previous_char_name=previous_char_name,
                        character_context=context,
                        model=model
                    )
                    result.characters[player.character_id] = char_options
                except Exception as e:
                    logger.error(
                        f"[PlayerOptionsService] Error generating options for {player.character_name}: {e}"
                    )
                    result.add_character_options(
                        character_id=player.character_id,
                        character_name=player.character_name,
                        options=[],
                        is_active=is_active
                    )

        return result

    async def _generate_single_player_options(
        self,
        player: ConnectedPlayer,
        is_active: bool,
        scene_narrative: str,
        previous_char_name: str,
        character_context: str,
        model: Optional[str] = None
    ) -> CharacterOptions:
        """
        Generate options for a single player.

        Args:
            player: The player to generate options for
            is_active: True if this is the turn-taker
            scene_narrative: What just happened
            previous_char_name: Who just acted
            character_context: Context about this character
            model: Optional model override

        Returns:
            CharacterOptions for this player
        """
        try:
            if is_active:
                # Use active agent for turn-taker
                logger.debug(f"[PlayerOptionsService] Generating ACTIVE options for {player.character_name}")
                agent_result = await self._active_agent.generate_options(
                    scene_narrative=scene_narrative,
                    current_char_name=previous_char_name,
                    next_char_name=player.character_name,
                    character_context=character_context,
                    model=model
                )
            else:
                # Use passive agent for observers
                logger.debug(f"[PlayerOptionsService] Generating PASSIVE options for {player.character_name}")
                passive_agent = self._get_passive_agent()
                agent_result = await passive_agent.generate_options(
                    scene_narrative=scene_narrative,
                    current_char_name=previous_char_name,
                    next_char_name=player.character_name,
                    character_context=character_context,
                    model=model
                )

            options = agent_result.get("player_options", [])

            return CharacterOptions(
                character_id=player.character_id,
                character_name=player.character_name,
                options=options,
                is_active=is_active,
                generated_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"[PlayerOptionsService] Failed to generate options for {player.character_name}: {e}")
            return CharacterOptions(
                character_id=player.character_id,
                character_name=player.character_name,
                options=[],
                is_active=is_active,
                generated_at=datetime.now()
            )

    async def generate_active_player_options_only(
        self,
        active_character_id: str,
        active_character_name: str,
        scene_narrative: str,
        previous_char_name: str,
        character_context: str = "",
        model: Optional[str] = None
    ) -> CharacterOptions:
        """
        Generate options for just the active (turn-taking) player.

        This is a convenience method when you only need active player options.

        Args:
            active_character_id: ID of the turn-taking character
            active_character_name: Name of the turn-taking character
            scene_narrative: What just happened
            previous_char_name: Who just acted
            character_context: Context about the active character
            model: Optional model override

        Returns:
            CharacterOptions for the active player
        """
        player = ConnectedPlayer(
            character_id=active_character_id,
            character_name=active_character_name
        )

        return await self._generate_single_player_options(
            player=player,
            is_active=True,
            scene_narrative=scene_narrative,
            previous_char_name=previous_char_name,
            character_context=character_context,
            model=model
        )


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
