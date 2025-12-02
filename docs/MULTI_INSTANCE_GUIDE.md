# Multi-Instance Configuration Guide

This guide explains how to run multiple instances of the Gaia application stack simultaneously for parallel development and testing.

## Quick Start

### Running Multiple Instances

```bash
# Start default instance (ports 8000/3000/8001/5432)
python3 gaia_launcher.py start

# Start second instance (ports 9000/5174/9001/5433)
python3 gaia_launcher.py start --instance 2

# Start third instance with GPU support
python3 gaia_launcher.py start --instance 3 --env gpu

# Using the helper script
./start-instance.sh          # Start instance 1
./start-instance.sh 2        # Start instance 2
./start-instance.sh 3 gpu    # Start instance 3 with GPU
```

### Stopping Instances

```bash
# Stop all instances
python3 gaia_launcher.py stop

# Stop specific instance
python3 gaia_launcher.py stop --instance 2

# Stop instance 3
python3 gaia_launcher.py stop --instance 3
```

## Port Allocation

Each instance uses a predefined set of ports to avoid conflicts:

### Instance 1 (Default)
- **Backend API**: 8000
- **Frontend**: 3000
- **STT Service**: 8001
- **PostgreSQL**: 5432

### Instance 2
- **Backend API**: 9000
- **Frontend**: 5174
- **STT Service**: 9001
- **PostgreSQL**: 5433

### Instance 3+
- **Backend API**: 8000 + (instance-1) × 1000
- **Frontend**: 3000 + (instance-1) × 1000
- **STT Service**: 8001 + (instance-1) × 1000
- **PostgreSQL**: 5432 + (instance-1)

## Configuration Files

### Environment Files

Each instance can have its own environment configuration:

```bash
.env.instance1    # Default instance configuration
.env.instance2    # Second instance configuration
.env.instance3    # Third instance configuration (auto-created if needed)
```

### Environment File Structure

```bash
# Instance Identification
GAIA_INSTANCE=2
INSTANCE_NAME=instance2

# Port Configuration
BACKEND_PORT=9000
FRONTEND_PORT=5174
STT_PORT=9001
POSTGRES_PORT=5433

# Service URLs
VITE_API_BASE_URL=http://localhost:9000
VITE_STT_BASE_URL=ws://localhost:9001

# Database Configuration
POSTGRES_DB=gaia_instance2
POSTGRES_USER=gaia
POSTGRES_PASSWORD=change_me_in_production

# Container Names (unique per instance)
BACKEND_CONTAINER_NAME=gaia-backend-instance2
FRONTEND_CONTAINER_NAME=gaia-frontend-instance2
STT_CONTAINER_NAME=gaia-stt-instance2
POSTGRES_CONTAINER_NAME=gaia-postgres-instance2

# Volume Names (isolated data)
POSTGRES_VOLUME=gaia_postgres_data_instance2
CAMPAIGN_VOLUME=gaia_campaigns_instance2
LOG_VOLUME=gaia_logs_instance2
```

## Common Use Cases

### 1. Testing Different Branches

Run two instances to compare different branches side by side:

```bash
# Terminal 1: Main branch on default ports
git checkout main
python3 gaia_launcher.py start

# Terminal 2: Feature branch on secondary ports
git checkout feature/new-feature
python3 gaia_launcher.py start --instance 2
```

Access them at:
- Main branch: http://localhost:3000
- Feature branch: http://localhost:5174

### 2. Backend/Frontend Development

Run backend and frontend on different instances for isolated development:

```bash
# Instance 1: Backend development
python3 gaia_launcher.py start --instance 1 --env dev

# Instance 2: Frontend with different backend
VITE_API_BASE_URL=http://localhost:8000 python3 gaia_launcher.py start --instance 2
```

### 3. Load Testing

Run multiple instances for load testing and performance comparison:

```bash
# Production instance
python3 gaia_launcher.py start --instance 1 --env prod

# Development instance for comparison
python3 gaia_launcher.py start --instance 2 --env dev

# GPU-enabled instance for ML testing
python3 gaia_launcher.py start --instance 3 --env gpu
```

## Docker Management

### Viewing Logs

```bash
# Instance 1 logs
docker compose logs -f

# Instance 2 logs
docker compose --env-file .env.instance2 logs -f

# Specific service logs
docker logs gaia-backend-instance2 -f
docker logs gaia-frontend-instance2 -f
```

### Container Status

```bash
# View all Gaia containers
docker ps | grep gaia

# View specific instance containers
docker ps | grep instance2
```

### Cleanup

```bash
# Remove all stopped containers
docker container prune

# Remove instance-specific volumes (WARNING: deletes data)
docker volume rm gaia_postgres_data_instance2
docker volume rm gaia_campaigns_instance2
docker volume rm gaia_logs_instance2
```

## Advanced Configuration

### Custom Ports

Create a custom environment file for non-standard ports:

```bash
# .env.custom
BACKEND_PORT=7777
FRONTEND_PORT=4444
STT_PORT=7778
POSTGRES_PORT=5555
```

Then use it:

```bash
docker compose --env-file .env.custom --profile dev up
```

### Using Docker Compose Directly

For more control, use Docker Compose directly with instance env files:

```bash
# Start with instance 2 configuration
docker compose --env-file .env.instance2 --profile dev up -d

# Stop instance 2
docker compose --env-file .env.instance2 down

# Rebuild and start instance 2
docker compose --env-file .env.instance2 --profile dev up -d --build
```

### Port Conflict Resolution

If you encounter port conflicts:

1. **Check what's using the port**:
   ```bash
   lsof -i :8000  # Check backend port
   lsof -i :3000  # Check frontend port
   ```

2. **Stop conflicting services**:
   ```bash
   # Stop all Gaia instances
   python3 gaia_launcher.py stop
   
   # Or stop specific Docker containers
   docker stop $(docker ps -q --filter name=gaia)
   ```

3. **Use alternative instance**:
   ```bash
   # If instance 1 ports are busy, use instance 2
   python3 gaia_launcher.py start --instance 2
   ```

## Environment Variables

### Instance Selection
- `GAIA_INSTANCE`: Instance number (1, 2, 3, etc.)

### Port Variables
- `BACKEND_PORT`: Backend API port
- `FRONTEND_PORT`: Frontend web server port
- `STT_PORT`: Speech-to-text service port
- `POSTGRES_PORT`: PostgreSQL database port

### Container Names
- `BACKEND_CONTAINER_NAME`: Backend container name
- `FRONTEND_CONTAINER_NAME`: Frontend container name
- `STT_CONTAINER_NAME`: STT service container name
- `POSTGRES_CONTAINER_NAME`: Database container name

### Volume Names
- `POSTGRES_VOLUME`: Database data volume
- `CAMPAIGN_VOLUME`: Campaign storage volume
- `LOG_VOLUME`: Application logs volume

## Troubleshooting

### Port Already in Use

**Error**: "bind: address already in use"

**Solution**:
```bash
# Find process using the port
lsof -i :8000

# Stop all Gaia instances
python3 gaia_launcher.py stop

# Or kill specific process
kill -9 <PID>
```

### Container Name Conflicts

**Error**: "container name already in use"

**Solution**:
```bash
# Remove the conflicting container
docker rm gaia-backend-instance2

# Or force remove
docker rm -f gaia-backend-instance2
```

### Database Connection Issues

**Error**: "database does not exist"

**Solution**:
Each instance uses a separate database. Ensure the database name matches:
- Instance 1: `gaia` or `gaia_instance1`
- Instance 2: `gaia_instance2`
- Instance 3: `gaia_instance3`

### Frontend Can't Connect to Backend

**Issue**: Frontend on instance 2 can't reach backend

**Solution**:
Check that environment variables are set correctly:
```bash
# In .env.instance2
VITE_API_BASE_URL=http://localhost:9000
VITE_STT_BASE_URL=ws://localhost:9001
```

## Best Practices

1. **Use Consistent Naming**: Keep instance numbers consistent across branches
2. **Document Port Usage**: Maintain a team document of who's using which instance
3. **Clean Up**: Stop instances when not in use to free resources
4. **Separate Databases**: Each instance should have its own database to avoid conflicts
5. **Monitor Resources**: Multiple instances consume more memory and CPU

## Example Workflows

### Parallel Feature Development

```bash
# Developer A working on authentication
git checkout feature/auth
./start-instance.sh 1

# Developer B working on UI improvements
git checkout feature/ui-update
./start-instance.sh 2

# QA testing main branch
git checkout main
./start-instance.sh 3
```

### A/B Testing

```bash
# Version A with current implementation
python3 gaia_launcher.py start --instance 1

# Version B with experimental features
EXPERIMENTAL_FEATURES=true python3 gaia_launcher.py start --instance 2
```

### Development and Production

```bash
# Development with hot reload
python3 gaia_launcher.py start --instance 1 --env dev

# Production build for testing
python3 gaia_launcher.py start --instance 2 --env prod
```

## Helper Script Usage

The `start-instance.sh` script provides additional features:

```bash
# Basic usage
./start-instance.sh [instance] [profile]

# Skip rebuild
GAIA_NO_BUILD=1 ./start-instance.sh 2

# Show logs in foreground
GAIA_SHOW_LOGS=1 ./start-instance.sh 2

# Combined options
GAIA_NO_BUILD=1 GAIA_SHOW_LOGS=1 ./start-instance.sh 2 gpu
```

The script will:
- Check for port conflicts before starting
- Create missing .env.instance files
- Display clear configuration information
- Handle build caching for faster restarts

## Limitations

1. **Resource Usage**: Each instance requires separate containers and volumes
2. **Port Range**: Limited by available ports on the host system
3. **Database Isolation**: Each instance has separate data - no sharing by default
4. **Network Complexity**: Inter-instance communication requires additional configuration

## Support

For issues or questions about multi-instance configuration:
1. Check container logs: `docker logs <container-name>`
2. Verify port availability: `lsof -i :<port>`
3. Review environment files: `.env.instance*`
4. Consult the main README.md for general setup issues