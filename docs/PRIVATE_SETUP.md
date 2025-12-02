# Private Repository Setup

This document explains how the Gaia repository is split between public and private components.

## Overview

The Gaia project uses a **git subtree** to manage private code that should not be included in the public open-source repository. This allows:

- **Public contributors** to work with the open-source infrastructure, mechanics, and API code
- **Boundless Studios team** to access proprietary AI agents, prompts, and production configuration

## Repository Structure

```
gaia-free/                              # Public repository (github.com/Boundless-Studios/gaia-free)
├── backend/src/
│   ├── gaia/                           # Public backend code
│   └── gaia_private/                   # ← Git subtree (from gaia-private repo)
│       ├── __init__.py
│       ├── agents/                     # AI agents (DM, combat, scene)
│       ├── extraction/                 # Character extraction AI
│       ├── models/                     # Private data models
│       ├── prompts/                    # Prompt templates
│       ├── _config/                    # Real configuration files
│       ├── _secrets/                   # SOPS-encrypted secrets
│       ├── _infra/                     # Terraform configs
│       └── _db/migrations/             # Private DB migrations
├── config/
│   ├── *.env.example                   # Public placeholders
│   └── *.env -> ../backend/src/gaia_private/_config/*.env  # Symlinks (after setup)
├── secrets/
│   └── .secrets.env -> ../backend/src/gaia_private/_secrets/.secrets.env
└── ...
```

## For Public Contributors

The public repository works without the private code for:

- Running the backend infrastructure
- Working on game mechanics and combat engine
- Developing API routes
- Building the frontend

Some features (AI DM, character generation, etc.) require the private code to function.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Boundless-Studios/gaia-free.git
   cd gaia-free
   ```

2. Copy example config files:
   ```bash
   cp config/cloudrun.dev.env.example config/cloudrun.dev.env
   cp config/gcp.env.example config/gcp.env
   # Edit with your own values
   ```

3. Follow the main README for development setup.

## For Boundless Studios Team

Team members with access to `gaia-private` can set up the full development environment.

### Initial Setup

```bash
# Clone the public repo
git clone git@github.com:Boundless-Studios/gaia-free.git
cd gaia-free

# Set up private subtree (requires gaia-private repo access)
make setup-private
```

This will:
1. Add the `gaia-private` remote
2. Pull the private subtree into `backend/src/gaia_private/`
3. Create symlinks for config files, secrets, and terraform configs

### Updating Private Code

```bash
# Pull latest from gaia-private
make update-private
```

### Pushing Changes to Private Repo

If you modify files in `backend/src/gaia_private/`:

```bash
# Push changes back to gaia-private
make push-private
```

### Available Commands

| Command | Description |
|---------|-------------|
| `make setup-private` | Initial setup of private subtree |
| `make update-private` | Pull latest changes from gaia-private |
| `make push-private` | Push changes to gaia-private |
| `make check-private` | Verify private setup is complete |

## What's Private vs Public

### Private (in `backend/src/gaia_private/`)

- `agents/` - AI agent definitions and orchestration
- `extraction/` - Character extraction AI
- `prompts/` - Prompt templates
- `_config/` - Production configuration (real project IDs, domains)
- `_secrets/` - SOPS-encrypted secrets
- `_infra/` - Infrastructure configuration (Terraform/OpenTofu)
- `_db/migrations/` - Database migrations with real user emails

### Public (in gaia-free)

- `backend/src/gaia/` - Infrastructure (audio, image, LLM, storage services)
- `backend/src/gaia/mechanics/` - Game mechanics (combat engine, character management)
- `backend/src/gaia/api/` - API routes and models
- `frontend/` - Frontend code
- `config/*.example` - Example configuration files
- `docs/` - Documentation (sanitized)

## Symlinks After Setup

After running `make setup-private`, these symlinks are created:

```
config/gcp.env           → ../backend/src/gaia_private/_config/gcp.env
config/cloudrun.*.env    → ../backend/src/gaia_private/_config/cloudrun.*.env
secrets/.secrets.env     → ../backend/src/gaia_private/_secrets/.secrets.env
infra/opentofu/gcp/terraform.tfvars → ../../../../backend/src/gaia_private/_infra/opentofu/gcp/terraform.tfvars
db/migrations/06-*.sql   → ../../backend/src/gaia_private/_db/migrations/06-*.sql
db/migrations/07-*.sql   → ../../backend/src/gaia_private/_db/migrations/07-*.sql
```

## Security Notes

- Never commit real secrets to either repository
- Use SOPS encryption for sensitive values in `_secrets/`
- The public repo should only contain `.example` config files
- Real email addresses should only exist in gaia-private

## Troubleshooting

### "Cannot access gaia-private"

Ensure you have SSH access to the Boundless-Studios organization:
```bash
ssh -T git@github.com
```

### "Subtree conflicts"

If you have conflicts when pulling:
```bash
git subtree pull --prefix=backend/src/gaia_private gaia-private main --squash
# Resolve conflicts manually, then commit
```

### "Directory already exists"

If `backend/src/gaia_private` exists (e.g., from the original Gaia repo):
```bash
# The setup script will prompt to remove it
make setup-private

# Or manually:
rm -rf backend/src/gaia_private
make setup-private
```
