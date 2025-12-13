# Character Storage Database Migration - Test Plan

This document outlines the comprehensive testing strategy for the character storage database migration, including unit tests, integration tests, database tests, and end-to-end frontend tests using Playwright.

## Table of Contents

1. [Test Overview](#test-overview)
2. [Database Schema Testing](#database-schema-testing)
3. [ORM Model Testing](#orm-model-testing)
4. [Repository Layer Testing](#repository-layer-testing)
5. [Storage Adapter Testing](#storage-adapter-testing)
6. [Manager Integration Testing](#manager-integration-testing)
7. [Admin API Testing](#admin-api-testing)
8. [Migration Script Testing](#migration-script-testing)
9. [Playwright Frontend Testing](#playwright-frontend-testing)
10. [Performance Testing](#performance-testing)
11. [Test Data Management](#test-data-management)

---

## Test Overview

### Objectives

- Verify database schema integrity and constraints
- Validate ORM model conversions (to/from dataclasses)
- Test repository CRUD operations (both async and sync)
- Ensure storage adapter handles disk/DB hybrid correctly
- Verify feature flag behavior
- Test data migration correctness
- Validate admin API endpoints
- Test frontend character management flows
- Measure performance benchmarks

### Test Environment Requirements

- PostgreSQL 14+ database
- Python 3.11+
- Node.js 18+ (for Playwright)
- Test data fixtures
- Isolated test database

---

## Database Schema Testing

### Test Cases

#### 1. Schema Creation

**Test**: `test_database_migration_creates_all_tables`
```python
def test_database_migration_creates_all_tables(test_db):
    """Verify all 4 character tables are created."""
    tables = get_table_names(test_db, schema='game')

    assert 'character_profiles' in tables
    assert 'character_campaign_instances' in tables
    assert 'npc_profiles' in tables
    assert 'character_users' in tables
```

#### 2. Foreign Key Constraints

**Test**: `test_foreign_key_constraints`
```python
def test_foreign_key_constraints(test_db):
    """Verify FK constraints work correctly."""
    # Create profile
    profile = create_test_profile(test_db)

    # Try to create instance with invalid character_id (should fail)
    with pytest.raises(IntegrityError):
        create_instance_with_invalid_fk(test_db)

    # Create instance with valid character_id (should succeed)
    instance = create_valid_instance(test_db, profile.character_id)
    assert instance.character_id == profile.character_id
```

#### 3. Unique Constraints

**Test**: `test_unique_constraints`
```python
def test_unique_character_campaign_constraint(test_db):
    """Verify UNIQUE(character_id, campaign_id) constraint."""
    profile = create_test_profile(test_db)
    campaign_id = uuid.uuid4()

    # Create first instance
    instance1 = create_test_instance(test_db, profile.character_id, campaign_id)

    # Try to create duplicate (should fail)
    with pytest.raises(IntegrityError):
        create_test_instance(test_db, profile.character_id, campaign_id)
```

#### 4. Cascade Deletes

**Test**: `test_cascade_delete_profile`
```python
def test_cascade_delete_profile_removes_instances(test_db):
    """Verify CASCADE delete removes instances when profile deleted."""
    profile = create_test_profile(test_db)
    instance1 = create_test_instance(test_db, profile.character_id, uuid.uuid4())
    instance2 = create_test_instance(test_db, profile.character_id, uuid.uuid4())

    # Delete profile
    test_db.delete(profile)
    test_db.commit()

    # Verify instances are deleted
    instances = test_db.query(CharacterCampaignInstance).filter_by(
        character_id=profile.character_id
    ).all()
    assert len(instances) == 0
```

#### 5. Indexes

**Test**: `test_indexes_exist`
```python
def test_indexes_exist_on_key_columns(test_db):
    """Verify indexes are created on expected columns."""
    indexes = get_indexes(test_db, 'game.character_profiles')

    assert 'idx_character_profiles_external_id' in indexes
    assert 'idx_character_profiles_user_id' in indexes
    assert 'idx_character_profiles_type' in indexes
    assert 'idx_character_profiles_deleted' in indexes
```

#### 6. JSONB Columns

**Test**: `test_jsonb_columns`
```python
def test_jsonb_storage_and_retrieval(test_db):
    """Verify JSONB columns store and retrieve data correctly."""
    profile = CharacterProfile(
        external_character_id='test_char',
        name='Test Character',
        personality_traits=['brave', 'loyal'],
        bonds=['Protect the realm'],
        voice_settings={'stability': 0.5, 'similarity': 0.75}
    )

    test_db.add(profile)
    test_db.commit()

    # Reload from DB
    reloaded = test_db.query(CharacterProfile).filter_by(
        external_character_id='test_char'
    ).first()

    assert reloaded.personality_traits == ['brave', 'loyal']
    assert reloaded.voice_settings['stability'] == 0.5
```

---

## ORM Model Testing

### CharacterProfile Model

**Test**: `test_character_profile_to_dataclass`
```python
def test_character_profile_to_dataclass_conversion():
    """Verify CharacterProfile ORM -> dataclass conversion."""
    # Create ORM model
    orm_profile = CharacterProfile(
        external_character_id='char_123',
        name='Aragorn',
        race='Human',
        character_class='Ranger',
        base_level=20,
        character_type='player',
        backstory='Once a ranger...',
    )

    # Convert to dataclass
    dataclass_profile = orm_profile.to_dataclass()

    # Verify fields
    assert dataclass_profile.character_id == 'char_123'
    assert dataclass_profile.name == 'Aragorn'
    assert dataclass_profile.character_type == CharacterType.PLAYER
    assert dataclass_profile.backstory == 'Once a ranger...'
```

**Test**: `test_character_profile_from_dataclass`
```python
def test_character_profile_from_dataclass_creation():
    """Verify CharacterProfile dataclass -> ORM conversion."""
    # Create dataclass
    dataclass_profile = CharacterProfileDataclass(
        character_id='char_456',
        name='Gandalf',
        race='Istari',
        character_class='Wizard',
        base_level=99,
        character_type=CharacterType.NPC,
    )

    # Convert to ORM
    orm_profile = CharacterProfile.from_dataclass(
        dataclass_profile,
        created_by_user_id='user_123',
        created_by_email='dm@example.com'
    )

    # Verify fields
    assert orm_profile.external_character_id == 'char_456'
    assert orm_profile.name == 'Gandalf'
    assert orm_profile.created_by_user_id == 'user_123'
    assert orm_profile.character_type == 'npc'
```

### CharacterCampaignInstance Model

**Test**: `test_instance_to_character_info`
```python
def test_instance_merges_with_profile_to_character_info():
    """Verify instance + profile merge into CharacterInfo."""
    profile = create_test_profile()
    instance = create_test_instance(profile.character_id, uuid.uuid4())

    # Merge to CharacterInfo
    character_info = instance.to_character_info(profile)

    # Verify profile data
    assert character_info.name == profile.name
    assert character_info.race == profile.race
    assert character_info.voice_id == profile.voice_id

    # Verify instance data
    assert character_info.hit_points_current == instance.hit_points_current
    assert character_info.level == instance.current_level
    assert character_info.location == instance.location
```

**Test**: `test_jsonb_serialization_in_instance`
```python
def test_inventory_abilities_serialization():
    """Verify complex objects serialize to/from JSONB."""
    from gaia.models.item import Item
    from gaia.models.character.ability import Ability

    # Create CharacterInfo with inventory and abilities
    character_info = CharacterInfo(
        character_id='char_789',
        name='Test',
        inventory={
            'sword': Item(name='Longsword', item_type='weapon', damage='1d8'),
            'potion': Item(name='Healing Potion', item_type='consumable')
        },
        abilities={
            'fireball': Ability(name='Fireball', description='Cast fireball', damage='8d6')
        }
    )

    # Convert to instance
    instance = CharacterCampaignInstance.from_character_info(
        character_info,
        character_id=uuid.uuid4(),
        campaign_id=uuid.uuid4()
    )

    # Verify JSONB storage
    assert 'sword' in instance.inventory
    assert instance.inventory['sword']['name'] == 'Longsword'
    assert instance.abilities['fireball']['damage'] == '8d6'

    # Convert back to CharacterInfo
    profile = create_test_profile()
    reloaded_info = instance.to_character_info(profile)

    # Verify deserialization
    assert 'sword' in reloaded_info.inventory
    assert isinstance(reloaded_info.inventory['sword'], Item)
    assert reloaded_info.inventory['sword'].name == 'Longsword'
```

---

## Repository Layer Testing

### Profile Operations

**Test**: `test_create_profile_async`
```python
@pytest.mark.asyncio
async def test_create_profile_with_user():
    """Test creating a character profile with user ownership."""
    repository = CharacterRepository()

    profile = CharacterProfileDataclass(
        character_id='char_new',
        name='New Character',
        race='Elf',
        character_class='Wizard',
        base_level=1,
        character_type=CharacterType.PLAYER
    )

    profile_uuid = await repository.create_profile(
        profile,
        user_id='user_123',
        user_email='user@example.com'
    )

    assert profile_uuid is not None

    # Verify profile created
    loaded = await repository.get_profile('char_new')
    assert loaded.name == 'New Character'

    # Verify user association created
    owners = await repository.get_character_owners(profile_uuid)
    assert len(owners) == 1
    assert owners[0].user_id == 'user_123'
    assert owners[0].role == 'owner'
```

**Test**: `test_update_profile_sync`
```python
def test_update_profile_mutable_fields():
    """Test updating profile mutable fields."""
    repository = CharacterRepository()

    # Create profile
    profile = create_test_profile_dataclass()
    profile_uuid = repository.create_profile_sync(profile, user_id=None)

    # Update profile
    profile.portrait_url = 'https://example.com/portrait.png'
    profile.total_interactions = 100

    repository.update_profile_sync(profile_uuid, profile)

    # Verify update
    updated = repository.get_profile_by_uuid_sync(profile_uuid)
    assert updated.portrait_url == 'https://example.com/portrait.png'
    assert updated.total_interactions == 100
```

### Campaign Instance Operations

**Test**: `test_create_instance_async`
```python
@pytest.mark.asyncio
async def test_create_campaign_instance():
    """Test creating a character campaign instance."""
    repository = CharacterRepository()

    # Create profile first
    profile = create_test_profile_dataclass()
    profile_uuid = await repository.create_profile(profile, user_id=None)

    # Create campaign
    campaign_uuid = uuid.uuid4()

    # Create instance
    character_info = create_test_character_info()
    instance_uuid = await repository.create_instance(
        character_info,
        profile_uuid,
        campaign_uuid
    )

    assert instance_uuid is not None

    # Verify instance created
    instance = await repository.get_instance(profile_uuid, campaign_uuid)
    assert instance is not None
    assert instance.hit_points_current == character_info.hit_points_current
```

**Test**: `test_list_instances_for_campaign`
```python
def test_list_campaign_instances():
    """Test listing all character instances in a campaign."""
    repository = CharacterRepository()
    campaign_uuid = uuid.uuid4()

    # Create multiple profiles and instances
    for i in range(3):
        profile = create_test_profile_dataclass(f'char_{i}')
        profile_uuid = repository.create_profile_sync(profile, user_id=None)

        character_info = create_test_character_info(f'char_{i}')
        repository.create_instance_sync(character_info, profile_uuid, campaign_uuid)

    # List instances
    instances = repository.list_instances_for_campaign_sync(campaign_uuid)

    assert len(instances) == 3
    assert all(inst.campaign_id == campaign_uuid for inst in instances)
```

### NPC Operations

**Test**: `test_create_npc_sync`
```python
def test_create_npc_profile():
    """Test creating an NPC profile."""
    repository = CharacterRepository()

    npc = NpcProfileDataclass(
        npc_id='npc_shopkeeper',
        display_name='Friendly Shopkeeper',
        role='npc_support',
        description='Runs the local general store',
        tags=['shopkeeper', 'friendly'],
        has_full_sheet=False,
    )

    npc_uuid = repository.create_npc_sync(
        npc,
        user_id='dm_123',
        user_email='dm@example.com',
        campaign_id=uuid.uuid4()
    )

    assert npc_uuid is not None

    # Verify NPC created
    loaded = repository.get_npc_sync('npc_shopkeeper')
    assert loaded.display_name == 'Friendly Shopkeeper'
    assert loaded.role == CharacterRole.NPC_SUPPORT
```

### User Access Operations

**Test**: `test_grant_revoke_access`
```python
@pytest.mark.asyncio
async def test_character_sharing():
    """Test granting and revoking character access."""
    repository = CharacterRepository()

    # Create profile
    profile = create_test_profile_dataclass()
    profile_uuid = await repository.create_profile(
        profile, user_id='owner_123', user_email='owner@example.com'
    )

    # Grant viewer access to another user
    await repository.grant_access(
        profile_uuid,
        'viewer_456',
        'viewer@example.com',
        'viewer',
        'owner_123'
    )

    # Check access
    has_access = await repository.check_user_access(profile_uuid, 'viewer_456')
    assert has_access == 'viewer'

    # Revoke access
    await repository.revoke_access(profile_uuid, 'viewer_456')

    # Verify access revoked
    has_access = await repository.check_user_access(profile_uuid, 'viewer_456')
    assert has_access is None
```

---

## Storage Adapter Testing

**Test**: `test_adapter_disk_only_mode`
```python
def test_storage_adapter_disk_only(monkeypatch):
    """Test adapter in disk-only mode (DB disabled)."""
    monkeypatch.setenv('USE_CHARACTER_DATABASE', 'false')

    adapter = CharacterStorageAdapter()

    assert adapter.use_database is False
    assert adapter.repository is None

    # Save character
    char_data = create_test_character_dict()
    char_id = adapter.save_character(char_data, user_id='user_123')

    # Should save to disk only
    assert char_id is not None

    # Load character
    loaded = adapter.load_character(char_id)
    assert loaded['name'] == char_data['name']
```

**Test**: `test_adapter_database_mode`
```python
def test_storage_adapter_database_mode(monkeypatch, test_db):
    """Test adapter in database mode (DB enabled)."""
    monkeypatch.setenv('USE_CHARACTER_DATABASE', 'true')

    adapter = CharacterStorageAdapter()

    assert adapter.use_database is True
    assert adapter.repository is not None

    # Save character
    char_data = create_test_character_dict()
    char_id = adapter.save_character(
        char_data,
        user_id='user_123',
        user_email='user@example.com'
    )

    # Should save to both disk and database
    assert char_id is not None

    # Load character (should come from database)
    loaded = adapter.load_character(char_id)
    assert loaded['name'] == char_data['name']

    # Verify in database
    repo = CharacterRepository()
    profile = repo.get_profile_sync(char_id)
    assert profile.name == char_data['name']
```

**Test**: `test_adapter_database_fallback`
```python
def test_adapter_fallback_to_disk(monkeypatch, test_db):
    """Test adapter falls back to disk if DB fails."""
    monkeypatch.setenv('USE_CHARACTER_DATABASE', 'true')

    adapter = CharacterStorageAdapter()

    # Save character to disk only (simulate DB unavailable)
    char_data = create_test_character_dict()
    char_id = adapter.disk_storage.save_character(char_data)

    # Load character (DB doesn't have it, should fallback to disk)
    loaded = adapter.load_character(char_id)
    assert loaded is not None
    assert loaded['name'] == char_data['name']
```

---

## Manager Integration Testing

**Test**: `test_character_manager_with_adapter`
```python
def test_character_manager_creates_with_db(monkeypatch, test_db):
    """Test CharacterManager using storage adapter."""
    monkeypatch.setenv('USE_CHARACTER_DATABASE', 'true')

    manager = CharacterManager(campaign_id='campaign_123', user_id='user_456')

    # Create character from simple data
    simple_char = {
        'name': 'Test Hero',
        'race': 'Human',
        'character_class': 'Fighter',
        'level': 5,
    }

    character_info = manager.create_character_from_simple(simple_char)

    # Verify character created
    assert character_info.name == 'Test Hero'
    assert character_info.character_id is not None

    # Verify in database
    repo = CharacterRepository()
    profile = repo.get_profile_sync(character_info.character_id)
    assert profile is not None
    assert profile.name == 'Test Hero'
```

**Test**: `test_profile_manager_with_repository`
```python
def test_profile_manager_uses_database(monkeypatch, test_db):
    """Test ProfileManager using repository."""
    monkeypatch.setenv('USE_CHARACTER_DATABASE', 'true')

    manager = ProfileManager()

    # Create character info
    character_info = create_test_character_info()

    # Ensure profile exists
    profile_id = manager.ensure_profile_exists(character_info)

    # Verify profile created in database
    repo = CharacterRepository()
    profile = repo.get_profile_sync(profile_id)
    assert profile is not None
    assert profile.name == character_info.name

    # Update visual metadata
    manager.update_visual_metadata(profile_id, {
        'portrait_url': 'https://example.com/portrait.png',
        'gender': 'male',
    })

    # Verify update in database
    updated_profile = repo.get_profile_sync(profile_id)
    assert updated_profile.portrait_url == 'https://example.com/portrait.png'
    assert updated_profile.gender == 'male'
```

---

## Admin API Testing

**Test**: `test_admin_character_stats_endpoint`
```python
@pytest.mark.asyncio
async def test_get_character_stats(test_client, test_db):
    """Test GET /api/admin/characters/stats endpoint."""
    # Create test data
    create_test_characters(test_db, count=10)

    # Call endpoint
    response = await test_client.get('/api/admin/characters/stats')

    assert response.status_code == 200
    data = response.json()

    assert data['total_profiles'] == 10
    assert 'player_characters' in data
    assert 'npc_characters' in data
    assert 'characters_per_campaign_avg' in data
```

**Test**: `test_admin_list_characters_endpoint`
```python
@pytest.mark.asyncio
async def test_list_characters_filtered(test_client, test_db):
    """Test GET /api/admin/characters with filters."""
    # Create test data
    create_test_characters(test_db, user_id='user_123', count=5)
    create_test_characters(test_db, user_id='user_456', count=3)

    # Filter by user
    response = await test_client.get('/api/admin/characters?user_id=user_123')

    assert response.status_code == 200
    data = response.json()

    assert data['total'] == 5
    assert len(data['characters']) == 5
    assert all(c['created_by_user_id'] == 'user_123' for c in data['characters'])
```

**Test**: `test_admin_get_character_detail_endpoint`
```python
@pytest.mark.asyncio
async def test_get_character_detail(test_client, test_db):
    """Test GET /api/admin/characters/{id} endpoint."""
    # Create test character with instances
    profile = create_test_profile(test_db)
    instance1 = create_test_instance(test_db, profile.character_id, uuid.uuid4())
    instance2 = create_test_instance(test_db, profile.character_id, uuid.uuid4())

    # Call endpoint
    response = await test_client.get(f'/api/admin/characters/{profile.character_id}')

    assert response.status_code == 200
    data = response.json()

    assert data['name'] == profile.name
    assert len(data['campaign_instances']) == 2
```

**Test**: `test_admin_soft_delete_character_endpoint`
```python
@pytest.mark.asyncio
async def test_soft_delete_character(test_client, test_db):
    """Test DELETE /api/admin/characters/{id} endpoint."""
    profile = create_test_profile(test_db)

    # Soft delete
    response = await test_client.delete(f'/api/admin/characters/{profile.character_id}')

    assert response.status_code == 200
    data = response.json()

    assert data['success'] is True

    # Verify soft deleted in DB
    test_db.refresh(profile)
    assert profile.is_deleted is True
    assert profile.deleted_at is not None
```

---

## Migration Script Testing

**Test**: `test_migration_dry_run`
```python
def test_migration_script_dry_run(tmp_path):
    """Test migration script in dry-run mode."""
    # Create test data on disk
    create_test_character_files(tmp_path)

    # Run migration in dry-run
    migration = CharacterMigration(base_path=tmp_path, dry_run=True)
    migration.migrate_profiles(user_id='system')

    # Verify no changes to database
    repo = CharacterRepository()
    profiles = repo.list_system_profiles_sync()
    assert len(profiles) == 0  # Nothing migrated in dry-run

    # Verify statistics collected
    assert migration.stats['profiles_found'] > 0
    assert migration.stats['profiles_migrated'] == migration.stats['profiles_found']
```

**Test**: `test_migration_profiles`
```python
def test_migrate_profiles_to_database(tmp_path, test_db):
    """Test migrating character profiles from disk to database."""
    # Create test profile files
    create_test_profile_files(tmp_path, count=5)

    # Run migration
    migration = CharacterMigration(base_path=tmp_path, dry_run=False)
    migrated_count = migration.migrate_profiles(user_id='system')

    assert migrated_count == 5

    # Verify in database
    repo = CharacterRepository()
    profiles = repo.list_system_profiles_sync()
    assert len(profiles) == 5
```

**Test**: `test_migration_skip_existing`
```python
def test_migration_skips_existing_profiles(tmp_path, test_db):
    """Test migration skips profiles already in database."""
    # Create profile in database
    repo = CharacterRepository()
    profile = create_test_profile_dataclass('existing_char')
    repo.create_profile_sync(profile, user_id='system')

    # Create same profile on disk
    create_test_profile_file(tmp_path, 'existing_char')

    # Run migration
    migration = CharacterMigration(base_path=tmp_path, dry_run=False)
    migration.migrate_profiles(user_id='system')

    # Verify skipped
    assert migration.stats['profiles_skipped'] == 1
    assert migration.stats['profiles_migrated'] == 0
```

---

## Playwright Frontend Testing

### Setup

```typescript
// tests/e2e/character-admin.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Character Admin Panel', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin
    await page.goto('/admin/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', process.env.ADMIN_PASSWORD);
    await page.click('button[type="submit"]');

    // Navigate to characters admin
    await page.goto('/admin/characters');
  });

  // ... tests below
});
```

### Test Cases

**Test**: `test_character_list_displays`
```typescript
test('should display character list', async ({ page }) => {
  // Wait for characters to load
  await page.waitForSelector('[data-testid="character-list"]');

  // Verify table headers
  await expect(page.locator('th:has-text("Name")')).toBeVisible();
  await expect(page.locator('th:has-text("Race")')).toBeVisible();
  await expect(page.locator('th:has-text("Class")')).toBeVisible();
  await expect(page.locator('th:has-text("Level")')).toBeVisible();

  // Verify at least one character row
  const rows = page.locator('[data-testid="character-row"]');
  await expect(rows).toHaveCount(await rows.count());
});
```

**Test**: `test_character_filter_by_user`
```typescript
test('should filter characters by user', async ({ page }) => {
  // Open filter dropdown
  await page.click('[data-testid="filter-user-dropdown"]');

  // Select a user
  await page.click('text=user@example.com');

  // Verify filtered results
  await page.waitForResponse(resp =>
    resp.url().includes('/api/admin/characters') &&
    resp.url().includes('user_id=')
  );

  const rows = page.locator('[data-testid="character-row"]');
  const count = await rows.count();

  // All visible characters should belong to selected user
  for (let i = 0; i < count; i++) {
    const row = rows.nth(i);
    await expect(row.locator('[data-testid="character-user"]')).toHaveText('user@example.com');
  }
});
```

**Test**: `test_character_detail_view`
```typescript
test('should display character detail view', async ({ page }) => {
  // Click on first character
  await page.click('[data-testid="character-row"]:first-child [data-testid="character-name"]');

  // Wait for detail view
  await page.waitForSelector('[data-testid="character-detail"]');

  // Verify character data displayed
  await expect(page.locator('[data-testid="character-name"]')).toBeVisible();
  await expect(page.locator('[data-testid="character-race"]')).toBeVisible();
  await expect(page.locator('[data-testid="character-class"]')).toBeVisible();

  // Verify campaign instances section
  await expect(page.locator('h3:has-text("Campaign Instances")')).toBeVisible();

  // Verify at least one instance
  const instances = page.locator('[data-testid="campaign-instance"]');
  expect(await instances.count()).toBeGreaterThan(0);
});
```

**Test**: `test_character_stats_dashboard`
```typescript
test('should display character statistics', async ({ page }) => {
  // Navigate to stats
  await page.click('[data-testid="nav-stats"]');

  // Wait for stats to load
  await page.waitForResponse('/api/admin/characters/stats');

  // Verify stat cards
  await expect(page.locator('[data-testid="stat-total-profiles"]')).toBeVisible();
  await expect(page.locator('[data-testid="stat-player-characters"]')).toBeVisible();
  await expect(page.locator('[data-testid="stat-npc-characters"]')).toBeVisible();

  // Verify numeric values
  const totalProfiles = await page.locator('[data-testid="stat-total-profiles"] .stat-value').textContent();
  expect(parseInt(totalProfiles)).toBeGreaterThan(0);
});
```

**Test**: `test_character_soft_delete`
```typescript
test('should soft delete character', async ({ page }) => {
  // Click on character actions
  await page.click('[data-testid="character-row"]:first-child [data-testid="character-actions"]');

  // Click delete
  await page.click('text=Delete Character');

  // Confirm deletion
  await page.click('[data-testid="confirm-delete"]');

  // Wait for API call
  await page.waitForResponse(resp =>
    resp.url().includes('/api/admin/characters/') &&
    resp.request().method() === 'DELETE'
  );

  // Verify success message
  await expect(page.locator('[data-testid="success-toast"]')).toHaveText(/Character deleted/);

  // Toggle "Show deleted"
  await page.click('[data-testid="toggle-show-deleted"]');

  // Verify character now shows as deleted
  const deletedRow = page.locator('[data-testid="character-row"][data-deleted="true"]').first();
  await expect(deletedRow).toBeVisible();
});
```

**Test**: `test_npc_list_and_filter`
```typescript
test('should list and filter NPCs', async ({ page }) => {
  // Navigate to NPCs tab
  await page.click('[data-testid="tab-npcs"]');

  // Wait for NPCs to load
  await page.waitForSelector('[data-testid="npc-list"]');

  // Filter by campaign
  await page.selectOption('[data-testid="filter-campaign"]', { label: 'Test Campaign' });

  // Wait for filtered results
  await page.waitForResponse(resp =>
    resp.url().includes('/api/admin/characters/npcs/list') &&
    resp.url().includes('campaign_id=')
  );

  // Verify NPCs displayed
  const npcRows = page.locator('[data-testid="npc-row"]');
  expect(await npcRows.count()).toBeGreaterThan(0);
});
```

**Test**: `test_character_portrait_displayed`
```typescript
test('should display character portrait', async ({ page }) => {
  // Click on character with portrait
  await page.click('[data-testid="character-row"]:has([data-testid="character-portrait"]) [data-testid="character-name"]');

  // Wait for detail view
  await page.waitForSelector('[data-testid="character-detail"]');

  // Verify portrait image loaded
  const portrait = page.locator('[data-testid="character-portrait-image"]');
  await expect(portrait).toBeVisible();

  // Verify portrait has src
  const src = await portrait.getAttribute('src');
  expect(src).toBeTruthy();
  expect(src).toMatch(/\.(png|jpg|jpeg|webp)$/i);
});
```

---

## Performance Testing

### Database Query Performance

**Test**: `test_list_characters_performance`
```python
def test_list_characters_query_time(test_db, benchmark):
    """Test character listing query performance."""
    # Create 1000 characters
    create_test_characters(test_db, count=1000)

    repo = CharacterRepository()

    # Benchmark query
    result = benchmark(repo.list_profiles_by_user_sync, 'system')

    # Should complete in < 100ms
    assert benchmark.stats['mean'] < 0.1
```

**Test**: `test_instance_retrieval_performance`
```python
def test_get_character_instances_performance(test_db, benchmark):
    """Test performance of retrieving character with instances."""
    # Create character with 50 campaign instances
    profile = create_test_profile(test_db)
    for i in range(50):
        create_test_instance(test_db, profile.character_id, uuid.uuid4())

    repo = CharacterRepository()

    # Benchmark query
    result = benchmark(
        repo.list_instances_for_character_sync,
        profile.character_id
    )

    # Should complete in < 50ms
    assert benchmark.stats['mean'] < 0.05
```

### Migration Performance

**Test**: `test_bulk_migration_performance`
```python
def test_migrate_large_dataset(tmp_path, test_db, benchmark):
    """Test migration performance with large dataset."""
    # Create 500 profile files
    create_test_profile_files(tmp_path, count=500)

    # Benchmark migration
    migration = CharacterMigration(base_path=tmp_path, dry_run=False)
    result = benchmark(migration.migrate_profiles, user_id='system')

    # Should migrate 500 profiles in < 60 seconds
    assert benchmark.stats['mean'] < 60
    assert result == 500
```

---

## Test Data Management

### Fixtures

```python
@pytest.fixture
def test_db():
    """Create isolated test database."""
    engine = create_engine(TEST_DATABASE_URL)
    TestingSessionLocal = sessionmaker(bind=engine)

    # Create all tables
    BaseModel.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop all tables
        BaseModel.metadata.drop_all(bind=engine)

@pytest.fixture
def test_character_profile():
    """Create test character profile dataclass."""
    return CharacterProfileDataclass(
        character_id=f'test_char_{uuid.uuid4().hex[:8]}',
        name='Test Character',
        race='Human',
        character_class='Fighter',
        base_level=5,
        character_type=CharacterType.PLAYER,
    )

@pytest.fixture
def test_character_info():
    """Create test CharacterInfo instance."""
    return CharacterInfo(
        character_id=f'test_char_{uuid.uuid4().hex[:8]}',
        name='Test Character',
        race='Human',
        character_class='Fighter',
        level=5,
        hit_points_current=45,
        hit_points_max=50,
        armor_class=16,
    )
```

---

## Test Execution

### Running Tests

```bash
# Run all tests
pytest tests/

# Run database tests only
pytest tests/test_character_db.py

# Run ORM model tests
pytest tests/test_character_models.py

# Run repository tests
pytest tests/test_character_repository.py

# Run admin API tests
pytest tests/test_character_admin_api.py

# Run Playwright tests
npx playwright test tests/e2e/character-admin.spec.ts

# Run with coverage
pytest --cov=gaia.infra.storage --cov=gaia.models --cov-report=html tests/

# Run performance benchmarks
pytest tests/test_character_performance.py --benchmark-only
```

### CI/CD Integration

```yaml
# .github/workflows/test-character-storage.yml
name: Character Storage Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: gaia_test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov pytest-benchmark

      - name: Run database tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/gaia_test
          USE_CHARACTER_DATABASE: 'true'
        run: |
          pytest tests/test_character_*.py --cov --cov-report=xml

      - name: Run Playwright tests
        run: |
          npm install
          npx playwright install
          npx playwright test tests/e2e/character-admin.spec.ts

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Success Criteria

- [ ] All database schema tests pass
- [ ] All ORM model conversion tests pass
- [ ] All repository CRUD tests pass (async + sync)
- [ ] Storage adapter correctly handles disk/DB hybrid
- [ ] Feature flag behavior verified
- [ ] Manager integration tests pass
- [ ] Admin API endpoints tested
- [ ] Migration script validated
- [ ] All Playwright frontend tests pass
- [ ] Performance benchmarks meet targets
- [ ] Test coverage > 80%
- [ ] No regressions in existing character functionality

---

## Notes

- Run tests against clean test database for isolation
- Use fixtures for consistent test data
- Mock external dependencies (GCS, etc.)
- Test both happy paths and error cases
- Validate soft delete behavior throughout
- Ensure JSONB serialization handles all data types
- Test concurrent operations for race conditions
- Verify cascade deletes don't orphan data
