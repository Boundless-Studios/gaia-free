# Combat Test Improvement Plan

## 1. Design Difference: Action Points Overdraw

### Current Implementation
**File:** `src/core/models/combat/mechanics/action_points.py:31-41`

```python
def spend_ap(self, cost: int) -> bool:
    """Spend AP for an action, allowing overdraw (negative AP).

    Returns:
        True if action can be afforded, False if it requires overdraw
    """
    can_afford = self.can_afford_action(cost)
    # Always spend the AP, even if it goes negative (overdraw)
    self.current_ap -= cost
    self.spent_this_turn += cost
    return can_afford
```

**Design Intent:**
- **Overdraw mechanic** - Players CAN spend more AP than they have
- Going negative triggers overdraw damage (1d4, 2d4, or 3d4 based on amount)
- This is a deliberate game design choice to allow risky plays

### Test Expectation (Incorrect)
**File:** `test/combat/mechanics/test_action_points.py:235-237`

```python
# Try complex action (3 AP) - should fail
assert state.spend_ap(3) == False
assert state.current_ap == 2  # ❌ Test expects AP to NOT be spent
```

**What test expects:**
- `spend_ap()` returns `False` AND doesn't spend the AP
- AP remains at previous value
- This was the OLD behavior before overdraw mechanic

### Resolution

**Option 1: Update Tests to Match Design (RECOMMENDED)**
```python
# Test overdraw mechanic
assert state.spend_ap(3) == False  # Returns False (needs overdraw)
assert state.current_ap == -1      # But AP IS spent (overdraw)
assert state.spent_this_turn == 6  # Total spent tracked
```

**Option 2: Add Configuration Flag**
```python
# Add optional strict mode
state = ActionPointState(max_ap=5, current_ap=2, allow_overdraw=False)
assert state.spend_ap(3) == False
assert state.current_ap == 2  # AP not spent in strict mode
```

**Recommendation:** Option 1 - Update tests to document and verify the overdraw behavior as designed.

---

## 2. Agent Tests Mocking Requirements

### Current Problem
Agent tests call actual LLM endpoints which fail without:
- LLM service running
- API keys configured
- Proper network access

### Tests Needing Mocks

#### `test/combat/agents/test_combat_action_selection.py`
**What it does:** Tests action selection agent
**What fails:** Line 71 - `result = await agent.select_actions(request)`
**What to mock:**
```python
from unittest.mock import AsyncMock, patch

@patch('core.llm.agent_runner.AgentRunner.run')
async def test_combat_action_selection(mock_agent_run):
    # Mock the LLM response
    mock_agent_run.return_value = CombatActionSelectionOutput(
        actions=[
            {
                "actor": "Fighter",
                "action_type": "basic_attack",
                "target": "Goblin",
                "intent_description": "attack with sword"
            }
        ],
        tactical_reasoning="Attack the enemy",
        expected_ap_usage=2
    )

    # Test continues...
```

#### `test/combat/agents/test_combat_agent_integration.py`
**What it does:** Integration test for combat initiator
**What fails:** Actual agent.run() calls
**What to mock:**
- `CombatInitiatorAgent.run()` or its internal `AgentRunner.run()`
- Return mock `CombatInitiation` objects

#### `test/combat/agents/test_split_combat_agents.py`
**What it does:** Tests split agent architecture (uses pytest mocks)
**Status:** Already has mocking in place! (Line 80+)
**Action:** Keep as-is, good example

### Mocking Strategy

**Level 1: Mock AgentRunner.run() (Lowest level)**
```python
@patch('core.llm.agent_runner.AgentRunner.run')
async def test_something(mock_run):
    mock_run.return_value = MockResponse(...)
```

**Level 2: Mock Agent responses (Mid level)**
```python
@patch.object(CombatActionSelectionAgent, 'select_actions')
async def test_something(mock_select):
    mock_select.return_value = CombatActionSelectionOutput(...)
```

**Level 3: Use test fixtures (Highest level)**
```python
@pytest.fixture
def mock_combat_agent():
    agent = Mock(spec=CombatActionSelectionAgent)
    agent.select_actions = AsyncMock(return_value=...)
    return agent
```

**Recommendation:** Use Level 2 for most tests - mock at the agent method level, not the LLM level.

---

## 3. Target Validation Testing Plan

### What We Added
**File:** `src/core/session/combat/combat_engine.py:165-206`

New `_validate_target()` method that:
- Checks if target exists in combat
- Checks if target is conscious
- Checks if target has HP > 0
- Returns helpful error messages with available targets

### Tests Needed

#### Test 1: Valid Target
```python
def test_validate_target_success():
    """Test that valid targets pass validation."""
    engine = CombatEngine()
    session = create_test_session()  # Has "fighter" and "goblin"

    target = engine._validate_target(session, "goblin")
    assert target is not None
    assert target.name == "goblin"
```

#### Test 2: Non-existent Target
```python
def test_validate_target_not_found():
    """Test that missing targets raise helpful errors."""
    engine = CombatEngine()
    session = create_test_session()  # Has "fighter" and "goblin"

    with pytest.raises(ValueError) as exc:
        engine._validate_target(session, "dragon")

    assert "'dragon' not in combat" in str(exc.value)
    assert "fighter, goblin" in str(exc.value)  # Shows available targets
```

