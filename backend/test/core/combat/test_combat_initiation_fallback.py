"""Test combat initiation with target validation and arena scenarios."""

import pytest
from gaia_private.models.combat.agent_io.initiation import (
    CombatInitiationRequest,
    CombatantInfo,
    SceneContext,
    OpeningAction
)
from gaia_private.agents.combat.initiator import CombatInitiatorAgent
from gaia_private.agents.tools.combat.combat_initiator_tools_export import (
    combat_initiator_output_formatter_tool_handler
)


class TestCombatTargetAssignment:
    """Test that combat initiation properly assigns targets in opening actions."""

    def test_arena_has_initiating_character(self):
        """Arena combat should specify an initiating character."""
        from gaia.api.routes.arena import build_arena_prompt

        # Build arena prompt with default initiating character
        prompt = build_arena_prompt(difficulty="medium")

        # Verify initiating character is mentioned
        assert "Marcus the Gladiator" in prompt
        assert "charges forward and strikes first" in prompt
        assert "Initiating Character: Marcus the Gladiator" in prompt

    def test_arena_custom_initiating_character(self):
        """Arena combat should support custom initiating characters."""
        from gaia.api.routes.arena import build_arena_prompt

        # Build arena prompt with custom initiating character
        prompt = build_arena_prompt(difficulty="hard", initiating_character="Lyra the Swift")

        # Verify custom initiating character is used
        assert "Lyra the Swift" in prompt
        assert "charges forward and strikes first" in prompt
        assert "Initiating Character: Lyra the Swift" in prompt

    @pytest.mark.asyncio
    async def test_opening_action_requires_target_for_attack(self):
        """Opening actions with attack types must have a target."""

        # Simulate tool call with missing target
        params = {
            "scene_id": "test_scene",
            "campaign_id": "test_campaign",
            "initiative_order": [
                {
                    "name": "Lyra the Swift",
                    "initiative": 15,
                    "is_player": True,
                    "is_surprised": False,
                    "dex_score": 12
                }
            ],
            "battlefield": {"terrain": "arena", "size": "medium"},
            "narrative": {
                "scene_description": "Combat begins",
                "combat_trigger": "Arena start"
            },
            "conditions": {},
            "opening_actions": [
                {
                    "actor": "Lyra the Swift",
                    "action_type": "basic_attack",
                    "target": None,  # Missing target!
                    "description": "strikes at Theron the Mystic"
                }
            ]
        }

        # Should raise ValueError for missing target
        with pytest.raises(ValueError) as exc_info:
            await combat_initiator_output_formatter_tool_handler(None, params)

        assert "requires a target" in str(exc_info.value)
        assert "Lyra the Swift" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_opening_action_with_target_succeeds(self):
        """Opening actions with proper target should succeed."""

        params = {
            "scene_id": "test_scene",
            "campaign_id": "test_campaign",
            "initiative_order": [
                {
                    "name": "Marcus the Gladiator",
                    "initiative": 15,
                    "is_player": True,
                    "is_surprised": False,
                    "dex_score": 12
                },
                {
                    "name": "Gorak the Brutal",
                    "initiative": 10,
                    "is_player": False,
                    "is_surprised": False,
                    "dex_score": 12
                }
            ],
            "battlefield": {"terrain": "arena", "size": "medium"},
            "narrative": {
                "scene_description": "Arena combat",
                "combat_trigger": "Marcus charges"
            },
            "conditions": {},
            "opening_actions": [
                {
                    "actor": "Marcus the Gladiator",
                    "action_type": "basic_attack",
                    "target": "Gorak the Brutal",  # Proper target!
                    "description": "swings his sword at Gorak"
                }
            ]
        }

        # Should succeed with proper target
        result = await combat_initiator_output_formatter_tool_handler(None, params)

        assert result is not None
        assert len(result.opening_actions) == 1
        assert result.opening_actions[0].actor == "Marcus the Gladiator"
        assert result.opening_actions[0].target == "Gorak the Brutal"
        assert result.opening_actions[0].action_type == "basic_attack"

    @pytest.mark.asyncio
    async def test_non_targeting_action_without_target_succeeds(self):
        """Non-targeting actions (move, defend) don't require a target."""

        params = {
            "scene_id": "test_scene",
            "campaign_id": "test_campaign",
            "initiative_order": [
                {
                    "name": "Lyra the Swift",
                    "initiative": 15,
                    "is_player": True,
                    "is_surprised": False,
                    "dex_score": 12
                }
            ],
            "battlefield": {"terrain": "arena", "size": "medium"},
            "narrative": {
                "scene_description": "Combat begins",
                "combat_trigger": "Movement"
            },
            "conditions": {},
            "opening_actions": [
                {
                    "actor": "Lyra the Swift",
                    "action_type": "move",
                    "target": None,  # No target needed for movement
                    "description": "dashes to cover"
                }
            ]
        }

        # Should succeed without target for move action
        result = await combat_initiator_output_formatter_tool_handler(None, params)

        assert result is not None
        assert len(result.opening_actions) == 1
        assert result.opening_actions[0].actor == "Lyra the Swift"
        assert result.opening_actions[0].target is None
        assert result.opening_actions[0].action_type == "move"

    @pytest.mark.asyncio
    async def test_multiple_targeting_actions_validation(self):
        """All targeting action types should be validated."""

        targeting_actions = ["basic_attack", "spell_cast", "shove", "grapple", "ranged_attack", "melee_attack"]

        for action_type in targeting_actions:
            params = {
                "scene_id": "test_scene",
                "campaign_id": "test_campaign",
                "initiative_order": [
                    {
                        "name": "Test Actor",
                        "initiative": 15,
                        "is_player": True,
                        "is_surprised": False,
                        "dex_score": 12
                    }
                ],
                "battlefield": {"terrain": "test", "size": "medium"},
                "narrative": {"scene_description": "Test", "combat_trigger": "Test"},
                "conditions": {},
                "opening_actions": [
                    {
                        "actor": "Test Actor",
                        "action_type": action_type,
                        "target": None,  # Missing target
                        "description": "test action"
                    }
                ]
            }

            # Should raise ValueError for each targeting action
            with pytest.raises(ValueError) as exc_info:
                await combat_initiator_output_formatter_tool_handler(None, params)

            assert "requires a target" in str(exc_info.value).lower()

    def test_combat_initiation_request_has_initiating_character_field(self):
        """CombatInitiationRequest should have initiating_character field."""

        # Create a minimal request
        request = CombatInitiationRequest(
            campaign_id="test_campaign",
            scene=SceneContext(
                scene_id="test_scene",
                title="Test Scene",
                description="Test",
                location="Arena",
                location_type="combat",
                environmental_factors=[]
            ),
            player_action="Marcus attacks!",
            combatants=[
                CombatantInfo(
                    name="Marcus the Gladiator",
                    type="player",
                    class_or_creature="Fighter",
                    hostile=False,
                    level=5
                )
            ],
            initiating_character="Marcus the Gladiator"
        )

        assert hasattr(request, 'initiating_character')
        assert request.initiating_character == "Marcus the Gladiator"

    def test_combat_initiation_request_initiating_character_optional(self):
        """CombatInitiationRequest should allow None for initiating_character."""

        # Create request without initiating character
        request = CombatInitiationRequest(
            campaign_id="test_campaign",
            scene=SceneContext(
                scene_id="test_scene",
                title="Test Scene",
                description="Test",
                location="Forest",
                location_type="wilderness",
                environmental_factors=[]
            ),
            player_action="Player explores",
            combatants=[]
        )

        assert hasattr(request, 'initiating_character')
        assert request.initiating_character is None
