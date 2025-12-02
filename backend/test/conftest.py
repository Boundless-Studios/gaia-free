"""Pytest configuration and shared fixtures."""
import os
import sys

# CRITICAL: Set DATABASE_URL BEFORE any imports that might initialize db_manager
# This ensures all tests use the gaia-postgres container, not localhost
if not os.getenv('DATABASE_URL'):
    os.environ["DATABASE_URL"] = "postgresql://gaia:test123@gaia-postgres:5432/gaia"

import json
import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, MagicMock
from test.test_agents.fake_llm_provider import FakeLLMProvider
from fastapi.testclient import TestClient
from gaia.api.app import app

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def test_campaign_storage_root():
    """
    Provide a test-specific campaign storage directory that gets cleaned up after all tests.
    This ensures test campaigns don't pollute the main campaign_storage directory.
    """
    test_storage = tempfile.mkdtemp(prefix="test_campaigns_")
    os.environ['CAMPAIGN_STORAGE_PATH'] = test_storage
    yield test_storage
    # Cleanup after all tests complete
    if os.path.exists(test_storage):
        shutil.rmtree(test_storage, ignore_errors=True)


@pytest.fixture
def test_campaign_storage(test_campaign_storage_root, tmp_path):
    """
    Provide a unique test campaign storage path for each test.
    Uses tmp_path for automatic cleanup but ensures CAMPAIGN_STORAGE_PATH is set.
    """
    # Use tmp_path to ensure each test gets isolated storage
    campaign_path = tmp_path / "campaigns"
    campaign_path.mkdir(exist_ok=True)

    # Set environment variable for this test
    old_path = os.environ.get('CAMPAIGN_STORAGE_PATH')
    os.environ['CAMPAIGN_STORAGE_PATH'] = str(campaign_path)

    yield campaign_path

    # Restore old value if there was one
    if old_path:
        os.environ['CAMPAIGN_STORAGE_PATH'] = old_path
    else:
        os.environ.pop('CAMPAIGN_STORAGE_PATH', None)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """FastAPI test client for API endpoint testing."""
    return TestClient(app)


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing."""
    return FakeLLMProvider()


@pytest.fixture
def mock_llm_response():
    """Factory for creating mock LLM responses."""
    def _create_response(content: str, tool_calls: List[Dict] = None):
        response = Mock()
        response.final_output = content
        response.messages = [
            Mock(content=content, tool_calls=tool_calls)
        ]
        return response
    return _create_response


@pytest.fixture
def mock_agent_runner():
    """Mock AgentRunner for testing."""
    runner = Mock()
    runner.run = AsyncMock()
    runner.extract_structured_output = Mock()
    runner.extract_text_response = Mock()
    return runner


@pytest.fixture
def mock_storage():
    """Mock storage for testing."""
    storage = Mock()
    storage.get_campaign = AsyncMock(return_value=None)
    storage.save_campaign = AsyncMock()
    storage.list_campaigns = AsyncMock(return_value=[])
    storage.delete_campaign = AsyncMock()
    return storage


@pytest.fixture
def test_campaign_data():
    """Sample campaign data for testing."""
    return {
        "id": "test-campaign-123",
        "name": "Test Campaign",
        "description": "A test campaign for unit testing",
        "dm_notes": "Test notes",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_campaign_data():
    """Extended campaign data for scene analyzer tests."""
    return {
        "campaign_id": "test_campaign_001",
        "title": "The Lost Mines of Phandelver",
        "total_sessions": 5,
        "created_at": "2025-08-01T00:00:00",
        "custom_data": {
            "setting": "Forgotten Realms",
            "dm_notes": "Party is level 3",
            "themes": ["exploration", "mystery", "combat"]
        }
    }


@pytest.fixture
def sample_scene_data():
    """Sample scene data from DungeonMaster output."""
    return {
        "narrative": "You stand at the entrance of a dark cave. Water drips from stalactites above, creating an eerie echo throughout the cavern. Three tunnels branch off from this main chamber, each disappearing into darkness.",
        "turn": "",
        "status": {
            "location": "Cave Entrance",
            "time": "Afternoon",
            "weather": "Clear outside",
            "visibility": "Dim light"
        },
        "characters": [
            {
                "name": "Thorin",
                "class": "Fighter",
                "level": 3,
                "hp": 28,
                "max_hp": 30,
                "status": "Healthy",
                "conditions": []
            },
            {
                "name": "Elara",
                "class": "Wizard",
                "level": 3,
                "hp": 18,
                "max_hp": 18,
                "status": "Healthy",
                "conditions": []
            }
        ]
    }


@pytest.fixture
def sample_combat_scene():
    """Sample combat scene data."""
    return {
        "narrative": "Three goblins emerge from the shadows, weapons drawn!",
        "turn": "Roll for initiative!",
        "status": {
            "location": "Cave Chamber",
            "combat": True,
            "round": 0,
            "initiative_order": []
        },
        "characters": [
            {
                "name": "Thorin",
                "class": "Fighter",
                "hp": 28,
                "ac": 16,
                "initiative": None
            },
            {
                "name": "Elara", 
                "class": "Wizard",
                "hp": 18,
                "ac": 12,
                "initiative": None
            }
        ],
        "enemies": [
            {
                "name": "Goblin 1",
                "hp": 7,
                "ac": 15,
                "initiative": None
            },
            {
                "name": "Goblin 2",
                "hp": 7,
                "ac": 15,
                "initiative": None
            },
            {
                "name": "Goblin 3",
                "hp": 7,
                "ac": 15,
                "initiative": None
            }
        ]
    }


@pytest.fixture
def sample_conversation_history():
    """Sample conversation history for testing."""
    return [
        {
            "role": "user",
            "content": "I want to explore the ancient ruins"
        },
        {
            "role": "assistant",
            "content": json.dumps({
                "narrative": "You approach the ancient ruins. Vines cover the stone walls, and you can see a partially collapsed entrance.",
                "status": {"location": "Ancient Ruins Entrance"}
            })
        },
        {
            "role": "user",
            "content": "I carefully enter through the collapsed entrance"
        },
        {
            "role": "assistant",
            "content": json.dumps({
                "narrative": "You squeeze through the collapsed entrance. Inside, you find a large hall with pillars supporting a cracked ceiling. Dust motes dance in shafts of light from above.",
                "status": {"location": "Ancient Ruins - Main Hall"}
            })
        }
    ]


@pytest.fixture
def test_session_data():
    """Sample session data for testing."""
    return {
        "session_id": "test-session-456",
        "campaign_id": "test-campaign-123",
        "messages": [],
        "created_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def test_agent_response():
    """Sample agent response for testing."""
    return {
        "narrative": "You enter a dimly lit tavern.",
        "turn": {"current_player": "Player 1", "phase": "exploration"},
        "status": {"location": "Tavern", "time": "Evening"},
        "characters": [{"name": "Innkeeper", "description": "A friendly halfling"}]
    }


@pytest.fixture
def mock_context_manager():
    """Mock ContextManager for testing."""
    manager = Mock()
    manager.get_analysis_context = Mock(return_value={
        "current_input": "test input",
        "previous_scenes": [],
        "last_user_actions": [],
        "game_state": {
            "location": "Test Location",
            "combat_active": False
        },
        "active_characters": [],
        "campaign_metadata": {
            "campaign_id": "test_campaign",
            "title": "Test Campaign"
        },
        "timestamp": "2025-08-18T00:00:00"
    })
    return manager


@pytest.fixture
def mock_history_manager():
    """Mock ConversationHistoryManager for testing."""
    manager = Mock()
    manager.get_full_history = Mock(return_value=[])
    manager.add_message = Mock()
    manager.get_recent_history = Mock(return_value=[])
    return manager


@pytest.fixture
def mock_campaign_manager():
    """Mock SimpleCampaignManager for testing."""
    manager = Mock()
    campaign = Mock()
    campaign.campaign_id = "test_campaign"
    campaign.title = "Test Campaign"
    campaign.total_sessions = 1
    campaign.created_at = Mock(isoformat=Mock(return_value="2025-08-18T00:00:00"))
    campaign.custom_data = {}
    manager.load_campaign = Mock(return_value=campaign)
    manager.save_campaign = Mock()
    manager.list_campaigns = Mock(return_value=[campaign])
    return manager


@pytest.fixture
def analyzer_test_cases():
    """Test cases for scene analyzers."""
    return [
        {
            "input": "I attack the goblin with my sword",
            "expected": {
                "complexity": "SIMPLE",
                "scene_type": "COMBAT",
                "primary_agent": "EncounterRunner"
            }
        },
        {
            "input": "I want to negotiate with the king about trade routes while secretly planning to steal the crown jewels",
            "expected": {
                "complexity": "COMPLEX",
                "scene_type": "SOCIAL",
                "primary_agent": "DungeonMaster"
            }
        },
        {
            "input": "I search the room for traps",
            "expected": {
                "complexity": "MODERATE",
                "scene_type": "EXPLORATION",
                "primary_agent": "DungeonMaster"
            }
        }
    ]


@pytest.fixture
async def mock_orchestrator(mock_llm_provider):
    """Mock orchestrator for testing."""
    from test.test_agents.mock_orchestrator import MockOrchestrator
    return MockOrchestrator(mock_llm_provider)


@pytest.fixture
def mock_agents_library():
    """Mock agents library components."""
    import pytest
    with pytest.mock.patch('agents.Agent') as mock_agent:
        with pytest.mock.patch('agents.Runner') as mock_runner:
            mock_agent_instance = Mock()
            mock_agent.return_value = mock_agent_instance
            
            mock_runner_instance = Mock()
            mock_runner.return_value = mock_runner_instance
            
            # Mock the run method to return a proper RunResult
            async def mock_run(*args, **kwargs):
                result = Mock()
                result.final_output = "Test output"
                result.messages = []
                return result
            
            mock_runner.run = mock_run
            
            yield {
                "Agent": mock_agent,
                "Runner": mock_runner,
                "agent_instance": mock_agent_instance,
                "runner_instance": mock_runner_instance
            }


# Markers for different test types
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.asyncio = pytest.mark.asyncio


# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers and test environment."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )

    # Set up test-specific campaign storage directory
    # This creates a temporary directory that will be used for all test campaigns
    test_storage = tempfile.mkdtemp(prefix="test_campaigns_")
    config.test_campaign_storage = test_storage

    # Set default CAMPAIGN_STORAGE_PATH for tests
    # Individual tests can override this with monkeypatch or tmp_path
    if 'CAMPAIGN_STORAGE_PATH' not in os.environ:
        os.environ['CAMPAIGN_STORAGE_PATH'] = test_storage


# Cleanup hook
def pytest_unconfigure(config):
    """Cleanup test campaign storage after all tests complete."""
    if hasattr(config, 'test_campaign_storage'):
        test_storage = config.test_campaign_storage
        if os.path.exists(test_storage):
            try:
                shutil.rmtree(test_storage, ignore_errors=True)
                print(f"\n✅ Cleaned up test campaign storage: {test_storage}")
            except Exception as e:
                print(f"\n⚠️  Warning: Could not clean up test storage {test_storage}: {e}")

    # Clean up async database connections
    try:
        from db.src import db_manager
        if db_manager.async_engine:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.run_until_complete(db_manager.async_engine.dispose())
            except RuntimeError:
                # If no event loop is available, create a new one
                asyncio.run(db_manager.async_engine.dispose())
    except Exception:
        pass  # Ignore cleanup errors


# Per-test cleanup hook for async database connections
def pytest_runtest_teardown(item, nextitem):
    """Clean up async database connections after each test.

    This prevents async connection pool issues when tests using async DB
    connections run before integration tests.
    """
    try:
        from db.src import db_manager
        if db_manager.async_engine:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.run_until_complete(db_manager.async_engine.dispose())
            except RuntimeError:
                # If no event loop, create a temporary one for cleanup
                asyncio.run(db_manager.async_engine.dispose())
    except Exception:
        pass  # Ignore cleanup errors


# Test collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on path."""
    for item in items:
        # Add markers based on test location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath) or "scene_analyzers" in str(item.fspath) or "api" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Mark async tests
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


