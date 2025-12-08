"""Unit tests for CombatantStatResolver.

These tests verify the stat resolution logic without using the LLM.
The stat resolver takes identified combatants and populates their stats
from roster data or creature defaults.
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

from gaia_private.agents.combat.combatant_stat_resolver import (
    CombatantStatResolver,
    resolve_combatant_stats,
    DEFAULT_CREATURE_STATS,
)
from gaia_private.models.combat.agent_io.initiation import (
    CombatantSelectionOutput,
    IdentifiedCombatant,
    ResolvedCombatant,
)


class TestCombatantStatResolver:
    """Unit tests for stat resolution logic."""

    @pytest.fixture
    def resolver(self) -> CombatantStatResolver:
        """Create a resolver with mocked roster manager."""
        with patch(
            "gaia_private.agents.combat.combatant_stat_resolver.SceneRosterManager"
        ):
            return CombatantStatResolver(
                campaign_id="test_campaign",
                scene_id="test_scene",
                party_level=5,
            )

    @pytest.fixture
    def known_players(self) -> List[Dict[str, Any]]:
        """Sample player data with stats."""
        return [
            {
                "name": "Thorin",
                "character_class": "Fighter",
                "level": 5,
                "hp_max": 45,
                "hp_current": 40,
                "armor_class": 18,
                "initiative_bonus": 2,
                "character_id": "player_1",
            },
            {
                "name": "Elara",
                "class": "Wizard",  # Test both 'class' and 'character_class'
                "level": 5,
                "hp_max": 28,
                "hp_current": 28,
                "ac": 12,  # Test 'ac' alias
                "initiative_bonus": 3,
                "character_id": "player_2",
            },
        ]

    @pytest.fixture
    def known_npcs(self) -> List[Dict[str, Any]]:
        """Sample NPC data with stats."""
        return [
            {
                "name": "Goblin Scout",
                "type": "Goblin",
                "hostile": True,
                "level": 1,
                "hp_max": 7,
                "hp_current": 7,
                "armor_class": 15,
                "initiative_bonus": 2,
                "character_id": "npc_1",
            },
        ]

    @pytest.fixture
    def basic_selection(self) -> CombatantSelectionOutput:
        """Basic selection output with players and enemies."""
        return CombatantSelectionOutput(
            combatants=[
                IdentifiedCombatant(
                    name="Thorin",
                    type="player",
                    hostile=False,
                    source="roster",
                    class_or_creature="Fighter",
                    is_new=False,
                ),
                IdentifiedCombatant(
                    name="Elara",
                    type="player",
                    hostile=False,
                    source="roster",
                    class_or_creature="Wizard",
                    is_new=False,
                ),
                IdentifiedCombatant(
                    name="Goblin Scout",
                    type="enemy",
                    hostile=True,
                    source="analysis",
                    class_or_creature="Goblin",
                    is_new=False,
                ),
            ],
            player_count=2,
            ally_count=0,
            enemy_count=1,
            selection_reasoning="Test selection",
        )

    def test_resolves_player_stats_from_known_players(
        self,
        resolver: CombatantStatResolver,
        basic_selection: CombatantSelectionOutput,
        known_players: List[Dict[str, Any]],
    ):
        """Player stats should come from known_players list."""
        resolved = resolver.resolve_stats(
            selection=basic_selection,
            known_players=known_players,
            known_npcs=[],
        )

        # Find Thorin
        thorin = next(c for c in resolved if c.name == "Thorin")

        assert thorin.hp_max == 45
        assert thorin.hp_current == 40  # Current HP preserved
        assert thorin.armor_class == 18
        assert thorin.level == 5
        assert thorin.initiative_bonus == 2
        assert thorin.character_id == "player_1"
        assert thorin.class_or_creature == "Fighter"
        assert thorin.hostile is False

    def test_resolves_player_stats_with_class_alias(
        self,
        resolver: CombatantStatResolver,
        basic_selection: CombatantSelectionOutput,
        known_players: List[Dict[str, Any]],
    ):
        """Should handle both 'class' and 'character_class' fields."""
        resolved = resolver.resolve_stats(
            selection=basic_selection,
            known_players=known_players,
            known_npcs=[],
        )

        # Find Elara (uses 'class' not 'character_class')
        elara = next(c for c in resolved if c.name == "Elara")

        assert elara.class_or_creature == "Wizard"
        assert elara.armor_class == 12  # Uses 'ac' alias

    def test_resolves_npc_stats_from_known_npcs(
        self,
        resolver: CombatantStatResolver,
        basic_selection: CombatantSelectionOutput,
        known_players: List[Dict[str, Any]],
        known_npcs: List[Dict[str, Any]],
    ):
        """NPC stats should come from known_npcs list."""
        resolved = resolver.resolve_stats(
            selection=basic_selection,
            known_players=known_players,
            known_npcs=known_npcs,
        )

        # Find Goblin Scout
        goblin = next(c for c in resolved if c.name == "Goblin Scout")

        assert goblin.hp_max == 7
        assert goblin.armor_class == 15
        assert goblin.hostile is True
        assert goblin.type == "enemy"

    def test_uses_creature_defaults_for_unknown_enemies(
        self, resolver: CombatantStatResolver
    ):
        """Unknown enemies should get stats from creature defaults."""
        selection = CombatantSelectionOutput(
            combatants=[
                IdentifiedCombatant(
                    name="Goblin Archer",
                    type="enemy",
                    hostile=True,
                    source="analysis",
                    class_or_creature="Goblin",
                    is_new=True,
                ),
            ],
            player_count=0,
            ally_count=0,
            enemy_count=1,
            selection_reasoning="Test",
        )

        resolved = resolver.resolve_stats(selection=selection)

        goblin = resolved[0]
        # Should use goblin defaults from DEFAULT_CREATURE_STATS
        assert goblin.hp_max == DEFAULT_CREATURE_STATS["goblin"]["hp"]
        assert goblin.armor_class == DEFAULT_CREATURE_STATS["goblin"]["ac"]
        assert goblin.source == "creature_defaults"

    def test_uses_creature_defaults_by_name_match(
        self, resolver: CombatantStatResolver
    ):
        """Creature defaults should be found by name even without class_or_creature."""
        selection = CombatantSelectionOutput(
            combatants=[
                IdentifiedCombatant(
                    name="Orc Berserker",
                    type="enemy",
                    hostile=True,
                    source="analysis",
                    class_or_creature=None,  # No creature type specified
                    is_new=True,
                ),
            ],
            player_count=0,
            ally_count=0,
            enemy_count=1,
            selection_reasoning="Test",
        )

        resolved = resolver.resolve_stats(selection=selection)

        orc = resolved[0]
        # Should match "orc" in name
        assert orc.hp_max == DEFAULT_CREATURE_STATS["orc"]["hp"]
        assert orc.armor_class == DEFAULT_CREATURE_STATS["orc"]["ac"]

    def test_scales_unknown_enemies_to_party_level(
        self, resolver: CombatantStatResolver
    ):
        """Enemies not in creature defaults should scale to party level."""
        selection = CombatantSelectionOutput(
            combatants=[
                IdentifiedCombatant(
                    name="Mysterious Cultist",
                    type="enemy",
                    hostile=True,
                    source="analysis",
                    class_or_creature="Cultist",
                    is_new=True,
                ),
            ],
            player_count=0,
            ally_count=0,
            enemy_count=1,
            selection_reasoning="Test",
        )

        # Resolver has party_level=5
        resolved = resolver.resolve_stats(selection=selection)

        cultist = resolved[0]
        # Should use party-level scaled defaults
        assert cultist.level == 5
        assert cultist.source == "scaled_default"
        # HP = 8 + (level * 5) = 8 + 25 = 33
        assert cultist.hp_max == 33
        # AC = min(18, 10 + (level // 3)) = min(18, 10 + 1) = 11
        assert cultist.armor_class == 11

    def test_uses_defaults_for_unknown_player(
        self, resolver: CombatantStatResolver
    ):
        """Unknown players should get defaults based on party level."""
        selection = CombatantSelectionOutput(
            combatants=[
                IdentifiedCombatant(
                    name="Unknown Hero",
                    type="player",
                    hostile=False,
                    source="roster",
                    class_or_creature="Adventurer",
                    is_new=False,
                ),
            ],
            player_count=1,
            ally_count=0,
            enemy_count=0,
            selection_reasoning="Test",
        )

        resolved = resolver.resolve_stats(selection=selection)

        player = resolved[0]
        assert player.level == 5  # party_level
        assert player.source == "default"

    def test_find_by_name_case_insensitive(self):
        """Name matching should be case-insensitive."""
        resolver = CombatantStatResolver(campaign_id="test", party_level=1)

        characters = [
            {"name": "Thorin Oakenshield", "level": 5},
            {"name": "ELARA THE WIZARD", "level": 5},
        ]

        # Should find regardless of case
        result1 = resolver._find_by_name("thorin oakenshield", characters)
        result2 = resolver._find_by_name("Elara The Wizard", characters)

        assert result1 is not None
        assert result2 is not None


class TestResolvedCombatantSerialization:
    """Test the to_player_dict and to_npc_dict methods."""

    def test_to_player_dict(self):
        """to_player_dict should serialize for player context."""
        combatant = ResolvedCombatant(
            name="Thorin",
            type="player",
            hostile=False,
            source="roster",
            class_or_creature="Fighter",
            level=5,
            hp_max=45,
            hp_current=40,
            armor_class=18,
            initiative_bonus=2,
            is_new=False,
            character_id="player_1",
        )

        result = combatant.to_player_dict()

        assert result["name"] == "Thorin"
        assert result["class"] == "Fighter"
        assert result["character_class"] == "Fighter"  # Both aliases
        assert result["level"] == 5
        assert result["hp_max"] == 45
        assert result["hp_current"] == 40
        assert result["armor_class"] == 18
        assert result["initiative_bonus"] == 2
        assert result["character_id"] == "player_1"
        # Should NOT have hostile or is_new
        assert "hostile" not in result
        assert "is_new" not in result

    def test_to_npc_dict(self):
        """to_npc_dict should serialize for NPC context."""
        combatant = ResolvedCombatant(
            name="Goblin Scout",
            type="enemy",
            hostile=True,
            source="analysis",
            class_or_creature="Goblin",
            level=1,
            hp_max=7,
            hp_current=7,
            armor_class=15,
            initiative_bonus=2,
            is_new=True,
            character_id=None,
        )

        result = combatant.to_npc_dict()

        assert result["name"] == "Goblin Scout"
        assert result["type"] == "Goblin"
        assert result["hostile"] is True
        assert result["level"] == 1
        assert result["hp_max"] == 7
        assert result["hp_current"] == 7
        assert result["armor_class"] == 15
        assert result["initiative_bonus"] == 2
        assert result["is_new"] is True
        assert result["character_id"] is None
        # Should NOT have 'class' or 'character_class'
        assert "class" not in result
        assert "character_class" not in result


class TestConvenienceFunction:
    """Test the resolve_combatant_stats convenience function."""

    def test_resolve_combatant_stats_function(self):
        """Convenience function should work without instantiating resolver."""
        selection = CombatantSelectionOutput(
            combatants=[
                IdentifiedCombatant(
                    name="Test Player",
                    type="player",
                    hostile=False,
                    source="roster",
                    class_or_creature="Fighter",
                    is_new=False,
                ),
            ],
            player_count=1,
            ally_count=0,
            enemy_count=0,
            selection_reasoning="Test",
        )

        known_players = [
            {
                "name": "Test Player",
                "character_class": "Fighter",
                "level": 3,
                "hp_max": 30,
                "hp_current": 30,
                "armor_class": 16,
            }
        ]

        with patch(
            "gaia_private.agents.combat.combatant_stat_resolver.SceneRosterManager"
        ):
            resolved = resolve_combatant_stats(
                selection=selection,
                campaign_id="test",
                known_players=known_players,
                party_level=3,
            )

        assert len(resolved) == 1
        assert resolved[0].name == "Test Player"
        assert resolved[0].hp_max == 30


class TestDefaultStats:
    """Test default stat calculations."""

    def test_default_hp_formula(self):
        """HP = 8 + (level * 5)."""
        resolver = CombatantStatResolver(campaign_id="test", party_level=1)

        assert resolver._default_hp(1) == 13  # 8 + 5
        assert resolver._default_hp(5) == 33  # 8 + 25
        assert resolver._default_hp(10) == 58  # 8 + 50

    def test_default_ac_formula(self):
        """AC = min(18, 10 + (level // 3))."""
        resolver = CombatantStatResolver(campaign_id="test", party_level=1)

        assert resolver._default_ac(1) == 10  # 10 + 0
        assert resolver._default_ac(3) == 11  # 10 + 1
        assert resolver._default_ac(6) == 12  # 10 + 2
        assert resolver._default_ac(20) == 16  # 10 + 6
        assert resolver._default_ac(30) == 18  # capped at 18


class TestCreatureDefaults:
    """Test creature default stat lookup."""

    def test_all_creatures_have_required_stats(self):
        """All creature defaults should have hp, ac, init."""
        for creature, stats in DEFAULT_CREATURE_STATS.items():
            assert "hp" in stats, f"{creature} missing hp"
            assert "ac" in stats, f"{creature} missing ac"
            assert "init" in stats, f"{creature} missing init"
            assert "level" in stats, f"{creature} missing level"

    def test_creature_lookup_by_type(self):
        """Should find creature defaults by class_or_creature."""
        resolver = CombatantStatResolver(campaign_id="test", party_level=1)

        result = resolver._get_creature_defaults("Orc Warrior", "orc")
        assert result is not None
        assert result == DEFAULT_CREATURE_STATS["orc"]

    def test_creature_lookup_by_name(self):
        """Should find creature defaults by name when type is None."""
        resolver = CombatantStatResolver(campaign_id="test", party_level=1)

        result = resolver._get_creature_defaults("Wolf Pack Leader", None)
        assert result is not None
        # Should match 'wolf' in name since 'wolves' redirects
        # Actually the lookup checks if "wolf" is in "wolf pack leader"
        assert result == DEFAULT_CREATURE_STATS["wolf"]

    def test_unknown_creature_returns_none(self):
        """Unknown creatures should return None for defaults."""
        resolver = CombatantStatResolver(campaign_id="test", party_level=1)

        result = resolver._get_creature_defaults("Mysterious Entity", "Unknown")
        assert result is None
