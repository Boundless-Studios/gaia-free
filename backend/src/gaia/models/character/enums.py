"""Character-related enumerations."""

from enum import Enum, IntFlag, auto


class CharacterStatus(Enum):
    """Character status conditions."""
    HEALTHY = "healthy"
    INJURED = "injured"
    AFFECTED = "affected"  # For various status effects
    UNCONSCIOUS = "unconscious"
    DEAD = "dead"


class Effect(Enum):
    """Status effects that can apply to characters and NPCs."""
    CURSED = "cursed"
    POISONED = "poisoned"
    CHARMED = "charmed"
    FRIGHTENED = "frightened"
    PARALYZED = "paralyzed"
    STUNNED = "stunned"
    EXHAUSTED = "exhausted"
    BLINDED = "blinded"
    DEAFENED = "deafened"
    RESTRAINED = "restrained"
    GRAPPLED = "grappled"
    INVISIBLE = "invisible"
    INCAPACITATED = "incapacitated"
    PETRIFIED = "petrified"
    PRONE = "prone"


class CharacterType(Enum):
    """Types of characters in the game."""
    PLAYER = "player"
    NPC = "npc"
    ENEMY = "enemy"
    CREATURE = "creature"


class CharacterRole(Enum):
    """Narrative/combat roles assigned to characters and participants."""

    PLAYER = "player"
    NPC_COMBATANT = "npc_combatant"
    NPC_SUPPORT = "npc_support"
    SUMMON = "summon"
    ENVIRONMENT = "environment"


class CharacterCapability(IntFlag):
    """Bitset describing which systems a character can interact with."""

    NONE = 0
    COMBAT = auto()
    NARRATIVE = auto()
    INVENTORY = auto()
    SKILLS = auto()


class VoiceArchetype(Enum):
    """Voice archetypes for character voice assignment."""
    HERO = "hero"
    VILLAIN = "villain"
    MENTOR = "mentor"
    MERCHANT = "merchant"
    NARRATOR = "narrator"
    CREATURE = "creature"
    CHILD = "child"
    ELDER = "elder"
