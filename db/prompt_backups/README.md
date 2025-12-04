# Prompt Backups

This directory contains SQL backup files for versioned agent prompts.

## Quick Start: Sync from Production

The primary workflow is a single command that:
1. Pulls active prompts from production database
2. Syncs them to your local database
3. Generates SQL backup files
4. Creates a branch, commits, and pushes the changes
5. Returns you to your original branch

```bash
python scripts/backend/sync_prompts_from_production.py
```

### Options

```bash
# Dry run - preview what would be synced
python scripts/backend/sync_prompts_from_production.py --dry-run

# Skip git operations (just sync DB and generate files)
python scripts/backend/sync_prompts_from_production.py --no-git

# Sync specific agent types only
python scripts/backend/sync_prompts_from_production.py --agent-type streaming_dm
```

### Environment Variables

Set one of these to connect to production:

```bash
# Option 1: Direct connection string
export PRODUCTION_DATABASE_URL="postgresql://user:pass@host:5432/db"

# Option 2: Cloud SQL Proxy components
export PROD_DB_INSTANCE_CONNECTION_NAME="project:region:instance"
export PROD_POSTGRES_USER="gaia"
export PROD_DB_PASSWORD="your-password"
export PROD_POSTGRES_DB="gaia"
```

## Standalone Backup Utility

For generating backups without the full sync workflow:

```bash
# Backup from local database
python scripts/backend/backup_prompts_to_sql.py

# Backup from production
python scripts/backend/backup_prompts_to_sql.py --source production

# Include all versions (not just active)
python scripts/backend/backup_prompts_to_sql.py --all-versions
```

## Restoring Backups

Apply individual prompt files to a database:

```bash
# Apply a specific prompt
psql -d gaia -f db/prompt_backups/individual/dm_runner/streaming_dm__system_prompt.sql

# Apply all prompts in a category
for f in db/prompt_backups/individual/dm_runner/*.sql; do psql -d gaia -f "$f"; done
```

## File Structure

```
prompt_backups/
├── README.md                     # This file
├── .gitignore                    # Ignores generated SQL files
└── individual/                   # Individual prompt files
    ├── dm_runner/
    │   ├── streaming_dm__system_prompt.sql
    │   └── ...
    ├── scene_agent/
    │   └── ...
    └── analyzer/
        └── ...
```

## Workflow

The typical workflow for editing prompts:

1. **Sync from production** to get the latest prompts:
   ```bash
   python scripts/backend/sync_prompts_from_production.py
   ```

2. **Edit prompts locally** using the admin UI or directly in the database

3. **Push changes to production** (via deployment or direct DB update)

4. **Sync again** to capture the changes in SQL backups

## Note

Generated SQL files are gitignored by default as they may contain sensitive prompt content.
The sync script creates a separate branch for backup updates to keep your working branch clean.
