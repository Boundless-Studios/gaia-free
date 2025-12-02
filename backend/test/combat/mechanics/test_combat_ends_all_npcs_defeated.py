"""Test that combat properly ends when all NPCs are defeated."""

import pytest

from gaia.models.combat.persistence.combat_session import CombatSession
from gaia.models.combat.persistence.combatant_state import CombatantState
from gaia.models.combat.mechanics.action_points import ActionPointState
from gaia.models.combat.mechanics.enums import CombatStatus


@pytest.mark.unit
class TestCombatEndsAllNPCsDefeated:
    """Test that combat properly detects victory when all NPCs reach 0 HP."""

    @pytest.fixture
    def combat_session(self):
        """Create a combat session with PCs and NPCs."""
        session = CombatSession(
            session_id="test_victory_001",
            scene_id="scene_001",
            status=CombatStatus.IN_PROGRESS,
            round_number=1,
            turn_order=["PC1", "PC2", "NPC1", "NPC2"],
            current_turn_index=0
        )

        # Add PC combatants
        session.combatants = {
            "PC1": CombatantState(
                character_id="PC1",
                name="Fighter",
                initiative=15,
                hp=30,
                max_hp=30,
                ac=16,
                level=3,
                is_npc=False,
                is_conscious=True,
                action_points=ActionPointState(max_ap=3, current_ap=3)
            ),
            "PC2": CombatantState(
                character_id="PC2",
                name="Wizard",
                initiative=12,
                hp=20,
                max_hp=20,
                ac=12,
                level=3,
                is_npc=False,
                is_conscious=True,
                action_points=ActionPointState(max_ap=3, current_ap=3)
            ),
            # NPC enemies
            "NPC1": CombatantState(
                character_id="NPC1",
                name="Goblin 1",
                initiative=10,
                hp=7,
                max_hp=7,
                ac=13,
                level=1,
                is_npc=True,
                is_conscious=True,
                action_points=ActionPointState(max_ap=2, current_ap=2)
            ),
            "NPC2": CombatantState(
                character_id="NPC2",
                name="Goblin 2",
                initiative=8,
                hp=7,
                max_hp=7,
                ac=13,
                level=1,
                is_npc=True,
                is_conscious=True,
                action_points=ActionPointState(max_ap=2, current_ap=2)
            )
        }

        return session

    def test_combat_ends_when_all_npcs_defeated(self, combat_session):
        """Test that check_victory_conditions returns players_victory when all NPCs are at 0 HP."""
        # Initially, combat should not be over
        result = combat_session.check_victory_conditions()
        assert result is None, "Combat should not be over with active combatants"

        # Defeat all NPCs by setting HP to 0 and is_conscious to False
        combat_session.combatants["NPC1"].hp = 0
        combat_session.combatants["NPC1"].is_conscious = False
        combat_session.combatants["NPC2"].hp = 0
        combat_session.combatants["NPC2"].is_conscious = False

        # Now check victory conditions
        result = combat_session.check_victory_conditions()
        assert result == "players_victory", "Combat should end with players_victory when all NPCs are defeated"

    def test_combat_ends_even_with_is_conscious_flag_bug(self, combat_session):
        """Test that combat ends even if is_conscious flag is incorrectly True when hp=0.

        This tests the edge case where is_conscious=True but hp=0.
        The check_victory_conditions should still detect victory by checking hp > 0.
        """
        # Simulate edge case: NPCs have 0 HP but is_conscious is still True
        combat_session.combatants["NPC1"].hp = 0
        combat_session.combatants["NPC1"].is_conscious = True  # Edge case
        combat_session.combatants["NPC2"].hp = 0
        combat_session.combatants["NPC2"].is_conscious = True  # Edge case

        # get_active_combatants should check BOTH is_conscious AND hp > 0
        active_npcs = [c for c in combat_session.get_active_combatants() if c.is_npc]

        # EXPECTED: NPCs with 0 HP should NOT be considered active
        assert len(active_npcs) == 0, "get_active_combatants should check hp > 0, not just is_conscious"

        # Combat should end with players_victory
        result = combat_session.check_victory_conditions()
        assert result == "players_victory", "Combat should end when all NPCs have 0 HP, regardless of is_conscious flag"

    def test_get_active_combatants_should_check_hp(self, combat_session):
        """Test that get_active_combatants filters by both is_conscious AND hp > 0."""
        # Set one NPC to 0 HP but leave is_conscious=True (edge case)
        combat_session.combatants["NPC1"].hp = 0
        combat_session.combatants["NPC1"].is_conscious = True

        # Get active combatants
        active = combat_session.get_active_combatants()
        npc1_in_active = any(c.character_id == "NPC1" for c in active)

        # EXPECTED: NPC1 should NOT be in active combatants because hp = 0
        assert not npc1_in_active, "NPC with 0 HP should not be considered active, regardless of is_conscious flag"

    def test_apply_damage_properly_sets_unconscious(self, combat_session):
        """Test that apply_damage() correctly sets is_conscious=False when HP reaches 0."""
        npc = combat_session.combatants["NPC1"]

        # Apply enough damage to knock unconscious
        result = npc.apply_damage(7)  # NPC has 7 HP

        assert result["knocked_unconscious"] is True
        assert npc.hp == 0
        assert npc.is_conscious is False

    def test_combat_ends_when_pcs_defeated(self, combat_session):
        """Test that check_victory_conditions returns players_defeat when all PCs are at 0 HP."""
        # Defeat all PCs
        combat_session.combatants["PC1"].hp = 0
        combat_session.combatants["PC1"].is_conscious = False
        combat_session.combatants["PC2"].hp = 0
        combat_session.combatants["PC2"].is_conscious = False

        # Check victory conditions
        result = combat_session.check_victory_conditions()
        assert result == "players_defeat", "Combat should end with players_defeat when all PCs are defeated"

    def test_combat_continues_with_mixed_state(self, combat_session):
        """Test that combat continues when both PCs and NPCs are still active."""
        # Defeat one NPC, leave one active
        combat_session.combatants["NPC1"].hp = 0
        combat_session.combatants["NPC1"].is_conscious = False

        # Combat should continue
        result = combat_session.check_victory_conditions()
        assert result is None, "Combat should continue when both sides have active combatants"
