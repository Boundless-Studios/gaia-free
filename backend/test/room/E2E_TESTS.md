# End-to-End User Journey Tests

Comprehensive integration tests that validate the complete game room user experience from campaign creation through campaign start.

## Test File: `test_complete_user_journey.py`

### Overview

These tests validate the full user journey as specified in `docs/game-room-revised.md`:

1. **Campaign Creation** - DM creates campaign with rooms and seats
2. **Player Invitation** - DM invites players to join
3. **Seat Assignment** - Players occupy available seats
4. **Character Creation** - Players create characters bound to seats
5. **DM Setup** - DM occupies DM seat
6. **Campaign Ready** - Campaign transitions to ready state
7. **Validation** - All prerequisites for campaign start verified

## Tests (3 comprehensive E2E tests)

### 1. `test_complete_user_journey_with_llm`

**Full end-to-end user journey validation**

**Steps:**
1. DM creates campaign → Verifies 1 DM seat + 4 player seats created
2. DM invites Alice and Bob
3. Alice and Bob occupy seats → Verifies seat occupation
4. Alice creates "Aria the Brave" (Paladin) → Verifies character binding
5. Bob creates "Borin Ironforge" (Fighter) → Verifies character binding
6. DM occupies DM seat → Verifies DM seat occupation
7. Campaign status updated to 'ready' → Verifies state transition
8. Validates all prerequisites for campaign start are met

**Validates:**
- ✅ Campaign creation with correct seat allocation
- ✅ Player invitation system
- ✅ Seat occupation mechanics
- ✅ Character creation and seat binding
- ✅ DM seat occupation
- ✅ Campaign state transitions
- ✅ Prerequisites for LLM integration
- ✅ Complete data integrity throughout journey

**Output:**
```
=== STEP 1: DM Creates Campaign ===
✓ Campaign created with 4 player seats

=== STEP 2: Invite Players ===
✓ Invited Alice and Bob to campaign

=== STEP 3: Players Occupy Seats ===
✓ Alice occupied seat 1
✓ Bob occupied seat 2
✓ 2 seats now occupied

=== STEP 4: Players Create Characters ===
✓ Alice created character 'Aria the Brave'
✓ Bob created character 'Borin Ironforge'
✓ Characters successfully bound to seats

=== STEP 5: DM Occupies DM Seat ===
✓ DM occupied DM seat

=== STEP 6: Prepare Campaign for Start ===
✓ Campaign status updated to 'ready'

=== STEP 7: Verify Campaign Ready for LLM ===
✓ Campaign prerequisites verified:
  - Campaign status: ready
  - DM seat occupied: True
  - Player seats with characters: 2
  - Ready for LLM integration: True

=== STEP 8: Verify Final State ===
✓ Final state verification complete
  - Campaign ready: ready
  - Seats occupied: 3 / 5
  - Characters created: 2

✓ COMPLETE USER JOURNEY TEST PASSED
```

### 2. `test_campaign_start_validation`

**Validates campaign state transitions and requirements**

**Purpose:** Ensures campaign properly tracks state from creation through readiness.

**Validates:**
- ✅ Campaign starts in 'setup' status
- ✅ Room starts in 'waiting_for_dm' status
- ✅ Seats can be occupied without characters (intermediate state)
- ✅ State tracking remains consistent throughout setup

**Use Case:** Ensures frontend can show correct UI state at each step.

### 3. `test_room_summary_during_journey`

**Validates room summary API at each stage of setup**

**Purpose:** Tests the lightweight summary endpoint used by frontend modals.

**Stages Tested:**

**Stage 1 - Empty Campaign:**
```json
{
  "filled_player_seats": 0,
  "user_seat_id": null,
  "user_character_name": null
}
```

**Stage 2 - Seat Occupied (no character):**
```json
{
  "filled_player_seats": 1,
  "user_seat_id": "seat-uuid-123",
  "user_character_name": null
}
```

**Stage 3 - Character Created:**
```json
{
  "filled_player_seats": 1,
  "user_seat_id": "seat-uuid-123",
  "user_character_name": "Test Hero"
}
```

**Validates:**
- ✅ Summary reflects real-time seat occupation
- ✅ Summary shows character assignment
- ✅ Summary tracks user's own seat/character
- ✅ Seat count updates correctly

## Running the Tests

