"""Health Point Management System for Combat.

This module centralizes all HP management logic including damage,
healing, death saves, and status effects related to health.
"""

from typing import Optional, Tuple, Dict, Any, List
from enum import Enum

from gaia.models.combat.persistence.combatant_state import CombatantState
from gaia.models.combat.persistence.status_effect import StatusEffect, StatusEffectType


class HealthStatus(Enum):
    """Health status categories for combatants."""
    HEALTHY = "healthy"  # Above 50% HP
    BLOODIED = "bloodied"  # 50% or less HP
    CRITICAL = "critical"  # 25% or less HP
    UNCONSCIOUS = "unconscious"  # 0 HP
    DEAD = "dead"  # Failed death saves or massive damage


class DamageType(Enum):
    """Types of damage that can be dealt."""
    SLASHING = "slashing"
    PIERCING = "piercing"
    BLUDGEONING = "bludgeoning"
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    THUNDER = "thunder"
    POISON = "poison"
    ACID = "acid"
    NECROTIC = "necrotic"
    RADIANT = "radiant"
    PSYCHIC = "psychic"
    FORCE = "force"


class HPManager:
    """Manages health point mechanics for combat."""

    def __init__(self, death_save_dc: int = 10, massive_damage_threshold_multiplier: float = 1.0):
        """Initialize the HP Manager.

        Args:
            death_save_dc: DC for death saving throws (default 10)
            massive_damage_threshold_multiplier: Multiplier for massive damage threshold
        """
        self.death_save_dc = death_save_dc
        self.massive_damage_multiplier = massive_damage_threshold_multiplier
        self.death_saves = {}  # Track death saves per combatant

    def get_health_status(self, combatant: CombatantState) -> HealthStatus:
        """Get the health status of a combatant.

        Args:
            combatant: The combatant to check

        Returns:
            The combatant's health status
        """
        if combatant.hp <= 0:
            if not combatant.is_conscious:
                # Check for death
                saves = self.death_saves.get(combatant.character_id, {})
                if saves.get("failures", 0) >= 3:
                    return HealthStatus.DEAD
                return HealthStatus.UNCONSCIOUS
            return HealthStatus.UNCONSCIOUS

        hp_percentage = (combatant.hp / combatant.max_hp) * 100

        if hp_percentage <= 25:
            return HealthStatus.CRITICAL
        elif hp_percentage <= 50:
            return HealthStatus.BLOODIED
        else:
            return HealthStatus.HEALTHY

    def apply_damage(
        self,
        combatant: CombatantState,
        damage: int,
        damage_type: Optional[DamageType] = None,
        source: Optional[str] = None
    ) -> Tuple[int, HealthStatus, List[str]]:
        """Apply damage to a combatant.

        Args:
            combatant: The combatant taking damage
            damage: Amount of damage to apply
            damage_type: Type of damage (for resistances/vulnerabilities)
            source: Source of the damage

        Returns:
            Tuple of (actual_damage, new_status, effects_triggered)
        """
        if damage <= 0:
            return 0, self.get_health_status(combatant), []

        effects_triggered = []
        actual_damage = damage

        # Check for resistances/vulnerabilities
        if damage_type:
            actual_damage = self._calculate_modified_damage(combatant, damage, damage_type)
            if actual_damage != damage:
                if actual_damage < damage:
                    effects_triggered.append(f"resistant_to_{damage_type.value}")
                else:
                    effects_triggered.append(f"vulnerable_to_{damage_type.value}")

        # Apply the damage
        old_hp = combatant.hp
        combatant.hp = max(0, combatant.hp - actual_damage)

        # Check for massive damage
        if actual_damage >= combatant.max_hp * self.massive_damage_multiplier:
            effects_triggered.append("massive_damage")
            if combatant.hp == 0:
                effects_triggered.append("instant_death")
                self._kill_combatant(combatant)
                return actual_damage, HealthStatus.DEAD, effects_triggered

        # Check for dropping to 0 HP
        if old_hp > 0 and combatant.hp == 0:
            self._handle_drop_to_zero(combatant, source)
            effects_triggered.append("dropped_to_zero")

        new_status = self.get_health_status(combatant)

        # Check for status transitions
        if old_hp > combatant.max_hp / 2 and combatant.hp <= combatant.max_hp / 2:
            effects_triggered.append("became_bloodied")

        return actual_damage, new_status, effects_triggered

    def apply_healing(
        self,
        combatant: CombatantState,
        healing: int,
        source: Optional[str] = None
    ) -> Tuple[int, HealthStatus, List[str]]:
        """Apply healing to a combatant.

        Args:
            combatant: The combatant being healed
            healing: Amount of healing to apply
            source: Source of the healing

        Returns:
            Tuple of (actual_healing, new_status, effects_triggered)
        """
        if healing <= 0:
            return 0, self.get_health_status(combatant), []

        effects_triggered = []
        old_hp = combatant.hp

        # Apply healing, capped at max HP
        actual_healing = min(healing, combatant.max_hp - combatant.hp)
        combatant.hp = min(combatant.max_hp, combatant.hp + healing)

        # Handle recovery from unconsciousness
        if old_hp == 0 and combatant.hp > 0:
            self._handle_recovery_from_zero(combatant)
            effects_triggered.append("recovered_from_unconscious")

        new_status = self.get_health_status(combatant)

        # Check for status transitions
        if old_hp <= combatant.max_hp / 2 and combatant.hp > combatant.max_hp / 2:
            effects_triggered.append("no_longer_bloodied")

        return actual_healing, new_status, effects_triggered

    def make_death_save(
        self,
        combatant: CombatantState,
        roll: int
    ) -> Tuple[bool, str, List[str]]:
        """Process a death saving throw.

        Args:
            combatant: The combatant making the save
            roll: The d20 roll result

        Returns:
            Tuple of (success, description, effects_triggered)
        """
        if combatant.hp > 0:
            return False, f"{combatant.name} doesn't need death saves", []

        combatant_id = combatant.character_id
        if combatant_id not in self.death_saves:
            self.death_saves[combatant_id] = {"successes": 0, "failures": 0}

        saves = self.death_saves[combatant_id]
        effects_triggered = []

        # Natural 20 - regain 1 HP
        if roll == 20:
            combatant.hp = 1
            self._handle_recovery_from_zero(combatant)
            effects_triggered.append("natural_20_recovery")
            description = f"{combatant.name} rolls a natural 20 and regains consciousness with 1 HP!"
            return True, description, effects_triggered

        # Natural 1 - two failures
        if roll == 1:
            saves["failures"] += 2
            effects_triggered.append("natural_1_double_failure")
            if saves["failures"] >= 3:
                saves["failures"] = 3
                self._kill_combatant(combatant)
                effects_triggered.append("death")
                description = f"{combatant.name} rolls a natural 1 and dies!"
            else:
                description = f"{combatant.name} rolls a natural 1 (2 failures: {saves['failures']}/3)"
            return False, description, effects_triggered

        # Normal save
        if roll >= self.death_save_dc:
            saves["successes"] += 1
            if saves["successes"] >= 3:
                self._stabilize_combatant(combatant)
                effects_triggered.append("stabilized")
                description = f"{combatant.name} succeeds and stabilizes!"
            else:
                description = f"{combatant.name} succeeds ({saves['successes']}/3 successes)"
            return True, description, effects_triggered
        else:
            saves["failures"] += 1
            if saves["failures"] >= 3:
                self._kill_combatant(combatant)
                effects_triggered.append("death")
                description = f"{combatant.name} fails and dies!"
            else:
                description = f"{combatant.name} fails ({saves['failures']}/3 failures)"
            return False, description, effects_triggered

    def _calculate_modified_damage(
        self,
        combatant: CombatantState,
        damage: int,
        damage_type: DamageType
    ) -> int:
        """Calculate damage after resistances and vulnerabilities.

        Args:
            combatant: The combatant taking damage
            damage: Base damage amount
            damage_type: Type of damage

        Returns:
            Modified damage amount
        """
        # Check status effects for resistances/vulnerabilities
        for effect in combatant.status_effects:
            modifiers = effect.modifiers or {}

            # Check for resistance
            resistances = modifiers.get("resistances", [])
            if damage_type.value in resistances:
                return damage // 2

            # Check for vulnerability
            vulnerabilities = modifiers.get("vulnerabilities", [])
            if damage_type.value in vulnerabilities:
                return damage * 2

        return damage

    def _handle_drop_to_zero(self, combatant: CombatantState, source: Optional[str] = None) -> None:
        """Handle a combatant dropping to 0 HP.

        Args:
            combatant: The combatant at 0 HP
            source: Source that caused the drop
        """
        combatant.is_conscious = False

        # Add unconscious status effect
        unconscious_effect = StatusEffect(
            effect_type=StatusEffectType.UNCONSCIOUS,
            duration_rounds=-1,  # Permanent until healed
            source=source or "damage",
            description="Unconscious at 0 HP"
        )
        combatant.add_status_effect(unconscious_effect)

        # Initialize death saves
        self.death_saves[combatant.character_id] = {"successes": 0, "failures": 0}

        # Clear AP
        if combatant.action_points:
            combatant.action_points.current_ap = 0

    def _handle_recovery_from_zero(self, combatant: CombatantState) -> None:
        """Handle recovery from 0 HP.

        Args:
            combatant: The combatant recovering
        """
        combatant.is_conscious = True

        # Remove unconscious/incapacitated effects
        combatant.status_effects = [
            effect for effect in combatant.status_effects
            if effect.effect_type not in {
                StatusEffectType.UNCONSCIOUS,
                StatusEffectType.INCAPACITATED
            }
        ]

        # Clear death saves
        if combatant.character_id in self.death_saves:
            del self.death_saves[combatant.character_id]

    def _stabilize_combatant(self, combatant: CombatantState) -> None:
        """Stabilize an unconscious combatant.

        Args:
            combatant: The combatant to stabilize
        """
        # Add stabilized effect
        stabilized_effect = StatusEffect(
            effect_type=StatusEffectType.STUNNED,  # Using stunned as "stabilized"
            duration_rounds=-1,
            source="death_saves",
            description="Stabilized at 0 HP"
        )
        combatant.add_status_effect(stabilized_effect)

        # Clear death saves
        if combatant.character_id in self.death_saves:
            del self.death_saves[combatant.character_id]

    def _kill_combatant(self, combatant: CombatantState) -> None:
        """Mark a combatant as dead.

        Args:
            combatant: The combatant who died
        """
        combatant.is_conscious = False
        combatant.hp = 0

        # Clear all status effects and add dead status
        combatant.status_effects = []
        dead_effect = StatusEffect(
            effect_type=StatusEffectType.INCAPACITATED,  # Using incapacitated as "dead"
            duration_rounds=-1,
            source="death",
            description="Dead"
        )
        combatant.add_status_effect(dead_effect)

        # Clear death saves
        if combatant.character_id in self.death_saves:
            del self.death_saves[combatant.character_id]

    def get_hp_summary(self, combatant: CombatantState) -> Dict[str, Any]:
        """Get a comprehensive HP summary for a combatant.

        Args:
            combatant: The combatant to summarize

        Returns:
            Dictionary with HP information
        """
        status = self.get_health_status(combatant)
        percentage = (combatant.hp / combatant.max_hp * 100) if combatant.max_hp > 0 else 0

        summary = {
            "current": combatant.hp,
            "max": combatant.max_hp,
            "percentage": percentage,
            "status": status.value,
            "is_conscious": combatant.is_conscious,
            "is_bloodied": combatant.hp <= combatant.max_hp / 2,
            "is_critical": combatant.hp <= combatant.max_hp / 4,
        }

        # Add death save information if applicable
        if combatant.character_id in self.death_saves:
            saves = self.death_saves[combatant.character_id]
            summary["death_saves"] = {
                "successes": saves["successes"],
                "failures": saves["failures"],
                "is_stable": saves["successes"] >= 3,
                "is_dead": saves["failures"] >= 3
            }

        return summary