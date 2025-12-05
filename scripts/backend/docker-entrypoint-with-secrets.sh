#!/bin/bash
# Docker entrypoint that decrypts SOPS secrets before starting the application
set -e

echo "=== Gaia Backend Startup with Secrets Decryption ==="

# Check if SOPS key file is available
if [ -n "$SOPS_AGE_KEY_FILE" ] && [ -f "$SOPS_AGE_KEY_FILE" ]; then
    echo "✓ Using SOPS AGE key file: $SOPS_AGE_KEY_FILE"
    # SOPS will use SOPS_AGE_KEY_FILE directly - no need to export contents
else
    echo "WARNING: No SOPS key found. Secrets will not be decrypted."
    echo "To enable secrets decryption:"
    echo "  - Mount AGE key file and set SOPS_AGE_KEY_FILE"
fi

# Path to encrypted secrets (configurable via env var)
ENCRYPTED_SECRETS="${ENCRYPTED_SECRETS_PATH:-/home/gaia/secrets/.secrets.env}"
if [ -f "$ENCRYPTED_SECRETS" ]; then
    echo "Decrypting secrets from $ENCRYPTED_SECRETS..."

    # Decrypt and export each secret as environment variable
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

            # Also write to a persistent location for uvicorn workers
            # (uvicorn --reload spawns workers that don't inherit env vars)
            PERSISTENT_SECRETS="/tmp/.decrypted_secrets.env"
            cp "$TEMP_SECRETS" "$PERSISTENT_SECRETS"
            chmod 600 "$PERSISTENT_SECRETS"
            export DECRYPTED_SECRETS_FILE="$PERSISTENT_SECRETS"

            echo "✓ Secrets decrypted and loaded into environment"
        else
            echo "ERROR: Failed to decrypt secrets. Check SOPS_AGE_KEY_FILE points to a valid key."
            exit 1
        fi
    else
        echo "ERROR: sops not found in container"
        exit 1
    fi
else
    echo "WARNING: No encrypted secrets file found at $ENCRYPTED_SECRETS"
    echo "Continuing without decrypted secrets..."
fi

# Function to handle shutdown gracefully
cleanup() {
    echo "Shutting down services..."
    if [ ! -z "$CLOUDFLARED_PID" ]; then
        kill $CLOUDFLARED_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start Cloudflare Tunnel if token is provided and not explicitly disabled
if [ "$DISABLE_CLOUDFLARE_TUNNEL" = "true" ]; then
    echo "Cloudflare Tunnel disabled via DISABLE_CLOUDFLARE_TUNNEL flag"
elif [ ! -z "$CLOUDFLARE_TUNNEL" ]; then
    echo "Starting Cloudflare Tunnel..."
    cloudflared tunnel --no-autoupdate run --token $CLOUDFLARE_TUNNEL &
    CLOUDFLARED_PID=$!
    echo "Cloudflare Tunnel started with PID $CLOUDFLARED_PID"

    # Give tunnel time to establish
    sleep 3
else
    echo "No CLOUDFLARE_TUNNEL token provided, skipping tunnel setup"
fi

# Execute the original command
exec "$@"
