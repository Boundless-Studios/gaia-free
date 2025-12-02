# Game Room Test Suite

Comprehensive test suite for the game room backend APIs, following the codebase testing patterns.

## Overview

This test suite validates all room functionality including seat management, character assignment, and authorization. It follows the established patterns from `test/rest/test_session_invites.py` using minimal FastAPI apps that reuse production logic.

## Files

### `conftest.py`
Test fixtures and utilities following codebase patterns:
- **`build_room_app()`** - Creates minimal FastAPI app with room endpoints
- **`DummyUser`** - Test user extracted from headers (`X-User-Id`, `X-User-Email`)
- **Helper functions** - `create_test_campaign()`, `add_campaign_member()`, `cleanup_campaign()`
- **Fixtures** - `client`, test user IDs, sample character data

### `test_room_flows.py`
Comprehensive integration tests (16 tests) covering:
- ✅ DM creates campaign and gets room state
- ✅ Authentication and authorization (unauthenticated, non-member, owner, member access)
- ✅ Player occupies/releases seats
- ✅ Character assignment and immutability
- ✅ Character rotation between players
- ✅ DM vacates seats
- ✅ Single seat per player enforcement
- ✅ Room summary data

## Test Pattern

### Following Codebase Conventions

Our tests follow the exact pattern from `test/rest/test_session_invites.py`:

1. **Minimal FastAPI app** - Not the full production app
2. **DummyUser with headers** - `X-User-Id` and `X-User-Email`
3. **Isolated storage** - `tmp_path` for campaign storage
4. **Direct service layer testing** - Reuses production `RoomService`
5. **Explicit cleanup** - `try/finally` with `cleanup_campaign()`

### Example Test Structure

```python
def test_player_occupies_seat(client, test_dm_id, test_player_ids):
    """Test: Player occupies an available seat."""
    campaign_id = f"test-camp-{uuid4().hex[:8]}"
    player_id = test_player_ids[0]

    try:
        # Setup
        create_test_campaign(campaign_id, test_dm_id)
        add_campaign_member(campaign_id, player_id, f"{player_id}@example.com")

        # Get seat
        with db_manager.get_sync_session() as session:
            seat = session.execute(...).scalars().first()
            seat_id = str(seat.seat_id)

        # Test
        r = client.post(
            f"/api/v2/rooms/{campaign_id}/seats/{seat_id}/occupy",
            headers={"X-User-Id": player_id}
        )

        # Verify
        assert r.status_code == 200
        assert r.json()["owner_user_id"] == player_id

    finally:
        cleanup_campaign(campaign_id)
```

## Running Tests

### Current Status: Database Connection Required

**⚠️ Known Issue**: Tests require PostgreSQL database connection which is not properly configured for the test environment inside Docker.

The tests use `db_manager.get_sync_session()` to interact with the database, but `db_manager` is trying to connect to `localhost:5432` instead of the `gaia-postgres` container.

### Potential Solutions

1. **Configure DATABASE_URL in test environment**:
   ```bash
   export DATABASE_URL="postgresql://postgres:postgres@gaia-postgres:5432/gaia_dev"
   ```

2. **Run tests with proper Docker networking**:
   ```bash
   docker exec gaia-backend-dev bash -c "
     export DATABASE_URL='postgresql://postgres:postgres@gaia-postgres:5432/gaia_dev' && \
     cd /home/gaia && \
     python3 -m pytest test/room/test_room_flows.py -v
   "
   ```

3. **Use test database configuration** (future improvement):
   - Create dedicated test database
   - Configure in pytest fixtures
   - Auto-migrate before tests

### When DATABASE_URL is Fixed

```bash
# Run all room tests
docker exec gaia-backend-dev bash -c "cd /home/gaia && python3 -m pytest test/room/ -v"

# Run specific test
docker exec gaia-backend-dev bash -c "cd /home/gaia && python3 -m pytest test/room/test_room_flows.py::test_player_occupies_seat -v"

# Run with coverage
docker exec gaia-backend-dev bash -c "cd /home/gaia && python3 -m pytest test/room/ --cov=src.core.session.room_service --cov-report=term-missing"
```

## Test Coverage

### User Flows (from game-room-revised.md)

✅ **Flow 4.1 - DM Creates Campaign**
- Campaign creation with seats
- Seat initialization (1 DM + N player)
- Room status management

