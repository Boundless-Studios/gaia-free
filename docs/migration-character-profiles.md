# Character Profile Migration Plan

**Status**: Deferred - To be executed after new structure is validated
**Created**: 2025-10-12
**Related**: [task-character-profile-refactoring.md](./task-character-profile-refactoring.md)

## Overview

This document outlines the migration strategy for converting existing campaigns from the old character storage structure (visual metadata in CharacterInfo) to the new structure (visual metadata in CharacterProfile).

**IMPORTANT**: This migration should only be executed AFTER the new structure has been validated with new campaigns and portrait generation is working correctly.

## Current State vs. Target State

### Current State (Old Structure)
```
CharacterInfo (campaign-specific)
├─ character_id, name, race, class
├─ Visual metadata (gender, build, etc.)
├─ Portrait (url, path, prompt)
├─ Campaign state (HP, inventory)
└─ No profile_id field

CharacterProfile (global)
├─ character_id, name
├─ voice_id, voice_settings
└─ portrait_path, portrait_prompt (minimal)
```

### Target State (New Structure)
```
CharacterProfile (global)
├─ character_id, name, race, class
├─ Visual metadata (gender, build, etc.)
├─ Portrait (url, path, prompt)
├─ Voice settings
└─ Backstory, descriptions

CharacterInfo (campaign-specific)
├─ character_id
├─ profile_id → references CharacterProfile
├─ level (optional override)
└─ Campaign state (HP, inventory)
```

## Migration Phases

### Phase 0.5: Create Migration Script

**File**: `backend/scripts/migrate_character_profiles.py`

**Script Structure**:
```python
"""
Migrate existing campaigns from old character structure to new profile-based structure.

Usage:
  # Dry run (preview changes)
  python3 migrate_character_profiles.py --dry-run

  # Migrate single campaign
  python3 migrate_character_profiles.py --campaign-id campaign_123

  # Migrate all campaigns
  python3 migrate_character_profiles.py --all

  # Backup only
  python3 migrate_character_profiles.py --backup-only
"""

class CharacterProfileMigration:
    """Handles migration of character data to profile-based structure."""

    def __init__(self, campaign_storage_path: str, dry_run: bool = False):
        self.campaign_storage_path = campaign_storage_path
        self.dry_run = dry_run
        self.profile_storage = ProfileStorage()
        self.stats = {
            "campaigns_processed": 0,
            "characters_migrated": 0,
            "profiles_created": 0,
            "profiles_updated": 0,
            "errors": []
        }

    def migrate_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Migrate all characters in a single campaign."""
        pass

    def migrate_character(
        self,
        character_info: CharacterInfo,
        campaign_id: str
    ) -> Tuple[CharacterProfile, CharacterInfo]:
        """Migrate a single character to profile-based structure."""
        pass

    def backup_campaign(self, campaign_id: str) -> str:
        """Create backup of campaign data before migration."""
        pass

    def validate_migration(self, campaign_id: str) -> bool:
        """Validate migration was successful."""
        pass

    def rollback_campaign(self, campaign_id: str, backup_path: str):
        """Rollback migration using backup."""
        pass
```

**Migration Logic for Each Character**:

1. **Load CharacterInfo** from campaign storage
2. **Find or Create CharacterProfile**:
   - Check if profile already exists (by character_id)
   - If exists, load it
   - If not, create new profile
3. **Copy Identity Data** from CharacterInfo → CharacterProfile:
   - race, character_class → profile
   - base_level = character_info.level
4. **Copy Visual Metadata** from CharacterInfo → CharacterProfile:
   - gender, age_category, build, height_description
   - facial_expression, facial_features
   - attire, primary_weapon, distinguishing_feature
   - background_setting, pose
5. **Copy Portrait Data** from CharacterInfo → CharacterProfile:
   - portrait_url, portrait_path, portrait_prompt
6. **Copy Descriptions** from CharacterInfo → CharacterProfile:
   - backstory, description, appearance, visual_description
7. **Copy Voice Data** from CharacterInfo → CharacterProfile:
   - voice_id, voice_settings
8. **Save CharacterProfile** to profile storage
9. **Add profile_id** to CharacterInfo:
   - character_info.profile_id = profile.character_id
10. **Save Updated CharacterInfo** to campaign storage
11. **Validate**: Verify all data copied correctly

**Error Handling**:
- Log all errors to migration log file
- Continue processing other characters if one fails
- Provide detailed error report at end
- Allow retry of failed characters

