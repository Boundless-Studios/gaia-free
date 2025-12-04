#!/usr/bin/env python3
"""
Backup active prompts to SQL files.

This script exports active prompts from the database to SQL backup files.
These backups can be used to:
- Restore prompts to a fresh database
- Version control prompt changes
- Review prompt history

Usage:
    # Backup from local database (default)
    python backup_prompts_to_sql.py

    # Backup from production database
    python backup_prompts_to_sql.py --source production

    # Backup to specific output directory
    python backup_prompts_to_sql.py --output-dir /path/to/backups

    # Include all versions (not just active)
    python backup_prompts_to_sql.py --all-versions

Environment Variables:
    DATABASE_URL: Local database connection string
    PRODUCTION_DATABASE_URL: Production database connection string
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "db"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default output directory
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent.parent / "db" / "prompt_backups"


def get_database_url(source: str = 'local') -> Optional[str]:
    """Get database connection URL based on source."""
    if source == 'production':
        url = os.getenv('PRODUCTION_DATABASE_URL')
        if url:
            return url

        # Try building from Cloud SQL components
        db_instance = os.getenv('PROD_DB_INSTANCE_CONNECTION_NAME')
        if db_instance:
            db_user = os.getenv('PROD_POSTGRES_USER', 'gaia')
            db_password = os.getenv('PROD_DB_PASSWORD')
            db_name = os.getenv('PROD_POSTGRES_DB', 'gaia')

            if db_password:
                socket_path = f"/cloudsql/{db_instance}"
                return f"postgresql://{db_user}:{db_password}@/{db_name}?host={socket_path}"
        return None
    else:
        # Local database
        url = os.getenv('LOCAL_DATABASE_URL') or os.getenv('DATABASE_URL')

        if url:
            return url

        # Build from POSTGRES_* variables
        db_user = os.getenv('POSTGRES_USER', 'gaia')
        db_host = os.getenv('POSTGRES_HOST', 'localhost')
        db_port = os.getenv('POSTGRES_PORT', '5432')
        db_name = os.getenv('POSTGRES_DB', 'gaia')
        db_password = os.getenv('POSTGRES_PASSWORD', '')

        if db_password:
            return f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
        return f'postgresql://{db_user}@{db_host}:{db_port}/{db_name}'


def create_sync_engine(database_url: str):
    """Create a SQLAlchemy engine with psycopg driver."""
    if database_url.startswith('postgresql://'):
        sync_url = database_url.replace('postgresql://', 'postgresql+psycopg://')
    else:
        sync_url = database_url

    return create_engine(
        sync_url,
        pool_pre_ping=True,
        pool_size=5,
        connect_args={"options": "-c timezone=utc"}
    )


def fetch_prompts(session, active_only: bool = True) -> List[Dict[str, Any]]:
    """Fetch prompts from database."""
    query = """
        SELECT
            prompt_id,
            agent_type,
            prompt_key,
            category,
            version_number,
            parent_prompt_id,
            prompt_text,
            description,
            is_active,
            created_by,
            created_at,
            updated_at
        FROM prompt.prompts
    """

    if active_only:
        query += " WHERE is_active = true"

    query += " ORDER BY agent_type, prompt_key, version_number"

    result = session.execute(text(query))
    rows = result.fetchall()

    prompts = []
    for row in rows:
        prompts.append({
            'prompt_id': str(row.prompt_id),
            'agent_type': row.agent_type,
            'prompt_key': row.prompt_key,
            'category': row.category,
            'version_number': row.version_number,
            'parent_prompt_id': str(row.parent_prompt_id) if row.parent_prompt_id else None,
            'prompt_text': row.prompt_text,
            'description': row.description,
            'is_active': row.is_active,
            'created_by': str(row.created_by) if row.created_by else None,
            'created_at': row.created_at,
            'updated_at': row.updated_at,
        })

    return prompts


def escape_sql_string(value: str) -> str:
    """Escape a string for use in SQL."""
    if value is None:
        return 'NULL'
    # Use dollar-quoting for prompt text to avoid escaping issues
    # Find a unique delimiter that doesn't appear in the text
    delimiter = "PROMPT"
    counter = 0
    while f"${delimiter}$" in value:
        counter += 1
        delimiter = f"PROMPT{counter}"
    return f"${delimiter}${value}${delimiter}$"


def generate_sql_insert(prompt: Dict[str, Any]) -> str:
    """Generate SQL INSERT statement for a prompt."""
    prompt_text_escaped = escape_sql_string(prompt['prompt_text'])
    description_escaped = escape_sql_string(prompt['description']) if prompt['description'] else 'NULL'

    return f"""-- {prompt['agent_type']}/{prompt['prompt_key']} v{prompt['version_number']}
