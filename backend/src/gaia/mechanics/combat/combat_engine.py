"""Combat engine for managing combat mechanics and rules."""
import json
import random
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Any

from gaia.models.combat.mechanics.action_points import (
    ActionPointConfig, ActionPointState
)
from gaia.models.combat.mechanics.action_definitions import (
    ActionCost, ActionName, STANDARD_ACTIONS
)
from gaia.models.combat import (
    CombatSession, CombatantState, CombatAction, StatusEffect,
    StatusEffectType, CombatStats, Position
)
from gaia_private.models.combat.agent_io.fight.character_status import AgentCharacterStatus
from gaia_private.models.combat.agent_io.fight.combat_action_request import CombatActionRequest
from gaia_private.models.combat.agent_io.fight.combatant_view import CombatantView as CombatantStatus
from gaia.models.character.character_info import CharacterInfo
from gaia.models.character.enums import CharacterRole
from gaia.utils.dice import DiceRoller
from gaia.mechanics.combat.combat_action_results import (
    AttackActionResult,
    DefendActionResult,
    MoveActionResult,
    RecoverActionResult,
    TurnTransitionResult,
    TurnTransitionReason,
    InvalidTargetActionResult
)
from gaia.mechanics.combat.combat_mechanics_structs import (
    CombatMechanicsResolution,
    CombatContext
)
from gaia.mechanics.combat.action_validator import ActionValidator

class AttackResult(Enum):
    """Result of an attack roll."""
    CRITICAL_MISS = "critical_miss"
    MISS = "miss"
    HIT = "hit"
    CRITICAL_HIT = "critical_hit"


@dataclass(slots=True)
class AttackResolution:
    """Structured attack outcome with serialization helpers."""
    success: bool = False
    attack_roll_total: Optional[int] = None
    damage: int = 0
    description: str = ""
    critical: bool = False
    attack_roll_detail: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return asdict(self)

    def to_json(self) -> str:
        """Return a JSON string representation of the attack resolution."""
        return json.dumps(self.to_dict())

## The combat engine handles application of actions to the game state
## It resolves damnage, healing, effects, ands updates turn information

