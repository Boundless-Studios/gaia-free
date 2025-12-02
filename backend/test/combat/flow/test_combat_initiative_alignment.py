"""Tests for aligning combat session turn order with initiative output."""

from gaia.mechanics.combat.combat_state_manager import CombatStateManager
from gaia.models.character.character_info import CharacterInfo
from gaia_private.models.combat.agent_io.initiation import InitiativeEntry


def _make_character(character_id: str, name: str, initiative_modifier: int = 0) -> CharacterInfo:
    return CharacterInfo(
        character_id=character_id,
        name=name,
        character_class="Fighter",
        level=3,
        hit_points_current=20,
        hit_points_max=20,
        armor_class=15,
        initiative_modifier=initiative_modifier
    )


def test_apply_initiative_order_overrides_session_turn_order():
    manager = CombatStateManager()
    characters = [
        _make_character("char_a", "Marcus the Gladiator"),
        _make_character("char_b", "Lyra the Swift"),
        _make_character("char_c", "Sister Elara Dawnshield"),
    ]

    session = manager.initialize_combat(
        scene_id="scene_test",
        characters=characters,
        battlefield_config=None,
        campaign_id=None
    )

    name_to_id = {c.name: c.character_id for c in characters}

    initiative_entries = [
        InitiativeEntry(name="Lyra the Swift", initiative=19, is_player=True, is_surprised=False),
        InitiativeEntry(name="Marcus the Gladiator", initiative=15, is_player=True, is_surprised=False),
        InitiativeEntry(name="Sister Elara Dawnshield", initiative=12, is_player=True, is_surprised=False),
    ]

    manager.apply_initiative_order(
        combat_session=session,
        initiative_entries=initiative_entries,
        name_to_combatant_id=name_to_id,
        campaign_id=None
    )

    assert session.turn_order == [
        "char_b",
        "char_a",
        "char_c",
    ], "Turn order should match initiative order mapping"

    assert [session.combatants[cid].initiative for cid in session.turn_order] == [19, 15, 12]
