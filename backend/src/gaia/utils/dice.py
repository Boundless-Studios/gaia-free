"""Dice utilities for D&D gameplay."""

import random
import re
from enum import Enum
from typing import Dict, Any, Optional


# TODO We should not be returning dicts, we should be returning well formed structs

class DiceType(Enum):
    """Standard dice types in D&D."""
    D4 = 4
    D6 = 6
    D8 = 8
    D10 = 10
    D12 = 12
    D20 = 20
    D100 = 100


class DiceRoller:
    """Roll dice for D&D gameplay."""

    def __init__(self):
        self.roll_history = []
    
    # TODO The way this is defined is way too damn complicated, simplify
    def roll(self, expression: str, advantage: bool = False, disadvantage: bool = False) -> Dict[str, Any]:
        """Roll dice based on expressions like '1d20+5', '2d8+1d6+3', or '2d6 fire damage'."""
        # Split expression into tokens for + and -
        tokens = re.findall(r'([+-]?[^+-]+)', expression.replace(' ', ''))
        if not tokens:
            raise ValueError(f"Invalid dice expression: {expression}")
        
        total = 0
        all_rolls = []
        all_raw_rolls = []
        all_raw_rolls2 = []
        modifier = 0
        damage_types = []
        is_critical = False
        is_critical_fail = False
        dice_found = False
        valid_token_found = False
        single_adv_dis_total = None
        for token in tokens:
            dice_match = re.match(r'([+-]?)(\d*)d(\d+)', token)
            if dice_match:
                dice_found = True
                valid_token_found = True
                sign, count_str, die_str = dice_match.groups()
                dice_count = int(count_str) if count_str else 1
                dice_type = int(die_str)
                
                # Validate dice count and type
                if dice_count <= 0:
                    raise ValueError(f"Invalid dice expression: {expression}")
                if dice_type <= 0:
                    raise ValueError(f"Invalid dice expression: {expression}")
                
                # Check for damage type (e.g., 2d6fire)
                dmg_type_match = re.match(r'.*d\d+(\w+)$', token)
                if dmg_type_match:
                    damage_types.append(dmg_type_match.group(1))
                # Roll the dice
                for _ in range(dice_count):
                    roll1 = random.randint(1, dice_type)
                    if advantage or disadvantage:
                        roll2 = random.randint(1, dice_type)
                        all_raw_rolls.append(roll1)
                        all_raw_rolls2.append(roll2)
                        if dice_count == 1:
                            # For single die, include both rolls in 'rolls' and set total to max/min
                            all_rolls.extend([roll1, roll2])
                            single_adv_dis_total = max(roll1, roll2) if advantage else min(roll1, roll2)
                        else:
                            chosen = max(roll1, roll2) if advantage else min(roll1, roll2)
                            all_rolls.append(chosen)
                        # Critical check for d20
                        if dice_type == 20:
                            if roll1 == 20 or roll2 == 20:
                                is_critical = True
                            if roll1 == 1 or roll2 == 1:
                                is_critical_fail = True
                    else:
                        all_raw_rolls.append(roll1)
                        all_rolls.append(roll1)
                        if dice_type == 20:
                            if roll1 == 20:
                                is_critical = True
                            if roll1 == 1:
                                is_critical_fail = True
            else:
                # Modifier (e.g., +3 or -2) - must match the whole token
                mod_match = re.fullmatch(r'([+-]?\d+)', token)
                if mod_match:
                    modifier += int(mod_match.group(1))
                    valid_token_found = True
                else:
                    pass  # Don't raise yet, check after loop
        # FINAL CHECK: If no valid dice or modifier tokens were found, raise ValueError
        if not valid_token_found:
            raise ValueError(f"Invalid dice expression: {expression}")
        if not dice_found:
            raise ValueError(f"Invalid dice expression: {expression}")
        if single_adv_dis_total is not None:
            total = single_adv_dis_total + modifier
        else:
            total = sum(all_rolls) + modifier
        result = {
            "expression": expression,
            "rolls": all_rolls,
            "total": total,
            "modifier": modifier,
            "critical": is_critical,
            "critical_fail": is_critical_fail,
            "advantage": advantage,
            "disadvantage": disadvantage
        }
        if advantage or disadvantage:
            result["raw_rolls"] = all_raw_rolls
            result["raw_rolls2"] = all_raw_rolls2
        if damage_types:
            result["damage_types"] = damage_types
        self.roll_history.append(result)
        return result

    def roll_dice(self,
                  dice_type: DiceType,
                  count: int = 1,
                  modifier: int = 0,
                  advantage: bool = False,
                  disadvantage: bool = False) -> Dict[str, Any]:
        """Roll dice programmatically using DiceType enum.

        Args:
            dice_type: The type of dice to roll
            count: Number of dice to roll
            modifier: Modifier to add to the total
            advantage: Roll with advantage (roll twice, take higher)
            disadvantage: Roll with disadvantage (roll twice, take lower)

        Returns:
            Dictionary with roll results
        """
        dice_value = dice_type.value
        all_rolls = []
        all_raw_rolls = []
        all_raw_rolls2 = []
        is_critical = False
        is_critical_fail = False
        single_adv_dis_total = None

        # Simplified rolling logic
        if advantage or disadvantage:
            # Roll twice for each die and pick the better/worse
            for _ in range(count):
                roll1 = random.randint(1, dice_value)
                roll2 = random.randint(1, dice_value)

                all_raw_rolls.append(roll1)
                all_raw_rolls2.append(roll2)

                # Pick the appropriate roll
                chosen = max(roll1, roll2) if advantage else min(roll1, roll2)

                if count == 1:
                    # For single die, keep both rolls for transparency
                    all_rolls.extend([roll1, roll2])
                    single_adv_dis_total = chosen
                else:
                    all_rolls.append(chosen)

                # Critical check for d20
                if dice_type == DiceType.D20:
                    is_critical = is_critical or chosen == 20
                    is_critical_fail = is_critical_fail or chosen == 1
        else:
            # Standard rolling - just roll the dice normally
            all_raw_rolls = [random.randint(1, dice_value) for _ in range(count)]
            all_rolls = all_raw_rolls

            # Critical check for d20
            if dice_type == DiceType.D20:
                is_critical = any(roll == 20 for roll in all_rolls)
                is_critical_fail = any(roll == 1 for roll in all_rolls)

        if single_adv_dis_total is not None:
            total = single_adv_dis_total + modifier
        else:
            total = sum(all_rolls) + modifier

        expression = f"{count}d{dice_value}{'+' + str(modifier) if modifier > 0 else '' if modifier == 0 else str(modifier)}"

        result = {
            "expression": expression,
            "rolls": all_rolls,
            "total": total,
            "modifier": modifier,
            "critical": is_critical,
            "critical_fail": is_critical_fail,
            "advantage": advantage,
            "disadvantage": disadvantage
        }

        if advantage or disadvantage:
            result["raw_rolls"] = all_raw_rolls
            result["raw_rolls2"] = all_raw_rolls2

        self.roll_history.append(result)
        return result

    def roll_attack(self,
                    attack_bonus: int = 0,
                    advantage: bool = False,
                    disadvantage: bool = False) -> Dict[str, Any]:
        """Roll a d20 attack roll.

        Args:
            attack_bonus: Attack modifier to add
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage

        Returns:
            Attack roll result
        """
        return self.roll_dice(DiceType.D20, 1, attack_bonus, advantage, disadvantage)

    def roll_saving_throw(self,
                          save_modifier: int = 0,
                          advantage: bool = False,
                          disadvantage: bool = False) -> Dict[str, Any]:
        """Roll a d20 saving throw.

        Args:
            save_modifier: Saving throw modifier
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage

        Returns:
            Saving throw result
        """
        return self.roll_dice(DiceType.D20, 1, save_modifier, advantage, disadvantage)

    def roll_ability_check(self,
                          ability_modifier: int = 0,
                          advantage: bool = False,
                          disadvantage: bool = False) -> Dict[str, Any]:
        """Roll a d20 ability check.

        Args:
            ability_modifier: Ability check modifier
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage

        Returns:
            Ability check result
        """
        return self.roll_dice(DiceType.D20, 1, ability_modifier, advantage, disadvantage)

    def roll_damage(self,
                   damage_dice: DiceType,
                   dice_count: int = 1,
                   damage_modifier: int = 0) -> Dict[str, Any]:
        """Roll damage dice.

        Args:
            damage_dice: Type of damage dice
            dice_count: Number of dice to roll
            damage_modifier: Damage modifier to add

        Returns:
            Damage roll result
        """
        return self.roll_dice(damage_dice, dice_count, damage_modifier)

    def roll_initiative(self, dex_modifier: int = 0,
                       initiative_bonus: int = 0) -> Dict[str, Any]:
        """Roll initiative for combat.

        Args:
            dex_modifier: Dexterity modifier
            initiative_bonus: Additional initiative bonuses

        Returns:
            Initiative roll result
        """
        return self.roll_dice(DiceType.D20, 1, dex_modifier + initiative_bonus)
    
    def get_statistics(self, expression: str, num_rolls: int = 1000) -> Dict[str, Any]:
        results = []
        for _ in range(num_rolls):
            result = self.roll(expression)
            results.append(result["total"])
        return {
            "expression": expression,
            "num_rolls": num_rolls,
            "min": min(results),
            "max": max(results),
            "average": sum(results) / len(results),
            "results": results
        }

