# Prompt Backups

This directory contains SQL backup files for versioned agent prompts.

## Generating Backups

Use the `backup_prompts_to_sql.py` script:

```bash
# Backup from local database (default)
python scripts/backend/backup_prompts_to_sql.py

# Backup from production database
python scripts/backend/backup_prompts_to_sql.py --source production

# Include all versions (not just active)
python scripts/backend/backup_prompts_to_sql.py --all-versions

# Generate individual files for version control
python scripts/backend/backup_prompts_to_sql.py --individual
```

## Restoring Backups

Apply a backup to a database:

```bash
# Apply latest backup
psql -d gaia -f db/prompt_backups/latest.sql

# Apply specific backup
psql -d gaia -f db/prompt_backups/prompts_backup_production_20250101_120000.sql
```

## File Structure

```
prompt_backups/
├── .gitignore                    # Ignores generated SQL files
├── README.md                     # This file
├── latest.sql -> ...             # Symlink to most recent backup
├── prompts_backup_*.sql          # Full backup files
└── individual/                   # Individual prompt files (with --individual)
    ├── dm_runner/
    │   ├── streaming_dm__system_prompt.sql
    │   └── ...
    └── scene_agent/
        └── ...
```

## Note

Generated SQL files are gitignored by default as they may contain sensitive prompt content.
If you want to version control specific prompts, use the `--individual` flag and
selectively add the files you want to track.
