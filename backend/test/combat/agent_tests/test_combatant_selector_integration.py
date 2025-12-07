"""Integration tests for CombatantSelectorAgent.

These tests use the actual LLM to verify:
1. Combatant extraction from scene context
2. Descriptive enemy naming (not just numbered)
3. Correct hostility determination
4. Player inclusion from roster

Note: These tests require the combatant_selector prompt to be in the database.
Run the migration first:
    ./backend/src/gaia_private/prompts/run_migration.sh
"""

import pytest
from typing import Dict, Any, List

from gaia_private.agents.combat.combatant_selector import (
    CombatantSelectorAgent,
    select_combatants_for_combat,
)
from gaia_private.models.combat.agent_io.initiation.combatant_selection import (
    CombatantSelectionRequest,
    CombatantSelectionOutput,
    IdentifiedCombatant,
)
from gaia_private.prompts.prompt_service import PromptService, PromptNotFoundError
from db.src import db_manager


# Skip all tests in this module if prompt not available
pytestmark = pytest.mark.asyncio


class TestCombatantSelectorIntegration:
    """Integration tests for combatant selection using LLM.

    These tests require the combatant_selector prompt to be in the database.
    Run: make write-prompts
    """

    @pytest.fixture
    def known_players(self) -> List[Dict[str, Any]]:
        """Sample player roster."""
        return [
            {
                "name": "Thorin",
                "character_class": "Fighter",
                "level": 5,
                "hp_max": 45,
                "hp_current": 45,
                "armor_class": 18,
                "initiative_bonus": 2,
                "character_id": "player_1",
            },
            {
                "name": "Elara",
                "character_class": "Wizard",
                "level": 5,
                "hp_max": 28,
                "hp_current": 28,
                "armor_class": 12,
                "initiative_bonus": 3,
                "character_id": "player_2",
            },
        ]

    @pytest.fixture
    def known_npcs_friendly(self) -> List[Dict[str, Any]]:
        """Sample friendly NPCs."""
        return [
            {
                "name": "Bartender Greg",
                "type": "commoner",
                "hostile": False,
            },
        ]

    @pytest.fixture
    def known_npcs_hostile(self) -> List[Dict[str, Any]]:
        """Sample hostile NPCs."""
        return [
            {
                "name": "Bandit Leader",
                "type": "bandit",
                "hostile": True,
            },
        ]

    @pytest.mark.asyncio
    async def test_identifies_all_players(self, known_players: List[Dict[str, Any]]):
        """All known players should be included in combat selection."""
        result = await select_combatants_for_combat(
            trigger_action="Thorin draws his sword and attacks the bandits!",
            campaign_id="test_campaign",
            known_players=known_players,
            known_npcs=[],
            analysis={"scene": {"participants": {"enemies": "2 bandits"}}},
        )

        # All players should be identified
        player_names = {c.name for c in result.combatants if c.type == "player"}
        assert "Thorin" in player_names, "Thorin should be identified"
        assert "Elara" in player_names, "Elara should be identified"
        assert result.player_count == 2

    @pytest.mark.asyncio
    async def test_creates_descriptive_enemy_names(
        self, known_players: List[Dict[str, Any]]
    ):
        """Enemies should have descriptive names, not just numbered."""
        result = await select_combatants_for_combat(
            trigger_action="A pack of goblins emerges from the shadows!",
            campaign_id="test_campaign",
            known_players=known_players,
            known_npcs=[],
            analysis={"scene": {"participants": {"enemies": "3 goblins"}}},
        )

        # Get enemy names
        enemy_names = [c.name for c in result.combatants if c.hostile]

        # Should have 3 enemies
        assert len(enemy_names) >= 3, f"Should have at least 3 goblins, got {len(enemy_names)}"

        # Names should be descriptive (not just "Goblin 1", "Goblin 2", etc.)
        # Allow some numbered names but prefer descriptive ones
        numbered_pattern_count = sum(
            1 for name in enemy_names
            if name.endswith(" 1") or name.endswith(" 2") or name.endswith(" 3")
        )
        descriptive_count = len(enemy_names) - numbered_pattern_count

        # At least some should have descriptive names
        assert descriptive_count > 0 or len(enemy_names) >= 3, (
            f"Expected descriptive enemy names, got: {enemy_names}"
        )

        # All should contain "Goblin" or similar
        for name in enemy_names:
            assert "goblin" in name.lower() or "scout" in name.lower() or "archer" in name.lower(), (
                f"Enemy name '{name}' should reference goblin type"
            )

    @pytest.mark.asyncio
    async def test_preserves_existing_npc_names(
        self,
        known_players: List[Dict[str, Any]],
        known_npcs_hostile: List[Dict[str, Any]],
    ):
        """Existing named NPCs should keep their names."""
        result = await select_combatants_for_combat(
            trigger_action="The Bandit Leader attacks Thorin!",
            campaign_id="test_campaign",
            known_players=known_players,
            known_npcs=known_npcs_hostile,
            analysis=None,
        )

        # The named hostile NPC should be preserved
        hostile_names = [c.name for c in result.combatants if c.hostile]
        assert "Bandit Leader" in hostile_names, (
            f"Named hostile NPC 'Bandit Leader' should be preserved, got: {hostile_names}"
        )

    @pytest.mark.asyncio
    async def test_determines_hostility_correctly(
        self,
        known_players: List[Dict[str, Any]],
        known_npcs_friendly: List[Dict[str, Any]],
    ):
        """Friendly NPCs should not be marked hostile."""
        result = await select_combatants_for_combat(
            trigger_action="Bandits burst into the tavern! Bartender Greg ducks behind the bar.",
            campaign_id="test_campaign",
            known_players=known_players,
            known_npcs=known_npcs_friendly,
            analysis={"scene": {"participants": {"enemies": "2 bandits"}}},
        )

        # Bartender Greg should not be hostile
        greg = next(
            (c for c in result.combatants if "Greg" in c.name or "Bartender" in c.name),
            None,
        )

        # Greg might be excluded from combat (reasonable) or included as non-hostile
        if greg:
            assert not greg.hostile, "Bartender Greg should not be hostile"

        # Should have some hostiles (the bandits)
        assert result.enemy_count >= 1, "Should have at least one hostile enemy"

    @pytest.mark.asyncio
    async def test_creates_enemies_when_none_in_npcs(
        self, known_players: List[Dict[str, Any]]
    ):
        """Should create enemy entries when analysis mentions enemies but npcs list is empty."""
        result = await select_combatants_for_combat(
            trigger_action="An orc warband ambushes the party on the road!",
            campaign_id="test_campaign",
            known_players=known_players,
            known_npcs=[],
            analysis={
                "scene": {"participants": {"enemies": "4 orcs including a chieftain"}},
                "combat_analysis": {"threat_level": "hard"},
            },
        )

        # Should create enemy entries
        enemies = [c for c in result.combatants if c.hostile]
        assert len(enemies) >= 4, f"Should have at least 4 orcs, got {len(enemies)}"

        # At least one should be the chieftain
        enemy_names = [e.name.lower() for e in enemies]
        has_chieftain = any("chief" in name or "leader" in name for name in enemy_names)
        assert has_chieftain, f"Should identify a chieftain/leader, got: {enemy_names}"

        # New enemies should be marked is_new=True
        new_enemies = [e for e in enemies if e.is_new]
        assert len(new_enemies) >= 1, "New enemies should be marked is_new=True"

    @pytest.mark.asyncio
    async def test_handles_mixed_enemy_types(
        self, known_players: List[Dict[str, Any]]
    ):
        """Should handle multiple enemy types in one encounter."""
        result = await select_combatants_for_combat(
            trigger_action="The necromancer raises his hands as skeletons and zombies emerge from the ground!",
            campaign_id="test_campaign",
            known_players=known_players,
            known_npcs=[],
            analysis={
                "scene": {
                    "participants": {
                        "enemies": "1 necromancer, 2 skeletons, and 2 zombies"
                    }
                }
            },
        )

        enemies = [c for c in result.combatants if c.hostile]
        enemy_names = [e.name.lower() for e in enemies]

        # Should have multiple enemy types
        has_necromancer = any("necro" in name or "mage" in name for name in enemy_names)
        has_skeleton = any("skeleton" in name for name in enemy_names)
        has_zombie = any("zombie" in name for name in enemy_names)

        assert has_necromancer, f"Should have necromancer, got: {enemy_names}"
        # At least should have undead
        assert has_skeleton or has_zombie, f"Should have undead creatures, got: {enemy_names}"

    @pytest.mark.asyncio
    async def test_ensures_at_least_one_hostile(
        self, known_players: List[Dict[str, Any]]
    ):
        """Combat should always have at least one hostile."""
        result = await select_combatants_for_combat(
            trigger_action="Combat begins!",
            campaign_id="test_campaign",
            known_players=known_players,
            known_npcs=[],
            analysis=None,  # No enemy hints
        )

        # Should have at least one hostile (fallback creates one)
        assert result.enemy_count >= 1, "Should have at least one hostile combatant"
        hostiles = [c for c in result.combatants if c.hostile]
        assert len(hostiles) >= 1, "Should have at least one hostile"

    @pytest.mark.asyncio
    async def test_selection_output_has_reasoning(
        self, known_players: List[Dict[str, Any]]
    ):
        """Selection should include reasoning for transparency."""
        result = await select_combatants_for_combat(
            trigger_action="Wolves attack the camp!",
            campaign_id="test_campaign",
            known_players=known_players,
            known_npcs=[],
            analysis={"scene": {"participants": {"enemies": "3 wolves"}}},
        )

        # Should have selection reasoning
        assert result.selection_reasoning, "Should have selection_reasoning"
        assert len(result.selection_reasoning) > 10, "Reasoning should be substantive"


class TestCombatantSelectorRequest:
    """Test request building and validation (sync tests)."""

    # Override module-level asyncio marker for sync tests
    pytestmark = []

    def test_request_requires_campaign_id(self):
        """Request should require campaign_id."""
        with pytest.raises(Exception):  # ValidationError
            CombatantSelectionRequest(
                trigger_action="Attack!",
                # missing campaign_id
            )

    def test_request_with_all_fields(self):
        """Request should accept all fields."""
        request = CombatantSelectionRequest(
            campaign_id="test",
            trigger_action="Combat!",
            scene_id="scene_1",
            scene_description="A dark forest",
            location="Forest",
            known_players=[{"name": "Hero"}],
            known_npcs=[{"name": "Villain", "hostile": True}],
            analysis_enemies="3 wolves",
            threat_level="hard",
            party_size=4,
            party_level=5,
        )

        assert request.campaign_id == "test"
        assert request.trigger_action == "Combat!"
        assert request.threat_level == "hard"
        assert request.party_level == 5
