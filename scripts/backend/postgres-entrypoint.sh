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

# If database is already initialized and POSTGRES_PASSWORD is set, update the password
# This ensures password changes in secrets are applied to existing databases
PGDATA="${PGDATA:-/var/lib/postgresql/data/pgdata}"
if [ -d "$PGDATA" ] && [ -n "$POSTGRES_PASSWORD" ]; then
    echo "Database already initialized, will update password after startup..."

    # Start postgres in background, wait for it to be ready, then update password
    docker-entrypoint.sh "$@" &
    PG_PID=$!

    # Wait for postgres to be ready (up to 30 seconds)
    for i in $(seq 1 30); do
        if pg_isready -U "${POSTGRES_USER:-gaia}" -d "${POSTGRES_DB:-gaia}" 2>/dev/null; then
            echo "PostgreSQL is ready, updating password..."
            psql -U "${POSTGRES_USER:-gaia}" -d "${POSTGRES_DB:-gaia}" -c "ALTER USER ${POSTGRES_USER:-gaia} PASSWORD '${POSTGRES_PASSWORD}';" 2>/dev/null || true
            echo "✓ Password updated"
            break
        fi
        sleep 1
    done

    # Wait for postgres process
    wait $PG_PID
else
    # Execute the original postgres entrypoint
    exec docker-entrypoint.sh "$@"
fi
