"""Combatant state model for tracking individual combatant status."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from gaia.models.combat.mechanics.status_effect import StatusEffect
from gaia.models.combat.mechanics.enums import StatusEffectType
from gaia.models.combat.mechanics.position import Position
from gaia.models.combat.mechanics.combat_stats import CombatStats
from gaia.models.combat.mechanics.action_points import ActionPointState


@dataclass
class CombatantState:
    """State of a single combatant in combat."""
    character_id: str
    name: str
    initiative: int
    hp: int
    max_hp: int
    ac: int
    level: int = 1
    is_npc: bool = False
    hostile: bool = False  # Whether this combatant is hostile (enemy) or friendly
    status_effects: List[StatusEffect] = field(default_factory=list)
    action_points: Optional[ActionPointState] = None
    position: Optional[Position] = None
    combat_stats: Optional[CombatStats] = None
    temporary_hp: int = 0
    is_conscious: bool = True
    has_taken_turn: bool = False

    def can_act(self) -> bool:
        """Return True if combatant can act (conscious with HP remaining)."""
        return self.is_conscious and self.hp > 0

    def apply_damage(self, damage: int) -> Dict[str, Any]:
        """Apply damage, handling temp HP and unconsciousness."""
        result = {"damage_taken": 0, "knocked_unconscious": False}

        # Apply to temp HP first
        if self.temporary_hp > 0:
            if damage <= self.temporary_hp:
                self.temporary_hp -= damage
                result["damage_taken"] = damage
                return result
            else:
                damage -= self.temporary_hp
                self.temporary_hp = 0

        # Apply remaining damage to HP
        self.hp -= damage
        result["damage_taken"] = damage

        # TODO This logic should live in engine
        # Check for unconsciousness
        if self.hp <= 0 and self.is_conscious:
            self.hp = 0
            self.is_conscious = False
            result["knocked_unconscious"] = True
            self.status_effects.append(
                StatusEffect(
                    effect_type=StatusEffectType.UNCONSCIOUS,
                    duration_rounds=-1,
                    source="damage",
                    description="Knocked unconscious at 0 HP"
                )
            )

        return result

    def heal(self, amount: int) -> int:
        """Heal the combatant, return actual amount healed."""
        old_hp = self.hp
        self.hp = min(self.hp + amount, self.max_hp)

        # Remove unconscious if healed from 0
        if old_hp == 0 and self.hp > 0:
            self.is_conscious = True
            self.status_effects = [
                e for e in self.status_effects
                if e.effect_type != StatusEffectType.UNCONSCIOUS
            ]

        return self.hp - old_hp

    def add_status_effect(self, effect: StatusEffect) -> None:
        """Add a status effect, replacing if same type exists."""
        # Remove existing effect of same type
        self.status_effects = [
            e for e in self.status_effects
            if e.effect_type != effect.effect_type
        ]
        self.status_effects.append(effect)

    def process_turn_end(self) -> List[str]:
        """Process end of turn effects, return messages."""
        messages = []
        expired = []

        for effect in self.status_effects:
            if effect.tick():
                expired.append(effect)
                messages.append(f"{effect.effect_type.value} effect expired")

        # Remove expired effects
        for effect in expired:
            self.status_effects.remove(effect)

        return messages

    def get_effective_ac(self) -> int:
        """Calculate AC with all modifiers."""
        ac = self.ac
        for effect in self.status_effects:
            if "ac_bonus" in effect.modifiers:
                ac += effect.modifiers["ac_bonus"]
        return ac

    def to_dict(self, compact: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Args:
            compact: If True, use compact format for action points (names only)
        """
        return {
            "character_id": self.character_id,
            "name": self.name,
            "initiative": self.initiative,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "ac": self.ac,
            "level": self.level,
            "is_npc": self.is_npc,
            "hostile": self.hostile,
            "status_effects": [e.to_dict() for e in self.status_effects],
            "action_points": self.action_points.to_dict(compact=compact) if self.action_points else None,
            "position": self.position.to_dict() if self.position else None,
            "combat_stats": self.combat_stats.to_dict() if self.combat_stats else None,
            "temporary_hp": self.temporary_hp,
            "is_conscious": self.is_conscious,
            "has_taken_turn": self.has_taken_turn
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CombatantState':
        """Create CombatantState from dictionary representation.

        Args:
            data: Dictionary containing combatant data

        Returns:
            Deserialized CombatantState
        """
        combatant = cls(
            character_id=data["character_id"],
            name=data["name"],
            initiative=data.get("initiative", 0),
            hp=data.get("hp", 0),
            max_hp=data.get("max_hp", 0),
            ac=data.get("ac", 10),
            level=data.get("level", 1),
            is_npc=data.get("is_npc", False),
            hostile=data.get("hostile", False),
            temporary_hp=data.get("temporary_hp", 0),
            is_conscious=data.get("is_conscious", True),
            has_taken_turn=data.get("has_taken_turn", False)
        )

        # Deserialize action points
        if data.get("action_points"):
            from core.models.combat.mechanics.action_points import ActionPointState
            ap_data = data["action_points"]
            combatant.action_points = ActionPointState(
                max_ap=ap_data.get("max_ap", 3),
                current_ap=ap_data.get("current_ap", 3),
                spent_this_turn=ap_data.get("spent_this_turn", 0)
            )

        # Deserialize status effects
        for effect_data in data.get("status_effects", []):
            effect = StatusEffect.from_dict(effect_data)
            if effect:
                combatant.status_effects.append(effect)

        # Deserialize position
        if data.get("position"):
            combatant.position = Position.from_dict(data["position"])

        # Deserialize combat stats
        if data.get("combat_stats"):
            combatant.combat_stats = CombatStats.from_dict(data["combat_stats"])

        return combatant
