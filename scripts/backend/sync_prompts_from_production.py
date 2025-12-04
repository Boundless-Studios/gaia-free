#!/usr/bin/env python3
"""
Sync production prompts to local database and update SQL backups.

This script:
1. Pulls active prompts from production and syncs them to the local database
2. Generates SQL backup files from the synced prompts
3. If backups changed, creates a branch, commits, and pushes the updates
4. Returns you to your original branch

Usage:
    # Full sync with automatic backup commit
    python sync_prompts_from_production.py

    # Dry run - show what would be synced without making changes
    python sync_prompts_from_production.py --dry-run

    # Skip the git operations (just sync DB and generate backups)
    python sync_prompts_from_production.py --no-git

    # Sync specific agent types only
    python sync_prompts_from_production.py --agent-type streaming_dm

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
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


# =============================================================================
# Database Functions
# =============================================================================

def get_production_database_url() -> Optional[str]:
    """Build production database connection URL."""
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


def get_local_database_url() -> str:
    """Get local database connection URL."""
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


def fetch_active_prompts(session, agent_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch all active prompts from database."""
    query = """
        SELECT
            prompt_id, agent_type, prompt_key, category,
            version_number, parent_prompt_id, prompt_text,
            description, is_active, created_by, created_at, updated_at
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
        WHERE agent_type = :agent_type AND prompt_key = :prompt_key AND is_active = true
        LIMIT 1
    """

    result = session.execute(text(query), {'agent_type': agent_type, 'prompt_key': prompt_key})
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

    result = session.execute(text(query), {'agent_type': agent_type, 'prompt_key': prompt_key})
    row = result.fetchone()
    return row.max_version if row else 0


def deactivate_prompts(session, agent_type: str, prompt_key: str):
    """Deactivate all versions of a prompt."""
    query = """
        UPDATE prompt.prompts
        SET is_active = false, updated_at = NOW()
        WHERE agent_type = :agent_type AND prompt_key = :prompt_key AND is_active = true
    """
    session.execute(text(query), {'agent_type': agent_type, 'prompt_key': prompt_key})


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
    query = "SELECT user_id FROM auth.users WHERE is_admin = true LIMIT 1"
    result = session.execute(text(query))
    row = result.fetchone()

    if row:
        return str(row.user_id)

    query = "SELECT user_id FROM auth.users LIMIT 1"
    result = session.execute(text(query))
    row = result.fetchone()

    if row:
        return str(row.user_id)

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
    stats = {'created': 0, 'updated': 0, 'unchanged': 0, 'errors': 0}

    if not dry_run:
        created_by = get_or_create_system_user(local_session)
    else:
        created_by = None

    for prompt in prod_prompts:
        agent_type = prompt['agent_type']
        prompt_key = prompt['prompt_key']

        try:
            existing = get_existing_prompt(local_session, agent_type, prompt_key)

            if existing:
                if existing['prompt_text'].strip() == prompt['prompt_text'].strip():
                    logger.info(f"  ⏭️  {agent_type}/{prompt_key} - unchanged")
                    stats['unchanged'] += 1
                    continue

                if dry_run:
                    logger.info(f"  🔄 {agent_type}/{prompt_key} - would update (v{existing['version_number']} -> v{existing['version_number'] + 1})")
                    stats['updated'] += 1
                else:
                    max_version = get_max_version(local_session, agent_type, prompt_key)
                    new_version = max_version + 1
                    deactivate_prompts(local_session, agent_type, prompt_key)
                    insert_prompt(local_session, prompt, new_version, created_by)
                    logger.info(f"  🔄 {agent_type}/{prompt_key} - updated to v{new_version}")
                    stats['updated'] += 1
            else:
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


# =============================================================================
# SQL Backup Functions
# =============================================================================

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
    """Generate SQL UPSERT statement that handles conflicts."""
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


def write_individual_prompt_files(prompts: List[Dict[str, Any]]) -> List[Path]:
    """Write each prompt to its own file for version control."""
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
-- Source: production
-- Updated: {datetime.now().isoformat()}

{generate_upsert_sql(prompt)}
""")

        files_written.append(filepath)

    return files_written


# =============================================================================
# Git Functions
# =============================================================================

def run_git(*args, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the repo root."""
    cmd = ['git', '-C', str(REPO_ROOT)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check
    )


def get_current_branch() -> str:
    """Get the current git branch name."""
    result = run_git('branch', '--show-current')
    return result.stdout.strip()


def has_uncommitted_changes() -> bool:
    """Check if there are uncommitted changes."""
    result = run_git('status', '--porcelain')
    return bool(result.stdout.strip())


def stash_changes() -> bool:
    """Stash current changes. Returns True if anything was stashed."""
    result = run_git('stash', 'push', '-m', 'Auto-stash for prompt sync')
    return 'No local changes' not in result.stdout


def pop_stash():
    """Pop the most recent stash."""
    run_git('stash', 'pop', check=False)


def create_and_checkout_branch(branch_name: str):
    """Create and checkout a new branch."""
    run_git('checkout', '-b', branch_name)