**Validation Checks**:
- All characters have profile_id field
- All profiles have required identity data
- No visual metadata lost during migration
- Portrait data preserved
- Campaign state intact

### Phase 0.6: Run Migration

**Pre-Migration Checklist**:
- [ ] New structure validated with test campaigns
- [ ] Portrait generation working correctly
- [ ] Visual updates working correctly
- [ ] Backup of campaign_storage created
- [ ] Migration script tested on single campaign
- [ ] Rollback procedure tested
- [ ] All tests passing

**Migration Steps**:

1. **Backup All Data**:
   ```bash
   # Create timestamped backup
   tar -czf campaign_storage_backup_$(date +%Y%m%d_%H%M%S).tar.gz campaign_storage/
   ```

2. **Dry Run Migration**:
   ```bash
   # Preview changes without modifying data
   python3 backend/scripts/migrate_character_profiles.py --dry-run --all
   ```

3. **Migrate Test Campaign**:
   ```bash
   # Migrate single campaign first
   python3 backend/scripts/migrate_character_profiles.py --campaign-id test_campaign_1

   # Validate migration
   python3 backend/scripts/validate_migration.py --campaign-id test_campaign_1
   ```

4. **Test Migrated Campaign**:
   - Start campaign
   - Load characters
   - View character sheets
   - Generate portrait
   - Update visual metadata
   - Verify all data correct

5. **Migrate All Campaigns**:
   ```bash
   # Only after test migration successful
   python3 backend/scripts/migrate_character_profiles.py --all
   ```

6. **Validation**:
   ```bash
   # Validate all campaigns
   python3 backend/scripts/validate_migration.py --all
   ```

7. **Post-Migration Testing**:
   - Run all backend tests
   - Start each campaign
   - Verify character data loads correctly
   - Test portrait generation
   - Test visual updates

**Rollback Procedure**:
```bash
# If migration fails, restore from backup
rm -rf campaign_storage/
tar -xzf campaign_storage_backup_YYYYMMDD_HHMMSS.tar.gz
```

### Phase 0.7: Remove Visual Fields from CharacterInfo

**CRITICAL**: Only execute AFTER successful migration of all campaigns.

**File**: `backend/src/core/character/models/character_info.py`

**Fields to Remove**:
```python
# DELETE these fields from CharacterInfo after migration:
portrait_url: Optional[str] = None
portrait_path: Optional[str] = None
portrait_prompt: Optional[str] = None
gender: Optional[str] = None
age_category: Optional[str] = None
build: Optional[str] = None
height_description: Optional[str] = None
facial_expression: Optional[str] = None
facial_features: Optional[str] = None
attire: Optional[str] = None
primary_weapon: Optional[str] = None
distinguishing_feature: Optional[str] = None
background_setting: Optional[str] = None
pose: Optional[str] = None
backstory: str = ""
description: str = ""
appearance: str = ""
visual_description: str = ""
voice_id: Optional[str] = None
voice_settings: Dict[str, Any] = field(default_factory=dict)
```

**ADD Required Field**:
```python
profile_id: str  # Required - link to CharacterProfile
```

**Update Methods**:
- Update `to_dict()` to remove visual fields
- Update `from_dict()` to require profile_id
- Update class documentation

**Testing After Removal**:
- All backend tests must pass
- CharacterInfo serialization works
- Campaign loading works
- EnrichedCharacter creation works

## Migration Script Template

