#!/usr/bin/env python3
"""
Sync production prompts to local database.

This script pulls active prompts from production and syncs them to the local database.
It enables a workflow where prompts can be edited via vibe coding locally and then
pushed back to production.

Usage:
    # Sync from production (requires PRODUCTION_DATABASE_URL or Cloud SQL access)
    python sync_prompts_from_production.py

    # Dry run - show what would be synced without making changes
    python sync_prompts_from_production.py --dry-run

    # Sync specific agent types only
    python sync_prompts_from_production.py --agent-type streaming_dm --agent-type scene_agent

Environment Variables:
    PRODUCTION_DATABASE_URL: Direct connection string to production database
    LOCAL_DATABASE_URL: Connection string for local database (defaults to DATABASE_URL)

    For Cloud SQL Proxy access (alternative to PRODUCTION_DATABASE_URL):
    PROD_DB_INSTANCE_CONNECTION_NAME: Cloud SQL instance connection name
    PROD_POSTGRES_USER: Production database user
    PROD_DB_PASSWORD: Production database password
    PROD_POSTGRES_DB: Production database name
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

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


def get_production_database_url() -> Optional[str]:
    """Build production database connection URL."""
    # Direct URL takes precedence
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
            # Cloud SQL Proxy uses Unix sockets
            socket_path = f"/cloudsql/{db_instance}"
            return f"postgresql://{db_user}:{db_password}@/{db_name}?host={socket_path}"

    return None


def get_local_database_url() -> str:
    """Get local database connection URL."""
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


def fetch_active_prompts(session, agent_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch all active prompts from database."""
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
        WHERE is_active = true
    """

    params = {}
    if agent_types:
        query += " AND agent_type = ANY(:agent_types)"
        params['agent_types'] = agent_types

    query += " ORDER BY agent_type, prompt_key"

    result = session.execute(text(query), params)
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


def get_existing_prompt(session, agent_type: str, prompt_key: str) -> Optional[Dict[str, Any]]:
    """Get existing active prompt for agent_type/prompt_key combination."""
    query = """
        SELECT prompt_id, version_number, prompt_text, is_active
        FROM prompt.prompts
        WHERE agent_type = :agent_type
          AND prompt_key = :prompt_key
          AND is_active = true
        LIMIT 1
    """

    result = session.execute(text(query), {
        'agent_type': agent_type,
        'prompt_key': prompt_key
    })
    row = result.fetchone()

    if row:
        return {
            'prompt_id': str(row.prompt_id),
            'version_number': row.version_number,
            'prompt_text': row.prompt_text,
            'is_active': row.is_active,
        }
    return None


def get_max_version(session, agent_type: str, prompt_key: str) -> int:
    """Get the maximum version number for a prompt."""
    query = """
        SELECT COALESCE(MAX(version_number), 0) as max_version
        FROM prompt.prompts
        WHERE agent_type = :agent_type AND prompt_key = :prompt_key
    """

    result = session.execute(text(query), {
        'agent_type': agent_type,
        'prompt_key': prompt_key
    })
    row = result.fetchone()
    return row.max_version if row else 0


def deactivate_prompts(session, agent_type: str, prompt_key: str):
    """Deactivate all versions of a prompt."""
    query = """
        UPDATE prompt.prompts
        SET is_active = false, updated_at = NOW()
        WHERE agent_type = :agent_type
          AND prompt_key = :prompt_key
          AND is_active = true
    """

    session.execute(text(query), {
        'agent_type': agent_type,
        'prompt_key': prompt_key
    })


def insert_prompt(session, prompt: Dict[str, Any], new_version: int, created_by: str):
    """Insert a new prompt version."""
    query = """
        INSERT INTO prompt.prompts (
            agent_type, prompt_key, category, version_number,
            prompt_text, description, is_active, created_by,
            created_at, updated_at
        ) VALUES (
            :agent_type, :prompt_key, :category, :version_number,
            :prompt_text, :description, true, :created_by,
            NOW(), NOW()
        )
    """

    session.execute(text(query), {
        'agent_type': prompt['agent_type'],
        'prompt_key': prompt['prompt_key'],
        'category': prompt['category'],
        'version_number': new_version,
        'prompt_text': prompt['prompt_text'],
        'description': prompt.get('description') or f"Synced from production on {datetime.now().isoformat()}",
        'created_by': created_by,
    })


def get_or_create_system_user(session) -> str:
    """Get or create a system user for automated operations."""
    # First try to find an existing admin user
    query = """
        SELECT user_id FROM auth.users
        WHERE is_admin = true
        LIMIT 1
    """
    result = session.execute(text(query))
    row = result.fetchone()

    if row:
        return str(row.user_id)

    # If no admin, try to find any user
    query = "SELECT user_id FROM auth.users LIMIT 1"
    result = session.execute(text(query))
    row = result.fetchone()

    if row:
        return str(row.user_id)

    # Create a system user if none exists
    query = """
        INSERT INTO auth.users (email, display_name, is_admin, is_active)
        VALUES ('system@gaia.local', 'System', true, true)
        RETURNING user_id
    """
    result = session.execute(text(query))
    row = result.fetchone()
    session.commit()

    return str(row.user_id)


def sync_prompts(
    prod_prompts: List[Dict[str, Any]],
    local_session,
    dry_run: bool = False
) -> Dict[str, int]:
    """Sync production prompts to local database."""
    stats = {
        'created': 0,
        'updated': 0,
        'unchanged': 0,
        'errors': 0,
    }

    if not dry_run:
        created_by = get_or_create_system_user(local_session)
    else:
        created_by = None

    for prompt in prod_prompts:
        agent_type = prompt['agent_type']
        prompt_key = prompt['prompt_key']

        try:
            # Check if prompt exists locally
            existing = get_existing_prompt(local_session, agent_type, prompt_key)

            if existing:
                # Compare prompt text
                if existing['prompt_text'].strip() == prompt['prompt_text'].strip():
                    logger.info(f"  ⏭️  {agent_type}/{prompt_key} - unchanged")
                    stats['unchanged'] += 1
                    continue

                # Prompt text differs - create new version
                if dry_run:
                    logger.info(f"  🔄 {agent_type}/{prompt_key} - would update (v{existing['version_number']} -> v{existing['version_number'] + 1})")
                    stats['updated'] += 1
                else:
                    max_version = get_max_version(local_session, agent_type, prompt_key)
                    new_version = max_version + 1

                    # Deactivate current version(s)
                    deactivate_prompts(local_session, agent_type, prompt_key)

                    # Insert new version as active
                    insert_prompt(local_session, prompt, new_version, created_by)

                    logger.info(f"  🔄 {agent_type}/{prompt_key} - updated to v{new_version}")
                    stats['updated'] += 1
            else:
                # New prompt - create it
                if dry_run:
                    logger.info(f"  ➕ {agent_type}/{prompt_key} - would create (v1)")
                    stats['created'] += 1
                else:
                    insert_prompt(local_session, prompt, 1, created_by)
                    logger.info(f"  ➕ {agent_type}/{prompt_key} - created v1")
                    stats['created'] += 1

        except Exception as e:
            logger.error(f"  ❌ {agent_type}/{prompt_key} - error: {e}")
            stats['errors'] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Sync production prompts to local database"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be synced without making changes'
    )
    parser.add_argument(
        '--agent-type',
        action='append',
        dest='agent_types',
        help='Only sync specific agent types (can be repeated)'
    )

    args = parser.parse_args()

    # Get database URLs
    prod_url = get_production_database_url()
    local_url = get_local_database_url()

    if not prod_url:
        logger.error("❌ No production database URL configured")
        logger.error("Set PRODUCTION_DATABASE_URL or PROD_DB_INSTANCE_CONNECTION_NAME")
        sys.exit(1)

    logger.info("🔄 Starting prompt sync from production")
    if args.dry_run:
        logger.info("   (DRY RUN - no changes will be made)")

    if args.agent_types:
        logger.info(f"   Filtering to agent types: {args.agent_types}")

    # Create database connections
    try:
        prod_engine = create_sync_engine(prod_url)
        local_engine = create_sync_engine(local_url)

        ProdSession = sessionmaker(bind=prod_engine)
        LocalSession = sessionmaker(bind=local_engine)
    except Exception as e:
        logger.error(f"❌ Failed to create database connections: {e}")
        sys.exit(1)

    # Fetch production prompts
    logger.info("\n📥 Fetching active prompts from production...")

    try:
        with ProdSession() as prod_session:
            prod_prompts = fetch_active_prompts(prod_session, args.agent_types)

        logger.info(f"   Found {len(prod_prompts)} active prompts")

        if not prod_prompts:
            logger.warning("⚠️  No active prompts found in production")
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Failed to fetch production prompts: {e}")
        sys.exit(1)

    # Sync to local
    logger.info("\n📤 Syncing to local database...")

    try:
        with LocalSession() as local_session:
            stats = sync_prompts(prod_prompts, local_session, args.dry_run)

            if not args.dry_run:
                local_session.commit()

    except Exception as e:
        logger.error(f"❌ Failed to sync prompts: {e}")
        sys.exit(1)

    # Print summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 Sync Summary:")
    logger.info(f"   Created:   {stats['created']}")
    logger.info(f"   Updated:   {stats['updated']}")
    logger.info(f"   Unchanged: {stats['unchanged']}")
    logger.info(f"   Errors:    {stats['errors']}")

    if args.dry_run:
        logger.info("\n   (DRY RUN - no changes were made)")
    else:
        logger.info("\n✅ Sync complete!")

    if stats['errors'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
