#!/usr/bin/env python3
"""
Backup prompts to SQL files (standalone utility).

This is a simpler utility for generating SQL backup files from a database.
For the full production sync workflow with git integration, use:
    sync_prompts_from_production.py

Usage:
    # Backup from local database (default)
    python backup_prompts_to_sql.py

    # Backup from production database
    python backup_prompts_to_sql.py --source production

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

# Paths
REPO_ROOT = Path(__file__).parent.parent.parent
BACKUP_DIR = REPO_ROOT / "db" / "prompt_backups"
INDIVIDUAL_DIR = BACKUP_DIR / "individual"


def get_database_url(source: str = 'local') -> Optional[str]:
    """Get database connection URL based on source."""
    if source == 'production':
        url = os.getenv('PRODUCTION_DATABASE_URL')
        if url:
            return url

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
        url = os.getenv('LOCAL_DATABASE_URL') or os.getenv('DATABASE_URL')
        if url:
            return url

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
            prompt_id, agent_type, prompt_key, category,
            version_number, parent_prompt_id, prompt_text,
            description, is_active, created_by, created_at, updated_at
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
    """Escape a string for use in SQL using dollar-quoting."""
    if value is None:
        return 'NULL'
    delimiter = "PROMPT"
    counter = 0
    while f"${delimiter}$" in value:
        counter += 1
        delimiter = f"PROMPT{counter}"
    return f"${delimiter}${value}${delimiter}$"


def generate_upsert_sql(prompt: Dict[str, Any]) -> str:
    """Generate SQL UPSERT statement."""
    prompt_text_escaped = escape_sql_string(prompt['prompt_text'])
    description_escaped = escape_sql_string(prompt['description']) if prompt['description'] else 'NULL'

    return f"""-- {prompt['agent_type']}/{prompt['prompt_key']} v{prompt['version_number']}
UPDATE prompt.prompts
SET is_active = false, updated_at = NOW()
WHERE agent_type = '{prompt['agent_type']}'
  AND prompt_key = '{prompt['prompt_key']}'
  AND is_active = true;

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


def write_individual_prompt_files(prompts: List[Dict[str, Any]], source: str) -> List[Path]:
    """Write each prompt to its own file."""
    INDIVIDUAL_DIR.mkdir(parents=True, exist_ok=True)
    files_written = []

    for prompt in prompts:
        if not prompt['is_active']:
            continue

        category_dir = INDIVIDUAL_DIR / prompt['category']
        category_dir.mkdir(parents=True, exist_ok=True)

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

{generate_upsert_sql(prompt)}
""")

        files_written.append(filepath)

    return files_written


def main():
    parser = argparse.ArgumentParser(
        description="Backup prompts to SQL files"
    )
    parser.add_argument(
        '--source',
        choices=['local', 'production'],
        default='local',
        help='Database source (default: local)'
    )
    parser.add_argument(
        '--all-versions',
        action='store_true',
        help='Include all versions, not just active'
    )

    args = parser.parse_args()

    db_url = get_database_url(args.source)

    if not db_url:
        logger.error(f"❌ No database URL configured for source: {args.source}")
        sys.exit(1)

    logger.info(f"📦 Backing up prompts from {args.source}")

    try:
        engine = create_sync_engine(db_url)
        Session = sessionmaker(bind=engine)
    except Exception as e:
        logger.error(f"❌ Failed to create database connection: {e}")
        sys.exit(1)

    logger.info("\n📥 Fetching prompts...")

    try:
        with Session() as session:
            prompts = fetch_prompts(session, active_only=not args.all_versions)

        active_count = sum(1 for p in prompts if p['is_active'])
        logger.info(f"   Found {len(prompts)} prompts ({active_count} active)")

        if not prompts:
            logger.warning("⚠️  No prompts found")
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Failed to fetch prompts: {e}")
        sys.exit(1)

    logger.info(f"\n💾 Writing to {INDIVIDUAL_DIR}...")

    try:
        files = write_individual_prompt_files(prompts, args.source)
        logger.info(f"   ✅ Created {len(files)} files")
    except Exception as e:
        logger.error(f"❌ Failed to write files: {e}")
        sys.exit(1)

    logger.info("\n✅ Backup complete!")


if __name__ == "__main__":
    main()
