"""Test all action handlers in combat engine."""
import pytest
from gaia.mechanics.combat.combat_engine import CombatEngine
from gaia.models.combat import CombatSession, CombatantState, CombatStats
from gaia.models.combat.mechanics.action_points import ActionPointState


def create_test_combatant(character_id: str, name: str, hp: int = 30) -> CombatantState:
    """Create a test combatant."""
    return CombatantState(
        character_id=character_id,
        name=name,
        initiative=10,
        hp=hp,
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


def create_test_session(*combatants) -> CombatSession:
    """Create a test combat session with the given combatants."""
    combatant_dict = {c.character_id: c for c in combatants}
    turn_order = [c.character_id for c in combatants]

    return CombatSession(
        session_id="test_session",
        scene_id="test_scene",
        round_number=1,
        turn_order=turn_order,
        current_turn_index=0,
        combatants=combatant_dict
    )


def test_dodge_action():
    """Test dodge action applies dodging status."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="dodge"
    )

    assert result.success
    assert "dodging" in result.effects_applied
    assert len(lyra.status_effects) == 1
    assert lyra.status_effects[0].effect_type.value == "dodging"


def test_dash_action():
    """Test dash action increases movement."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="dash"
    )

    assert result.success
    assert "60ft" in result.description  # Speed doubled


def test_disengage_action():
    """Test disengage action applies disengaged status."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="disengage"
    )

    assert result.success
    assert len(lyra.status_effects) == 1
    assert lyra.status_effects[0].effect_type.value == "disengaged"


def test_hide_action():
    """Test hide action performs stealth check."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="hide"
    )

    assert result.roll_result is not None
    assert "stealth" in result.description.lower()


def test_search_action():
    """Test search action performs perception check."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="search"
    )

    assert result.success
    assert "perception" in result.description.lower()
    assert result.roll_result is not None


def test_help_action():
    """Test help action grants advantage to ally."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    marcus = create_test_combatant("marcus", "Marcus")
    session = create_test_session(lyra, marcus)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="help",
        target_id="marcus"
    )

    assert result.success
    assert "helped_ally" in result.effects_applied
    assert len(marcus.status_effects) == 1
    assert marcus.status_effects[0].effect_type.value == "helped"


def test_help_requires_target():
    """Test help action requires a target."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="help"
    )

    assert not result.success
    assert "requires a target" in result.description.lower()


def test_grapple_action():
    """Test grapple action performs contested check."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    marcus = create_test_combatant("marcus", "Marcus")
    session = create_test_session(lyra, marcus)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="grapple",
        target_id="marcus"
    )

    assert result.roll_result is not None
    # Success depends on rolls, but should have proper description
    if result.success:
        assert "grappled_target" in result.effects_applied
        assert any(e.effect_type.value == "grappled" for e in marcus.status_effects)
    else:
        assert "grapple_failed" in result.effects_applied


def test_shove_action():
    """Test shove action performs contested check."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    marcus = create_test_combatant("marcus", "Marcus")
    session = create_test_session(lyra, marcus)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="shove",
        target_id="marcus"
    )

    assert result.roll_result is not None
    # Success depends on rolls
    if result.success:
        assert "knocked_prone" in result.effects_applied
        assert any(e.effect_type.value == "prone" for e in marcus.status_effects)
    else:
        assert "shove_failed" in result.effects_applied


def test_ready_action():
    """Test ready action prepares an action."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="ready_action"
    )

    assert result.success
    assert "action_readied" in result.effects_applied


def test_heal_self():
    """Test heal action on self."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra", hp=10)
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="heal"
    )

    assert result.success
    assert "healed" in result.effects_applied
    assert lyra.hp > 10  # Should be healed


def test_heal_ally():
    """Test heal action on ally."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    marcus = create_test_combatant("marcus", "Marcus", hp=10)
    session = create_test_session(lyra, marcus)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="heal",
        target_id="marcus"
    )

    assert result.success
    assert "healed" in result.effects_applied
    assert marcus.hp > 10  # Marcus should be healed


def test_special_ability():
    """Test special ability action."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="special_ability"
    )

    assert result.success
    assert "special_ability_used" in result.effects_applied


def test_full_attack():
    """Test full attack makes multiple attacks."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    marcus = create_test_combatant("marcus", "Marcus")
    session = create_test_session(lyra, marcus)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="full_attack",
        target_id="marcus"
    )

    # Should have roll result from attacks
    assert result.roll_result is not None
    assert "multiple attacks" in result.description.lower()


def test_full_attack_requires_target():
    """Test full attack requires a target."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="full_attack"
    )

    assert not result.success
    assert "requires a target" in result.description.lower()


def test_bonus_action():
    """Test bonus action."""
    engine = CombatEngine()
    lyra = create_test_combatant("lyra", "Lyra")
    session = create_test_session(lyra)

    result = engine.process_action(
        combat_session=session,
        actor_id="lyra",
        action_type="bonus_action"
    )

    assert result.success
    assert "bonus_action_used" in result.effects_applied