class DiceParser:
    """Parse dice expressions."""
    def parse(self, expression: str) -> Dict[str, Any]:
        # Split expression into tokens for + and -
        tokens = re.findall(r'([+-]?[^+-]+)', expression.replace(' ', ''))
        if not tokens:
            raise ValueError(f"Invalid dice expression: {expression}")
        dice_sets = []
        total_dice = 0
        last_type = None
        modifier = 0
        dice_found = False
        valid_token_found = False
        for token in tokens:
            dice_match = re.match(r'([+-]?)(\d*)d(\d+)', token)
            if dice_match:
                dice_found = True
                valid_token_found = True
                sign, count_str, die_str = dice_match.groups()
                dice_count = int(count_str) if count_str else 1
                dice_type = int(die_str)
                
                # Validate dice count and type
                if dice_count <= 0:
                    raise ValueError(f"Invalid dice expression: {expression}")
                if dice_type <= 0:
                    raise ValueError(f"Invalid dice expression: {expression}")
                
                dice_sets.append({"count": dice_count, "type": dice_type})
                total_dice += dice_count
                last_type = dice_type
            else:
                # Modifier (e.g., +3 or -2) - must match the whole token
                mod_match = re.fullmatch(r'([+-]?\d+)', token)
                if mod_match:
                    modifier += int(mod_match.group(1))
                    valid_token_found = True
                else:
                    pass  # Don't raise yet, check after loop
        # FINAL CHECK: If no valid dice or modifier tokens were found, raise ValueError
        if not valid_token_found:
            raise ValueError(f"Invalid dice expression: {expression}")
        if not dice_found:
            raise ValueError(f"Invalid dice expression: {expression}")
        result = {
            "dice_count": total_dice,
            "dice_type": last_type,
            "modifier": modifier
        }
        if len(dice_sets) > 1:
            result["dice_sets"] = dice_sets
        # Parse damage type if present
        damage_type_match = re.search(r"\d+d\d+(?:[+-]\d+)?\s+(\w+)", expression)
        if damage_type_match:
            result["damage_type"] = damage_type_match.group(1)
        return result 