```python
#!/usr/bin/env python3
"""Migrate character data to profile-based structure."""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CharacterProfileMigration:
    """Migrate characters from old to new profile-based structure."""

    def __init__(self, campaign_storage_path: str, dry_run: bool = False):
        self.campaign_storage_path = Path(campaign_storage_path)
        self.dry_run = dry_run
        self.backup_dir = None
        self.stats = {
            "campaigns_processed": 0,
            "characters_migrated": 0,
            "profiles_created": 0,
            "profiles_updated": 0,
            "errors": []
        }

    def backup_all_data(self) -> Path:
        """Create backup of all campaign data."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"campaign_storage_backup_{timestamp}"
        backup_path = self.campaign_storage_path.parent / backup_name

        logger.info(f"Creating backup at {backup_path}")

        if not self.dry_run:
            shutil.copytree(self.campaign_storage_path, backup_path)

        self.backup_dir = backup_path
        return backup_path

    def list_campaigns(self) -> List[str]:
        """List all campaign IDs."""
        campaigns_dir = self.campaign_storage_path / "campaigns"
        if not campaigns_dir.exists():
            return []

        return [d.name for d in campaigns_dir.iterdir() if d.is_dir()]

    def migrate_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Migrate all characters in a campaign."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Migrating campaign: {campaign_id}")
        logger.info(f"{'='*60}")

        campaign_result = {
            "campaign_id": campaign_id,
            "characters_migrated": 0,
            "errors": []
        }

        # Load characters from campaign
        characters_path = self.campaign_storage_path / "campaigns" / campaign_id / "characters.json"

        if not characters_path.exists():
            logger.warning(f"No characters.json found for campaign {campaign_id}")
            return campaign_result

        try:
            with open(characters_path, 'r') as f:
                characters_data = json.load(f)

            logger.info(f"Found {len(characters_data)} characters")

            # Migrate each character
            for char_id, char_data in characters_data.items():
                try:
                    self._migrate_character(char_id, char_data, campaign_id)
                    campaign_result["characters_migrated"] += 1
                except Exception as e:
                    error_msg = f"Failed to migrate character {char_id}: {str(e)}"
                    logger.error(error_msg)
                    campaign_result["errors"].append(error_msg)

            self.stats["campaigns_processed"] += 1

        except Exception as e:
            error_msg = f"Failed to process campaign {campaign_id}: {str(e)}"
            logger.error(error_msg)
            campaign_result["errors"].append(error_msg)

        return campaign_result

    def _migrate_character(
        self,
        char_id: str,
        char_data: Dict[str, Any],
        campaign_id: str
    ):
        """Migrate a single character."""
        logger.info(f"  Migrating character: {char_data.get('name', char_id)}")

        # Create or load profile
        profile_id = char_id
        profile_path = self.campaign_storage_path / "character_profiles" / f"{profile_id}.json"

        if profile_path.exists():
            logger.info(f"    Profile exists, updating...")
            with open(profile_path, 'r') as f:
                profile_data = json.load(f)
            self.stats["profiles_updated"] += 1
        else:
            logger.info(f"    Creating new profile...")
            profile_data = {
                "character_id": char_id,
                "name": char_data.get("name", "Unknown"),
                "character_type": "player" if char_data.get("character_type") == "player" else "npc",
                "first_created": datetime.now().isoformat(),
                "total_interactions": 0
            }
            self.stats["profiles_created"] += 1

        # Copy identity data
        profile_data["race"] = char_data.get("race", "human")
        profile_data["character_class"] = char_data.get("character_class", "adventurer")
        profile_data["base_level"] = char_data.get("level", 1)

        # Copy visual metadata
        visual_fields = [
            'gender', 'age_category', 'build', 'height_description',
            'facial_expression', 'facial_features', 'attire',
            'primary_weapon', 'distinguishing_feature',
            'background_setting', 'pose'
        ]
        for field in visual_fields:
            if field in char_data:
                profile_data[field] = char_data[field]
                logger.debug(f"      Copied {field}: {char_data[field]}")

        # Copy portrait data
        if 'portrait_url' in char_data:
            profile_data['portrait_url'] = char_data['portrait_url']
        if 'portrait_path' in char_data:
            profile_data['portrait_path'] = char_data['portrait_path']
        if 'portrait_prompt' in char_data:
            profile_data['portrait_prompt'] = char_data['portrait_prompt']

        # Copy descriptions
        for field in ['backstory', 'description', 'appearance', 'visual_description']:
            if field in char_data:
                profile_data[field] = char_data[field]

        # Copy voice data
        if 'voice_id' in char_data:
            profile_data['voice_id'] = char_data['voice_id']
        if 'voice_settings' in char_data:
            profile_data['voice_settings'] = char_data['voice_settings']

        # Add profile_id to character data
        char_data['profile_id'] = profile_id

        # Save profile and character (if not dry run)
        if not self.dry_run:
            # Ensure character_profiles directory exists
            profile_path.parent.mkdir(parents=True, exist_ok=True)

            # Save profile
            with open(profile_path, 'w') as f:
                json.dump(profile_data, f, indent=2)

            logger.info(f"    ✓ Profile saved to {profile_path}")
        else:
            logger.info(f"    [DRY RUN] Would save profile to {profile_path}")

        self.stats["characters_migrated"] += 1

    def print_summary(self):
        """Print migration summary."""
        logger.info("\n" + "="*60)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Campaigns processed: {self.stats['campaigns_processed']}")
        logger.info(f"Characters migrated: {self.stats['characters_migrated']}")
        logger.info(f"Profiles created: {self.stats['profiles_created']}")
        logger.info(f"Profiles updated: {self.stats['profiles_updated']}")

        if self.stats['errors']:
            logger.info(f"\nErrors: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                logger.error(f"  - {error}")
        else:
            logger.info("\n✓ No errors!")

        if self.backup_dir:
            logger.info(f"\nBackup location: {self.backup_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate character data to profile-based structure")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without modifying data")
    parser.add_argument('--campaign-id', type=str, help="Migrate single campaign by ID")
    parser.add_argument('--all', action='store_true', help="Migrate all campaigns")
    parser.add_argument('--backup-only', action='store_true', help="Only create backup, don't migrate")
    parser.add_argument('--storage-path', type=str, default='campaign_storage', help="Path to campaign storage")

    args = parser.parse_args()

    # Initialize migration
    migration = CharacterProfileMigration(args.storage_path, dry_run=args.dry_run)

    # Create backup
    if not args.dry_run:
        backup_path = migration.backup_all_data()
        logger.info(f"✓ Backup created at {backup_path}\n")

        if args.backup_only:
            logger.info("Backup complete. Exiting.")
            return

    # Migrate campaigns
    if args.all:
        campaigns = migration.list_campaigns()
        logger.info(f"Found {len(campaigns)} campaigns to migrate\n")

        for campaign_id in campaigns:
            migration.migrate_campaign(campaign_id)

    elif args.campaign_id:
        migration.migrate_campaign(args.campaign_id)

    else:
        logger.error("Must specify --campaign-id or --all")
        return

    # Print summary
    migration.print_summary()


if __name__ == "__main__":
    main()
```