class CombatEngine:
    """Core combat mechanics engine."""

    def __init__(self):
        """Initialize the combat engine."""
        self.ap_config = ActionPointConfig()
        self.action_costs = {
            action.name.value if isinstance(action.name, ActionName) else action.name: action
            for action in STANDARD_ACTIONS
        }
        self.dice_roller = DiceRoller()

    def initialize_combatant(self, character: CharacterInfo) -> CombatantState:
        """Initialize a combatant from character info."""
        # Calculate initiative
        dex_modifier = (character.dexterity - 10) // 2
        initiative_roll = self.dice_roller.roll_initiative(
            dex_modifier=dex_modifier,
            initiative_bonus=character.initiative_modifier
        )
        initiative = initiative_roll["total"]

        # Calculate max AP based on level
        max_ap = self.ap_config.calculate_max_ap(character.level)

        # Create action point state
        ap_state = ActionPointState(
            max_ap=max_ap,
            current_ap=max_ap,
            available_actions=self.get_available_actions(character.level)
        )

        # Create combat stats if not present
        # Note: Using D&D 5e calculations, adjust for other rulesets if needed
        if not character.combat_stats:
            character.combat_stats = CombatStats(
                attack_bonus=(character.strength - 10) // 2,  # STR for melee
                damage_bonus=(character.strength - 10) // 2,
                spell_save_dc=8 + 2 + (character.intelligence - 10) // 2,  # 8 + prof + INT
                initiative_bonus=dex_modifier,
                speed=30
            )

        return CombatantState(
            character_id=character.character_id,
            name=character.name,
            initiative=initiative,
            hp=character.hit_points_current,
            max_hp=character.hit_points_max,
            ac=character.armor_class,
            level=character.level,
            is_npc=(character.character_role != CharacterRole.PLAYER),
            hostile=character.character_role == CharacterRole.NPC_COMBATANT,
            action_points=ap_state,
            combat_stats=character.combat_stats
        )

    # Make smarter later
    def get_available_actions(self, level: int) -> List[ActionCost]:
        """Get baseline actions available at a given level.

        Recover is excluded here and only surfaced dynamically when the
        combatant is incapacitated.
        """
        available = []
        for action in STANDARD_ACTIONS:
            if action.name == ActionName.RECOVER:
                continue

            available.append(action)
        return available

    def get_actions_for_combatant(self, combatant: CombatantState) -> List[ActionCost]:
        """Return actions appropriate for the combatant's current state."""
        if self._player_is_incapacitated(combatant):
            recover = self.action_costs.get(ActionName.RECOVER.value)
            return [recover] if recover else []
        return self.get_available_actions(combatant.level)

    def _player_is_incapacitated(self, combatant: CombatantState) -> bool:
        """Determine if a player combatant is incapacitated."""
        if combatant.is_npc:
            return False
        if not combatant.is_conscious:
            return True

        recoverable_effects = {
            StatusEffectType.UNCONSCIOUS,
            StatusEffectType.INCAPACITATED
        }
        return any(effect.effect_type in recoverable_effects for effect in combatant.status_effects)

    def _check_prerequisite(self, prerequisite: str, level: int) -> bool:
        """Check if a prerequisite is met."""
        if "level >=" in prerequisite:
            required_level = int(prerequisite.split(">=")[1].strip())
            return level >= required_level
        _ = level  # Suppress unused warning for non-level prerequisites
        return True

    def _validate_target(
        self,
        combat_session: CombatSession,
        target_id: str,
        allow_unconscious: bool = False
    ) -> CombatantState:
        """Validate that a target exists and can be targeted.

        Args:
            combat_session: Current combat session
            target_id: ID of the target to validate
            allow_unconscious: Whether unconscious targets are valid (e.g., for healing)

        Returns:
            CombatantState if target is valid

        Raises:
            ValueError: With helpful message if target is invalid
        """
        # Check if target exists in combat
        target = combat_session.combatants.get(target_id)
        if not target:
            # Provide list of available targets
            available = [c.name for c in combat_session.combatants.values()]
            if available:
                targets_str = ", ".join(available)
                raise ValueError(f"'{target_id}' not in combat. Available targets: {targets_str}")
            else:
                raise ValueError(f"'{target_id}' not in combat. No valid targets available.")

        # Check if target is conscious (unless we allow unconscious targets)
        if not allow_unconscious and not target.is_conscious:
            raise ValueError(f"{target.name} is unconscious and cannot be targeted")

        # Check if target has HP (dead combatants can't be targeted)
        if target.hp <= 0 and not allow_unconscious:
            raise ValueError(f"{target.name} has been defeated and cannot be targeted")

        return target


    def resolve_attack(
        self,
        attacker: CombatantState,
        target: CombatantState,
        weapon_damage: str = "1d8"
    ) -> AttackResolution:
        """Resolve an attack action (DETERMINISTIC game mechanics).

        Returns raw mechanical results for LLM narration.
        """
        # DETERMINISTIC: Attack roll calculation
        attack_bonus = attacker.combat_stats.attack_bonus if attacker.combat_stats else 0
        attack_roll = self.dice_roller.roll_attack(attack_bonus=attack_bonus)
        resolution = AttackResolution(
            attack_roll_total=attack_roll["total"],
            attack_roll_detail=attack_roll
        )

        if attack_roll.get("critical_fail", False):
            # DETERMINISTIC: Critical fail is a mechanical result
            resolution.description = "Critical miss! The attack fails spectacularly."
            return resolution

        # DETERMINISTIC: AC comparison
        target_ac = target.get_effective_ac()

        if attack_roll.get("critical", False) or attack_roll["total"] >= target_ac:
            resolution.success = True

            # DETERMINISTIC: Damage calculation
            damage_bonus = attacker.combat_stats.damage_bonus if attacker.combat_stats else 0
            damage_roll = self.dice_roller.roll(f"{weapon_damage}+{damage_bonus}")

            # D&D 5e rule: minimum damage is always 1 (even with negative modifiers)
            base_damage = max(1, damage_roll["total"])

            if attack_roll.get("critical", False):
                resolution.critical = True
                resolution.damage = base_damage * 2  # Critical still doubles the damage
                resolution.description = (
                    f"Critical hit! Rolled {attack_roll['total']} vs AC {target_ac}. "
                    f"Damage: {resolution.damage}"
                )
            else:
                resolution.damage = base_damage
                resolution.description = (
                    f"Hit! Rolled {attack_roll['total']} vs AC {target_ac}. "
                    f"Damage: {resolution.damage}"
                )

            damage_result = target.apply_damage(resolution.damage)
            if damage_result["knocked_unconscious"]:
                resolution.description += f" {target.name} falls unconscious!"
        else:
            resolution.description = f"Miss! Rolled {attack_roll['total']} vs AC {target_ac}"

        return resolution

    def resolve_spell(
        self,
        caster: CombatantState,
        targets: List[CombatantState],
        spell_damage: Optional[str] = None,
        save_type: Optional[str] = None,
        save_dc: Optional[int] = None,
        effect: Optional[StatusEffect] = None
    ) -> Dict[str, Any]:
        """Resolve a spell action."""
        result = {
            "success": True,
            "targets_affected": [],
            "damage_dealt": {},
            "effects_applied": [],
            "description": ""
        }

        # Use caster's spell save DC if not provided
        if save_dc is None and caster.combat_stats:
            save_dc = caster.combat_stats.spell_save_dc

        for target in targets:
            target_result = {"name": target.name, "saved": False, "damage": 0}

            # Roll saving throw if required
            if save_type and save_dc:
                # Get appropriate save modifier
                save_modifier = self._get_save_modifier(target, save_type)
                save_roll = self.dice_roller.roll_saving_throw(save_modifier=save_modifier)

                if save_roll["total"] >= save_dc:
                    target_result["saved"] = True
                    result["description"] += f"{target.name} saves (rolled {save_roll['total']} vs DC {save_dc}). "
                else:
                    result["description"] += f"{target.name} fails save (rolled {save_roll['total']} vs DC {save_dc}). "

            # Apply damage if spell deals damage
            if spell_damage and not target_result["saved"]:
                # Spell damage is variable, so still use string parsing
                damage_roll = self.dice_roller.roll(spell_damage)
                target_result["damage"] = damage_roll["total"]
                damage_result = target.apply_damage(damage_roll["total"])
                result["damage_dealt"][target.character_id] = damage_roll["total"]

                if damage_result["knocked_unconscious"]:
                    result["description"] += f"{target.name} falls unconscious! "

            # Apply status effect if not saved
            if effect and not target_result["saved"]:
                target.add_status_effect(effect)
                result["effects_applied"].append(f"{target.name}: {effect.effect_type.value}")

            result["targets_affected"].append(target_result)

        return result

    def _get_save_modifier(self, combatant: CombatantState, save_type: str) -> int:
        """Get saving throw modifier based on ability.

        Currently returns 0 for all saves. Will be updated when character
        ability scores are properly integrated.
        """
        _ = combatant  # Future use when ability scores are integrated
        _ = save_type  # Future use when ability scores are integrated
        return 0

    def _handle_ap_spending(
        self,
        actor: CombatantState,
        ap_cost: int
    ) -> tuple[int, str]:
        """Handle AP spending and overdraw damage.

        Args:
            actor: The acting combatant
            ap_cost: AP cost of the action

        Returns:
            Tuple of (overdraw_damage, overdraw_description)
        """
        overdraw_damage = 0
        overdraw_description = ""

        if actor.action_points and ap_cost:
            actor.action_points.spend_ap(ap_cost)

            # Check for overdraw and apply damage
            if actor.action_points.current_ap < 0:
                overdraw_amount = abs(actor.action_points.current_ap)

                if overdraw_amount == 1:
                    overdraw_damage = self.dice_roller.roll("1d4")["total"]
                    overdraw_level = "minor"
                elif overdraw_amount == 2:
                    overdraw_damage = self.dice_roller.roll("2d4")["total"]
                    overdraw_level = "moderate"
                else:
                    overdraw_damage = self.dice_roller.roll("3d4")["total"]
                    overdraw_level = "major"

                # Apply damage to the actor
                actor.hp -= overdraw_damage
                actor.hp = max(0, actor.hp)  # Don't go below 0

                # Prepare overdraw description
                overdraw_description = f" (Pushed beyond limits - {overdraw_level} overdraw: {overdraw_damage} strain damage)"

        return overdraw_damage, overdraw_description

    def process_action(
        self,
        combat_session: CombatSession,
        actor_id: str,
        action_type: str,  # Accept string for backward compatibility
        target_id: Optional[str] = None,
        **kwargs
    ) -> CombatAction:
        """Process a combat action and update the session."""
        from datetime import datetime

        actor = combat_session.combatants.get(actor_id)
        if not actor:
            raise ValueError(f"Actor {actor_id} not found in combat")


        # Special handling for end_turn action
        if action_type == "end_turn":
            return self._handle_end_turn(combat_session, actor, actor_id)

        # Note: We allow actions even with insufficient AP (overdraw is permitted)
        # The overdraw damage will be applied below when AP goes negative

        # Get action cost and spend AP
        action_def = self.action_costs.get(action_type)
        if not action_def:
            action_def = ActionCost(action_type, 2, "", "standard")
        ap_cost = action_def.cost

        # Handle AP spending and overdraw
        overdraw_damage, overdraw_description = self._handle_ap_spending(actor, ap_cost)

        # Process different action types
        description = ""
        success = True
        damage_dealt = None
        effects_applied = []
        roll_result = None

        if action_type == "basic_attack":
            if not target_id:
                success = False
                description = "Basic attack requires a target"
            else:
                attack_result = self._handle_basic_attack(
                    combat_session, actor, target_id
                )
                success = attack_result.success
                damage_dealt = attack_result.damage
                description = attack_result.description
                roll_result = attack_result.attack_roll
                effects_applied = attack_result.effects_applied
        elif action_type in ["cast_simple_spell", ActionName.CAST_SIMPLE_SPELL.value]:
            if not target_id:
                success = False
                description = "Simple spell requires a target"
            else:
                spell_result = self._handle_simple_spell(
                    combat_session, actor, target_id
                )
                success = spell_result.success
                damage_dealt = spell_result.damage
                description = spell_result.description
                roll_result = spell_result.attack_roll
                effects_applied = spell_result.effects_applied
        elif action_type in ["complex_spell", ActionName.COMPLEX_SPELL.value]:
            if not target_id:
                success = False
                description = "Complex spell requires a target"
            else:
                complex_spell_result = self._handle_complex_spell(
                    combat_session, actor, target_id
                )
                success = complex_spell_result.success
                damage_dealt = complex_spell_result.damage
                description = complex_spell_result.description
                roll_result = complex_spell_result.attack_roll
                effects_applied = complex_spell_result.effects_applied
        elif action_type == "defend":
            defend_result = self._handle_defend(actor, actor_id)
            success = defend_result.success
            description = defend_result.description
            effects_applied = defend_result.effects_applied
        elif action_type == "move":
            move_result = self._handle_move(actor, kwargs)
            success = move_result.success
            description = move_result.description
        elif action_type == ActionName.RECOVER.value:
            recover_result = self._handle_recover(actor)
            success = recover_result.success
            description = recover_result.description
            roll_result = recover_result.roll_result
            effects_applied = recover_result.effects_removed if recover_result.success else ["recovery_failed"]
            ap_cost = 0
        elif action_type in ["dodge", ActionName.DODGE.value]:
            dodge_result = self._handle_dodge(actor, actor_id)
            success = dodge_result.success
            description = dodge_result.description
            effects_applied = dodge_result.effects_applied
        elif action_type in ["dash", ActionName.DASH.value]:
            dash_result = self._handle_dash(actor)
            success = dash_result.success
            description = dash_result.description
        elif action_type in ["disengage", ActionName.DISENGAGE.value]:
            disengage_result = self._handle_disengage(actor, actor_id)
            success = disengage_result.success
            description = disengage_result.description
        elif action_type in ["hide", ActionName.HIDE.value]:
            hide_result = self._handle_hide(actor)
            success = hide_result.success
            description = hide_result.description
            roll_result = hide_result.roll_result
            effects_applied = ["hidden"] if hide_result.success else ["hide_failed"]
        elif action_type in ["search", ActionName.SEARCH.value]:
            search_result = self._handle_search(actor)
            success = search_result.success
            description = search_result.description
            roll_result = search_result.roll_result
            effects_applied = ["searched"]
        elif action_type in ["help", ActionName.HELP.value]:
            if not target_id:
                success = False
                description = "Help action requires a target"
            else:
                help_result = self._handle_help(combat_session, actor, target_id)
                success = help_result.success
                damage_dealt = help_result.damage
                description = help_result.description
                effects_applied = help_result.effects_applied
        elif action_type in ["grapple", ActionName.GRAPPLE.value]:
            if not target_id:
                success = False
                description = "Grapple action requires a target"
            else:
                grapple_result = self._handle_grapple(combat_session, actor, target_id)
                success = grapple_result.success
                damage_dealt = grapple_result.damage
                description = grapple_result.description
                roll_result = grapple_result.attack_roll
                effects_applied = grapple_result.effects_applied
        elif action_type in ["shove", ActionName.SHOVE.value]:
            if not target_id:
                success = False
                description = "Shove action requires a target"
            else:
                shove_result = self._handle_shove(combat_session, actor, target_id)
                success = shove_result.success
                damage_dealt = shove_result.damage
                description = shove_result.description
                roll_result = shove_result.attack_roll
                effects_applied = shove_result.effects_applied
        elif action_type in ["ready_action", ActionName.READY_ACTION.value]:
            ready_result = self._handle_ready_action(actor)
            success = ready_result.success
            description = ready_result.description
            effects_applied = ready_result.effects_applied
        elif action_type in ["heal", ActionName.HEAL.value]:
            heal_result = self._handle_heal(combat_session, actor, target_id)
            success = heal_result.success
            damage_dealt = heal_result.damage
            description = heal_result.description
            roll_result = heal_result.attack_roll
            effects_applied = heal_result.effects_applied
        elif action_type in ["special_ability", ActionName.SPECIAL_ABILITY.value]:
            special_result = self._handle_special_ability(actor)
            success = special_result.success
            description = special_result.description
            effects_applied = special_result.effects_applied
        elif action_type in ["full_attack", ActionName.FULL_ATTACK.value]:
            if not target_id:
                success = False
                description = "Full attack requires a target"
            else:
                full_attack_result = self._handle_full_attack(combat_session, actor, target_id)
                success = full_attack_result.success
                damage_dealt = full_attack_result.damage
                description = full_attack_result.description
                roll_result = full_attack_result.attack_roll
                effects_applied = full_attack_result.effects_applied
        elif action_type in ["bonus_action", ActionName.BONUS_ACTION.value]:
            bonus_result = self._handle_bonus_action(actor)
            success = bonus_result.success
            description = bonus_result.description
            effects_applied = bonus_result.effects_applied
        else:
            # Fallback: validate target for any action that specifies one
            if target_id:
                try:
                    self._validate_target(combat_session, target_id)
                    description = f"{actor.name} performs {action_type}"
                except ValueError as e:
                    success = False
                    description = str(e)
                    effects_applied.append("invalid_target")
            else:
                description = f"{actor.name} performs {action_type}"

        # Add overdraw description if applicable
        if overdraw_description:
            description += overdraw_description
            if overdraw_damage > 0:
                effects_applied.append(f"overdraw_damage_{overdraw_damage}")

        # Create and log the action
        action = CombatAction(
            timestamp=datetime.now(),
            round_number=combat_session.round_number,
            actor_id=actor_id,
            action_type=action_type,
            target_id=target_id,
            ap_cost=ap_cost,
            roll_result=roll_result,
            damage_dealt=damage_dealt,
            success=success,
            description=description,
            effects_applied=effects_applied
        )

        combat_session.combat_log.append(action)

        # Check if turn should automatically end due to AP exhaustion
        if CombatEngine.should_end_turn(combat_session, actor_id):
            action.effects_applied.append(f"turn_ended_ap_exhaustion")
            action.turn_should_end = True  # Signal that turn should end

        return action

    # TODO LLM data should be well structured
    def resolve_combat_mechanics(
        self,
        combatant: CombatantStatus,
        context: CombatContext,
        llm_data: Dict[str, Any],
        combatant_id: Optional[str] = None
    ) -> CombatMechanicsResolution:
        """Calculate deterministic HP/AP strings and status effects for a combatant.

        Args:
            combatant: The combatant's status
            context: Combat context with state tracking
            llm_data: Additional LLM response data
            combatant_id: Optional ID to use for lookups (defaults to name)
        """
        name = combatant.name
        # Use provided ID or fall back to name for lookups
        lookup_key = combatant_id if combatant_id else name
        status = AgentCharacterStatus()

        hp_data = context.get_authoritative_hp(lookup_key) if hasattr(context, "get_authoritative_hp") else None
        if hp_data:
            status.hp = f"{hp_data['current']}/{hp_data['max']}"
        elif combatant.hp_current is not None and combatant.hp_max is not None:
            net_damage = context.get_net_damage(lookup_key) if hasattr(context, "get_net_damage") else 0
            current_hp = combatant.hp_current - net_damage
            status.hp = f"{max(0, current_hp)}/{combatant.hp_max}"
        else:
            status.hp = "unknown"

        # Simplified AP calculation
        ap_data = context.get_authoritative_ap(lookup_key) if hasattr(context, "get_authoritative_ap") else None
        if ap_data:
            current_ap_value = ap_data.get("current")
            max_ap_value = ap_data.get("max")
        elif combatant.action_points_current is not None:
            # Calculate remaining AP after actions
            ap_spent = sum(
                getattr(action, "ap_cost", 0)
                for action in context.action_resolutions
                if getattr(action, "actor_id", None) == lookup_key
            )
            current_ap_value = max(0, combatant.action_points_current - ap_spent)
            max_ap_value = combatant.action_points_max or 3
        else:
            # Default values
            current_ap_value = combatant.action_points_max or 3
            max_ap_value = combatant.action_points_max or 3

        status.ap = f"{current_ap_value}/{max_ap_value}"

        status_list: List[str] = []
        context_effects = context.status_effects_applied
        if name in context_effects:
            status_list.extend(context_effects[name])

        narrative_effects = llm_data.get("narrative_effects", []) if isinstance(llm_data, dict) else []
        if isinstance(narrative_effects, list):
            for effect_obj in narrative_effects:
                if isinstance(effect_obj, dict) and effect_obj.get("character") == name:
                    effect_text = effect_obj.get("effect", "")
                    if effect_text:
                        status_list.append(effect_text)

        status.status = status_list if status_list else []
        return CombatMechanicsResolution(
            character_status=status,
            current_ap=current_ap_value,
            max_ap=max_ap_value
        )

    def resolve_turn_transition(
        self,
        current_actor: Optional[str],
        reason: Optional[TurnTransitionReason | str],
        request: CombatActionRequest,
        *,
        turn_ended_by_action: bool = False,
        remaining_ap: Optional[int] = None
    ) -> Optional[TurnTransitionResult]:
        """Determine next combatant turn information based on initiative order."""
        if not current_actor:
            return None

        computed_reason: Optional[TurnTransitionReason | str] = reason

        if computed_reason is None:
            if turn_ended_by_action:
                ap_value = remaining_ap if remaining_ap is not None else 0
                computed_reason = (
                    TurnTransitionReason.AP_OVERDRAWN if ap_value < 0
                    else TurnTransitionReason.AP_EXHAUSTED
                )
            elif remaining_ap is not None and remaining_ap <= 0:
                computed_reason = (
                    TurnTransitionReason.AP_OVERDRAWN if remaining_ap < 0
                    else TurnTransitionReason.AP_EXHAUSTED
                )
            else:
                return None

        reason_enum = (
            computed_reason if isinstance(computed_reason, TurnTransitionReason)
            else TurnTransitionReason(computed_reason)
        )

        initiative_order = list(request.initiative_order) if request.initiative_order else [
            combatant.name for combatant in request.combatants
        ]

        if not initiative_order:
            return None

        try:
            current_index = next(
                idx for idx, name in enumerate(initiative_order)
                if name.lower() == current_actor.lower()
            )
        except StopIteration:
            current_index = 0

        total = len(initiative_order)
        for offset in range(1, total + 1):
            idx = (current_index + offset) % total
            candidate = initiative_order[idx]
            candidate_state = next((c for c in request.combatants if c.name == candidate), None)
            # Check if combatant can fight (is_active already checks conscious AND hp > 0)
            can_act = candidate_state and candidate_state.is_active
            if can_act:
                new_round = idx <= current_index
                round_number = request.current_turn.round_number + 1 if new_round else request.current_turn.round_number
                return TurnTransitionResult(
                    current_actor=current_actor,
                    next_combatant=candidate,
                    reason=reason_enum,
                    new_round=new_round,
                    round_number=round_number,
                    order_index=idx
                )

        return None

    def calculate_initiative_order(self, combatants: List[CombatantState]) -> List[str]:
        """Calculate initiative order for combatants."""
        # Sort by initiative (highest first), break ties randomly
        sorted_combatants = sorted(
            combatants,
            key=lambda c: (c.initiative, random.random()),
            reverse=True
        )
        return [c.character_id for c in sorted_combatants]

    def check_combat_end(self, combat_session: CombatSession) -> Optional[str]:
        """Check if combat should end, return victory condition if so."""
        return combat_session.check_victory_conditions()

    @staticmethod
    def should_end_turn(combat_session: CombatSession, character_id: str) -> bool:
        """Check if a character's turn should end based on AP.

        Args:
            combat_session: Current combat session
            character_id: Character to check

        Returns:
            True if character has 0 or negative AP
        """
        combatant = combat_session.combatants.get(character_id)
        if not combatant or not combatant.action_points:
            return False
        return combatant.action_points.current_ap <= 0

    @staticmethod
    def is_fighting_combatant(combatant: CombatantState) -> bool:
        """Check if a combatant is capable of fighting (conscious and has HP > 0).

        Args:
            combatant: Combatant to check

        Returns:
            True if combatant is conscious and has HP > 0
        """
        return combatant.can_act() and CombatEngine._is_not_incapacitated(combatant, False)

    @staticmethod
    def _is_not_incapacitated(combatant: CombatantState, is_recover_action: bool) -> bool:
        """Check if combatant is incapacitated and unable to act.

        Args:
            combatant: The combatant to check
            is_recover_action: Whether this is a recovery action

        Returns:
            True if combatant can act, False if incapacitated
        """
        incapacitating = [
            StatusEffectType.STUNNED,
            StatusEffectType.PARALYZED,
            StatusEffectType.INCAPACITATED,
            StatusEffectType.UNCONSCIOUS
        ]

        for effect in combatant.status_effects:
            if effect.effect_type in incapacitating:
                # Allow recovery attempts while unconscious/incapacitated
                if is_recover_action and effect.effect_type in (
                    StatusEffectType.UNCONSCIOUS,
                    StatusEffectType.INCAPACITATED
                ):
                    continue
                return False

        return True

    def _handle_end_turn(self, combat_session: CombatSession, actor: CombatantState, actor_id: str) -> CombatAction:
        """Handle ending a combatant's turn.

        Args:
            combat_session: Current combat session
            actor: The combatant ending their turn
            actor_id: ID of the combatant

        Returns:
            CombatAction for ending the turn
        """
        action = CombatAction(
            timestamp=datetime.now(),
            round_number=combat_session.round_number,
            actor_id=actor_id,
            action_type="end_turn",
            target_id=None,
            ap_cost=0,
            success=True,
            description=f"{actor.name} ends their turn"
        )
        combat_session.combat_log.append(action)

        # Signal that turn should end (orchestrator will handle advancement)
        action.turn_should_end = True
        action.effects_applied = [f"turn_ended"]

        return action

    def _handle_simple_spell(self, combat_session: CombatSession, actor: CombatantState,
                             target_id: str):
        """Handle a simple spell attack action.

        Args:
            combat_session: Current combat session
            actor: The casting combatant
            target_id: ID of the target

        Returns:
            AttackActionResult with spell outcome
        """
        # Validate target
        try:
            target = self._validate_target(combat_session, target_id)
        except ValueError as e:
            return InvalidTargetActionResult(target_id=target_id, description=str(e))

        # Simple spells use spell attack bonus and deal spell damage
        # For now, treat it like a basic attack but with spell damage (e.g., 1d6 fire)
        # Note: resolve_attack already handles minimum damage of 1
        spell_result = self.resolve_attack(actor, target, weapon_damage="1d6")
        effects_applied = []
        if spell_result.critical:
            effects_applied.append("critical_hit")

        return AttackActionResult(
            success=spell_result.success,
            damage=spell_result.damage,
            description=spell_result.description.replace("Hit!", "Spell hit!").replace("Miss!", "Spell miss!"),
            attack_roll=spell_result.attack_roll_total,
            effects_applied=effects_applied,
            target_id=target_id,
            critical=spell_result.critical
        )

    def _handle_complex_spell(self, combat_session: CombatSession, actor: CombatantState,
                              target_id: str):
        """Handle a complex spell attack action.

        Args:
            combat_session: Current combat session
            actor: The casting combatant
            target_id: ID of the target

        Returns:
            AttackActionResult with spell outcome
        """
        # Validate target
        try:
            target = self._validate_target(combat_session, target_id)
        except ValueError as e:
            return InvalidTargetActionResult(target_id=target_id, description=str(e))

        # Complex spells are more powerful (2d8 damage)
        spell_result = self.resolve_attack(actor, target, weapon_damage="2d8")
        effects_applied = []
        if spell_result.critical:
            effects_applied.append("critical_hit")

        return AttackActionResult(
            success=spell_result.success,
            damage=spell_result.damage,
            description=spell_result.description.replace("Hit!", "Powerful spell hit!").replace("Miss!", "Spell miss!"),
            attack_roll=spell_result.attack_roll_total,
            effects_applied=effects_applied,
            target_id=target_id,
            critical=spell_result.critical
        )

    def _handle_basic_attack(self, combat_session: CombatSession, actor: CombatantState,
                             target_id: str):
        """Handle a basic attack action.

        Args:
            combat_session: Current combat session
            actor: The attacking combatant
            target_id: ID of the target

        Returns:
            AttackActionResult with attack outcome
        """
        # Validate target
        try:
            target = self._validate_target(combat_session, target_id)
        except ValueError as e:
            return InvalidTargetActionResult(target_id=target_id, description=str(e))

        attack_result = self.resolve_attack(actor, target)
        effects_applied = []
        if attack_result.critical:
            effects_applied.append("critical_hit")

        return AttackActionResult(
            success=attack_result.success,
            damage=attack_result.damage,
            description=attack_result.description,
            attack_roll=attack_result.attack_roll_total,
            effects_applied=effects_applied,
            target_id=target_id,
            critical=attack_result.critical
        )

    def _handle_defend(self, actor: CombatantState, actor_id: str) -> DefendActionResult:
        """Handle a defend action.

        Args:
            actor: The defending combatant
            actor_id: ID of the defender

        Returns:
            DefendActionResult with defense outcome
        """
        defend_effect = StatusEffect(
            effect_type=StatusEffectType.DEFENDING,
            duration_rounds=1,
            source=actor_id,
            description="Defensive stance",
            modifiers={"ac_bonus": 2}
        )
        actor.add_status_effect(defend_effect)
        description = f"{actor.name} takes a defensive stance (+2 AC)"
        return DefendActionResult(
            success=True,
            description=description,
            effects_applied=["defending"],
            ac_bonus=2
        )

    def _handle_move(self, actor: CombatantState, kwargs: Dict[str, Any]) -> MoveActionResult:
        """Handle a movement action.

        Args:
            actor: The moving combatant
            kwargs: Additional arguments containing position

        Returns:
            MoveActionResult with movement outcome
        """
        # new_position = kwargs.get("position")
        # if new_position:
        #     actor.position = Position(**new_position)
        #     pos_x = actor.position.x if actor.position else 0
        #     pos_y = actor.position.y if actor.position else 0
        #     return MoveActionResult(
        #         success=True,
        #         description=f"{actor.name} moves to position ({pos_x}, {pos_y})",
        #         new_position={"x": pos_x, "y": pos_y},
        #         distance_moved=None  # Could calculate if we had previous position
        #     )
        # return MoveActionResult(
        #     # TODO not helpful right now since we're not handling action properly
        #     success=False,
        #     description=f"{actor.name} attempts to move but no position specified",
        #     new_position=None,
        #     distance_moved=None
        # )
        return MoveActionResult(
                success=True,
                description=f"{actor.name} repositions!",
                new_position={"x": 0, "y": 0},
                distance_moved=None  # Could calculate if we had previous position
            )

    def _handle_recover(self, actor: CombatantState) -> RecoverActionResult:
        """Handle a recovery attempt.

        Args:
            actor: The combatant attempting to recover

        Returns:
            RecoverActionResult with recovery outcome
        """
        roll = self.dice_roller.roll("1d20")
        roll_result = roll["total"]
        success = roll_result >= 19

        if actor.action_points:
            actor.action_points.current_ap = 0

        hp_recovered = 0
        effects_removed = []
        if success:
            actor.is_conscious = True
            hp_recovered = max(1 - actor.hp, 0) if actor.hp < 1 else 0
            actor.hp = max(actor.hp, 1)

            # Track which effects were removed
            for effect in actor.status_effects:
                if effect.effect_type in {StatusEffectType.UNCONSCIOUS, StatusEffectType.INCAPACITATED}:
                    effects_removed.append(effect.effect_type.value)

            actor.status_effects = [
                effect
                for effect in actor.status_effects
                if effect.effect_type not in {
                    StatusEffectType.UNCONSCIOUS,
                    StatusEffectType.INCAPACITATED
                }
            ]
            description = f"{actor.name} musters the strength to recover (roll {roll_result})."
            effects_applied = ["self_recovered"]
        else:
            description = f"{actor.name} struggles to recover (roll {roll_result})."
            effects_applied = ["recovery_failed"]

        return RecoverActionResult(
            success=success,
            description=description,
            hp_recovered=hp_recovered,
            effects_removed=effects_removed,
            roll_result=roll_result
        )

    def _handle_dodge(self, actor: CombatantState, actor_id: str) -> DefendActionResult:
        """Handle a dodge action.

        Args:
            actor: The dodging combatant
            actor_id: ID of the dodger

        Returns:
            DefendActionResult with dodge outcome
        """
        dodge_effect = StatusEffect(
            effect_type=StatusEffectType.DODGING,
            duration_rounds=1,
            source=actor_id,
            description="Dodging - attacks against this character have disadvantage",
            modifiers={"evasion": True}
        )
        actor.add_status_effect(dodge_effect)
        return DefendActionResult(
            success=True,
            description=f"{actor.name} focuses on evasion",
            effects_applied=["dodging"],
            ac_bonus=0
        )

    def _handle_dash(self, actor: CombatantState) -> MoveActionResult:
        """Handle a dash action.

        Args:
            actor: The dashing combatant

        Returns:
            MoveActionResult with dash outcome
        """
        speed = actor.combat_stats.speed if actor.combat_stats else 30
        return MoveActionResult(
            success=True,
            description=f"{actor.name} dashes forward (speed doubled to {speed * 2}ft)",
            new_position=None,
            distance_moved=None
        )

    def _handle_disengage(self, actor: CombatantState, actor_id: str) -> MoveActionResult:
        """Handle a disengage action.

        Args:
            actor: The disengaging combatant
            actor_id: ID of the disengager

        Returns:
            MoveActionResult with disengage outcome
        """
        disengage_effect = StatusEffect(
            effect_type=StatusEffectType.DISENGAGED,
            duration_rounds=1,
            source=actor_id,
            description="Disengaged - movement doesn't provoke opportunity attacks",
            modifiers={"no_opportunity_attacks": True}
        )
        actor.add_status_effect(disengage_effect)
        return MoveActionResult(
            success=True,
            description=f"{actor.name} carefully disengages from combat",
            new_position=None,
            distance_moved=None
        )

    def _handle_hide(self, actor: CombatantState) -> RecoverActionResult:
        """Handle a hide action.

        Args:
            actor: The hiding combatant

        Returns:
            RecoverActionResult with hide outcome (reusing for roll-based action)
        """
        stealth_roll = self.dice_roller.roll("1d20+3")
        roll_total = stealth_roll["total"]
        success = roll_total >= 12

        if success:
            return RecoverActionResult(
                success=True,
                description=f"{actor.name} successfully hides (stealth {roll_total})",
                hp_recovered=0,
                effects_removed=[],
                roll_result=roll_total
            )
        else:
            return RecoverActionResult(
                success=False,
                description=f"{actor.name} attempts to hide but fails (stealth {roll_total})",
                hp_recovered=0,
                effects_removed=[],
                roll_result=roll_total
            )

    def _handle_search(self, actor: CombatantState) -> RecoverActionResult:
        """Handle a search action.

        Args:
            actor: The searching combatant

        Returns:
            RecoverActionResult with search outcome (reusing for roll-based action)
        """
        perception_roll = self.dice_roller.roll("1d20+2")
        roll_total = perception_roll["total"]

        return RecoverActionResult(
            success=True,
            description=f"{actor.name} searches the area (perception {roll_total})",
            hp_recovered=0,
            effects_removed=[],
            roll_result=roll_total
        )

    def _handle_help(self, combat_session: CombatSession, actor: CombatantState, target_id: str):
        """Handle a help action.

        Args:
            combat_session: Current combat session
            actor: The helping combatant
            target_id: ID of the ally being helped

        Returns:
            AttackActionResult with help outcome
        """
        try:
            target = self._validate_target(combat_session, target_id, allow_unconscious=True)
        except ValueError as e:
            return InvalidTargetActionResult(target_id=target_id, description=str(e))

        help_effect = StatusEffect(
            effect_type=StatusEffectType.HELPED,
            duration_rounds=1,
            source=actor.character_id,
            description=f"Helped by {actor.name} - advantage on next action",
            modifiers={"advantage": True}
        )
        target.add_status_effect(help_effect)

        return AttackActionResult(
            success=True,
            damage=0,
            description=f"{actor.name} helps {target.name}",
            attack_roll=None,
            effects_applied=["helped_ally"],
            target_id=target_id,
            critical=False
        )

    def _handle_grapple(self, combat_session: CombatSession, actor: CombatantState, target_id: str):
        """Handle a grapple action.

        Args:
            combat_session: Current combat session
            actor: The grappling combatant
            target_id: ID of the target

        Returns:
            AttackActionResult with grapple outcome
        """
        try:
            target = self._validate_target(combat_session, target_id)
        except ValueError as e:
            return InvalidTargetActionResult(target_id=target_id, description=str(e))

        attacker_roll = self.dice_roller.roll("1d20+3")["total"]
        defender_roll = self.dice_roller.roll("1d20+2")["total"]
        success = attacker_roll > defender_roll

        if success:
            grapple_effect = StatusEffect(
                effect_type=StatusEffectType.GRAPPLED,
                duration_rounds=99,
                source=actor.character_id,
                description=f"Grappled by {actor.name}",
                modifiers={"speed": 0, "movement_restricted": True}
            )
            target.add_status_effect(grapple_effect)

            return AttackActionResult(
                success=True,
                damage=0,
                description=f"{actor.name} grapples {target.name} (roll {attacker_roll} vs {defender_roll})",
                attack_roll=attacker_roll,
                effects_applied=["grappled_target"],
                target_id=target_id,
                critical=False
            )
        else:
            return AttackActionResult(
                success=False,
                damage=0,
                description=f"{actor.name} fails to grapple {target.name} (roll {attacker_roll} vs {defender_roll})",
                attack_roll=attacker_roll,
                effects_applied=["grapple_failed"],
                target_id=target_id,
                critical=False
            )

    def _handle_shove(self, combat_session: CombatSession, actor: CombatantState, target_id: str):
        """Handle a shove action.

        Args:
            combat_session: Current combat session
            actor: The shoving combatant
            target_id: ID of the target

        Returns:
            AttackActionResult with shove outcome
        """
        try:
            target = self._validate_target(combat_session, target_id)
        except ValueError as e:
            return InvalidTargetActionResult(target_id=target_id, description=str(e))

        attacker_roll = self.dice_roller.roll("1d20+3")["total"]
        defender_roll = self.dice_roller.roll("1d20+2")["total"]
        success = attacker_roll > defender_roll

        if success:
            prone_effect = StatusEffect(
                effect_type=StatusEffectType.PRONE,
                duration_rounds=99,
                source=actor.character_id,
                description="Knocked prone",
                modifiers={"prone": True}
            )
            target.add_status_effect(prone_effect)

            return AttackActionResult(
                success=True,
                damage=0,
                description=f"{actor.name} shoves {target.name} prone (roll {attacker_roll} vs {defender_roll})",
                attack_roll=attacker_roll,
                effects_applied=["knocked_prone"],
                target_id=target_id,
                critical=False
            )
        else:
            return AttackActionResult(
                success=False,
                damage=0,
                description=f"{actor.name} fails to shove {target.name} (roll {attacker_roll} vs {defender_roll})",
                attack_roll=attacker_roll,
                effects_applied=["shove_failed"],
                target_id=target_id,
                critical=False
            )

    def _handle_ready_action(self, actor: CombatantState) -> DefendActionResult:
        """Handle readying an action.

        Args:
            actor: The combatant readying an action

        Returns:
            DefendActionResult with ready action outcome
        """
        return DefendActionResult(
            success=True,
            description=f"{actor.name} readies an action",
            effects_applied=["action_readied"],
            ac_bonus=0
        )

    def _handle_heal(self, combat_session: CombatSession, actor: CombatantState, target_id: Optional[str]):
        """Handle a healing action.

        Args:
            combat_session: Current combat session
            actor: The healing combatant
            target_id: ID of the target (can be self if None)

        Returns:
            AttackActionResult with healing outcome
        """
        if not target_id:
            target_id = actor.character_id
            target = actor
        else:
            try:
                target = self._validate_target(combat_session, target_id, allow_unconscious=True)
            except ValueError as e:
                return InvalidTargetActionResult(target_id=target_id, description=str(e))

        healing_roll = self.dice_roller.roll("2d4+2")
        healing_amount = healing_roll["total"]

        old_hp = target.hp
        target.hp = min(target.hp + healing_amount, target.max_hp)
        actual_healing = target.hp - old_hp

        return AttackActionResult(
            success=True,
            damage=-actual_healing,  # Negative damage represents healing
            description=f"{actor.name} heals {target.name} for {actual_healing} HP",
            attack_roll=healing_amount,
            effects_applied=["healed"],
            target_id=target_id,
            critical=False
        )

    def _handle_special_ability(self, actor: CombatantState) -> DefendActionResult:
        """Handle a special ability action.

        Args:
            actor: The combatant using special ability

        Returns:
            DefendActionResult with special ability outcome
        """
        return DefendActionResult(
            success=True,
            description=f"{actor.name} uses a special ability",
            effects_applied=["special_ability_used"],
            ac_bonus=0
        )

    def _handle_full_attack(self, combat_session: CombatSession, actor: CombatantState, target_id: str):
        """Handle a full attack action (multiple attacks).

        Args:
            combat_session: Current combat session
            actor: The attacking combatant
            target_id: ID of the target

        Returns:
            AttackActionResult with full attack outcome
        """
        try:
            target = self._validate_target(combat_session, target_id)
        except ValueError as e:
            return InvalidTargetActionResult(target_id=target_id, description=str(e))

        attack1 = self.resolve_attack(actor, target, weapon_damage="1d6")
        attack2 = self.resolve_attack(actor, target, weapon_damage="1d6")

        total_damage = attack1.damage + attack2.damage
        hits = sum([attack1.success, attack2.success])

        effects_applied = []
        if attack1.critical or attack2.critical:
            effects_applied.append("critical_hit")

        description = f"{actor.name} makes multiple attacks: {hits} hits for {total_damage} total damage"

        return AttackActionResult(
            success=hits > 0,
            damage=total_damage,
            description=description,
            attack_roll=max(attack1.attack_roll_total or 0, attack2.attack_roll_total or 0),
            effects_applied=effects_applied,
            target_id=target_id,
            critical=attack1.critical or attack2.critical
        )

    def _handle_bonus_action(self, actor: CombatantState) -> DefendActionResult:
        """Handle a bonus action.

        Args:
            actor: The combatant using bonus action

        Returns:
            DefendActionResult with bonus action outcome
        """
        return DefendActionResult(
            success=True,
            description=f"{actor.name} uses a bonus action",
            effects_applied=["bonus_action_used"],
            ac_bonus=0
        )