INSERT INTO prompt.prompts (
    agent_type, prompt_key, category, version_number,
    prompt_text, description, is_active, created_by,
    created_at, updated_at
)
SELECT
    '{prompt['agent_type']}',
    '{prompt['prompt_key']}',
    '{prompt['category']}',
    {prompt['version_number']},
    {prompt_text_escaped},
    {description_escaped},
    {str(prompt['is_active']).lower()},
    (SELECT user_id FROM auth.users WHERE is_admin = true LIMIT 1),
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM prompt.prompts
    WHERE agent_type = '{prompt['agent_type']}'
      AND prompt_key = '{prompt['prompt_key']}'
      AND version_number = {prompt['version_number']}
);
"""


def generate_upsert_sql(prompt: Dict[str, Any]) -> str:
    """Generate SQL UPSERT statement that handles conflicts."""
    prompt_text_escaped = escape_sql_string(prompt['prompt_text'])
    description_escaped = escape_sql_string(prompt['description']) if prompt['description'] else 'NULL'

    return f"""-- {prompt['agent_type']}/{prompt['prompt_key']} v{prompt['version_number']}
-- First deactivate existing active versions
UPDATE prompt.prompts
SET is_active = false, updated_at = NOW()
WHERE agent_type = '{prompt['agent_type']}'
  AND prompt_key = '{prompt['prompt_key']}'
  AND is_active = true;

-- Insert or update the prompt
INSERT INTO prompt.prompts (
    agent_type, prompt_key, category, version_number,
    prompt_text, description, is_active, created_by,
    created_at, updated_at
)
VALUES (
    '{prompt['agent_type']}',
    '{prompt['prompt_key']}',
    '{prompt['category']}',
    {prompt['version_number']},
    {prompt_text_escaped},
    {description_escaped},
    {str(prompt['is_active']).lower()},
    (SELECT user_id FROM auth.users WHERE is_admin = true LIMIT 1),
    NOW(),
    NOW()
)
ON CONFLICT (agent_type, prompt_key, version_number)
DO UPDATE SET
    prompt_text = EXCLUDED.prompt_text,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();
"""


def write_backup_file(
    prompts: List[Dict[str, Any]],
    output_dir: Path,
    source: str,
    use_upsert: bool = False
) -> Path:
    """Write prompts to SQL backup file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"prompts_backup_{source}_{timestamp}.sql"
    filepath = output_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"""-- Prompt Backup
-- Source: {source}
-- Generated: {datetime.now().isoformat()}
-- Total prompts: {len(prompts)}
--
-- This file contains {'UPSERT' if use_upsert else 'INSERT'} statements for active prompts.
-- Run this file to restore prompts to a database.

-- Ensure prompt schema exists
CREATE SCHEMA IF NOT EXISTS prompt;

-- Begin transaction
BEGIN;

""")

        # Group prompts by category for organization
        prompts_by_category: Dict[str, List[Dict[str, Any]]] = {}
        for prompt in prompts:
            category = prompt['category']
            if category not in prompts_by_category:
                prompts_by_category[category] = []
            prompts_by_category[category].append(prompt)

        # Write prompts grouped by category
        for category in sorted(prompts_by_category.keys()):
            f.write(f"\n-- ============================================\n")
            f.write(f"-- Category: {category}\n")
            f.write(f"-- ============================================\n\n")

            for prompt in prompts_by_category[category]:
                if use_upsert:
                    f.write(generate_upsert_sql(prompt))
                else:
                    f.write(generate_sql_insert(prompt))
                f.write("\n")

        # Write footer
        f.write("""
-- Commit transaction
COMMIT;

-- Summary
-- To apply this backup:
-- psql -d gaia -f this_file.sql
""")

    return filepath


