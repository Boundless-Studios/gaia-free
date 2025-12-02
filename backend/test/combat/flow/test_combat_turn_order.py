"""Unit tests for combat turn order and round advancement."""
import sys
sys.path.append('/home/gaia')

from gaia.models.combat.persistence.combat_session import CombatSession
from gaia.models.combat.persistence.combatant_state import CombatantState

def test_basic_turn_advancement():
    """Test basic turn advancement without any unconscious combatants."""
    print("\n=== TEST: Basic Turn Advancement ===")

    session = CombatSession(
        session_id='test',
        scene_id='test_scene'
    )

    # Add 4 combatants
    combatants = [
        ('warrior', 'Warrior', 15),
        ('archer', 'Archer', 12),
        ('mage', 'Mage', 10),
        ('rogue', 'Rogue', 8)
    ]

    for cid, name, init in combatants:
        combatant = CombatantState(
            character_id=cid,
            name=name,
            initiative=init,
            hp=10,
            max_hp=10,
            ac=15,
            level=1,
            is_npc=True
        )
        session.add_combatant(combatant)

    print(f"Initial state:")
    print(f"  Turn order: {session.turn_order}")
    print(f"  Current index: {session.current_turn_index}")
    print(f"  Current character: {session.resolve_current_character()}")
    print(f"  Round: {session.round_number}")

    # Advance through one complete round
    for i in range(4):
        print(f"\n--- Advancing turn {i+1} ---")
        result = session.advance_turn()
        print(f"  Next character: {result['next_character']}")
        print(f"  New round: {result['new_round']}")
        print(f"  Round number: {result['round_number']}")
        print(f"  Current index: {session.current_turn_index}")

    assert session.round_number == 2, f"Expected round 2, got {session.round_number}"
    print("\n✅ Basic turn advancement works correctly")


def test_skip_unconscious_combatant():
    """Test that unconscious combatants are properly skipped."""
    print("\n=== TEST: Skip Unconscious Combatant ===")

    session = CombatSession(
        session_id='test',
        scene_id='test_scene'
    )

    # Add 4 combatants
    combatants = [
        ('warrior', 'Warrior', 15, True),   # conscious
        ('archer', 'Archer', 12, False),    # unconscious
        ('mage', 'Mage', 10, True),         # conscious
        ('rogue', 'Rogue', 8, True)         # conscious
    ]

    for cid, name, init, conscious in combatants:
        combatant = CombatantState(
            character_id=cid,
            name=name,
            initiative=init,
            hp=10 if conscious else 0,
            max_hp=10,
            ac=15,
            level=1,
            is_npc=True
        )
        combatant.is_conscious = conscious
        session.add_combatant(combatant)

    print(f"Initial state:")
    print(f"  Turn order: {session.turn_order}")
    print(f"  Archer conscious: {session.combatants['archer'].is_conscious}")
    print(f"  Current: {session.resolve_current_character()}")
    print(f"  Round: {session.round_number}")

    # Advance from Warrior - should skip unconscious Archer and go to Mage
    print(f"\nAdvancing from Warrior...")
    result = session.advance_turn()
    print(f"  Next character: {result['next_character']}")
    print(f"  Current index: {session.current_turn_index}")
    print(f"  New round: {result['new_round']}")

    assert result['next_character'] == 'mage', f"Expected mage, got {result['next_character']}"
    assert not result['new_round'], "Should not start new round yet"

    # Continue through the round
    print(f"\nAdvancing from Mage...")
    result = session.advance_turn()
    print(f"  Next character: {result['next_character']}")
    assert result['next_character'] == 'rogue'

    print(f"\nAdvancing from Rogue...")
    result = session.advance_turn()
    print(f"  Next character: {result['next_character']}")
    print(f"  New round: {result['new_round']}")
    print(f"  Round number: {result['round_number']}")

    assert result['next_character'] == 'warrior', "Should return to warrior"
    assert result['new_round'], "Should start new round after rogue"
    assert result['round_number'] == 2, f"Should be round 2, got {result['round_number']}"

    print("\n✅ Unconscious skipping works correctly")