@pytest.fixture(autouse=True)
def reset_pregenerated_content_singleton():
    """Reset PreGeneratedContent singleton before each test to prevent test pollution.

    Tests that modify PreGeneratedContent.characters or other singleton state
    can cause test failures when run in the full suite. This fixture ensures
    each test starts with a fresh singleton instance.
    """
    import copy
    from gaia.utils.singleton import SingletonMeta
    from gaia.api.routes.campaign_generation import PreGeneratedContent

    # Store reference to existing instance if present
    existing_instance = SingletonMeta._instances.get(PreGeneratedContent)
    original_characters = None
    original_campaigns = None

    if existing_instance:
        # Save original data using deepcopy to handle nested structures
        original_characters = getattr(existing_instance, 'characters', None)
        original_campaigns = getattr(existing_instance, 'campaigns', None)
        if original_characters is not None:
            original_characters = copy.deepcopy(original_characters)
        if original_campaigns is not None:
            original_campaigns = copy.deepcopy(original_campaigns)

    yield

    # After test: restore singleton to original state
    if existing_instance:
        # Restore the original singleton instance
        SingletonMeta._instances[PreGeneratedContent] = existing_instance

        # Restore original data if we saved it
        if original_characters is not None:
            existing_instance.characters = original_characters
        if original_campaigns is not None:
            existing_instance.campaigns = original_campaigns
    else:
        # No instance existed before, so remove any instance created during test
        SingletonMeta._instances.pop(PreGeneratedContent, None)


# Environment setup for tests
os.environ["TESTING"] = "true"
os.environ["USE_SMALLER_MODEL"] = "true"
os.environ["GAIA_AUDIO_DISABLED"] = "true"
os.environ["OLLAMA_DEBUG"] = "false"
os.environ["LLAMA_LOG_LEVEL"] = "ERROR"
