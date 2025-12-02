"""Transient combat context that tracks deterministic updates during encounters."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .combat_action import CombatAction


@dataclass
class CombatUpdate:
    """Holds transient state for a single combat agent run.

    This context follows the tool-integration-best-practices pattern to ensure
    deterministic combat resolution. Tools write their results here, and the
    normalization phase uses these values as the source of truth, with LLM
    output only providing narrative flavor.
    """

    damage_dealt: Dict[str, int] = field(default_factory=dict)
    healing_applied: Dict[str, int] = field(default_factory=dict)
    status_effects_applied: Dict[str, List[str]] = field(default_factory=dict)
    status_effects_removed: Dict[str, List[str]] = field(default_factory=dict)
    action_resolutions: List[CombatAction] = field(default_factory=list)
    hp_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    ap_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    defeated_combatants: List[str] = field(default_factory=list)
    turn_resolution: Optional[Dict[str, Any]] = None
    combat_session: Optional[Any] = None
    initiative_order: Optional[List[str]] = None

    def record_damage(self, target: str, amount: int, source: Optional[str] = None) -> None:
        """Record damage dealt to a target."""
        if target not in self.damage_dealt:
            self.damage_dealt[target] = 0
        self.damage_dealt[target] += amount

    def record_healing(self, target: str, amount: int, source: Optional[str] = None) -> None:
        """Record healing applied to a target."""
        if target not in self.healing_applied:
            self.healing_applied[target] = 0
        self.healing_applied[target] += amount

    def record_status_effect(self, target: str, effect: str, applied: bool = True) -> None:
        """Record status effect changes."""
        if applied:
            if target not in self.status_effects_applied:
                self.status_effects_applied[target] = []
            self.status_effects_applied[target].append(effect)
        else:
            if target not in self.status_effects_removed:
                self.status_effects_removed[target] = []
            self.status_effects_removed[target].append(effect)

    def record_action_resolution(
        self,
        *,
        actor_id: str,
        action_type: str,
        target_id: Optional[str] = None,
        ap_cost: int = 0,
        roll_result: Optional[int] = None,
        damage_dealt: Optional[int] = None,
        success: bool = True,
        description: str = "",
        round_number: int = 1
    ) -> None:
        """Record a resolved combat action."""
        action = CombatAction(
            timestamp=datetime.now(),
            round_number=round_number,
            actor_id=actor_id,
            action_type=action_type,
            target_id=target_id,
            ap_cost=ap_cost,
            roll_result=roll_result,
            damage_dealt=damage_dealt,
            success=success,
            description=description
        )
        self.action_resolutions.append(action)

    def record_hp_change(self, combatant: str, current_hp: int, max_hp: int) -> None:
        """Record HP state change for a combatant."""
        self.hp_changes[combatant] = {"current": current_hp, "max": max_hp}
        if current_hp <= 0 and combatant not in self.defeated_combatants:
            self.defeated_combatants.append(combatant)

    def record_ap_change(self, combatant: str, current_ap: int, max_ap: int) -> None:
        """Record AP state change for a combatant."""
        self.ap_changes[combatant] = {"current": current_ap, "max": max_ap}

    def get_authoritative_hp(self, combatant: str) -> Optional[Dict[str, int]]:
        """Return authoritative HP for a combatant."""
        return self.hp_changes.get(combatant)

    def get_authoritative_ap(self, combatant: str) -> Optional[Dict[str, int]]:
        """Return authoritative AP for a combatant."""
        return self.ap_changes.get(combatant)

    def get_net_damage(self, combatant: str) -> int:
        """Calculate net damage for a combatant (damage - healing)."""
        damage = self.damage_dealt.get(combatant, 0)
        healing = self.healing_applied.get(combatant, 0)
        return damage - healing
