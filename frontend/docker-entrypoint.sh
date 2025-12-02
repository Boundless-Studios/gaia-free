#!/bin/sh
set -euo pipefail

TEMPLATE=/etc/nginx/conf.d/default.conf.template
OUTPUT=/etc/nginx/conf.d/default.conf

PORT="${PORT:-3000}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"

# Derive backend host for SNI/Host headers (avoids regex in nginx config)
# shellcheck disable=SC2001
BACKEND_SCHEME="$(printf '%s' "${BACKEND_URL}" | sed -E 's~^([a-zA-Z][a-zA-Z0-9+.-]*).*$~\1~')"
if [ -z "${BACKEND_SCHEME}" ] || [ "${BACKEND_SCHEME}" = "${BACKEND_URL}" ]; then
    BACKEND_SCHEME="http"
fi
BACKEND_HOST="$(printf '%s' "${BACKEND_URL}" | sed -E 's~^[a-zA-Z][a-zA-Z0-9+.-]*://([^/:]+).*~\1~')"
if [ -z "${BACKEND_HOST}" ] || [ "${BACKEND_HOST}" = "${BACKEND_URL}" ]; then
    BACKEND_HOST="$(printf '%s' "${BACKEND_URL}" | cut -d/ -f1)"
fi

# Avoid accidentally passing an empty host which breaks TLS handshakes
if [ -z "${BACKEND_HOST}" ]; then
    echo "Fatal: unable to derive BACKEND_HOST from BACKEND_URL='${BACKEND_URL}'" >&2
    exit 1
fi

echo "Starting frontend proxy with BACKEND_URL='${BACKEND_URL}', BACKEND_SCHEME='${BACKEND_SCHEME}', BACKEND_HOST='${BACKEND_HOST}'"

# Determine STT proxy target.
# In Cloud Run (K_SERVICE present) default to disabling the /stt route unless explicitly set.
# For local Docker usage fall back to host.docker.internal to mirror previous behaviour.
STT_URL_VALUE="${STT_URL:-}"
STT_SCHEME=""
STT_HOST=""
if [ -z "$STT_URL_VALUE" ]; then
    if [ -n "${K_SERVICE:-}" ]; then
        STT_URL_VALUE=""
    else
        STT_URL_VALUE="http://host.docker.internal:8001"
    fi
fi

# Avoid Cloud Run crashes if someone sets host.docker.internal explicitly.
if [ -n "${K_SERVICE:-}" ] && printf '%s' "$STT_URL_VALUE" | grep -q 'host\.docker\.internal'; then
    STT_URL_VALUE=""
fi

if [ -n "$STT_URL_VALUE" ]; then
    STT_SCHEME="$(printf '%s' "${STT_URL_VALUE}" | sed -E 's~^([a-zA-Z][a-zA-Z0-9+.-]*).*$~\1~')"
    if [ -z "${STT_SCHEME}" ] || [ "${STT_SCHEME}" = "${STT_URL_VALUE}" ]; then
        STT_SCHEME="http"
    fi
    STT_HOST="$(printf '%s' "${STT_URL_VALUE}" | sed -E 's~^[a-zA-Z][a-zA-Z0-9+.-]*://([^/:]+).*~\1~')"
    if [ -z "${STT_HOST}" ] || [ "${STT_HOST}" = "${STT_URL_VALUE}" ]; then
        STT_HOST="$(printf '%s' "${STT_URL_VALUE}" | cut -d/ -f1)"
    fi
fi

if [ -n "$STT_URL_VALUE" ]; then
    echo "Enabling STT proxy to '${STT_URL_VALUE}' (scheme='${STT_SCHEME}', host='${STT_HOST}')"
else
    echo "STT proxy disabled"
fi

export PORT BACKEND_URL BACKEND_SCHEME BACKEND_HOST STT_URL="$STT_URL_VALUE" STT_SCHEME STT_HOST

envsubst '${PORT} ${BACKEND_URL} ${BACKEND_SCHEME} ${BACKEND_HOST} ${STT_URL} ${STT_SCHEME} ${STT_HOST}' < "$TEMPLATE" > /tmp/default.conf

if [ -z "$STT_URL_VALUE" ]; then
    awk 'BEGIN {skip=0} /# STT_PROXY_START/ {skip=1; next} /# STT_PROXY_END/ {skip=0; next} skip==0 {print}' /tmp/default.conf > "$OUTPUT"
else
    mv /tmp/default.conf "$OUTPUT"
fi

exec nginx -g 'daemon off;'
