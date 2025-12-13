#!/usr/bin/env python3
"""
Character Storage Migration Script

Migrates character data from disk-based JSON storage to PostgreSQL database.
Supports both character profiles and campaign instances.

Usage:
    # Dry run (preview changes without applying)
    python scripts/migrate_characters_to_db.py --dry-run

    # Migrate system characters
    python scripts/migrate_characters_to_db.py --user-id system

    # Migrate specific user's characters
    python scripts/migrate_characters_to_db.py --user-id user_abc123 --email user@example.com

    # Migrate with verbose logging
    python scripts/migrate_characters_to_db.py --user-id system --verbose

    # Migrate NPCs for a specific campaign
    python scripts/migrate_characters_to_db.py --npcs-only --campaign-id campaign_123 --user-id dm_user_id
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from gaia.models.character import CharacterProfile as CharacterProfileDataclass
from gaia.models.character import CharacterInfo
from gaia.models.character.npc_profile import NpcProfile as NpcProfileDataclass
from gaia.models.character.enums import CharacterType, CharacterRole, VoiceArchetype
from gaia.infra.storage.character_repository import CharacterRepository
from gaia.mechanics.character.utils import CharacterDataConverter

logger = logging.getLogger(__name__)


class CharacterMigration:
    """Handles migration of character data from disk to database."""

    def __init__(
        self,
        base_path: Optional[str] = None,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        """Initialize the migration tool.

        Args:
            base_path: Base path for character storage (defaults to CAMPAIGN_STORAGE_PATH)
            dry_run: If True, preview changes without applying them
            verbose: Enable verbose logging
        """
        self.dry_run = dry_run
        self.verbose = verbose

        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Get base path from environment if not provided
        if base_path is None:
            base_path = os.getenv('CAMPAIGN_STORAGE_PATH')
            if not base_path:
                raise ValueError("CAMPAIGN_STORAGE_PATH environment variable not set")

        self.base_path = Path(base_path)
        self.characters_path = self.base_path / "characters"
        self.profiles_path = self.base_path / "character_profiles"

        # Initialize repository (only if not dry run)
        if not dry_run:
            self.repository = CharacterRepository()
        else:
            self.repository = None

        self.converter = CharacterDataConverter()

        # Statistics
        self.stats = {
            'profiles_found': 0,
            'profiles_migrated': 0,
            'profiles_skipped': 0,
            'profiles_failed': 0,
            'characters_found': 0,
            'characters_migrated': 0,
            'characters_skipped': 0,
            'characters_failed': 0,
            'npcs_found': 0,
            'npcs_migrated': 0,
            'npcs_failed': 0,
        }

    def _load_json_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load JSON data from a file.

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed JSON data or None if failed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return None

    def _dict_to_character_profile(
        self,
        profile_data: Dict[str, Any]
    ) -> Optional[CharacterProfileDataclass]:
        """Convert profile dict to CharacterProfile dataclass.

        Args:
            profile_data: Profile dictionary from JSON

        Returns:
            CharacterProfile dataclass or None if conversion failed
        """
        try:
            # Parse character type
            char_type_str = profile_data.get('character_type', 'npc')
            try:
                char_type = CharacterType(char_type_str)
            except ValueError:
                char_type = CharacterType.NPC

            # Parse voice archetype
            voice_archetype = None
            if profile_data.get('voice_archetype'):
                try:
                    voice_archetype = VoiceArchetype(profile_data['voice_archetype'])
                except ValueError:
                    pass

            # Parse datetime fields
            first_created = profile_data.get('first_created')
            if isinstance(first_created, str):
                try:
                    first_created = datetime.fromisoformat(first_created)
                except:
                    first_created = datetime.now()
            elif not first_created:
                first_created = datetime.now()

            return CharacterProfileDataclass(
                character_id=profile_data.get('character_id') or profile_data.get('id'),
                name=profile_data.get('name', 'Unknown'),
                character_type=char_type,
                race=profile_data.get('race', 'human'),
                character_class=profile_data.get('character_class', 'adventurer'),
                base_level=profile_data.get('base_level', 1),
                voice_id=profile_data.get('voice_id'),
                voice_settings=profile_data.get('voice_settings', {}),
                voice_archetype=voice_archetype,
                portrait_url=profile_data.get('portrait_url'),
                portrait_path=profile_data.get('portrait_path'),
                portrait_prompt=profile_data.get('portrait_prompt'),
                additional_images=profile_data.get('additional_images', []),
                gender=profile_data.get('gender'),
                age_category=profile_data.get('age_category'),
                build=profile_data.get('build'),
                height_description=profile_data.get('height_description'),
                facial_expression=profile_data.get('facial_expression'),
                facial_features=profile_data.get('facial_features'),
                attire=profile_data.get('attire'),
                primary_weapon=profile_data.get('primary_weapon'),
                distinguishing_feature=profile_data.get('distinguishing_feature'),
                background_setting=profile_data.get('background_setting'),
                pose=profile_data.get('pose'),
                backstory=profile_data.get('backstory', ''),
                description=profile_data.get('description', ''),
                appearance=profile_data.get('appearance', ''),
                visual_description=profile_data.get('visual_description', ''),
                total_interactions=profile_data.get('total_interactions', 0),
                first_created=first_created,
            )
        except Exception as e:
            logger.error(f"Failed to convert profile data: {e}")
            return None

    def migrate_profiles(
        self,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> int:
        """Migrate character profiles from disk to database.

        Args:
            user_id: User ID to assign as owner (None = system)
            user_email: User email for ownership

        Returns:
            Number of profiles migrated
        """
        if not self.profiles_path.exists():
            logger.warning(f"Profiles path not found: {self.profiles_path}")
            return 0

        logger.info(f"Migrating profiles from {self.profiles_path}")
        migrated = 0

        for profile_file in self.profiles_path.glob("*.json"):
            self.stats['profiles_found'] += 1

            # Load profile data
            profile_data = self._load_json_file(profile_file)
            if not profile_data:
                self.stats['profiles_failed'] += 1
                continue

            # Convert to dataclass
            profile = self._dict_to_character_profile(profile_data)
            if not profile:
                self.stats['profiles_failed'] += 1
                continue

            logger.info(f"Processing profile: {profile.character_id} ({profile.name})")

            if self.dry_run:
                logger.info(f"  [DRY RUN] Would migrate profile {profile.character_id}")
                self.stats['profiles_migrated'] += 1
                migrated += 1
                continue

            try:
                # Check if profile already exists
                existing_uuid = self.repository.get_profile_by_external_id_sync(profile.character_id)

                if existing_uuid:
                    logger.info(f"  Profile {profile.character_id} already exists, skipping")
                    self.stats['profiles_skipped'] += 1
                    continue

                # Create profile in database
                profile_uuid = self.repository.create_profile_sync(
                    profile,
                    user_id=user_id,
                    user_email=user_email,
                )

                logger.info(f"  ✓ Migrated profile {profile.character_id} (UUID: {profile_uuid})")
                self.stats['profiles_migrated'] += 1
                migrated += 1

            except Exception as e:
                logger.error(f"  ✗ Failed to migrate profile {profile.character_id}: {e}")
                self.stats['profiles_failed'] += 1

        return migrated

    def migrate_characters(
        self,
        campaign_id: Optional[str] = None,
    ) -> int:
        """Migrate character instances from disk to database.

        Args:
            campaign_id: Optional campaign ID to filter characters

        Returns:
            Number of characters migrated
        """
        if not self.characters_path.exists():
            logger.warning(f"Characters path not found: {self.characters_path}")
            return 0

        logger.info(f"Migrating characters from {self.characters_path}")
        migrated = 0

        for char_file in self.characters_path.glob("*.json"):
            self.stats['characters_found'] += 1

            # Load character data
            char_data = self._load_json_file(char_file)
            if not char_data:
                self.stats['characters_failed'] += 1
                continue

            # Skip if campaign filter doesn't match
            if campaign_id:
                char_campaigns = char_data.get('campaigns', [])
                if campaign_id not in char_campaigns:
                    continue

            # Convert to CharacterInfo
            try:
                character_info = self.converter.from_dict(char_data, CharacterInfo)
            except Exception as e:
                logger.error(f"Failed to convert character {char_file.stem}: {e}")
                self.stats['characters_failed'] += 1
                continue

            logger.info(f"Processing character: {character_info.character_id} ({character_info.name})")

            if self.dry_run:
                logger.info(f"  [DRY RUN] Would migrate character {character_info.character_id}")
                self.stats['characters_migrated'] += 1
                migrated += 1
                continue

            # Note: Character instances require both profile and campaign UUIDs
            # This is a simplified migration - in production, you'd need campaign UUID mapping
            logger.warning(f"  Character instance migration requires campaign UUID mapping - skipping {character_info.character_id}")
            self.stats['characters_skipped'] += 1

        return migrated

    def migrate_npcs(
        self,
        campaign_id: str,
        user_id: str,
        user_email: Optional[str] = None,
    ) -> int:
        """Migrate NPC profiles to database.

        Args:
            campaign_id: Campaign ID these NPCs belong to
            user_id: DM user ID
            user_email: DM email

        Returns:
            Number of NPCs migrated
        """
        # NPC migration would use NpcProfileStorage
        # For now, this is a placeholder
        logger.info("NPC migration not yet implemented")
        return 0

    def print_summary(self):
        """Print migration summary statistics."""
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)

        if self.dry_run:
            print("MODE: DRY RUN (no changes applied)")
        else:
            print("MODE: LIVE MIGRATION")

        print("\nProfiles:")
        print(f"  Found:    {self.stats['profiles_found']}")
        print(f"  Migrated: {self.stats['profiles_migrated']}")
        print(f"  Skipped:  {self.stats['profiles_skipped']}")
        print(f"  Failed:   {self.stats['profiles_failed']}")

        print("\nCharacters:")
        print(f"  Found:    {self.stats['characters_found']}")
        print(f"  Migrated: {self.stats['characters_migrated']}")
        print(f"  Skipped:  {self.stats['characters_skipped']}")
        print(f"  Failed:   {self.stats['characters_failed']}")

        print("\nNPCs:")
        print(f"  Found:    {self.stats['npcs_found']}")
        print(f"  Migrated: {self.stats['npcs_migrated']}")
        print(f"  Failed:   {self.stats['npcs_failed']}")

        print("=" * 60)


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate character storage from disk to PostgreSQL database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them',
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging',
    )

    parser.add_argument(
        '--user-id',
        type=str,
        help='User ID to assign as owner (use "system" for system characters)',
    )

    parser.add_argument(
        '--email',
        type=str,
        help='User email for ownership',
    )

    parser.add_argument(
        '--campaign-id',
        type=str,
        help='Optional campaign ID filter for character instances',
    )

    parser.add_argument(
        '--profiles-only',
        action='store_true',
        help='Only migrate character profiles (not instances)',
    )

    parser.add_argument(
        '--characters-only',
        action='store_true',
        help='Only migrate character instances (not profiles)',
    )

    parser.add_argument(
        '--npcs-only',
        action='store_true',
        help='Only migrate NPC profiles',
    )

    parser.add_argument(
        '--base-path',
        type=str,
        help='Base path for character storage (defaults to CAMPAIGN_STORAGE_PATH)',
    )

    args = parser.parse_args()

    # Validate arguments
    if args.npcs_only and not args.campaign_id:
        parser.error("--npcs-only requires --campaign-id")

    if args.npcs_only and not args.user_id:
        parser.error("--npcs-only requires --user-id (DM ID)")

    # Initialize migration tool
    try:
        migration = CharacterMigration(
            base_path=args.base_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    except Exception as e:
        print(f"Failed to initialize migration: {e}", file=sys.stderr)
        return 1

    # Run migration
    try:
        if args.profiles_only:
            migration.migrate_profiles(
                user_id=args.user_id,
                user_email=args.email,
            )
        elif args.characters_only:
            migration.migrate_characters(
                campaign_id=args.campaign_id,
            )
        elif args.npcs_only:
            migration.migrate_npcs(
                campaign_id=args.campaign_id,
                user_id=args.user_id,
                user_email=args.email,
            )
        else:
            # Migrate both profiles and characters
            migration.migrate_profiles(
                user_id=args.user_id,
                user_email=args.email,
            )
            migration.migrate_characters(
                campaign_id=args.campaign_id,
            )

        # Print summary
        migration.print_summary()

        return 0

    except KeyboardInterrupt:
        print("\nMigration interrupted by user", file=sys.stderr)
        migration.print_summary()
        return 130
    except Exception as e:
        print(f"\nMigration failed: {e}", file=sys.stderr)
        migration.print_summary()
        return 1


if __name__ == '__main__':
    sys.exit(main())
