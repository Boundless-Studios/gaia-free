#!/bin/bash
# Helper script to run commands in Docker with decrypted secrets
#
# Usage:
#   ./scripts/backend/run-with-secrets.sh python3 /home/gaia/private_scripts/pregenerate_content.py
#   ./scripts/backend/run-with-secrets.sh pytest /home/gaia/tests/
#
# This script:
#   1. Sources the secrets entrypoint to decrypt SOPS secrets
#   2. Runs the specified command with those secrets available as environment variables

set -e

CONTAINER_NAME="${CONTAINER_NAME:-gaia-backend-dev}"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <command> [args...]"
    echo ""
    echo "Examples:"
    echo "  $0 python3 /home/gaia/private_scripts/pregenerate_content.py"
    echo "  $0 pytest /home/gaia/tests/"
    echo "  $0 python3 -c 'import os; print(os.environ.get(\"PARASAIL_API_KEY\", \"not set\")[:10])'"
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Error: Container '$CONTAINER_NAME' is not running."
    echo "Start it with: docker compose -f backend/docker-compose.yml up dev -d"
    exit 1
fi

# Run the command with secrets
# Note: We source the entrypoint script which decrypts secrets into env vars
# DISABLE_CLOUDFLARE_TUNNEL prevents the tunnel from starting
docker exec "$CONTAINER_NAME" bash -c "
    source /home/gaia/scripts/backend/docker-entrypoint-with-secrets.sh 2>/dev/null
    exec \"\$@\"
" -- "$@"
