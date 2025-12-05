#!/bin/bash
# PostgreSQL entrypoint that decrypts SOPS secrets before starting
set -e

echo "=== PostgreSQL Startup with Secrets Decryption ==="

# Check if SOPS key is available
if [ -n "$SOPS_AGE_KEY_FILE" ] && [ -f "$SOPS_AGE_KEY_FILE" ]; then
    export SOPS_AGE_KEY=$(cat "$SOPS_AGE_KEY_FILE")
    echo "✓ Loaded SOPS AGE key from $SOPS_AGE_KEY_FILE"
elif [ -z "$SOPS_AGE_KEY" ]; then
    echo "WARNING: No SOPS key found. Secrets will not be decrypted."
fi

# Path to encrypted secrets
ENCRYPTED_SECRETS="${ENCRYPTED_SECRETS_PATH:-/secrets/.secrets.env}"
if [ -f "$ENCRYPTED_SECRETS" ]; then
    echo "Decrypting secrets from $ENCRYPTED_SECRETS..."

    if command -v sops &> /dev/null; then
        # Create temporary file for decrypted secrets
        TEMP_SECRETS=$(mktemp)
        trap "rm -f $TEMP_SECRETS" EXIT

        # Decrypt to temp file
        if sops -d "$ENCRYPTED_SECRETS" > "$TEMP_SECRETS" 2>/dev/null; then
            # Source the secrets into environment
            set -a  # Auto-export all variables
            source "$TEMP_SECRETS"
            set +a
            echo "✓ Secrets decrypted and loaded into environment"
        else
            echo "ERROR: Failed to decrypt secrets. Check SOPS_AGE_KEY is set correctly."
            exit 1
        fi
    else
        echo "ERROR: sops not found in container"
        exit 1
    fi
else
    echo "WARNING: No encrypted secrets file found at $ENCRYPTED_SECRETS"
fi

# Execute the original postgres entrypoint
exec docker-entrypoint.sh "$@"