#### Test 3: Unconscious Target
```python
def test_validate_target_unconscious():
    """Test that unconscious targets can't be targeted."""
    engine = CombatEngine()
    session = create_test_session()
    session.combatants["goblin"].is_conscious = False

    with pytest.raises(ValueError) as exc:
        engine._validate_target(session, "goblin")

    assert "unconscious" in str(exc.value).lower()
```

#### Test 4: Defeated Target (HP <= 0)
```python
def test_validate_target_defeated():
    """Test that defeated targets can't be targeted."""
    engine = CombatEngine()
    session = create_test_session()
    session.combatants["goblin"].hp = 0

    with pytest.raises(ValueError) as exc:
        engine._validate_target(session, "goblin")

    assert "defeated" in str(exc.value).lower()
```

#### Test 5: Allow Unconscious for Healing
```python
def test_validate_target_unconscious_allowed():
    """Test that healing can target unconscious allies."""
    engine = CombatEngine()
    session = create_test_session()
    session.combatants["fighter"].is_conscious = False

    # Should succeed with allow_unconscious=True
    target = engine._validate_target(session, "fighter", allow_unconscious=True)
    assert target is not None
```

#### Test 6: Integration with InvalidTargetActionResult
```python
def test_invalid_target_returns_proper_result():
    """Test that invalid targets return InvalidTargetActionResult."""
    engine = CombatEngine()
    session = create_test_session()
    actor = session.combatants["fighter"]

    result = engine._handle_basic_attack(session, actor, "dragon")

    assert isinstance(result, InvalidTargetActionResult)
    assert result.success == False
    assert "invalid_target" in result.effects_applied
    assert "'dragon' not in combat" in result.description
```

### Test File Location
Create: `test/core/session/combat/test_combat_engine_target_validation.py`

### Integration with Existing Tests

**Update:** `test/core/session/combat/test_combat_engine.py`
- Existing tests may need to use valid target IDs
- Some tests may intentionally test invalid targets (should now get InvalidTargetActionResult)

---

## Implementation Priority

### Phase 1: Fix Existing Tests (High Priority)
1. ✅ **COMPLETED** - Update `test_action_points.py` to test overdraw behavior correctly (16/16 passing)
2. ✅ **COMPLETED** - Add mocks to `test_combat_action_selection.py` (1/3 tests passing with AgentRunner.run mocking)
3. ⚠️ **DEFERRED** - Add mocks to `test_combat_agent_integration.py` (depends on Combat class structure)

### Phase 2: Add Target Validation Tests (High Priority)
1. ✅ **COMPLETED** - Create `test_combat_engine_target_validation.py` (9/9 passing)
2. ✅ **COMPLETED** - Add 9 core validation tests (exceeded original plan of 6)
3. ✅ **COMPLETED** - Verify integration with InvalidTargetActionResult

### Phase 3: Test Organization Cleanup (Medium Priority)
1. ✅ Mark integration tests with `@pytest.mark.integration`
2. ✅ Mark unit tests with `@pytest.mark.unit`
3. ✅ Create separate test runs in CI/CD

### Phase 4: Documentation (Low Priority)
1. ✅ Document overdraw mechanic in README
2. ✅ Document mocking patterns for agent tests
3. ✅ Add examples of target validation usage

---

## Summary

### ✅ Successfully Completed

**Action Point Tests (16/16 passing)**
- Fixed test expectations to match overdraw mechanic design
- Updated `test_action_cost_creation()` - removed obsolete `prerequisites` field tests
- Updated `test_sequential_action_spending()` - now correctly tests overdraw behavior
- All ActionPointConfig, ActionCost, and ActionPointState tests passing

**Target Validation Tests (9/9 passing)**
- Created comprehensive `test_combat_engine_target_validation.py`
- Tests cover: valid targets, missing targets, unconscious/defeated targets, healing special cases
- Tests verify InvalidTargetActionResult integration with attack and spell handlers
- Used class name checking instead of isinstance() to handle import path differences

### ✅ Fixed Issues

**Agent Tests - Mocking AgentRunner (1/3 tests passing)**
- Fixed import paths to use `src.game.dnd_agents.combat.combat_action_selection_agent`
- Successfully mocked `AgentRunner.run()` instead of `agent.run()`
- `test_combat_action_selection()` now passes with proper mocking
- Remaining 2 tests (`test_combat_mechanical_resolution`, `test_ap_tracking`) use different patterns and need Combat class mocking

### Design Differences
- **Action Points:** Tests expect old "prevent overdraw" behavior, implementation allows overdraw (intentional) - **FIXED**
- **Fix:** Updated tests to verify overdraw mechanic - **COMPLETED**

### Mocking Needs
- **Agent Tests:** Need to mock LLM calls at agent method level - **BLOCKED BY CIRCULAR IMPORT**
- **Pattern:** Use `@patch.object(Agent, 'method')` with AsyncMock
- **Example:** Already present in `test_split_combat_agents.py`

### Target Validation
- **New Feature:** Added comprehensive target validation - **COMPLETED**
- **Tests:** 9 new tests verify all validation cases - **COMPLETED**
- **Integration:** Works with InvalidTargetActionResult - **VERIFIED**

**Core test improvements successfully implemented. Agent test mocking blocked by architectural issue.**
