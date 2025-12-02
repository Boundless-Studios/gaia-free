"""Well-formed data structures for dice roll results."""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class DiceType(Enum):
    """Standard dice types in D&D."""
    D4 = 4
    D6 = 6
    D8 = 8
    D10 = 10
    D12 = 12
    D20 = 20
    D100 = 100


@dataclass
class DiceRollResult:
    """Result of a dice roll."""
    expression: str
    rolls: List[int]
    total: int
    modifier: int = 0
    critical: bool = False
    critical_fail: bool = False
    advantage: bool = False
    disadvantage: bool = False
    damage_types: List[str] = field(default_factory=list)
    raw_rolls: Optional[List[int]] = None  # For advantage/disadvantage
    raw_rolls2: Optional[List[int]] = None  # For advantage/disadvantage

    @property
    def is_success(self) -> bool:
        """Check if this was a successful roll (not a critical fail)."""
        return not self.critical_fail


@dataclass
class AttackRollResult:
    """Result of an attack roll."""
    attack_roll: int
    attack_bonus: int
    total: int
    critical: bool = False
    critical_fail: bool = False
    advantage: bool = False
    disadvantage: bool = False
    rolls: List[int] = field(default_factory=list)

    @property
    def hits_ac(self) -> int:
        """The AC this attack would hit."""
        return self.total


@dataclass
class SavingThrowResult:
    """Result of a saving throw."""
    save_roll: int
    save_modifier: int
    total: int
    save_type: str = ""
    success_dc: Optional[int] = None
    advantage: bool = False
    disadvantage: bool = False
    rolls: List[int] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """Check if the save was successful against the DC."""
        if self.success_dc is None:
            return True
        return self.total >= self.success_dc


@dataclass
class DamageRollResult:
    """Result of a damage roll."""
    damage_dice: str
    rolls: List[int]
    total_damage: int
    damage_modifier: int = 0
    damage_type: str = "physical"
    is_critical: bool = False


@dataclass
class InitiativeRollResult:
    """Result of an initiative roll."""
    character_id: str
    character_name: str
    roll: int
    modifier: int
    total: int

    @property
    def initiative_value(self) -> int:
        """The final initiative value for turn order."""
        return self.total


@dataclass
class DiceParseResult:
    """Result of parsing a dice expression."""
    dice_count: int
    dice_type: int
    modifier: int = 0
    dice_sets: Optional[List[dict]] = None
    damage_type: Optional[str] = None


@dataclass
class DiceStatistics:
    """Statistics from multiple rolls of the same expression."""
    expression: str
    num_rolls: int
    minimum: int
    maximum: int
    average: float
    results: List[int]