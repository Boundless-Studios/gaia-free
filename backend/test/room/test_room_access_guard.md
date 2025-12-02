# RoomAccessGuard Test Suite

Comprehensive tests for the chat interface gatekeeping guards that protect `/api/chat` endpoint.

## Overview

The `RoomAccessGuard` class enforces two critical rules for gameplay:
1. **DM must be present** - No actions allowed when DM hasn't joined
2. **Players must have characters** - No playing without a character bound to seat

## Test Coverage

### ✅ 12/12 Tests Passing (100%)

#### ensure_dm_present() Tests (3 tests)

**1. test_ensure_dm_present_success**
- **Scenario:** DM has joined (room_status = 'active')
- **Result:** Action allowed ✓
- **Validates:** Normal gameplay flow when DM present

**2. test_ensure_dm_present_waiting_for_dm**
- **Scenario:** DM not joined (room_status = 'waiting_for_dm')
- **Result:** 409 Conflict - "Waiting for DM"
- **Validates:** Gameplay blocked when DM absent

**3. test_ensure_dm_present_campaign_not_found**
- **Scenario:** Invalid campaign ID
- **Result:** 404 Not Found
- **Validates:** Error handling for missing campaigns

---

#### ensure_player_has_character() Tests (6 tests)

**4. test_ensure_player_has_character_success**
- **Scenario:** Player has seat + character
- **Result:** Action allowed ✓
- **Validates:** Normal gameplay flow for players

**5. test_ensure_player_has_character_no_seat**
- **Scenario:** Player is invited but hasn't claimed a seat
- **Result:** 400 Bad Request - "Seat must be claimed before playing"
- **Validates:** Forces players to occupy seats before playing

**6. test_ensure_player_has_character_no_character**
- **Scenario:** Player has seat but no character assigned
- **Result:** 400 Bad Request - "Seat requires character"
- **Validates:** Forces character creation before gameplay

**7. test_ensure_player_has_character_dm_exempt**
- **Scenario:** DM (campaign owner) calling endpoint
- **Result:** Always allowed (exempt from character requirement) ✓
- **Validates:** DM doesn't need player seat/character to play

**8. test_ensure_player_has_character_no_user_id**
- **Scenario:** No user_id provided (unauthenticated)
- **Result:** 401 Unauthorized - "Authentication required"
- **Validates:** Authentication enforcement

**9. test_ensure_player_has_character_campaign_not_found**
- **Scenario:** Invalid campaign ID
- **Result:** 404 Not Found
- **Validates:** Error handling for missing campaigns

---

#### Integration Tests (3 tests)

**10. test_chat_flow_both_guards_pass**
- **Scenario:** DM present + player has character
- **Result:** Both guards pass, chat flow allowed ✓
- **Validates:** Complete happy path for chat endpoint

**11. test_chat_flow_dm_not_present**
- **Scenario:** DM absent but player has character
- **Result:** DM guard fails with 409 Conflict
- **Validates:** DM presence takes priority

**12. test_chat_flow_player_no_character**
- **Scenario:** DM present but player has no character
- **Result:** Character guard fails with 400 Bad Request
- **Validates:** Character requirement enforced even when DM present

---

## Test Pattern

Following existing room test conventions:
- **Isolated database** - Each test creates/cleans up its own campaign
- **Real services** - Uses actual RoomService, db_manager
- **Explicit cleanup** - `try/finally` ensures cleanup on failure
- **Comprehensive assertions** - Validates status codes and error messages

## Running Tests

```bash
# Run all RoomAccessGuard tests
python3 gaia_launcher.py test test/room/test_room_access_guard.py

# Run specific test
python3 gaia_launcher.py test test/room/test_room_access_guard.py::test_ensure_dm_present_success -v

# Run all room tests (31 total)
python3 gaia_launcher.py test test/room/
```

## Coverage by Guard Method

| Method | Tests | Coverage |
|--------|-------|----------|
| `ensure_dm_present()` | 3 | 100% ✅ |
| `ensure_player_has_character()` | 6 | 100% ✅ |
| Integration (both guards) | 3 | 100% ✅ |

## Error Scenarios Covered

| Status Code | Scenario | Test |
|-------------|----------|------|
| **200 OK** | DM present + player has character | ✅ |
| **200 OK** | DM calling (exempt from character requirement) | ✅ |
| **400 Bad Request** | Player has no seat | ✅ |
| **400 Bad Request** | Player has seat but no character | ✅ |
| **401 Unauthorized** | No user_id provided | ✅ |
| **404 Not Found** | Campaign doesn't exist | ✅ |
| **409 Conflict** | DM not joined (room_status != 'active') | ✅ |

## Integration with /api/chat

The guards are applied in the chat endpoint like this:

```python
@app.post("/api/chat")
async def chat_endpoint(campaign_id: str, user_id: str, message: str):
    # Guard 1: Ensure DM is present
    room_guard.ensure_dm_present(campaign_id)

    # Guard 2: Ensure player has character (DM exempt)
    room_guard.ensure_player_has_character(campaign_id, user_id)

    # If both pass, process chat message
    return await process_chat(campaign_id, user_id, message)
```

## Related Files

- `backend/src/api/guards/room_access.py` - Implementation (67 lines)
- `backend/test/room/test_room_access_guard.py` - Tests (350 lines)
- `backend/test/room/README.md` - Room test suite overview
- `docs/game-room-revised.md` - Game room specification

## Test Results

```
✅ 31/31 tests passing (100%)

RoomAccessGuard Tests (12):
✓ test_ensure_dm_present_success
✓ test_ensure_dm_present_waiting_for_dm
✓ test_ensure_dm_present_campaign_not_found
✓ test_ensure_player_has_character_success
✓ test_ensure_player_has_character_no_seat
✓ test_ensure_player_has_character_no_character
✓ test_ensure_player_has_character_dm_exempt
✓ test_ensure_player_has_character_no_user_id
✓ test_ensure_player_has_character_campaign_not_found
✓ test_chat_flow_both_guards_pass
✓ test_chat_flow_dm_not_present
✓ test_chat_flow_player_no_character

Other Room Tests (19):
✓ test_complete_user_journey_with_llm (E2E)
✓ test_campaign_start_validation
✓ test_room_summary_during_journey
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

## Future Enhancements

While RoomAccessGuard is now fully tested, these related areas still need tests:

- [ ] WebSocket broadcast verification (`test_room_broadcasts.py`)
- [ ] CampaignService.start_campaign_from_seats() (`test_campaign_start.py`)
- [ ] Real-time seat state updates via WebSocket
- [ ] DM/Player connection/disconnection flows
- [ ] Concurrent seat operations

See `backend/test/room/README.md` for complete test coverage roadmap.
