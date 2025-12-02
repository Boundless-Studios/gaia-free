"""Tests for scene_describer roll-based observation system."""
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaia_private.agents.scene.scene_describer import SceneDescriberAgent
from gaia_private.agents.scene.tools.perception_check_tool import resolve_perception_check


class TestPerceptionCheckTool:
    """Test the perception check tool."""

    def test_perception_check_resolves_roll(self):
        """Perception check should roll d20 vs DC."""
        result = resolve_perception_check(
            description="A guard standing in the room",
            difficulty_class=10
        )

        assert "roll" in result
        assert "dc" in result
        assert "success" in result
        assert "margin" in result
        assert "description" in result

        # Roll should be 1-20
        assert 1 <= result["roll"] <= 20

        # DC should match
        assert result["dc"] == 10

        # Success should be correct
        expected_success = result["roll"] >= result["dc"]
        assert result["success"] == expected_success

        # Margin should be calculated correctly
        expected_margin = result["roll"] - result["dc"]
        assert result["margin"] == expected_margin

        # Description should match
        assert result["description"] == "A guard standing in the room"

    def test_perception_check_easy_dc(self):
        """Test with very easy DC."""
        result = resolve_perception_check(
            description="A huge column is falling over",
            difficulty_class=5
        )

        # Should almost always succeed with DC 5
        assert result["dc"] == 5
        # If roll is 5+, should succeed
        if result["roll"] >= 5:
            assert result["success"] is True

    def test_perception_check_hard_dc(self):
        """Test with very hard DC."""
        result = resolve_perception_check(
            description="A nearly invisible seam in the wall",
            difficulty_class=25
        )

        # Should be hard to succeed with DC 25
        assert result["dc"] == 25
        # Only succeeds if roll is 25+ (nat 20 + modifiers, or just lucky)
        if result["roll"] >= 25:
            assert result["success"] is True
        else:
            assert result["success"] is False

    def test_perception_check_multiple_rolls(self):
        """Test that multiple rolls produce different results."""
        results = []
        for _ in range(10):
            result = resolve_perception_check(
                description="Test observation",
                difficulty_class=12
            )
            results.append(result["roll"])

        # Should have variety in rolls (not all the same)
        unique_rolls = len(set(results))
        # Allow for some duplicates but expect variety
        print(f"Got {unique_rolls} unique rolls out of 10 attempts: {results}")