def write_individual_prompt_files(
    prompts: List[Dict[str, Any]],
    output_dir: Path,
    source: str
) -> List[Path]:
    """Write each prompt to its own file for easier version control."""
    prompts_dir = output_dir / "individual"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    files_written = []

    for prompt in prompts:
        # Create directory structure by category
        category_dir = prompts_dir / prompt['category']
        category_dir.mkdir(parents=True, exist_ok=True)

        # Filename: agent_type__prompt_key.sql
        safe_agent = prompt['agent_type'].replace('/', '_')
        safe_key = prompt['prompt_key'].replace('/', '_')
        filename = f"{safe_agent}__{safe_key}.sql"
        filepath = category_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"""-- Prompt: {prompt['agent_type']}/{prompt['prompt_key']}
-- Category: {prompt['category']}
-- Version: {prompt['version_number']}
-- Source: {source}
-- Updated: {datetime.now().isoformat()}

""")
            f.write(generate_upsert_sql(prompt))

        files_written.append(filepath)

    return files_written


def write_latest_symlink(output_dir: Path, backup_file: Path):
    """Create a symlink to the latest backup."""
    latest_link = output_dir / "latest.sql"

    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()

    latest_link.symlink_to(backup_file.name)


def main():
    parser = argparse.ArgumentParser(
        description="Backup active prompts to SQL files"
    )
    parser.add_argument(
        '--source',
        choices=['local', 'production'],
        default='local',
        help='Database source to backup from (default: local)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f'Output directory for backup files (default: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--all-versions',
        action='store_true',
        help='Include all versions, not just active ones'
    )
    parser.add_argument(
        '--upsert',
        action='store_true',
        help='Generate UPSERT statements instead of INSERT'
    )
    parser.add_argument(
        '--individual',
        action='store_true',
        help='Also write individual prompt files for version control'
    )

    args = parser.parse_args()

    # Get database URL
    db_url = get_database_url(args.source)

    if not db_url:
        logger.error(f"❌ No database URL configured for source: {args.source}")
        if args.source == 'production':
            logger.error("Set PRODUCTION_DATABASE_URL or PROD_DB_INSTANCE_CONNECTION_NAME")
        else:
            logger.error("Set DATABASE_URL or POSTGRES_* environment variables")
        sys.exit(1)

    logger.info(f"📦 Starting prompt backup from {args.source}")

    # Create database connection
    try:
        engine = create_sync_engine(db_url)
        Session = sessionmaker(bind=engine)
    except Exception as e:
        logger.error(f"❌ Failed to create database connection: {e}")
        sys.exit(1)

    # Fetch prompts
    logger.info("\n📥 Fetching prompts...")

    try:
        with Session() as session:
            prompts = fetch_prompts(session, active_only=not args.all_versions)

        active_count = sum(1 for p in prompts if p['is_active'])
        logger.info(f"   Found {len(prompts)} prompts ({active_count} active)")

        if not prompts:
            logger.warning("⚠️  No prompts found to backup")
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Failed to fetch prompts: {e}")
        sys.exit(1)

    # Write backup file
    logger.info(f"\n💾 Writing backup to {args.output_dir}...")

    try:
        backup_file = write_backup_file(
            prompts,
            args.output_dir,
            args.source,
            use_upsert=args.upsert
        )
        logger.info(f"   ✅ Created: {backup_file}")

        # Create latest symlink
        try:
            write_latest_symlink(args.output_dir, backup_file)
            logger.info(f"   ✅ Updated: {args.output_dir / 'latest.sql'}")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not create latest symlink: {e}")

        # Write individual files if requested
        if args.individual:
            logger.info("\n📄 Writing individual prompt files...")
            individual_files = write_individual_prompt_files(
                [p for p in prompts if p['is_active']],  # Only active for individual
                args.output_dir,
                args.source
            )
            logger.info(f"   ✅ Created {len(individual_files)} individual files")

    except Exception as e:
        logger.error(f"❌ Failed to write backup: {e}")
        sys.exit(1)

    # Print summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 Backup Summary:")
    logger.info(f"   Source:       {args.source}")
    logger.info(f"   Total:        {len(prompts)} prompts")
    logger.info(f"   Active:       {active_count} prompts")
    logger.info(f"   Output:       {backup_file}")
    logger.info("\n✅ Backup complete!")


if __name__ == "__main__":
    main()
