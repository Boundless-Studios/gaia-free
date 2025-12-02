
@sessions/CLAUDE.sessions.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General Approach
1. Explore the codebase
2. Make a plan
3. Execute your plan
4. Create or update tests based on changes
5. Test your changes by running the actual code
6. **Commit working changes** with descriptive commit messages after testing confirms functionality
7. When working on a current_task make sure you always update that task with your changes and TODO lists

## Development Guidelines

### Branching & PRs
- **Before starting new features**: Always check `git status` for uncommitted changes
  - If uncommitted files exist, ask the user whether to:
    - Commit the existing changes first, OR
    - Create a new branch and continue, OR
    - Stash the changes
  - Never proceed without explicit user direction when there are uncommitted changes
- Create new branches off of main (ensure main is up to date)
- Avoid stacked branches where possible
- Create a PR once complete for every branch

### Git Commit Workflow
- **Test before committing**: Always run tests and verify functionality works as expected
- **Propose Commits to User**: After successful testing, inform the user about the changes. Propose a commit by first running `git status` and `git diff` to show the user the changes, then ask if they want to `git add` the changes and commit them. Do not run `git add` or `git commit` without user confirmation.
- **Descriptive commit messages**: Use clear, descriptive commit messages that explain:
  - What was changed (features, fixes, refactors)
  - Why it was changed (purpose, problem solved)
  - Format: `<type>: <description>` (e.g., "feat: Add portrait generation with retry logic")
  - Types: feat, fix, refactor, test, docs, chore, perf, style
- **Atomic commits**: Each commit should represent a logical unit of work
- **Commit frequency**: Commit working code frequently rather than waiting for large batches

### Testing & Validation
- **IMPORTANT**: Always test code inside Docker containers, not locally - dependencies are properly installed there
- Run tests using: `python3 gaia_launcher.py test YOUR_TEST_FILE`
- Ensure changes compile on both frontend and backend
- Check logs at `backend/src/logs/gaia_all.log` for errors
- When adding dependencies, ensure they're properly installed in Docker images
- Don't catch exceptions in test
- Don't build special logic in tests for testing, depend on the actual constructs in code to handle logic, tests should be written to verify outcomes, not implement custom logic to make the tests conform to observed behavior
- Tests should not be tautological but should actually validate correct operation. Test should not test a wrong behavior for the sake of passing when the wrong behavior happens. Instead, they should fail if the wrong behavior is detected or be written to catch and process an appropriate exception in a bad case. 

### File Organization
- Documentation goes in `docs/` folder
- Test scripts go in `scripts/claude_helpers/`
- Frontend code is in `src/frontend/`
- Backend code is in `src/backend`

## Docker-First Workflow

**CRITICAL**: Never run npm or python commands directly. Always use Docker commands.

### Container Management

1. **Check if containers are running**:
   ```bash
   docker ps
   ```

2. **Restart running containers** (apply changes without rebuilding):
   ```bash
   docker restart gaia-frontend-dev
   docker restart gaia-backend-dev
   ```

3. **Launch containers if not running**:
   ```bash
   # Frontend development
   docker compose --profile dev up frontend-dev -d

   # Backend development
   docker compose --profile dev up backend-dev -d

   # Both
   docker compose --profile dev up -d
   ```

4. **View logs to validate changes**:
   ```bash
   # Tail logs (follow new output)
   docker logs -f gaia-frontend-dev
   docker logs -f gaia-backend-dev

   # Last 50 lines
   docker logs --tail 50 gaia-frontend-dev
   docker logs --tail 50 gaia-backend-dev
   ```

### Testing Frontend Changes
```bash
# Build frontend in container
docker exec gaia-frontend-dev npm run build

# Or restart to apply changes
docker restart gaia-frontend-dev

# Check logs for errors
docker logs --tail 100 gaia-frontend-dev
```

### Testing Backend Changes
```bash
# Run tests in container
docker exec gaia-backend-dev python3 gaia_launcher.py test YOUR_TEST_FILE

# Restart to apply changes
docker restart gaia-backend-dev

# Check logs for errors
docker logs --tail 100 gaia-backend-dev
```

## Quick Start Commands

```bash
# Start all development services
docker compose --profile dev up -d

# Check system health
curl http://localhost:8000/api/health

# View logs
docker logs -f gaia-backend-dev
docker logs -f gaia-frontend-dev
```

## Deployment

### Quick Reference

```bash
# Deploy to staging (recommended for testing)
./scripts/deploy_staging.sh --local

# Deploy to production (from main branch only)
./scripts/deploy_production.sh --local

# Force pre-generation during deployment
./scripts/deploy_production.sh --local --force-pregen
```

### Deployment Scripts

The deployment scripts trigger GitHub Actions workflows that build and deploy to Google Cloud Run.

**Script Options:**
- `--local` - **Recommended**: Triggers deployment from your current branch/commit
- `--force-pregen` - Regenerates pre-generated campaigns/characters during deployment
- Without `--local` - Triggers deployment from remote main/staging branch (less common)

**How it works:**
1. Script triggers GitHub Actions workflow via `gh workflow run`
2. GitHub Actions builds Docker images and pushes to Artifact Registry
3. Secrets are decrypted and synced to GCP Secret Manager
4. Cloud Run services are updated with new images and secrets
5. Health checks verify deployment success

**Deployment Targets:**
- **Staging**: Uses `secrets-management-cleanup` branch, deploys to `gaia-*-stg` services
- **Production**: Uses `main` branch, deploys to `gaia-*-prod` services

### Secrets Management

Secrets are automatically synced during deployment:

1. `secrets/.secrets.env` is decrypted using `SOPS_AGE_KEY` (from GitHub Secrets)
2. Secrets matching patterns (`*_PASSWORD`, `*_KEY`, `*_USER`, `*_HOST`, etc.) are uploaded to GCP Secret Manager
3. Cloud Run services mount secrets as environment variables

See [secrets/README.md](secrets/README.md) for detailed secrets management documentation.

**Common Deployment Issues:**

- **Missing secrets in Cloud Run**: Check if secret name matches a pattern (see secrets/README.md)
- **Deployment fails**: Check GitHub Actions logs: `gh run list --limit 5`
- **Health check fails**: Check Cloud Run logs: `gcloud logging read ...`

**Pre-Generation Behavior:**
- Non-blocking by default - deployment succeeds even if pre-generation fails
- Content is loaded from GCS bucket before attempting generation
- Uses Parasail-only model fallback to avoid API provider issues
- See `backend/CLAUDE.md` for detailed pre-generation documentation

@CLAUDE.sessions.md
