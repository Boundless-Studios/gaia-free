# GEMINI.md

This file provides guidance for interacting with the Gemini model within this repository.

## General Approach
1. Understand the user's request and context.
2. Explore relevant parts of the codebase using available tools.
3. Formulate a plan for implementation, bug fixing, or feature addition.
4. Execute the plan, making changes incrementally.
5. Create or update tests to validate changes.
6. Verify changes by running actual code and tests.
7. **Commit working changes** with descriptive commit messages after testing confirms functionality.
8. Continuously update the user with progress and any new TODOs.

## Development Guidelines

### Branching & PRs
- **Before starting new features**: Always check `git status` for uncommitted changes.
  - If uncommitted files exist, ask the user whether to:
    - Commit the existing changes first, OR
    - Create a new branch and continue, OR
    - Stash the changes
  - Never proceed without explicit user direction when there are uncommitted changes.
- Create new branches off of `main` (ensure `main` is up to date).
- Avoid stacked branches where possible.
- Create a PR once complete for every branch.

### Git Commit Workflow
- **Test before committing**: Always run tests and verify functionality works as expected.
- **Propose Commits to User**: After successful testing, inform the user about the changes. Propose a commit by first running `git status` and `git diff` to show the user the changes, then ask if they want to `git add` the changes and commit them. Do not run `git add` or `git commit` without user confirmation.
- **Descriptive commit messages**: Use clear, descriptive commit messages that explain:
  - What was changed (features, fixes, refactors).
  - Why it was changed (purpose, problem solved).
  - Format: `<type>: <description>` (e.g., "feat: Integrate Gemini for text generation").
  - Types: feat, fix, refactor, test, docs, chore, perf, style.
- **Atomic commits**: Each commit should represent a logical unit of work.
- **Commit frequency**: Commit working code frequently rather than waiting for large batches.

## Testing & Validation
- **IMPORTANT**: Always test code inside Docker containers, not locally - dependencies are properly installed there.
- Run tests using: `python3 gaia_launcher.py test YOUR_TEST_FILE` (for backend) or `npm run test` (for frontend).
- Ensure changes compile on both frontend and backend.
- Check logs at `backend/src/logs/gaia_all.log` for errors.
- When adding dependencies, ensure they're properly installed in Docker images.
- Tests should validate correct operation and fail if wrong behavior is detected.

## File Organization
- Documentation goes in `docs/` folder.
- Frontend code is in `frontend/src/`.
- Backend code is in `backend/src/`.
- Shared services such as authentication, persistence, and campaign storage are broken out into the top-level `auth/`, `db/`, and `campaign_storage/` packages.

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

## Task Management and Persistence

- **Evaluate Task Complexity**: Before starting any task, evaluate its complexity. For medium to large tasks, break it down into smaller, manageable subtasks.
- **Use a TODO List**: For any task that requires more than a few steps, create a TODO list. This helps in tracking progress and ensures that all parts of the task are completed.
- **Be Persistent**: Once a task is started, be persistent in completing it. Go through all the items in the TODO list until the task is fully resolved.
- **Do Not Stop Prematurely**: Do not stop working on a task until it is fully completed, or you are explicitly asked to stop. If you encounter a problem, try to solve it or ask for help, but do not give up.