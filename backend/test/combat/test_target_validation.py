"""Test target validation in combat engine."""
import pytest
from gaia.mechanics.combat.combat_engine import CombatEngine
from gaia.models.combat import CombatSession, CombatantState, CombatStats
from gaia.models.combat.mechanics.action_points import ActionPointState


def create_test_combatant(character_id: str, name: str) -> CombatantState:
    """Create a test combatant."""
    return CombatantState(
        character_id=character_id,
        name=name,
        initiative=10,
        hp=30,
        max_hp=30,
        ac=15,
        level=5,
        is_npc=False,
        action_points=ActionPointState(
            max_ap=4,
            current_ap=4,
            available_actions=[]
        ),
        combat_stats=CombatStats(
            attack_bonus=3,
            damage_bonus=2,
            spell_save_dc=13,
            initiative_bonus=2,
            speed=30
        )
    )


def test_complex_spell_invalid_target():
    """Test that complex_spell properly validates targets."""
    engine = CombatEngine()

    # Create session with only two combatants
    lyra = create_test_combatant("lyra_the_swift", "Lyra the Swift")
    marcus = create_test_combatant("marcus_the_gladiator", "Marcus the Gladiator")

    session = CombatSession(
        session_id="test_session",
        scene_id="test_scene",
        round_number=1,
        turn_order=["lyra_the_swift", "marcus_the_gladiator"],
        current_turn_index=0,
        combatants={
            "lyra_the_swift": lyra,
            "marcus_the_gladiator": marcus
        }
    )

    # Try to cast complex_spell on non-existent target "Theron"
    result = engine.process_action(
        combat_session=session,
        actor_id="lyra_the_swift",
        action_type="complex_spell",
        target_id="Theron"
    )

    # Should fail with invalid target
    assert result.success == False
    assert "not in combat" in result.description.lower()
    assert "invalid_target" in result.effects_applied


def test_basic_attack_invalid_target():
    """Test that basic_attack properly validates targets."""
    engine = CombatEngine()

    lyra = create_test_combatant("lyra_the_swift", "Lyra the Swift")
    marcus = create_test_combatant("marcus_the_gladiator", "Marcus the Gladiator")

    session = CombatSession(
        session_id="test_session",
        scene_id="test_scene",
        round_number=1,
        turn_order=["lyra_the_swift", "marcus_the_gladiator"],
        current_turn_index=0,
        combatants={
            "lyra_the_swift": lyra,
            "marcus_the_gladiator": marcus
        }
    )

    # Try to attack non-existent target "Gorak"
    result = engine.process_action(
        combat_session=session,
        actor_id="lyra_the_swift",
        action_type="basic_attack",
        target_id="Gorak"
    )

    # Should fail with invalid target
    assert result.success == False
    assert "gorak" in result.description.lower()
    assert "not in combat" in result.description.lower()


def test_valid_target():
    """Test that valid targets work correctly."""
    engine = CombatEngine()

    lyra = create_test_combatant("lyra_the_swift", "Lyra the Swift")
    marcus = create_test_combatant("marcus_the_gladiator", "Marcus the Gladiator")

    session = CombatSession(
        session_id="test_session",
        scene_id="test_scene",
        round_number=1,
        turn_order=["lyra_the_swift", "marcus_the_gladiator"],
        current_turn_index=0,
        combatants={
            "lyra_the_swift": lyra,
            "marcus_the_gladiator": marcus
        }
    )

    # Attack valid target Marcus
    result = engine.process_action(
        combat_session=session,
        actor_id="lyra_the_swift",
        action_type="complex_spell",
        target_id="marcus_the_gladiator"
    )

    # Should work (success depends on roll, but shouldn't have invalid_target)
    assert "invalid_target" not in result.effects_applied
    assert "not in combat" not in result.description.lower()