## Validation Script Template

```python
#!/usr/bin/env python3
"""Validate character profile migration."""

import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def validate_campaign(campaign_id: str, storage_path: str) -> Dict[str, Any]:
    """Validate migration for a single campaign."""

    validation_result = {
        "campaign_id": campaign_id,
        "valid": True,
        "issues": []
    }

    # Load characters
    characters_path = Path(storage_path) / "campaigns" / campaign_id / "characters.json"

    if not characters_path.exists():
        validation_result["valid"] = False
        validation_result["issues"].append("characters.json not found")
        return validation_result

    with open(characters_path, 'r') as f:
        characters = json.load(f)

    # Validate each character
    for char_id, char_data in characters.items():
        # Check profile_id exists
        if 'profile_id' not in char_data:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Character {char_id} missing profile_id")
            continue

        profile_id = char_data['profile_id']
        profile_path = Path(storage_path) / "character_profiles" / f"{profile_id}.json"

        # Check profile exists
        if not profile_path.exists():
            validation_result["valid"] = False
            validation_result["issues"].append(f"Profile {profile_id} not found for character {char_id}")
            continue

        # Load profile
        with open(profile_path, 'r') as f:
            profile_data = json.load(f)

        # Validate profile has required fields
        required_fields = ['character_id', 'name', 'race', 'character_class']
        for field in required_fields:
            if field not in profile_data:
                validation_result["valid"] = False
                validation_result["issues"].append(f"Profile {profile_id} missing {field}")

    return validation_result
```

## Timeline

**DO NOT EXECUTE until:**
- ✅ New structure validated with test campaigns
- ✅ Portrait generation working correctly
- ✅ Visual updates working correctly
- ✅ All tests passing
- ✅ User approval to proceed

**Estimated Time**:
- Script development: 2-3 hours
- Testing on single campaign: 30 minutes
- Full migration: 5-10 minutes (depending on data volume)
- Validation: 10-15 minutes

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | High | Full backup before migration |
| Migration script bugs | High | Dry run testing on single campaign first |
| Incomplete data copy | Medium | Comprehensive validation checks |
| Rollback needed | Medium | Documented rollback procedure |
| Long migration time | Low | Can migrate incrementally by campaign |

## Success Criteria

- [ ] All campaigns migrated successfully
- [ ] All characters have profile_id
- [ ] All profiles have required fields
- [ ] No visual metadata lost
- [ ] Portrait data preserved
- [ ] All tests pass after migration
- [ ] Campaigns load and function correctly
- [ ] No data duplication detected