def checkout_branch(branch_name: str):
    """Checkout an existing branch."""
    run_git('checkout', branch_name)


def add_files(patterns: List[str]):
    """Add files to git staging."""
    for pattern in patterns:
        run_git('add', pattern, check=False)


def commit_changes(message: str) -> bool:
    """Commit staged changes. Returns True if commit was made."""
    result = run_git('commit', '-m', message, check=False)
    return result.returncode == 0


def push_branch(branch_name: str, retries: int = 4) -> bool:
    """Push branch to origin with retries."""
    import time

    delays = [2, 4, 8, 16]
    for attempt in range(retries):
        result = run_git('push', '-u', 'origin', branch_name, check=False)
        if result.returncode == 0:
            return True

        if attempt < retries - 1:
            delay = delays[attempt]
            logger.warning(f"   Push failed, retrying in {delay}s... (attempt {attempt + 1}/{retries})")
            time.sleep(delay)

    return False


def get_backup_file_changes() -> List[str]:
    """Get list of changed backup files."""
    result = run_git('status', '--porcelain', str(BACKUP_DIR.relative_to(REPO_ROOT)))
    changed = []
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            # Format is "XY filename" where XY is status
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                changed.append(parts[1].strip())
    return changed


def generate_branch_name() -> str:
    """Generate a unique branch name for the prompt sync."""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    return f"chore/prompt-sync-{timestamp}"


# =============================================================================
# Main Flow
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Sync production prompts to local database and update SQL backups"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be synced without making changes'
    )
    parser.add_argument(
        '--no-git',
        action='store_true',
        help='Skip git operations (just sync DB and generate backups)'
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

    # Sync to local database
    logger.info("\n📤 Syncing to local database...")

    try:
        with LocalSession() as local_session:
            stats = sync_prompts(prod_prompts, local_session, args.dry_run)
            if not args.dry_run:
                local_session.commit()
    except Exception as e:
        logger.error(f"❌ Failed to sync prompts: {e}")
        sys.exit(1)

    logger.info("\n" + "=" * 50)
    logger.info("📊 Database Sync Summary:")
    logger.info(f"   Created:   {stats['created']}")
    logger.info(f"   Updated:   {stats['updated']}")
    logger.info(f"   Unchanged: {stats['unchanged']}")
    logger.info(f"   Errors:    {stats['errors']}")

    if args.dry_run:
        logger.info("\n   (DRY RUN - no changes were made)")
        sys.exit(0)

    # Generate SQL backup files
    logger.info("\n💾 Generating SQL backup files...")

    try:
        files_written = write_individual_prompt_files(prod_prompts)
        logger.info(f"   Generated {len(files_written)} individual prompt files")
    except Exception as e:
        logger.error(f"❌ Failed to generate backup files: {e}")
        sys.exit(1)

    if args.no_git:
        logger.info("\n✅ Sync complete (--no-git: skipping git operations)")
        sys.exit(0)

    # Check for changes to backup files
    logger.info("\n🔍 Checking for backup file changes...")

    changed_files = get_backup_file_changes()
    if not changed_files:
        logger.info("   No changes to backup files")
        logger.info("\n✅ Sync complete!")
        sys.exit(0)

    logger.info(f"   Found {len(changed_files)} changed files")

    # Save current state
    original_branch = get_current_branch()
    logger.info(f"\n📌 Current branch: {original_branch}")

    stashed = False
    if has_uncommitted_changes():
        logger.info("   Stashing uncommitted changes...")
        stashed = stash_changes()

    # Create new branch for the update
    sync_branch = generate_branch_name()
    logger.info(f"\n🌿 Creating branch: {sync_branch}")

    try:
        create_and_checkout_branch(sync_branch)

        # Stage and commit the backup files
        logger.info("   Staging backup files...")
        add_files([str(BACKUP_DIR.relative_to(REPO_ROOT))])

        logger.info("   Committing changes...")
        commit_message = f"chore: Update prompt SQL backups from production\n\nSynced {len(prod_prompts)} active prompts from production database.\n\nChanges:\n- Created: {stats['created']}\n- Updated: {stats['updated']}\n- Unchanged: {stats['unchanged']}"

        if commit_changes(commit_message):
            logger.info("   ✅ Changes committed")

            # Push the branch
            logger.info(f"\n📤 Pushing branch {sync_branch}...")
            if push_branch(sync_branch):
                logger.info("   ✅ Branch pushed successfully")
            else:
                logger.error("   ❌ Failed to push branch after retries")
        else:
            logger.info("   No changes to commit")

    except Exception as e:
        logger.error(f"❌ Git operation failed: {e}")

    finally:
        # Return to original branch
        logger.info(f"\n🔙 Returning to original branch: {original_branch}")
        checkout_branch(original_branch)

        if stashed:
            logger.info("   Restoring stashed changes...")
            pop_stash()

    logger.info("\n" + "=" * 50)
    logger.info("✅ Sync complete!")
    logger.info(f"   Prompt backup branch: {sync_branch}")
    logger.info(f"   Create PR at: https://github.com/Boundless-Studios/gaia-free/compare/{sync_branch}")

    if stats['errors'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
