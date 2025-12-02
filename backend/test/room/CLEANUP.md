# Test Campaign Cleanup

## Overview

Room tests create campaign directories in `campaign_storage/` during execution. To prevent stale test data from accumulating, we have implemented automatic cleanup in test fixtures and a manual cleanup script.

## Automatic Cleanup

The `cleanup_campaign()` function in `conftest.py` now cleans up both:
1. **Database entries** - Seats, members, and campaign records
2. **Filesystem directories** - Campaign storage directories

All tests use `try/finally` blocks to ensure cleanup happens even if tests fail:

```python
def test_something(client, test_dm_id):
    campaign_id = f"test-camp-{uuid4().hex[:8]}"

    try:
        # Test code here
        create_test_campaign(campaign_id, test_dm_id)
        # ... test logic ...
    finally:
        cleanup_campaign(campaign_id)  # Always runs, even on failure
```

## Manual Cleanup Script

For cleaning up stale test campaigns that accumulated before automatic cleanup was implemented:

### Usage

```bash
# From project root, show what would be deleted (dry-run)
python3 backend/test/room/cleanup_stale_campaigns.py --filesystem-only --dry-run

# Actually delete stale test campaigns
python3 backend/test/room/cleanup_stale_campaigns.py --filesystem-only

# Or run from Docker
docker exec gaia-backend-dev bash -c "cd /home/gaia && python3 test/room/cleanup_stale_campaigns.py --filesystem-only"
```

### What Gets Cleaned Up

The script removes campaign directories matching these patterns:
- `e2e-test-*` - End-to-end test campaigns
- `test-camp-*` - General test campaigns
- `summary-test-*` - Room summary test campaigns
- `validation-test-*` - Validation test campaigns

### Options

- `--dry-run` - Show what would be deleted without actually deleting
- `--filesystem-only` - Only clean up directories, skip database cleanup (recommended)
- `--storage-path PATH` - Specify custom campaign storage path

## Why This Was Needed

Test campaigns were creating directories in `campaign_storage/` but only cleaning up database entries. This caused:

1. **Accumulation of stale directories** - 183 test campaign directories were left behind
2. **Warning logs** - SimpleCampaignManager scanned these directories and warned about "corrupted metadata and no chat history"
3. **Disk space usage** - Small but unnecessary storage consumption

## Verification

Check for stale test campaigns:

```bash
# Count stale test campaign directories
ls campaign_storage/ | grep -E "^(e2e-test-|test-camp-|summary-test-|validation-test-)" | wc -l
```

Should return `0` if cleanup is working properly.

## Recent Cleanup

**Date**: 2025-11-21
**Result**: Successfully cleaned up 183 stale test campaign directories
**Warnings Resolved**: All test campaign warnings eliminated from logs
