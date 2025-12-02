# PostgreSQL Database Setup

## Overview

Gaia uses PostgreSQL 16 (Alpine) as its primary database for:
- User authentication and OAuth2 tokens
- Campaign and game state persistence
- Chat history storage
- Audit logging
- Access control management

## Architecture

### Database Schemas

The database is organized into three schemas:

1. **`auth` schema** - Authentication and user management
   - `users` - User accounts
   - `oauth_accounts` - OAuth2 provider accounts
   - `sessions` - Active user sessions
   - `access_control` - Resource-level permissions

2. **`game` schema** - Game data and state
   - `campaigns` - Campaign metadata and settings
   - `campaign_participants` - Players in campaigns
   - `chat_history` - Message history

3. **`audit` schema** - Security and audit logging
   - `security_events` - Login attempts, permission changes, etc.

### Technology Stack

- **PostgreSQL 16** - Latest stable version with Alpine Linux
- **SQLAlchemy 2.0.43** - Modern ORM with async support
- **asyncpg 0.30.0** - Fastest PostgreSQL async driver
- **psycopg3 3.2.9** - Latest PostgreSQL adapter
- **Alembic 1.16.4** - Database migration tool

## Quick Start

### 1. Start PostgreSQL

```bash
# Start PostgreSQL with development profile
docker compose --profile dev up -d postgres

# Or with GPU profile
docker compose --profile gpu up -d postgres

# Check status
docker ps | grep gaia-postgres
```

### 2. Verify Setup

```bash
# Run verification script
./backend/scripts/postgres/test_docker.sh

# Or test connection manually
docker exec gaia-postgres psql -U gaia -d gaia -c "SELECT 1"
```

### 3. Start Backend with Database

```bash
# Start backend (will connect to PostgreSQL automatically)
docker compose --profile dev up backend-dev

# Or with GPU support
docker compose --profile gpu up backend-gpu
```

## Database Management

### Connection Details

- **Host**: `postgres` (from Docker containers) or `localhost:5432` (from host)
- **Database**: `gaia`
- **User**: `gaia`
- **Password**: `gaia_secure_password` (change in production!)
- **Connection String**: `postgresql://gaia:gaia_secure_password@postgres:5432/gaia`

### Environment Variables

Set these in your `.env` or `.settings.docker.env`:

```bash
# Database connection
DATABASE_URL=postgresql://gaia:gaia_secure_password@postgres:5432/gaia

# PostgreSQL container settings
POSTGRES_DB=gaia
POSTGRES_USER=gaia
POSTGRES_PASSWORD=gaia_secure_password  # CHANGE IN PRODUCTION!

# Optional: Enable SQL echo for debugging
DATABASE_ECHO=false
```

### Backup and Restore

#### Create Backup

```bash
# Manual backup
./backend/scripts/postgres/backup.sh

# Backup is saved to ./backups/ with timestamp
# Automatically compressed with gzip
# Keeps last 10 backups
```

#### Restore from Backup

```bash
# Interactive restore (shows list of backups)
./backend/scripts/postgres/restore.sh

# Or restore specific backup
./backend/scripts/postgres/restore.sh ./backups/gaia_backup_20240101_120000.sql.gz
```

### Database Migrations

Using Alembic for schema migrations:

```bash
# Create new migration
docker exec gaia-backend-dev alembic revision --autogenerate -m "Description"

# Apply migrations
docker exec gaia-backend-dev alembic upgrade head

# Rollback one migration
docker exec gaia-backend-dev alembic downgrade -1

# View migration history
docker exec gaia-backend-dev alembic history
```

## Development

### Accessing PostgreSQL CLI

```bash
# Connect to PostgreSQL CLI
docker exec -it gaia-postgres psql -U gaia -d gaia

# Useful PostgreSQL commands:
\l          # List databases
\dn         # List schemas
\dt auth.*  # List tables in auth schema
\d+ auth.users  # Describe users table
\q          # Quit
```

### Sample Queries

```sql
-- View all users
SELECT * FROM auth.users;

-- View active campaigns
SELECT c.*, u.username as owner 
FROM game.campaigns c
JOIN auth.users u ON c.owner_id = u.user_id
WHERE c.is_active = true;

-- Check recent security events
SELECT * FROM audit.security_events 
ORDER BY created_at DESC 
LIMIT 10;

-- Grant admin access to user
UPDATE auth.users 
SET is_admin = true 
WHERE email = 'user@example.com';
```

### Python Database Access