def test_all_but_one_unconscious():
    """Test when all but one combatant are unconscious."""
    print("\n=== TEST: All But One Unconscious ===")

    session = CombatSession(
        session_id='test',
        scene_id='test_scene'
    )

    # Add 4 combatants, 3 unconscious
    combatants = [
        ('warrior', 'Warrior', 15, False),  # unconscious
        ('archer', 'Archer', 12, False),    # unconscious
        ('mage', 'Mage', 10, True),         # conscious - only one!
        ('rogue', 'Rogue', 8, False)        # unconscious
    ]

    for cid, name, init, conscious in combatants:
        combatant = CombatantState(
            character_id=cid,
            name=name,
            initiative=init,
            hp=10 if conscious else 0,
            max_hp=10,
            ac=15,
            level=1,
            is_npc=True
        )
        combatant.is_conscious = conscious
        session.add_combatant(combatant)

    print(f"Initial state:")
    print(f"  Turn order: {session.turn_order}")
    print(f"  Current: {session.resolve_current_character()}")

    # Since warrior is unconscious, should skip to mage
    current = session.resolve_current_character()
    print(f"  Resolved current: {current}")
    assert current == 'mage', f"Should start with mage (only conscious), got {current}"

    # Advance turn - with only one combatant, stays at index 0
    # so new_round will be False (doesn't wrap from non-zero to 0)
    print(f"\nAdvancing from Mage...")
    result = session.advance_turn()
    print(f"  Next character: {result['next_character']}")
    print(f"  New round: {result['new_round']}")
    print(f"  Round number: {result['round_number']}")

    assert result['next_character'] == 'mage', "Should stay on mage"
    assert not result['new_round'], "With only one combatant, stays at index 0 (no wrap)"
    assert result['round_number'] == 1, "Round should stay at 1"

    print("\n✅ Single conscious combatant works correctly")


def test_midround_knockout():
    """Test what happens when a combatant is knocked out mid-round."""
    print("\n=== TEST: Mid-Round Knockout ===")

    session = CombatSession(
        session_id='test',
        scene_id='test_scene'
    )

    # Add 3 combatants, all conscious initially
    combatants = [
        ('warrior', 'Warrior', 15),
        ('archer', 'Archer', 12),
        ('mage', 'Mage', 10)
    ]

    for cid, name, init in combatants:
        combatant = CombatantState(
            character_id=cid,
            name=name,
            initiative=init,
            hp=10,
            max_hp=10,
            ac=15,
            level=1,
            is_npc=True
        )
        session.add_combatant(combatant)

    print(f"Initial state: All conscious")
    print(f"  Turn order: {session.turn_order}")

    # Advance to archer
    print(f"\nAdvancing from Warrior to Archer...")
    result = session.advance_turn()
    assert result['next_character'] == 'archer'

    # Now knock out archer (simulate taking damage)
    print(f"\nKnocking out Archer...")
    session.combatants['archer'].is_conscious = False
    session.combatants['archer'].hp = 0

    # Advance turn - should skip archer and go to mage
    print(f"\nAdvancing from Archer (now unconscious)...")
    result = session.advance_turn()
    print(f"  Next character: {result['next_character']}")
    print(f"  Current index: {session.current_turn_index}")

    assert result['next_character'] == 'mage', f"Should skip to mage, got {result['next_character']}"

    # Complete the round
    print(f"\nAdvancing from Mage...")
    result = session.advance_turn()
    print(f"  Next character: {result['next_character']}")
    print(f"  New round: {result['new_round']}")

    assert result['next_character'] == 'warrior'
    assert result['new_round'], "Should start new round"

    # In round 2, archer should still be skipped
    print(f"\nAdvancing in round 2 from Warrior...")
    result = session.advance_turn()
    print(f"  Next character: {result['next_character']}")

    assert result['next_character'] == 'mage', "Should still skip unconscious archer"

    print("\n✅ Mid-round knockout handled correctly")


if __name__ == "__main__":
    test_basic_turn_advancement()
    test_skip_unconscious_combatant()
    test_all_but_one_unconscious()
    test_midround_knockout()
    print("\n🎉 All tests passed!")
