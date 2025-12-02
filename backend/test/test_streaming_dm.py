"""Tests for streaming DM narrative generation.

This test validates the streaming orchestrator and its integration.
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
async def test_imports():
    """Test that all streaming components can be imported."""
    logger.info("🔍 Testing imports...")

    try:
        from gaia_private.agents.dungeon_master.prompts import (
            UNIFIED_STREAMING_DM_PROMPT,
            METADATA_GENERATION_PROMPT,
        )
        logger.info("✅ Streaming prompts imported successfully")

        from gaia_private.agents.dungeon_master.orchestrator import (
            StreamingDMOrchestrator,
            StreamingDMConfig,
            StreamingDMResult,
        )
        logger.info("✅ Streaming orchestrator imported successfully")

        from gaia.infra.llm.streaming_llm_client import (
            StreamingLLMClient,
            streaming_llm_client,
        )
        logger.info("✅ Streaming LLM client imported successfully")

        from gaia.connection.websocket.campaign_broadcaster import campaign_broadcaster
        logger.info("✅ Campaign broadcaster imported successfully")

        return True

    except Exception as e:
        logger.error(f"❌ Import failed: {e}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_orchestrator_creation():
    """Test creating a streaming orchestrator."""
    logger.info("🔍 Testing orchestrator creation...")

    try:
        from gaia_private.agents.dungeon_master.orchestrator import (
            StreamingDMOrchestrator,
            StreamingDMConfig,
        )

        # Track callbacks for unified streaming
        content_chunks = []
        metadata = {}

        async def on_content_chunk(content: str, is_final: bool):
            content_chunks.append((content, is_final))
            logger.info(f"📖 Content chunk: {len(content)} chars, final={is_final}")

        async def on_metadata_ready(meta: dict):
            metadata.update(meta)
            logger.info(f"📊 Metadata ready: {list(meta.keys())}")

        config = StreamingDMConfig(
            model="parasail-kimi-k2-instruct-0905",
            temperature=0.7,
            narrative_streaming=False,  # Disable actual streaming for test
            enable_metadata=False,
        )

        orchestrator = StreamingDMOrchestrator(
            config=config,
            on_content_chunk=on_content_chunk,
            on_metadata_ready=on_metadata_ready,
        )

        logger.info("✅ Orchestrator created successfully")
        logger.info(f"   Model: {orchestrator.config.model}")
        logger.info(f"   Temperature: {orchestrator.config.temperature}")

        return True

    except Exception as e:
        logger.error(f"❌ Orchestrator creation failed: {e}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_prompt_building():
    """Test that prompt building methods work with DB-backed templates."""
    logger.info("🔍 Testing prompt building with template variables...")

    try:
        from gaia_private.agents.dungeon_master.orchestrator import (
            StreamingDMOrchestrator,
            StreamingDMConfig,
        )
        from gaia_private.session.scene.scene_payloads import SceneContextData

        config = StreamingDMConfig()
        orchestrator = StreamingDMOrchestrator(config=config)

        # Create test scene context
        scene_context = SceneContextData(
            has_scene=True,
            formatted_text="Location: The Rusty Dragon Inn. A crowded tavern filled with adventurers.",
            is_fallback=False,
            campaign_id="test_campaign",
        )

        # Test unified prompt building with template variables
        logger.info("Testing _build_unified_prompt...")
        unified_prompt = await orchestrator._build_unified_prompt(
            conversation_history="Player: I enter the tavern.",
            scene_context=scene_context,
            player_input="I look around for suspicious characters.",
        )

        # Verify template variables were resolved
        assert "I enter the tavern" in unified_prompt, "Should contain conversation history"
        assert "Rusty Dragon Inn" in unified_prompt, "Should contain scene context"
        assert "look around for suspicious characters" in unified_prompt, "Should contain player input"
        logger.info("✅ Unified prompt built and template variables resolved")

        # Test metadata prompt building with template variables
        logger.info("Testing _build_metadata_prompt...")
        metadata_prompt = await orchestrator._build_metadata_prompt(
            conversation_history="Player: I enter the tavern.",
            scene_context=scene_context,
            player_input="I look around for suspicious characters.",
            narrative="You push open the heavy oak door...",
            player_response="Three hooded figures sit in the corner...",
        )

        # Verify template variables were resolved
        assert "I enter the tavern" in metadata_prompt, "Should contain conversation history"
        assert "Rusty Dragon Inn" in metadata_prompt, "Should contain scene context"
        assert "look around for suspicious characters" in metadata_prompt, "Should contain player input"
        assert "heavy oak door" in metadata_prompt, "Should contain narrative"
        assert "hooded figures" in metadata_prompt, "Should contain player response"
        logger.info("✅ Metadata prompt built and template variables resolved")

        # Test with missing scene (should include scene_status)
        logger.info("Testing _build_unified_prompt with missing scene...")
        missing_scene_context = SceneContextData(
            has_scene=False,
            formatted_text="",
            is_fallback=True,
        )

        unified_prompt_no_scene = await orchestrator._build_unified_prompt(
            conversation_history="Player: Where am I?",
            scene_context=missing_scene_context,
            player_input="I look around.",
        )

        assert "scene_creator" in unified_prompt_no_scene, "Should mention scene_creator tool when no scene"
        logger.info("✅ Missing scene handling works correctly")

        return True

    except Exception as e:
        logger.error(f"❌ Prompt building failed: {e}", exc_info=True)
        raise

@pytest.mark.asyncio
async def test_db_backed_template_loading():
    """Test DB-backed prompt loading with template variable resolution."""
    logger.info("🔍 Testing DB-backed template loading...")

    try:
        from gaia_private.prompts.prompt_loader import load_prompt_text
        from gaia_private.agents.dungeon_master.prompts import (
            UNIFIED_STREAMING_DM_PROMPT,
            METADATA_GENERATION_PROMPT,
        )

        # Test loading unified streaming prompt with template variables
        logger.info("Testing load_prompt_text for unified_streaming...")
        unified_result = await load_prompt_text(
            agent_type="streaming_dm",
            prompt_key="unified_streaming",
            fallback=UNIFIED_STREAMING_DM_PROMPT,
            logger=logger,
            log_name="TestUnifiedStreaming",
            template_vars={
                "conversation_history": "Test history",
                "formatted_text": "Test scene",
                "player_input": "Test input",
                "scene_status": "Test status",
            },
            resolve_template=True,
        )

        # Verify template variables were resolved
        assert "Test history" in unified_result, "Should resolve conversation_history"
        assert "Test scene" in unified_result, "Should resolve formatted_text"
        assert "Test input" in unified_result, "Should resolve player_input"
        assert "Test status" in unified_result, "Should resolve scene_status"
        assert "{{conversation_history}}" not in unified_result, "Should not have unresolved template vars"
        logger.info("✅ Unified streaming prompt loaded with resolved templates")

        # Test loading metadata prompt with template variables
        logger.info("Testing load_prompt_text for metadata_generation...")
        metadata_result = await load_prompt_text(
            agent_type="streaming_dm",
            prompt_key="metadata_generation",
            fallback=METADATA_GENERATION_PROMPT,
            logger=logger,
            log_name="TestMetadataGeneration",
            template_vars={
                "conversation_history": "Meta history",
                "formatted_text": "Meta scene",
                "player_input": "Meta input",
                "narrative": "Meta narrative",
                "player_response": "Meta response",
            },
            resolve_template=True,
        )

        # Verify template variables were resolved
        assert "Meta history" in metadata_result, "Should resolve conversation_history"
        assert "Meta scene" in metadata_result, "Should resolve formatted_text"
        assert "Meta input" in metadata_result, "Should resolve player_input"
        assert "Meta narrative" in metadata_result, "Should resolve narrative"
        assert "Meta response" in metadata_result, "Should resolve player_response"
        assert "{{conversation_history}}" not in metadata_result, "Should not have unresolved template vars"
        logger.info("✅ Metadata generation prompt loaded with resolved templates")

        # Test that core_persona cross-prompt reference is resolved
        # Both prompts should contain core_persona content (not the placeholder)
        assert "{{core_persona}}" not in unified_result, "Should resolve core_persona cross-prompt reference"
        assert "{{core_persona}}" not in metadata_result, "Should resolve core_persona cross-prompt reference"
        logger.info("✅ Cross-prompt references resolved correctly")

        return True

    except Exception as e:
        logger.error(f"❌ DB-backed template loading failed: {e}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_end_to_end_streaming():
    """Test actual streaming DM generation end-to-end."""
    logger.info("🔍 Testing end-to-end streaming DM generation...")

    try:
        from gaia_private.agents.dungeon_master.orchestrator import (
            StreamingDMOrchestrator,
            StreamingDMConfig,
        )
        from gaia_private.session.scene.scene_payloads import SceneContextData

        # Track what we receive
        content_chunks = []

        async def on_content_chunk(content: str, is_final: bool):
            content_chunks.append((content, is_final))
            logger.info(f"📖 Content chunk {len(content_chunks)}: {len(content)} chars, final={is_final}")

        config = StreamingDMConfig(
            model="parasail-kimi-k2-instruct-0905",
            temperature=0.7,
            narrative_streaming=True,
            enable_metadata=False,  # Skip metadata for faster test
        )

        orchestrator = StreamingDMOrchestrator(
            config=config,
            on_content_chunk=on_content_chunk,
        )

        # Simple test context
        conversation_history = "Player: I enter the ancient tomb."
        scene_context = SceneContextData(
            has_scene=True,
            formatted_text="Location: Ancient Tomb Entrance. The air is cold and stale.",
            is_fallback=False,
            campaign_id="test_campaign",
        )
        player_input = "I light a torch and look around."

        logger.info("🎬 Starting streaming generation...")
        result = await orchestrator.generate_streaming_response(
            conversation_history=conversation_history,
            scene_context=scene_context,
            player_input=player_input,
        )

        # Validate results - should have some content
        assert result.narrative or result.player_response, "Should have narrative or player_response"

        # Log results
        logger.info(f"✅ Streaming generation complete!")
        logger.info(f"   Narrative: {len(result.narrative)} chars")
        logger.info(f"   Response: {len(result.player_response)} chars")
        logger.info(f"   Total chunks received: {len(content_chunks)}")

        # Verify we got actual streaming (chunks > 0) or fallback response
        if len(content_chunks) == 0:
            logger.warning("⚠️ No streaming chunks received - using fallback mode")
            # In fallback mode, we should still have content in the response
            assert result.player_response, "Fallback should provide player_response"
        else:
            logger.info(f"✅ Received {len(content_chunks)} streaming chunks")

        if result.narrative:
            logger.info(f"   Narrative preview: {result.narrative[:100]}...")
        if result.player_response:
            logger.info(f"   Response preview: {result.player_response[:100]}...")

        return True

    except Exception as e:
        logger.error(f"❌ End-to-end streaming test failed: {e}", exc_info=True)
        raise


async def main():
    """Run all tests."""
    logger.info("🚀 Starting streaming DM tests...\n")

    tests = [
        ("Imports", test_imports),
        ("Orchestrator Creation", test_orchestrator_creation),
        ("Prompt Building", test_prompt_building),
        ("DB-Backed Template Loading", test_db_backed_template_loading),
        ("End-to-End Streaming", test_end_to_end_streaming),
    ]

    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*60}")

        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' raised exception: {e}")
            results[test_name] = False

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")

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