```python
# Example: Using the database in your code
from db.src import db_manager

# Async context
async with db_manager.get_async_session() as session:
    result = await session.execute(
        "SELECT * FROM auth.users WHERE email = :email",
        {"email": "admin@gaia.local"}
    )
    user = result.fetchone()

# Sync context (for scripts/migrations)
with db_manager.get_sync_session() as session:
    users = session.execute("SELECT COUNT(*) FROM auth.users")
    print(f"Total users: {users.scalar()}")
```

## Production Deployment (Cloud SQL)

### 1. Provision the Instance

1. Enable required services:
   ```bash
   gcloud services enable sqladmin.googleapis.com \
     secretmanager.googleapis.com \
     iam.googleapis.com
   ```
2. Create the instance (cost-optimized configuration):
   ```bash
   gcloud sql instances create gaia-prod-db \
     --project=${PROJECT_ID} \
     --database-version=POSTGRES_16 \
     --tier=db-g1-small \
     --storage-size=10 \
     --storage-type=HDD \
     --region=us-west1 \
     --availability-type=zonal \
     --backup \
     --maintenance-window-day=MON \
     --maintenance-window-hour=2 \
     --edition=ENTERPRISE
   ```
   **Cost Optimization Notes**:
   - `db-g1-small`: Shared-core instance (0.5 vCPU, 1.7GB RAM) - sufficient for MVP/development
   - `HDD` storage: Cheaper than SSD, adequate for low-traffic workloads
   - `10GB` storage: Minimal size, auto-increases as needed
   - `zonal` availability: Single-zone deployment reduces costs vs regional HA
   - For production scale-up: Consider `db-custom-2-7680` (2 vCPU, 7.68GB) with SSD storage
   - For high availability: Change to `--availability-type=regional` when budget allows

3. (Optional) If you prefer private networking, add a Serverless VPC Access connector:
   ```bash
   gcloud compute networks vpc-access connectors create gaia-prod-connector \
     --region=${REGION} \
     --network=default \
     --range=10.8.0.0/28
   ```
   Then create the instance with `--network=projects/${PROJECT_ID}/global/networks/default` and `--ipv4-enabled=false`. Cloud Run deploys with `--vpc-connector gaia-prod-connector`.

### 2. Create Databases and Users

```bash
gcloud sql users create gaia_app \
  --instance=gaia-prod-db \
  --password="$(openssl rand -base64 32)"

gcloud sql databases create gaia \
  --instance=gaia-prod-db
```

- Store the generated password in `secrets/.secrets.env` (encrypted with SOPS) or directly in Secret Manager.
- Record the instance connection name:
  ```bash
  gcloud sql instances describe gaia-prod-db \
    --format='value(connectionName)'
  ```
  This becomes the `DB_INSTANCE_CONNECTION_NAME` used by Cloud Run.

### 3. Configure Environment Variables

Add the following keys to `secrets/.secrets.env` (then re-encrypt with SOPS if applicable):

```bash
DB_USER=gaia_app
DB_PASSWORD=<super_secret_password>
DB_NAME=gaia
DB_HOST=/cloudsql/${DB_INSTANCE_CONNECTION_NAME}
DATABASE_URL=postgresql://$(printf '%s' "$DB_USER" | jq -sRr @uri):$(printf '%s' "$DB_PASSWORD" | jq -sRr @uri)@/gaia?host=$DB_HOST
```

When using public IP connectivity, set `DB_HOST=<PUBLIC_IP>` instead and restrict access via `gcloud sql instances patch --authorized-networks`. Ensure SSL is enforced (`--require-ssl`) and provide certificates if you terminate TLS inside the instance.

### 4. Grant Cloud Run Access

1. Assign the Cloud Run runtime service account the `roles/cloudsql.client` permission:
   ```bash
   gcloud projects add-iam-policy-binding ${PROJECT_ID} \
     --member="serviceAccount:gaia-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/cloudsql.client"
   ```
2. Add the service account to the instance:
   ```bash
   gcloud sql instances patch gaia-prod-db \
     --assign-ip # only if using public IP
   ```
   For private IP, ensure the VPC connector is attached during deployment.

### 5. Deploy from Cloud Run

During deployment, append:

```bash
gcloud run deploy gaia-backend \
  --image=${IMAGE} \
  --service-account=gaia-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --set-env-vars=DB_USER=${DB_USER},DB_PASSWORD=${DB_PASSWORD},DB_NAME=${DB_NAME},DB_HOST=${DB_HOST},DATABASE_URL=${DATABASE_URL} \
  --add-cloudsql-instances=${DB_INSTANCE_CONNECTION_NAME} \
  --vpc-connector=gaia-prod-connector # only if using private IP
```

If you store secrets in Secret Manager, replace `--set-env-vars` with:

```bash
  --set-secrets=DB_USER=db-user:latest \
               DB_PASSWORD=db-password:latest \
               DB_NAME=db-name:latest \
               DATABASE_URL=db-url:latest
```

### 6. Run Migrations

Choose one of the following approaches:

- **Cloud Run job**: Package Alembic CLI into the backend image and execute `gcloud run jobs execute gaia-db-migrate --args "alembic upgrade head"`.
- **Cloud Build step**: Add a build stage that runs migrations against the instance before deploying.
- **Local machine**: Use Cloud SQL Proxy/Auth Proxy to connect securely and run `alembic upgrade head`.

Always create an automated backup or snapshot before large migration batches.

### 7. Backups and Maintenance

- Automated backups are enabled via `--backup`; configure point-in-time recovery if required.
- Schedule manual exports to Cloud Storage for long-term retention:
  ```bash
  gcloud sql export sql gaia-prod-db gs://gaia-db-backups/gaia-prod-$(date +%F).sql.gz \
    --database=gaia
  ```
- Monitor instance metrics in Cloud Monitoring (`cloudsql.googleapis.com/database/cpu/utilization`, connections, storage). Set alerts for high CPU or approaching storage limits.
- Rotate the `gaia_app` password periodically and update `secrets/.secrets.env` + Secret Manager entries.

With these steps in place the production Cloud SQL instance is locked down, backed up, and reachable from Cloud Run with minimum downtime risk.

## Security Considerations

### Production Checklist

- [ ] Change default passwords in environment variables
- [ ] Use strong passwords (min 16 characters)
- [ ] Enable SSL connections (already configured in connection manager)
- [ ] Set up regular automated backups
- [ ] Restrict network access to PostgreSQL port
- [ ] Enable query logging for audit purposes
- [ ] Set up monitoring and alerts
- [ ] Use secrets management for credentials

### Access Control

The database uses multiple levels of access control:

1. **Database Level**: PostgreSQL user permissions
2. **Schema Level**: Separate schemas for different concerns
3. **Application Level**: Access control table for resource permissions
4. **API Level**: JWT tokens and middleware validation

## Troubleshooting

### Common Issues

#### Container won't start
```bash
# Check logs
docker logs gaia-postgres

# Ensure no other PostgreSQL is running on port 5432
lsof -i :5432
```

#### Connection refused
```bash
# Ensure PostgreSQL is healthy
docker ps | grep gaia-postgres

# Test connection from host
psql -h localhost -U gaia -d gaia -c "SELECT 1"

# Check Docker network
docker network ls
docker network inspect gaia_default
```

#### Permission denied
```bash
# Check file permissions on migration scripts
ls -la db/migrations/

# Ensure scripts are readable
chmod 644 db/migrations/*.sql
```

#### Out of connections
```bash
# Check current connections
docker exec gaia-postgres psql -U gaia -d gaia -c "
  SELECT count(*) FROM pg_stat_activity;
"

# Terminate idle connections
docker exec gaia-postgres psql -U gaia -d gaia -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE state = 'idle' 
    AND state_change < NOW() - INTERVAL '10 minutes';
"
```

## Performance Tuning

### Connection Pool Settings

Configured in `src/core/database/connection.py`:

- **Async Pool**: 20 connections (API endpoints)
- **Sync Pool**: 5 connections (migrations/admin)
- **Connection Recycling**: 1 hour
- **Connection Timeout**: 30 seconds

### PostgreSQL Tuning

For production, consider adjusting in `postgresql.conf`:

```ini
# Memory
shared_buffers = 256MB
effective_cache_size = 1GB

# Connections
max_connections = 200
idle_in_transaction_session_timeout = 10min

# Performance
random_page_cost = 1.1  # For SSD storage
effective_io_concurrency = 200  # For SSD storage
```

## Monitoring

### Database Statistics

```sql
-- Database size
SELECT pg_database_size('gaia') / 1024 / 1024 as size_mb;

-- Table sizes
SELECT 
  schemaname, 
  tablename, 
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname IN ('auth', 'game', 'audit')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Active connections
SELECT 
  datname, 
  usename, 
  application_name,
  client_addr, 
  state,
  state_change
FROM pg_stat_activity
WHERE datname = 'gaia';
```

### Health Checks

The PostgreSQL container includes automatic health checks:
- Runs every 10 seconds
- Timeout after 5 seconds
- Marks unhealthy after 5 failures

## Future Enhancements

- [ ] Add read replicas for scaling
- [ ] Implement table partitioning for chat_history
- [ ] Add full-text search for messages
- [ ] Set up streaming replication for HA
- [ ] Add TimescaleDB for time-series data
- [ ] Implement row-level security policies
- [ ] Add GraphQL interface via Hasura/PostGraphile
