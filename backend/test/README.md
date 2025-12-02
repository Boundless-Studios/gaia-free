# Gaia Test Suite

Comprehensive test suite for the Gaia D&D orchestrator system.

## Overview

The test suite covers all major components:
- API endpoints (including internal debug endpoints)
- Agent behavior and handoffs
- Orchestrator functionality
- Campaign/session persistence
- Character and NPC management
- Scene management and transitions
- Combat system integration
- LLM model selection
- Utility functions
- Audio/TTS services

### Current Test Status (Oct 2025)
- **386 tests passing** consistently
- **1 test skipped** intentionally (manual-only full combat integration)
- **1 remaining warning** (internal to Pydantic library, not actionable)
- All integration tests re-enabled and passing

## Test Structure

```
test/
├── api/                    # API endpoint tests
│   ├── test_main.py       # Main API endpoints
│   └── test_audio.py      # TTS/Audio endpoints
├── agents/                 # Agent behavior tests
│   ├── test_dungeon_master_agent.py
│   ├── test_scenario_analyzer_agent.py
│   └── test_agent_handoffs.py
├── campaigns/              # Campaign management tests
│   ├── test_storage.py
│   └── test_campaign_manager.py
├── llm/                    # LLM provider tests
│   ├── test_model_manager.py
│   └── test_ollama_manager.py
├── orchestrator/           # Orchestrator tests
│   ├── test_orchestrator.py
│   └── test_agent_integration.py
├── utils/                  # Utility tests
│   ├── test_dice_roller.py
│   ├── test_formatters.py
│   └── test_tts_service.py
└── test_agents/            # Mock agents for testing
    ├── fake_llm_provider.py
    ├── test_dungeon_master.py
    ├── test_scenario_analyzer.py
    └── mock_orchestrator.py
```

## Running Tests

### Quick Start
```bash
# Run all tests
python run_tests.py

# Run with verbose output
python run_tests.py -v

# Run with coverage report
python run_tests.py -c
```

### Specific Tests
```bash
# Run only API tests
python run_tests.py test/api/

# Run specific test file
python run_tests.py test/api/test_main.py

# Run specific test class
python run_tests.py test/api/test_main.py::TestChatEndpoints

# Run specific test method
python run_tests.py test/api/test_main.py::TestChatEndpoints::test_chat_simple_message
```

### Test Categories
```bash
# Run only unit tests (fast)
python run_tests.py --quick

# Run only integration tests
python run_tests.py --integration

# Run tests by marker
python run_tests.py -m "not slow"
```

### Coverage Reports
```bash
# Generate HTML coverage report
python run_tests.py -c

# View coverage report
open htmlcov/index.html
```

## Mock Components

### Fake LLM Provider
The `FakeLLMProvider` returns deterministic responses based on agent type and scenario. This ensures tests are:
- Fast (no real LLM calls)
- Deterministic (same input = same output)
- Comprehensive (can test all scenarios)

### Test Agents
Test agents in `test_agents/` provide preset responses for different scenarios:
- `TestDungeonMaster`: Returns preset game narratives
- `TestScenarioAnalyzer`: Analyzes input and recommends agents
- `MockOrchestrator`: Simulates full orchestrator behavior

## Writing New Tests

### Basic Test Structure
```python
import pytest
from unittest.mock import Mock, patch

class TestNewFeature:
    """Test new feature functionality."""
    
    @pytest.fixture
    def setup_data(self):
        """Setup test data."""
        return {"test": "data"}
    
    def test_feature_behavior(self, setup_data):
        """Test specific behavior."""
        # Arrange
        expected = "expected result"
        
        # Act
        result = new_feature(setup_data)
        
        # Assert
        assert result == expected
```

### Async Tests
```python
@pytest.mark.asyncio
async def test_async_feature():
    """Test async functionality."""
    result = await async_function()
    assert result is not None
```

### Mocking External Services
```python
def test_with_mock():
    """Test with mocked external service."""
    with patch('module.external_service') as mock_service:
        mock_service.return_value = "mocked response"
        
        result = function_using_service()
        assert result == "processed: mocked response"
```

## Test Configuration

### Environment Variables
Tests automatically set:
- `TESTING=true`: Indicates test environment
- `USE_SMALLER_MODEL=true`: Use smaller models for speed
- `GAIA_AUDIO_DISABLED=true`: Disable auto-TTS and client audio during tests

### Custom Configuration
Create `test/.env` for test-specific settings:
```env
# Test-specific configuration
TEST_CAMPAIGN_ID=test-campaign-123
TEST_API_KEY=test-key
```

## Continuous Integration

### GitHub Actions
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt
      - run: python run_tests.py -c
```

## Recent Modernization (Oct 2025)

### Code Quality Improvements
- **Pydantic v2 Migration**: All models updated from Pydantic v1 to v2 syntax
  - Changed `class Config` to `model_config = ConfigDict()`
  - Updated constraint names (`min_items` → `min_length`, etc.)
  - See: `src/api/schemas/chat.py`, `src/game/dnd_agents/character_generator.py`, `src/game/dnd_agents/campaign_generator.py`

- **SQLAlchemy Modernization**: Updated to current import conventions
  - Fixed deprecation warnings in database models

- **Pytest Collection Warnings**: Fixed test helper class naming
  - Renamed helper classes to avoid `Test*` prefix
  - Prevents pytest from incorrectly attempting to collect utilities as tests

### Integration Test Re-enablement
Previously skipped integration tests have been re-enabled and verified:

1. **Character-Campaign Integration** (`test/core/character/test_character_campaign_integration.py`)
   - 5 tests validating character persistence with campaign storage
   - Tests use proper temp directory fixtures for isolation

2. **Character-Scene Integration** (`test/test_character_scene_integration.py`)
   - 2 tests validating character state within scene context
   - Proper singleton management in setUp/tearDown

3. **Manual Integration Test** (`test/combat/integration/test_combat_full_integration.py`)
   - 1 comprehensive end-to-end combat test
   - Kept skipped for CI/CD (requires full LLM environment)
   - Enhanced documentation for manual execution

### Warning Cleanup
Fixed 16 Python warnings across the test suite:
- Pydantic v1/v2 compatibility warnings
- SQLAlchemy deprecation warnings
- Pytest collection warnings
- Only 1 warning remains (internal to Pydantic library)

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure `src/` is in Python path
   - Run from project root directory
   - Use `python3 gaia_launcher.py test` to run tests in Docker with proper environment

2. **Async Test Failures**
   - Use `@pytest.mark.asyncio` decorator
   - Ensure proper async/await usage

3. **Mock Not Working**
   - Check patch path is correct
   - Use `spec=True` for better mocking

4. **Slow Tests**
   - Mark slow tests with `@pytest.mark.slow`
   - Use `--quick` flag to skip them

5. **Singleton State Issues**
   - Integration tests should clear singletons in setUp/tearDown
   - See `test/test_scene_improvements.py` for examples
   - Use `SingletonMeta._instances` to manually clear when needed

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Clear Names**: Test names should describe what they test
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Mock External Dependencies**: Don't rely on external services
5. **Test Edge Cases**: Include error scenarios
6. **Keep Tests Fast**: Mock heavy operations
7. **Use Fixtures**: Share common setup code
8. **Document Complex Tests**: Add comments for clarity
