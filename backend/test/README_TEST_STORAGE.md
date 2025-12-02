# Test Campaign Storage

## Overview

All unit tests that exercise campaign storage functionality now use isolated, temporary directories that are automatically cleaned up after tests complete. This prevents test campaigns from polluting the main `campaign_storage/` directory.

## How It Works

### Automatic Test Isolation

The test framework automatically provides isolated campaign storage through pytest fixtures defined in `conftest.py`:

1. **Session-level storage** (`test_campaign_storage_root`): Creates a temporary directory for the entire test session at `/tmp/test_campaigns_XXXXX/`
2. **Per-test storage** (`test_campaign_storage`): Each test gets its own isolated directory using pytest's `tmp_path` fixture
3. **Automatic cleanup**: All test campaign directories are removed after tests complete

### Default Behavior

When you run tests with `python3 gaia_launcher.py test`, the framework automatically:
- Sets `CAMPAIGN_STORAGE_PATH` to a temporary directory
- Creates isolated storage for each test
- Cleans up all test data after completion

You'll see a message like this after tests complete:
```
✅ Cleaned up test campaign storage: /tmp/test_campaigns_yjduf_cp
```

## Writing Tests with Campaign Storage

### Option 1: Use the Default (Recommended)

Most tests don't need to do anything special - the framework handles it automatically:

```python
def test_my_campaign_feature():
    # CAMPAIGN_STORAGE_PATH is already set to a temp directory
    campaign_manager = CampaignManager()
    campaign_manager.create_campaign("test_campaign", title="Test")
    # Campaign data goes to /tmp/test_campaigns_XXX/
    # Automatically cleaned up after test
```

### Option 2: Use the test_campaign_storage Fixture

For tests that need explicit control over the storage path:

```python
def test_with_explicit_storage(test_campaign_storage):
    # test_campaign_storage is a Path to a unique temp directory
    assert os.environ['CAMPAIGN_STORAGE_PATH'] == str(test_campaign_storage)
    # Your test code here
```

### Option 3: Use monkeypatch with tmp_path

For maximum isolation (already used by many existing tests):

```python
def test_with_monkeypatch(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPAIGN_STORAGE_PATH", str(tmp_path))
    # Your test code here
```

## Legacy Tests

Some older tests still use `tempfile.mkdtemp()` or `self.temp_dir` patterns. These still work but should be migrated to use pytest fixtures for consistency:

**Before:**
```python
import tempfile
import shutil

class TestMyCampaign:
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        os.environ['CAMPAIGN_STORAGE_PATH'] = self.temp_dir

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
```

**After:**
```python
def test_my_campaign(test_campaign_storage):
    # test_campaign_storage is already set up and will be cleaned up
    campaign_manager = CampaignManager()
    # ... test code ...
```

## Verifying Test Isolation

To verify tests are using isolated storage:

1. Check that no new directories appear in `campaign_storage/` after running tests
2. Look for the cleanup message in test output
3. Verify `/tmp/test_campaigns_*` directories are removed after tests

## Troubleshooting

**Problem**: Test campaigns appearing in main `campaign_storage/`

**Solution**: Ensure your test is either:
- Using the `test_campaign_storage` fixture
- Using `monkeypatch.setenv("CAMPAIGN_STORAGE_PATH", str(tmp_path))`
- Not manually overriding `CAMPAIGN_STORAGE_PATH` with a real path

**Problem**: Tests failing with "CAMPAIGN_STORAGE_PATH not set"

**Solution**: The `conftest.py` automatically sets this. Check if you're unsetting it somewhere in your test.

## Implementation Details

The test campaign storage setup is implemented in:
- `backend/test/conftest.py` - Contains fixtures and hooks
- `pytest_configure()` - Sets up session-level test storage
- `pytest_unconfigure()` - Cleans up test storage after all tests
