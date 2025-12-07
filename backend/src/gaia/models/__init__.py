"""Gaia game models package - re-exports for public API"""

from gaia.models.game_enums import (
    GameStyle,
    GameTheme,
)
from gaia.models.campaign import CampaignData
from gaia.models.npc import NPCInfo
from gaia.models.environment import EnvironmentInfo
from gaia.models.scene_info import SceneInfo
from gaia.models.narrative import NarrativeInfo
from gaia.models.quest import QuestInfo
from gaia.models.item import Item
from gaia.models.scene_participant import SceneParticipant
from gaia.models.turn import Turn
from gaia.models.combat import CombatSession, CombatantState
from gaia.models.character_options import CharacterOptions
from gaia.models.personalized_player_options import PersonalizedPlayerOptions
from gaia.models.player_observation import PlayerObservation
from gaia.models.pending_observations import PendingObservations
from gaia.models.connected_player import ConnectedPlayer

__all__ = [
    # Enums
    "GameStyle",
    "GameTheme",
    # Campaign
    "CampaignData",
    # Game objects
    "NPCInfo",
    "EnvironmentInfo",
    "SceneInfo",
    "NarrativeInfo",
    "QuestInfo",
    "Item",
    "SceneParticipant",
    "Turn",
    "CombatSession",
    "CombatantState",
    # Player options
    "CharacterOptions",
    "PersonalizedPlayerOptions",
    "PlayerObservation",
    "PendingObservations",
    "ConnectedPlayer",
]
