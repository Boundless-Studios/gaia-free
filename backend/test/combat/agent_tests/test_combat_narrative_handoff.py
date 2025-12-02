"""Unit tests for combat narrative handoff between orchestrator and combat request."""

import unittest
from unittest.mock import MagicMock
from gaia_private.models.combat.agent_io.fight import (
    CombatActionRequest,
    CurrentTurnInfo,
    CombatantView
)
from gaia_private.models.combat.agent_io.initiation import BattlefieldConfig
from gaia_private.models.combat.agent_io.initiation.combat_narrative import CombatNarrative
from gaia_private.models.combat.orchestration.cached_payload import CombatCachedPayload
from gaia_private.models.combat.orchestration.analysis_context import CombatAnalysisContext
from gaia_private.orchestration.combat_orchestrator import CombatOrchestrator


class TestCombatNarrativeHandoff(unittest.TestCase):
    """Test the handling of combat narrative in request building."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock campaign runner
        self.campaign_runner = MagicMock()
        self.orchestrator = CombatOrchestrator(self.campaign_runner)

        # Create common test data
        self.campaign_id = "test_campaign"
        self.user_input = "I attack with my sword"

        # Create minimal required data for request
        self.base_context = CombatAnalysisContext(
            campaign_id=self.campaign_id,
            players=[{'name': 'Alice'}],
            npcs=[{'name': 'Goblin'}]
        )

        self.cached_payload = CombatCachedPayload(
            initiative_order=[
                {'name': 'Alice', 'type': 'player'},
                {'name': 'Goblin', 'type': 'enemy'}
            ],
            current_combatant='Alice',
            round_number=1,
            name_to_combatant_id={}
        )

    def test_combat_narrative_pydantic_object(self):
        """Test that a CombatNarrative object is properly passed through."""
        # Add CombatNarrative object to context
        narrative = CombatNarrative(
            scene_description='The tavern erupts into chaos',
            combat_trigger='Bar fight started',
            enemy_description='Angry patrons',
            tactical_notes='Tables provide cover',
            atmosphere='Tense and chaotic'
        )
        self.base_context.combat_narrative = narrative

        # Build the request
        request = self.orchestrator.build_combat_action_request(
            user_input=self.user_input,
            campaign_id=self.campaign_id,
            analysis_context=self.base_context,
            combat_session=None,
            cached_payload=self.cached_payload
        )

        # Verify the narrative is the same CombatNarrative object
        self.assertIs(request.combat_narrative, narrative)
        self.assertEqual(request.combat_narrative.scene_description, 'The tavern erupts into chaos')
        self.assertEqual(request.combat_narrative.combat_trigger, 'Bar fight started')
        self.assertEqual(request.combat_narrative.enemy_description, 'Angry patrons')
        self.assertEqual(request.combat_narrative.tactical_notes, 'Tables provide cover')
        self.assertEqual(request.combat_narrative.atmosphere, 'Tense and chaotic')

    def test_combat_narrative_none_when_not_provided(self):
        """Test that narrative is None when not provided."""
        # No narrative in context
        # Build the request
        request = self.orchestrator.build_combat_action_request(
            user_input=self.user_input,
            campaign_id=self.campaign_id,
            analysis_context=self.base_context,
            combat_session=None,
            cached_payload=self.cached_payload
        )

        # Verify narrative is None
        self.assertIsNone(request.combat_narrative)

    def test_combat_narrative_expects_pydantic_type(self):
        """Test that only CombatNarrative Pydantic types are expected."""
        # Context should contain CombatNarrative objects only
        # This test documents the expectation rather than testing rejection
        narrative = CombatNarrative(scene_description='Proper Pydantic object')
        self.base_context.combat_narrative = narrative

        # Build the request
        request = self.orchestrator.build_combat_action_request(
            user_input=self.user_input,
            campaign_id=self.campaign_id,
            analysis_context=self.base_context,
            combat_session=None,
            cached_payload=self.cached_payload
        )

        # Verify narrative is used directly
        self.assertIs(request.combat_narrative, narrative)

    def test_battlefield_pydantic_object(self):
        """Test that battlefield is properly handled as a Pydantic object."""
        # Add battlefield to context
        battlefield = BattlefieldConfig(
            terrain='forest',
            size='large',
            features=['trees', 'rocks'],
            hazards=['thorns'],
            lighting='dim',
            visibility=30
        )
        self.cached_payload.battlefield = battlefield

        # Build the request
        request = self.orchestrator.build_combat_action_request(
            user_input=self.user_input,
            campaign_id=self.campaign_id,
            analysis_context=self.base_context,
            combat_session=None,
            cached_payload=self.cached_payload
        )

        # Verify battlefield is properly set
        self.assertIsInstance(request.battlefield, BattlefieldConfig)
        self.assertEqual(request.battlefield.terrain, 'forest')
        self.assertEqual(request.battlefield.size, 'large')
        self.assertEqual(request.battlefield.features, ['trees', 'rocks'])
        self.assertEqual(request.battlefield.hazards, ['thorns'])
        self.assertEqual(request.battlefield.lighting, 'dim')
        self.assertEqual(request.battlefield.visibility, 30)

    def test_full_request_with_all_pydantic_models(self):
        """Test that the full request works with all Pydantic models."""
        # Create complete Pydantic models
        narrative = CombatNarrative(
            scene_description='Epic mountain battle',
            combat_trigger='Dragon swoops down',
            enemy_description='Ancient red dragon',
            tactical_notes='Seek cover from breath weapon',
            atmosphere='Terrifying'
        )
        self.base_context.combat_narrative = narrative
        self.base_context.tactical_situation = 'Party caught in the open'

        battlefield = BattlefieldConfig(
            terrain='mountains',
            size='huge',
            features=['cliffs', 'boulders'],
            hazards=['falling rocks', 'narrow ledges'],
            environmental_effects=['strong winds'],
            lighting='bright',
            visibility=120,
            movement_difficulty='difficult'
        )
        self.cached_payload.battlefield = battlefield

        # Build the request
        request = self.orchestrator.build_combat_action_request(
            user_input=self.user_input,
            campaign_id=self.campaign_id,
            analysis_context=self.base_context,
            combat_session=None,
            cached_payload=self.cached_payload
        )

        # Verify all fields are properly set
        self.assertEqual(request.campaign_id, self.campaign_id)
        self.assertEqual(request.player_action, self.user_input)
        self.assertIsInstance(request.combat_narrative, CombatNarrative)
        self.assertIsInstance(request.battlefield, BattlefieldConfig)
        self.assertEqual(request.tactical_situation, 'Party caught in the open')

        # Verify specific field values
        self.assertEqual(request.combat_narrative.scene_description, 'Epic mountain battle')
        self.assertEqual(request.battlefield.terrain, 'mountains')
        self.assertEqual(request.battlefield.size, 'huge')

        # Verify the request can be serialized and deserialized (model_dump and reconstruction)
        request_dict = request.model_dump()
        self.assertIsInstance(request_dict, dict)
        self.assertIn('combat_narrative', request_dict)
        self.assertIn('battlefield', request_dict)

        # Verify we can create a new request from the dumped data
        reconstructed = CombatActionRequest(**request_dict)
        self.assertEqual(reconstructed.campaign_id, request.campaign_id)
        self.assertEqual(reconstructed.player_action, request.player_action)
        # After reconstruction, these will be new instances but with same data
        self.assertEqual(reconstructed.combat_narrative.scene_description,
                        request.combat_narrative.scene_description)
        self.assertEqual(reconstructed.battlefield.terrain, request.battlefield.terrain)

    def test_request_validation_with_minimal_data(self):
        """Test that request validates with only required fields."""
        # Build request with minimal data (no optional narrative)
        request = self.orchestrator.build_combat_action_request(
            user_input=self.user_input,
            campaign_id=self.campaign_id,
            analysis_context=self.base_context,
            combat_session=None,
            cached_payload=self.cached_payload
        )

        # Should still create a valid request
        self.assertIsInstance(request, CombatActionRequest)
        self.assertEqual(request.campaign_id, self.campaign_id)
        self.assertEqual(request.player_action, self.user_input)
        self.assertIsNone(request.combat_narrative)  # Optional field
        self.assertIsInstance(request.battlefield, BattlefieldConfig)  # Has default
        self.assertIsInstance(request.current_turn, CurrentTurnInfo)
        self.assertIsInstance(request.combatants, list)


if __name__ == '__main__':
    unittest.main()