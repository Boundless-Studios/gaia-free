"""Tests for CharacterSetupManager name normalization."""

from gaia.mechanics.combat.character_setup import CharacterSetupManager
from gaia_private.models.combat.agent_io.initiation import (
    BattlefieldConfig,
    CombatInitiation,
    CombatNarrative,
    InitiativeEntry,
)
from gaia.models.character.enums import CharacterRole


def test_setup_combat_characters_preserves_llm_names():
    """LLM-provided names should remain canonical, with aliases for cleanup."""
    manager = CharacterSetupManager()
    malformed_name = (
        "Silas Vex: Healthy, 13/13 Hp. "
        "Grok The Unyielding: Healthy, 16/16 Hp. "
        "Seven Unknown Corpses Seated At The Table Appear Recently Deceased."
    )

    combat_model = CombatInitiation(
        scene_id="scene_001",
        campaign_id="campaign_145",
        initiative_order=[
            InitiativeEntry(name="Silas Vex", initiative=7, is_player=True),
            InitiativeEntry(name=malformed_name, initiative=7, is_player=False),
            InitiativeEntry(name="Grok the Unyielding", initiative=4, is_player=True),
        ],
        battlefield=BattlefieldConfig(terrain="stone"),
        narrative=CombatNarrative(scene_description="desc"),
    )

    result = manager.setup_combat_characters(combat_model, combat_request=None)

    # NPC should keep the raw LLM-provided name
    npc_names = [
        character.name
        for character in result.characters
        if character.character_role == CharacterRole.NPC_COMBATANT
    ]
    assert npc_names == [malformed_name]

    # Initiative entry should remain unchanged
    assert combat_model.initiative_order[1].name == malformed_name

    # Alias mapping still exposes the cleaned-up variant for downstream references
    normalized_id = result.name_to_combatant_id[malformed_name]
    assert result.name_to_combatant_id["Seven Unknown Corpses"] == normalized_id