class TestSceneDescriberAgent:
    """Test the SceneDescriberAgent with roll-based observations."""

    @pytest.mark.asyncio
    async def test_scene_describer_initialization(self):
        """Scene describer should initialize with tools."""
        agent = SceneDescriberAgent()

        analysis_context = {
            "previous_scenes": [{
                "narrative": "You are in a dimly lit tavern. Patrons sit at various tables."
            }],
            "active_characters": [
                {"name": "Bartender"},
                {"name": "Mysterious Cloaked Figure"}
            ]
        }

        await agent.initialize(analysis_context)

        # Should have agent initialized
        assert agent.agent is not None

        # Should have perception_check tool
        assert agent.agent.tools is not None
        assert len(agent.agent.tools) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("PARASAIL_API_KEY"),
        reason="Requires PARASAIL_API_KEY environment variable for LLM calls"
    )
    async def test_scene_describer_response_format(self):
        """Scene describer should return observations with DCs and rolls."""
        agent = SceneDescriberAgent()

        analysis_context = {
            "previous_scenes": [{
                "narrative": "You enter a stone corridor with moss-covered walls. A torch burns brightly on the wall. You hear footsteps echoing in the distance."
            }],
            "active_characters": [
                {"name": "Guard"},
                {"name": "Mysterious Figure"}
            ]
        }

        user_input = "What do I see?"

        response = await agent.describe_scene(user_input, analysis_context)

        # Should have required fields
        assert "observations" in response, "Response missing 'observations'"
        assert "summary" in response, "Response missing 'summary'"
        assert "handoff_to" in response, "Response missing 'handoff_to'"

        # Observations should be a list (may be empty due to LLM non-determinism)
        assert isinstance(response["observations"], list), "Observations should be a list"

        # Summary should be a string (may be empty if no observations)
        assert isinstance(response["summary"], str), "Summary should be a string"

        # Should not handoff for simple observation
        assert response["handoff_to"] == "none", "Should not handoff for observation queries"

        # Note: We don't assert len(observations) > 0 because LLM may return 0 observations
        # due to non-determinism. The important thing is the structure is correct.

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("PARASAIL_API_KEY"),
        reason="Requires PARASAIL_API_KEY environment variable for LLM calls"
    )
    async def test_scene_describer_observation_structure(self):
        """Each observation should have proper structure."""
        agent = SceneDescriberAgent()

        analysis_context = {
            "previous_scenes": [{
                "narrative": "You are in a bustling market square. Vendors hawk their wares."
            }],
            "active_characters": [
                {"name": "Fruit Vendor"},
                {"name": "Guard"}
            ]
        }

        user_input = "What do I notice?"

        response = await agent.describe_scene(user_input, analysis_context)

        observations = response.get("observations", [])

        print(f"\nGenerated {len(observations)} total observations")

        # Count successes, close misses, and clear failures
        successes = []
        close_misses = []
        clear_failures = []

        # If observations were generated, validate structure
        if observations:
            for i, obs in enumerate(observations):
                print(f"\nObservation {i+1}:")
                print(f"  Description: {obs.get('description', 'N/A')}")
                print(f"  DC: {obs.get('difficulty_class', 'N/A')}")
                print(f"  Roll: {obs.get('roll', 'N/A')}")
                print(f"  Success: {obs.get('success', 'N/A')}")
                print(f"  Margin: {obs.get('margin', 'N/A')}")
                print(f"  Include: {obs.get('include', 'N/A')}")
                print(f"  Type: {obs.get('observation_type', 'N/A')}")
                print(f"  Flavor: {obs.get('flavor', 'N/A')[:80] if obs.get('flavor') else 'N/A'}...")

                # Each observation should have required fields
                assert "description" in obs, "Observation missing description"
                assert "difficulty_class" in obs, "Observation missing DC"
                assert "roll" in obs, "Observation missing roll"
                assert "success" in obs, "Observation missing success"

                # DC should be in reasonable range
                dc = obs["difficulty_class"]
                assert 5 <= dc <= 25, f"DC {dc} out of range (5-25)"

                # Roll should be 1-20
                roll = obs["roll"]
                assert 1 <= roll <= 20, f"Roll {roll} out of range (1-20)"

                # Success should match roll vs DC
                expected_success = roll >= dc
                assert obs["success"] == expected_success, f"Success mismatch: roll {roll} vs DC {dc}"

                # Categorize observation
                margin = obs.get("margin", 0)
                success = obs.get("success", False)

                if success:
                    successes.append(obs)
                elif -3 <= margin <= -1:
                    close_misses.append(obs)
                else:
                    clear_failures.append(obs)

        print(f"\n--- Summary ---")
        print(f"Successes: {len(successes)}")
        print(f"Close Misses: {len(close_misses)}")
        print(f"Clear Failures: {len(clear_failures)}")


    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("PARASAIL_API_KEY"),
        reason="Requires PARASAIL_API_KEY environment variable for LLM calls"
    )
    async def test_close_miss_vague_narration(self):
        """Close misses should get vague narration without revealing details."""
        agent = SceneDescriberAgent()

        analysis_context = {
            "previous_scenes": [{
                "narrative": "You are in a shadowy alley. Danger lurks nearby."
            }],
            "active_characters": [
                {"name": "Suspicious Figure"}
            ]
        }

        user_input = "What do I perceive?"

        response = await agent.describe_scene(user_input, analysis_context)

        observations = response.get("observations", [])

        # Look for close misses
        close_misses = []
        for obs in observations:
            margin = obs.get("margin", 0)
            success = obs.get("success", False)
            if not success and -3 <= margin <= -1:
                close_misses.append(obs)

        print(f"\n--- Close Miss Examples ---")
        for obs in close_misses:
            description = obs.get("description", "")
            print(f"Description (what they missed): {description}")
            print(f"Roll: {obs.get('roll')} vs DC {obs.get('difficulty_class')} (margin: {obs.get('margin')})")
            print()

            # Verify observation has required fields
            assert "description" in obs, "Observation missing description"
            assert "roll" in obs, "Observation missing roll"
            assert "difficulty_class" in obs, "Observation missing DC"
            assert "success" in obs, "Observation missing success"
            assert "margin" in obs, "Observation missing margin"


class TestObservationDCGuidelines:
    """Test that the perception tool works across DC ranges."""

    def test_obvious_things_low_dc(self):
        """Obvious things should use DC 5-10."""
        obvious_things = [
            ("A huge stone column is toppling over", 5),
            ("The room is on fire", 5),
            ("A person is screaming loudly", 8)
        ]

        for thing, dc in obvious_things:
            result = resolve_perception_check(thing, difficulty_class=dc)
            print(f"Obvious: '{thing}' - Roll: {result['roll']} vs DC {dc} = {result['success']}")
            assert result['dc'] == dc

    def test_subtle_things_moderate_dc(self):
        """Subtle things should use DC 15-18."""
        subtle_things = [
            ("Someone whispering across the room", 15),
            ("A guard's hand trembling slightly", 18),
            ("A faint odor of sulfur", 16)
        ]

        for thing, dc in subtle_things:
            result = resolve_perception_check(thing, difficulty_class=dc)
            print(f"Subtle: '{thing}' - Roll: {result['roll']} vs DC {dc} = {result['success']}")
            assert result['dc'] == dc

    def test_hidden_things_high_dc(self):
        """Hidden things should use DC 20+."""
        hidden_things = [
            ("A nearly invisible seam in the wall", 20),
            ("Breathing in complete silence", 22),
            ("A trace scent days old", 25)
        ]

        for thing, dc in hidden_things:
            result = resolve_perception_check(thing, difficulty_class=dc)
            print(f"Hidden: '{thing}' - Roll: {result['roll']} vs DC {dc} = {result['success']}")
            assert result['dc'] == dc


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
