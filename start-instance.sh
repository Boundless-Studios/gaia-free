#!/bin/bash
# start-instance.sh - Helper script for starting Gaia instances
#
# Usage:
#   ./start-instance.sh          # Start default instance (instance 1)
#   ./start-instance.sh 2        # Start instance 2
#   ./start-instance.sh 3 gpu    # Start instance 3 with GPU profile
#   ./start-instance.sh 1 prod   # Start instance 1 in production mode
#
# Environment:
#   GAIA_NO_BUILD=1              # Skip build step
#   GAIA_SHOW_LOGS=1             # Show logs in foreground

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    echo -e "${2}${1}${NC}"
}

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Parse arguments
INSTANCE=${1:-1}
PROFILE=${2:-dev}

# Validate instance number
if ! [[ "$INSTANCE" =~ ^[0-9]+$ ]]; then
    print_color "Error: Instance must be a number" "$RED"
    exit 1
fi

# Calculate ports based on instance
if [ "$INSTANCE" -eq 1 ]; then
    BACKEND_PORT=8000
    FRONTEND_PORT=3000
    STT_PORT=8001
    POSTGRES_PORT=5432
elif [ "$INSTANCE" -eq 2 ]; then
    BACKEND_PORT=9000
    FRONTEND_PORT=5174
    STT_PORT=9001
    POSTGRES_PORT=5433
else
    # Custom instance - calculate ports
    BACKEND_PORT=$((8000 + (INSTANCE - 1) * 1000))
    FRONTEND_PORT=$((3000 + (INSTANCE - 1) * 1000))
    STT_PORT=$((8001 + (INSTANCE - 1) * 1000))
    POSTGRES_PORT=$((5432 + INSTANCE - 1))
fi

print_color "🚀 Starting Gaia Instance $INSTANCE" "$BLUE"
print_color "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" "$BLUE"

# Check for port conflicts
print_color "\n📊 Checking port availability..." "$YELLOW"

PORT_CONFLICT=0
if check_port $BACKEND_PORT; then
    print_color "  ❌ Backend port $BACKEND_PORT is already in use" "$RED"
    PORT_CONFLICT=1
else
    print_color "  ✅ Backend port $BACKEND_PORT is available" "$GREEN"
fi

if check_port $FRONTEND_PORT; then
    print_color "  ❌ Frontend port $FRONTEND_PORT is already in use" "$RED"
    PORT_CONFLICT=1
else
    print_color "  ✅ Frontend port $FRONTEND_PORT is available" "$GREEN"
fi

if check_port $STT_PORT; then
    print_color "  ❌ STT port $STT_PORT is already in use" "$RED"
    PORT_CONFLICT=1
else
    print_color "  ✅ STT port $STT_PORT is available" "$GREEN"
fi

if check_port $POSTGRES_PORT; then
    print_color "  ❌ PostgreSQL port $POSTGRES_PORT is already in use" "$RED"
    PORT_CONFLICT=1
else
    print_color "  ✅ PostgreSQL port $POSTGRES_PORT is available" "$GREEN"
fi

if [ "$PORT_CONFLICT" -eq 1 ]; then
    print_color "\n⚠️  Port conflicts detected!" "$RED"
    print_color "   You may have another instance running on these ports." "$YELLOW"
    print_color "   To stop all instances: python3 gaia_launcher.py stop" "$YELLOW"
    print_color "   To stop specific instance: python3 gaia_launcher.py stop --instance $INSTANCE" "$YELLOW"
    echo
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_color "Aborted." "$RED"
        exit 1
    fi
fi

# Check if .env.instance file exists
ENV_FILE=".env.instance${INSTANCE}"
if [ "$INSTANCE" -gt 1 ] && [ ! -f "$ENV_FILE" ]; then
    print_color "\n⚠️  Warning: $ENV_FILE not found" "$YELLOW"
    print_color "   Creating from template..." "$YELLOW"
    
    # Create instance env file from template
    cat > "$ENV_FILE" << EOF
# Gaia Instance $INSTANCE Configuration
GAIA_INSTANCE=$INSTANCE
INSTANCE_NAME=instance$INSTANCE

# Port Configuration
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT
STT_PORT=$STT_PORT
POSTGRES_PORT=$POSTGRES_PORT

# Service URLs
VITE_API_BASE_URL=http://localhost:$BACKEND_PORT
VITE_STT_BASE_URL=ws://localhost:$STT_PORT

# Database
POSTGRES_DB=gaia_instance$INSTANCE
POSTGRES_USER=gaia
POSTGRES_PASSWORD=change_me_in_production

# Container Names
BACKEND_CONTAINER_NAME=gaia-backend-instance$INSTANCE
FRONTEND_CONTAINER_NAME=gaia-frontend-instance$INSTANCE
STT_CONTAINER_NAME=gaia-stt-instance$INSTANCE
POSTGRES_CONTAINER_NAME=gaia-postgres-instance$INSTANCE

# Volumes
POSTGRES_VOLUME=gaia_postgres_data_instance$INSTANCE
CAMPAIGN_VOLUME=gaia_campaigns_instance$INSTANCE
LOG_VOLUME=gaia_logs_instance$INSTANCE

# Environment
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:$FRONTEND_PORT,http://localhost:$BACKEND_PORT
EOF
    print_color "   ✅ Created $ENV_FILE" "$GREEN"
fi

# Build command
print_color "\n🔨 Preparing Docker command..." "$YELLOW"

CMD="python3 gaia_launcher.py start --instance $INSTANCE --env $PROFILE"

# Add build flag if not disabled
if [ "$GAIA_NO_BUILD" != "1" ]; then
    if [ "$INSTANCE" -eq 1 ] || [ ! -f ".env.instance${INSTANCE}.built" ]; then
        CMD="$CMD --force-build"
        print_color "   Will rebuild containers (set GAIA_NO_BUILD=1 to skip)" "$YELLOW"
    fi
fi

# Add logs flag if requested
if [ "$GAIA_SHOW_LOGS" == "1" ]; then
    CMD="$CMD --logs"
    print_color "   Will show logs in foreground" "$YELLOW"
fi

# Display configuration
print_color "\n📋 Instance Configuration:" "$BLUE"
print_color "   Instance:    $INSTANCE" "$NC"
print_color "   Profile:     $PROFILE" "$NC"
print_color "   Backend:     http://localhost:$BACKEND_PORT" "$NC"
print_color "   Frontend:    http://localhost:$FRONTEND_PORT" "$NC"
print_color "   STT Service: ws://localhost:$STT_PORT" "$NC"
print_color "   PostgreSQL:  localhost:$POSTGRES_PORT" "$NC"

# Execute the command
print_color "\n▶️  Executing: $CMD" "$GREEN"
print_color "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" "$BLUE"

# Run the command
$CMD

# Mark instance as built (for future runs)
if [ $? -eq 0 ] && [ "$INSTANCE" -gt 1 ]; then
    touch ".env.instance${INSTANCE}.built"
fi