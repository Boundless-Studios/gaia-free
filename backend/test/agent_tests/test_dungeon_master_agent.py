"""Tests for DungeonMaster agent configuration and run context."""

import json
from types import SimpleNamespace

import pytest

from gaia_private.agents.dungeon_master import (
    DungeonMasterAgent,
    DungeonMasterHooks,
    DungeonMasterRunContext,
)
from gaia_private.agents.tools.formatters.dm_output_formatter_tool import (
    dm_output_formatter_tool_handler,
)


@pytest.fixture
def dm_agent():
    """Create a DungeonMaster agent instance for tests."""
    return DungeonMasterAgent()


def test_agent_configuration_disables_guardrails(dm_agent):
    """The DM agent should no longer enforce output guardrails or output types."""
    agent = dm_agent.as_openai_agent()

    assert agent.model_settings.tool_choice == "auto"
    assert agent.output_type is None
    assert not agent.output_guardrails

    tool_names = {tool.name for tool in agent.tools}
    assert "scene_creator" in tool_names
    assert "dm_output_formatter_tool" in tool_names


@pytest.mark.asyncio
async def test_hooks_capture_scene_and_formatter_usage():
    """DungeonMaster hooks should track tool usage and persist formatter payload.

    Note: Scene details are now persisted directly by SceneCreatorHooks via EnhancedSceneManager,
    not returned through the DM's structured output.
    """
    run_context = DungeonMasterRunContext()
    hooks = DungeonMasterHooks()
    ctx_wrapper = SimpleNamespace(context=run_context)

    # Simulate scene creator tool lifecycle
    await hooks.on_tool_start(ctx_wrapper, None, SimpleNamespace(name="scene_creator"))
    await hooks.on_tool_end(
        ctx_wrapper,
        None,
        SimpleNamespace(name="scene_creator"),
        {"result": "A roaring arena crowd watches from stone terraces."},
    )

    # Simulate formatter tool invocation
    await hooks.on_tool_start(ctx_wrapper, None, SimpleNamespace(name="dm_output_formatter_tool"))
    formatter_payload = {
        "player_response": "You feel the grit of the arena sand underfoot as you accept the duel.",
        "narrative": "Sunlight pours into the circular arena while banners snap above the roaring crowd.",
        "status": "Arena pressure mounts; foes circle with measured steps.",
    }
    formatter_json = await dm_output_formatter_tool_handler(
        SimpleNamespace(context=run_context),
        formatter_payload,
    )

    # Finalize run via hook
    await hooks.on_end(ctx_wrapper, None, json.loads(formatter_json))

    assert run_context.final_structured_output is not None
    # Verify tool usage tracking
    assert "scene_creator" in run_context.final_structured_output["tools_used"]
    assert "dm_output_formatter_tool" in run_context.final_structured_output["tools_used"]
    # Verify formatter output is captured
    assert run_context.final_structured_output["player_response"].startswith("You feel the grit")


def test_finalize_handles_formatter_payload_without_cycles():
    """Finalized structured data should serialize cleanly for history persistence."""
    run_context = DungeonMasterRunContext()
    formatter_payload = {
        "player_response": "The crowd roars as you raise a battered shield.",
        "narrative": "Dust hangs in the arena air while sunlight stripes the combatants.",
        "status": "You sense your opponent gauging your next move.",
    }

    run_context.record_formatter_usage("dm_output_formatter", formatter_payload)
    structured = run_context.finalize(formatter_payload)

    # The structured payload should be JSON serializable without circular references
    json.dumps(structured)
