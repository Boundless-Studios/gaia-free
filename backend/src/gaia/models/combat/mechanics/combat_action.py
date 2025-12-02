"""Combat action model - backward compatibility wrapper.

DEPRECATED: Use CombatActionRecord from combat_action_record.py instead.
This file exists only for backward compatibility.
"""
from .combat_action_record import CombatActionRecord, CombatAction

__all__ = ['CombatAction', 'CombatActionRecord']