```bash
# Run all E2E tests
docker exec gaia-backend-dev bash -c "cd /home/gaia && python3 -m pytest test/room/test_complete_user_journey.py -v"

# Run specific E2E test
docker exec gaia-backend-dev bash -c "cd /home/gaia && python3 -m pytest test/room/test_complete_user_journey.py::test_complete_user_journey_with_llm -v -s"

# Run all room tests (unit + E2E)
docker exec gaia-backend-dev bash -c "cd /home/gaia && python3 -m pytest test/room/ -v"
```

## Test Results

```
✅ 19/19 tests passing (100%)

End-to-End Tests (3):
✓ test_complete_user_journey_with_llm
✓ test_campaign_start_validation
✓ test_room_summary_during_journey

Unit/Integration Tests (16):
✓ test_dm_creates_campaign_and_gets_state
✓ test_unauthenticated_access_denied
✓ test_non_member_access_denied
✓ test_owner_always_has_access
✓ test_member_can_access
✓ test_player_occupies_seat
✓ test_uninvited_player_cannot_occupy_seat
✓ test_assign_character_to_seat
✓ test_character_immutability
✓ test_character_rotation
✓ test_dm_vacates_player_seat
✓ test_non_dm_cannot_vacate_seat
✓ test_room_summary
✓ test_player_can_only_hold_one_seat
✓ test_release_seat
✓ test_character_assignment_requires_ownership
```

## Coverage

### User Journeys Covered

✅ **Flow 1: DM Creates Campaign**
- Campaign creation with automatic room/seat generation
- Correct seat allocation (1 DM + N player seats)
- Initial state setup

✅ **Flow 2: Players Join Campaign**
- Player invitation via email
- Campaign member addition
- Access control validation

✅ **Flow 3: Players Occupy Seats**
- Seat occupation mechanics
- Single seat per player enforcement
- Seat status updates
- Room state synchronization

✅ **Flow 4: Character Creation**
- Character binding to seats
- Character immutability after creation
- Character-to-seat persistence
- Authorization (owner or DM only)

✅ **Flow 5: Character Rotation**
- DM vacates occupied seat
- Different player occupies vacated seat
- Character persists across ownership change

✅ **Flow 6: Campaign Ready State**
- DM occupies DM seat
- Campaign status transitions
- Prerequisites validation
- Ready for LLM integration

### Security Validations

✅ **Authentication**
- Unauthenticated requests rejected (401)

✅ **Authorization**
- Non-members cannot access (403)
- Uninvited players cannot occupy seats
- Only seat owner or DM can assign characters
- Only DM can vacate seats

✅ **Data Integrity**
- Characters immutable after creation
- Seat ownership properly tracked
- State transitions validated
- Database constraints enforced

## Test Patterns

### E2E Test Structure

```python
@pytest.mark.asyncio
async def test_complete_user_journey_with_llm(client, test_dm_id, test_player_ids, sample_character_data):
    campaign_id = f"e2e-test-{uuid4().hex[:8]}"

    try:
        # STEP 1: Setup
        create_test_campaign(campaign_id, test_dm_id, max_seats=4)

        # STEP 2-N: Execute user journey
        # ... (invite, occupy, create characters, etc.)

        # FINAL: Verify complete state
        assert all_prerequisites_met()

    finally:
        # Always cleanup
        cleanup_campaign(campaign_id)
```

### Key Principles

1. **Isolated Execution** - Each test creates its own campaign
2. **Explicit Cleanup** - `try/finally` ensures cleanup even on failure
3. **Step-by-Step Validation** - Assert after each major action
4. **Real Services** - Uses actual RoomService, CharacterManager
5. **Database Integration** - Validates actual DB state
6. **Comprehensive Logging** - Prints progress for debugging

## Future Enhancements

### Planned Tests

- [ ] Multi-player concurrent seat operations
- [ ] WebSocket broadcast verification
- [ ] Campaign start flow with actual LLM
- [ ] Full combat integration in room context
- [ ] Scene transitions with room state
- [ ] Player disconnect/reconnect scenarios
- [ ] Character deletion/recreation flows

### LLM Integration

The current E2E test validates that the campaign reaches a state ready for LLM integration. Full LLM testing would require:

1. Initializing `CampaignRunner` with `current_game_config`
2. Mocking or using `FakeLLMProvider` for deterministic responses
3. Validating turn execution and state updates
4. Testing agent handoffs and tool calls

This is planned for future iterations as it requires more complex test infrastructure.

## Related Documentation

- `test/room/README.md` - Room test suite overview
- `test/room/SUMMARY.md` - Implementation summary
- `docs/game-room-revised.md` - Game room specification
- `docs/game-room-revised-code.md` - Implementation guide
