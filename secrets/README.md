# Secrets Directory

This directory contains encrypted secrets for the Gaia application.

## For Public Contributors

You'll need to create your own secrets file for local development:

```bash
cp secrets.env.example .secrets.env
# Edit .secrets.env with your own API keys
```

## For Boundless Studios Team

Run `make setup-private` to set up the private subtree, which will create
a symlink to the encrypted secrets file.

## Required Secrets

See `secrets.env.example` for the list of required environment variables.
