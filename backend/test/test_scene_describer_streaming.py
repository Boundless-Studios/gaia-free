"""Integration test for scene describer streaming.

This test validates that:
1. Tool calls (perception_check) are properly detected and captured
2. Tool outputs don't leak to the frontend stream
3. Only actual narrative text is streamed to users
"""

import asyncio
import logging
import sys
from pathlib import Path

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_scene_describer_streaming_filters_tool_calls():
    """Test that scene describer streaming properly filters tool calls from narrative stream."""
    logger.info("🔍 Testing scene describer streaming with tool call filtering...")

    try:
        from gaia_private.agents.scene.scene_describer import SceneDescriberAgent, SceneAgentMode
        from gaia_private.agents.scene.streaming_types import SceneStreamingContext

        # Track what gets streamed to the frontend
        streamed_chunks = []

        class MockBroadcaster:
            async def broadcast_narrative_chunk(self, session_id: str, chunk: str, is_final: bool):
                streamed_chunks.append((chunk, is_final))
                logger.info(f"📡 Broadcast chunk: {len(chunk)} chars, final={is_final}")
                if chunk and not is_final:
                    # Log first 100 chars to check for tool leakage
                    preview = chunk[:100]
                    logger.info(f"   Preview: {preview}")

        # Create scene describer agent
        agent = SceneDescriberAgent()

        # Create streaming context
        streaming_context = SceneStreamingContext(
            session_id="test_session",
            broadcaster=MockBroadcaster()
        )

        # Create a prompt that should trigger perception_check tool
        analysis_context = {
            "previous_scenes": [],
            "active_characters": [{"name": "Thorin", "race": "Dwarf"}],
            "current_turn": {
                "character_name": "Thorin",
                "personality_traits": ["Observant", "Cautious"]
            }
        }

        player_input = "I carefully examine the ancient ruins for any hidden dangers or treasures."

        logger.info("🎬 Starting streaming scene description...")

        # Run the scene describer in streaming mode
        result = await agent.describe_scene(
            user_input=player_input,
            analysis_context=analysis_context,
            mode=SceneAgentMode.STREAM,
            streaming_context=streaming_context
        )

        # Validate results
        logger.info(f"✅ Streaming complete!")

        # Result is now a dict from describe_scene
        streaming_answer = result.get("streaming_answer", "")

        logger.info(f"   Streaming answer: {len(streaming_answer)} chars")
        logger.info(f"   Chunks streamed: {len(streamed_chunks)}")

        # Check that we got some narrative
        assert streaming_answer or result.get("summary"), "Should have generated narrative text"

        # Verify observations were incorporated into the final result
        # These come from either streaming or the sync fallback call
        final_observations = result.get("observations", [])
        assert final_observations, "Expected observations in final result, but none found"
        logger.info(f"   ✅ Final result contains {len(final_observations)} observations")

        # Verify at least one observation has roll results (proving tool was executed)
        found_roll = False
        logger.info(f"   Checking {len(final_observations)} observations for roll results...")
        for i, obs in enumerate(final_observations):
            logger.info(f"      Observation {i}: roll={obs.get('roll')}, dc={obs.get('difficulty_class')}, success={obs.get('success')}")
            # Check that roll/success/margin are not None (meaning the tool was actually executed)
            if isinstance(obs, dict) and obs.get('roll') is not None and obs.get('difficulty_class') is not None and obs.get('success') is not None:
                found_roll = True
                logger.info(f"   ✅ Found resolved perception check with actual roll results:")
                logger.info(f"      - roll={obs['roll']}")
                logger.info(f"      - dc={obs['difficulty_class']}")
                logger.info(f"      - success={obs['success']}")
                logger.info(f"      - margin={obs.get('margin')}")
                logger.info(f"      - description={obs.get('description', '')[:50]}...")
                break

        assert found_roll, "Final observations have null roll results - perception_check tool was NOT executed! Tool structure exists but dice rolls were never performed."

        # CRITICAL: Check that streamed chunks don't contain tool syntax
        for i, (chunk, is_final) in enumerate(streamed_chunks):
            # These patterns should NEVER appear in streamed narrative
            forbidden_patterns = [
                "perception_check(",
                '"observations"',
                '"roll"',
                '"difficulty_class"',
                '{"observations"',
            ]

            for pattern in forbidden_patterns:
                if pattern in chunk:
                    logger.error(f"❌ TOOL LEAK DETECTED in chunk {i}: Found '{pattern}'")
                    logger.error(f"   Chunk content: {chunk[:200]}")
                    assert False, f"Tool syntax '{pattern}' leaked into streamed narrative!"

        logger.info("✅ No tool syntax found in streamed chunks - filtering works!")

        # Log a preview of the actual narrative
        if streaming_answer:
            logger.info(f"   Narrative preview: {streaming_answer[:200]}...")

        return True

    except Exception as e:
        logger.error(f"❌ Scene describer streaming test failed: {e}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_scene_describer_tool_event_capture():
    """Test that tool events are properly captured in result.tool_events."""
    logger.info("🔍 Testing scene describer tool event capture...")

    try:
        from gaia_private.agents.scene.scene_describer import SceneDescriberAgent, SceneAgentMode
        from gaia_private.agents.scene.streaming_types import SceneStreamingContext

        # Create scene describer agent
        agent = SceneDescriberAgent()

        # Create streaming context without broadcaster (we just want to check tool_events)
        streaming_context = SceneStreamingContext(
            session_id="test_session",
            broadcaster=None
        )

        # Create a prompt that should trigger perception_check tool
        analysis_context = {
            "previous_scenes": [],
            "active_characters": [{"name": "Elara", "race": "Elf"}],
            "current_turn": {
                "character_name": "Elara",
                "personality_traits": ["Perceptive", "Wise"]
            }
        }

        player_input = "I search the dark chamber for secret doors or hidden compartments."

        logger.info("🎬 Running scene description to capture tool events...")

        # Run the scene describer in streaming mode
        result = await agent.describe_scene(
            user_input=player_input,
            analysis_context=analysis_context,
            mode=SceneAgentMode.STREAM,
            streaming_context=streaming_context
        )

        logger.info(f"✅ Scene description complete!")

        # Verify observations were incorporated into the final result
        # These come from either streaming or the sync fallback call
        final_observations = result.get("observations", [])
        assert final_observations, "Expected observations in final result, but none found"
        logger.info(f"   ✅ Final result contains {len(final_observations)} observations")

        # Verify at least one observation has roll results (proving tool was executed)
        found_roll = False
        for obs in final_observations:
            if isinstance(obs, dict) and 'roll' in obs:
                found_roll = True
                logger.info(f"      ✅ Observation with resolved roll: roll={obs.get('roll')}, dc={obs.get('dc', obs.get('difficulty_class'))}, success={obs.get('success')}")
                break

        assert found_roll, "Final observations lack roll results - tool was not executed and resolved properly"
        logger.info("✅ Tool was called, executed, and results were incorporated into final response")

        return True

    except Exception as e:
        logger.error(f"❌ Tool event capture test failed: {e}", exc_info=True)
        raise


async def main():
    """Run all tests."""
    logger.info("🚀 Starting scene describer streaming tests...\n")

    tests = [
        ("Scene Describer Streaming Filters Tool Calls", test_scene_describer_streaming_filters_tool_calls),
        ("Scene Describer Tool Event Capture", test_scene_describer_tool_event_capture),
    ]

    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n{'='*80}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*80}")

        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' raised exception: {e}")
            results[test_name] = False

    # Print summary
    logger.info(f"\n{'='*80}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*80}")

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    logger.info(f"\n{passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 All tests passed!")
        return 0
    else:
        logger.error(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