✅ **Flow 4.3 - Room Summary**
- Lightweight summary for pre-join status
- Seat counts and availability
- User's current seat and character

✅ **Flow 4.4 - Player Joins & Selects Seat**
- Seat occupation by invited players
- Uninvited player rejection
- Single seat per player enforcement

✅ **Flow 4.5 - Player Creates Character**
- Character creation on occupied seats
- Character binding to seats
- Cannot create on unclaimed seat
- **Authorization**: Only seat owner or DM can assign character

✅ **Flow 4.6 - Character Immutability**
- Character cannot be changed once assigned
- Validation prevents reassignment

✅ **Flow 4.7 - Character Rotation**
- DM must vacate seat first (only DM can vacate occupied seats)
- Then different player can occupy the vacant seat
- Character persists across owner changes
- Session-to-session continuity

✅ **Flow 4.8 - DM Vacates Seat**
- DM-only seat vacation
- Character persists after vacation
- Seat available for new player

### Authorization & Validation

✅ **Authentication**
- Unauthenticated requests rejected (401)
- Valid authentication required for all mutating operations

✅ **Authorization**
- Campaign owner always has access
- Invited members can access
- Non-members rejected (403)

✅ **Invite-Only Model**
- Only invited players can occupy seats
- Validation at seat occupation time

✅ **DM-Only Operations**
- Only campaign owner can vacate seats
- Non-DM players blocked (403)

✅ **Seat Constraints**
- Player can only hold one seat at a time
- Occupying new seat releases previous seat
- Cannot modify character once assigned

## Comparison with Existing Tests

### Similarities to `test/rest/test_session_invites.py`

| Aspect | Session Invites | Room Tests |
|--------|----------------|------------|
| App Creation | Minimal FastAPI app | Minimal FastAPI app |
| User Auth | `DummyUser` with headers | `DummyUser` with headers |
| Storage | `tmp_path` isolation | `tmp_path` isolation |
| Cleanup | Automatic via fixtures | Manual `try/finally` |
| Database | `SESSION_REGISTRY_DISABLE_DB=1` | Requires actual DB |

### Key Difference: Database Dependency

**Session/Invite Tests**: Use `SessionRegistry` which can disable DB sync
```python
os.environ["SESSION_REGISTRY_DISABLE_DB"] = "1"  # No DB needed
```

**Room Tests**: Use `RoomService` which requires database for:
- `CampaignSession` table
- `RoomSeat` table
- `CampaignSessionMember` table

This is why room tests need proper DATABASE_URL configuration.

## Future Enhancements

### Short Term
- [ ] Fix DATABASE_URL configuration for Docker tests
- [ ] Add pytest fixture for test database setup/teardown
- [ ] Add database migration runner for tests

### Medium Term
- [ ] Add WebSocket broadcast verification tests
- [ ] Add campaign start flow tests (Flow 4.10)
- [ ] Add concurrent seat operation tests
- [ ] Add performance benchmarks

### Long Term
- [ ] Integration with character manager tests
- [ ] Campaign orchestrator integration tests
- [ ] End-to-end flow with frontend

## Related Files

- `backend/src/api/routes/room.py` - Production room API endpoints
- `backend/src/core/session/room_service.py` - Room service implementation
- `backend/src/core/session/session_models.py` - Database models
- `docs/game-room-revised.md` - Complete system plan
- `test/rest/test_session_invites.py` - Testing pattern reference

## Notes for Developers

### Why Not Mock the Database?

We could mock `db_manager` and `RoomService`, but that would defeat the purpose of integration testing. These tests validate:

1. **Database schema correctness** - Tables, columns, constraints
2. **SQLAlchemy ORM behavior** - Relationships, cascades
3. **Transaction handling** - Commits, rollbacks
4. **Query correctness** - SELECT, UPDATE, DELETE logic

Mocking would only test our mocks, not the actual system.

### Alternative: Unit Tests

For testing `RoomService` logic without database, we could create unit tests with mocked database sessions. However, the current integration test approach provides higher confidence that the system works end-to-end.

### Testing Philosophy

Following the codebase pattern established in `test/rest/`:
- **Integration tests** for API endpoints (minimal app + real services)
- **Unit tests** for complex business logic (mocked dependencies)
- **End-to-end tests** for critical user flows (full system)

Room tests fall into the **integration test** category.
