#!/usr/bin/env python3
"""
Cleanup script for stale test campaigns in campaign_storage.

This script removes campaign directories created by tests that match the following patterns:
- e2e-test-*
- test-camp-*
- summary-test-*
- validation-test-*

It also cleans up the corresponding database entries if they exist.

Usage:
    python3 test/room/cleanup_stale_campaigns.py [--dry-run]
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

# Database imports are conditional (only needed when not using --filesystem-only)
db_manager = None
CampaignSession = None
CampaignSessionMember = None
RoomSeat = None
select = None


TEST_CAMPAIGN_PREFIXES = [
    "e2e-test-",
    "test-camp-",
    "summary-test-",
    "validation-test-",
]


def is_test_campaign(campaign_id: str) -> bool:
    """Check if a campaign ID matches test campaign patterns."""
    return any(campaign_id.startswith(prefix) for prefix in TEST_CAMPAIGN_PREFIXES)


def cleanup_campaign_db(campaign_id: str, dry_run: bool = False) -> bool:
    """
    Clean up database entries for a test campaign.

    Returns True if cleanup was performed (or would be in dry-run), False otherwise.
    """
    if db_manager is None:
        return False

    try:
        with db_manager.get_sync_session() as session:
            # Check if campaign exists in DB
            campaign = session.get(CampaignSession, campaign_id)

            if not campaign:
                return False

            if dry_run:
                print(f"  [DRY-RUN] Would delete campaign {campaign_id} from database")
                return True

            # Delete seats
            seats = session.execute(
                select(RoomSeat).where(RoomSeat.campaign_id == campaign_id)
            ).scalars().all()
            for seat in seats:
                session.delete(seat)

            # Delete members
            members = session.execute(
                select(CampaignSessionMember).where(
                    CampaignSessionMember.session_id == campaign_id
                )
            ).scalars().all()
            for member in members:
                session.delete(member)

            # Delete campaign
            session.delete(campaign)
            session.commit()

            print(f"  ✓ Deleted campaign {campaign_id} from database")
            return True

    except Exception as e:
        print(f"  ✗ Error cleaning up database for {campaign_id}: {e}")
        return False


def cleanup_campaign_filesystem(campaign_dir: Path, dry_run: bool = False) -> bool:
    """
    Clean up filesystem directory for a test campaign.

    Returns True if cleanup was performed (or would be in dry-run), False otherwise.
    """
    try:
        if not campaign_dir.exists():
            return False

        # Get directory size and age
        size_mb = sum(f.stat().st_size for f in campaign_dir.rglob('*') if f.is_file()) / (1024 * 1024)
        mtime = datetime.fromtimestamp(campaign_dir.stat().st_mtime, tz=timezone.utc)
        age_days = (datetime.now(timezone.utc) - mtime).days

        if dry_run:
            print(f"  [DRY-RUN] Would delete directory {campaign_dir} ({size_mb:.2f} MB, {age_days} days old)")
            return True

        shutil.rmtree(campaign_dir)
        print(f"  ✓ Deleted directory {campaign_dir} ({size_mb:.2f} MB, {age_days} days old)")
        return True

    except Exception as e:
        print(f"  ✗ Error cleaning up directory {campaign_dir}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Clean up stale test campaigns")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--storage-path",
        default=None,
        help="Path to campaign storage directory (default: from CAMPAIGN_STORAGE_PATH env or 'campaign_storage')"
    )
    parser.add_argument(
        "--filesystem-only",
        action="store_true",
        help="Only clean up filesystem directories, skip database cleanup"
    )
    args = parser.parse_args()

    # Import database modules only if needed
    if not args.filesystem_only:
        global db_manager, CampaignSession, CampaignSessionMember, RoomSeat, select
        try:
            from db.src.connection import db_manager
            from gaia_private.session.session_models import CampaignSession, CampaignSessionMember, RoomSeat
            from sqlalchemy import select
        except ImportError as e:
            print(f"⚠️  Warning: Database imports failed: {e}")
            print("⚠️  Falling back to --filesystem-only mode\n")
            args.filesystem_only = True

    # Get campaign storage path
    storage_path = args.storage_path or os.environ.get("CAMPAIGN_STORAGE_PATH", "campaign_storage")
    storage_dir = Path(storage_path)

    if not storage_dir.exists():
        print(f"❌ Campaign storage directory not found: {storage_dir}")
        sys.exit(1)

    print(f"🔍 Scanning campaign storage: {storage_dir}")
    if args.dry_run:
        print("🔵 DRY-RUN MODE - No changes will be made\n")
    else:
        print("⚠️  CLEANUP MODE - Changes will be made\n")

    # Find all test campaign directories
    test_campaigns = []
    for item in storage_dir.iterdir():
        if item.is_dir() and is_test_campaign(item.name):
            test_campaigns.append(item)

    if not test_campaigns:
        print("✓ No stale test campaigns found")
        return

    print(f"Found {len(test_campaigns)} stale test campaigns:\n")

    # Clean up each campaign
    db_cleaned = 0
    fs_cleaned = 0

    for campaign_dir in sorted(test_campaigns):
        campaign_id = campaign_dir.name
        print(f"📁 {campaign_id}")

        # Clean up database (unless --filesystem-only)
        if not args.filesystem_only:
            if cleanup_campaign_db(campaign_id, dry_run=args.dry_run):
                db_cleaned += 1

        # Clean up filesystem
        if cleanup_campaign_filesystem(campaign_dir, dry_run=args.dry_run):
            fs_cleaned += 1

        print()

    # Summary
    print("=" * 60)
    if args.dry_run:
        print("📊 DRY-RUN SUMMARY:")
        if not args.filesystem_only:
            print(f"  Would clean up {db_cleaned} database entries")
        print(f"  Would delete {fs_cleaned} directories")
        print("\nRun without --dry-run to perform cleanup")
    else:
        print("📊 CLEANUP SUMMARY:")
        if not args.filesystem_only:
            print(f"  ✓ Cleaned up {db_cleaned} database entries")
        print(f"  ✓ Deleted {fs_cleaned} directories")


if __name__ == "__main__":
    main()
