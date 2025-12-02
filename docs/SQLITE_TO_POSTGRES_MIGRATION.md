# SQLite to PostgreSQL Migration Guide

## Migration Process

### 1. Code Changes Required: **MINIMAL**

Since we use SQLAlchemy ORM, the same models work for both databases:

```python
# Only change needed is the connection string:

# SQLite (current):
DATABASE_URL = "sqlite:///./auth_data/gaia_auth.db"

# PostgreSQL (future):
DATABASE_URL = "postgresql://gaia:password@postgres:5432/gaia_auth"
```

### 2. Data Migration Steps

```bash
# Step 1: Export SQLite data
python scripts/export_auth_data.py --format=json

# Step 2: Spin up PostgreSQL container
docker-compose up -d postgres

# Step 3: Create PostgreSQL schema
python scripts/init_postgres_db.py

# Step 4: Import data to PostgreSQL
python scripts/import_auth_data.py --source=auth_export.json

# Step 5: Update environment variable
export DATABASE_URL="postgresql://..."

# Step 6: Restart application
docker-compose restart backend
```

### 3. Schema Differences to Handle

| Feature | SQLite | PostgreSQL | Migration Impact |
|---------|---------|------------|------------------|
| UUID | TEXT | UUID native type | Automatic with SQLAlchemy |
| JSON | TEXT | JSONB | Better querying, automatic |
| Timestamps | TEXT/INTEGER | TIMESTAMP WITH TIMEZONE | Automatic conversion |
| Full-text search | Limited | Built-in | New features available |
| Concurrent writes | File locks | MVCC | Better performance |

### 4. Docker Compose Addition

```yaml
# Add to docker-compose.yml when ready:
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: gaia_auth
    POSTGRES_USER: gaia
    POSTGRES_PASSWORD: ${DB_PASSWORD}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  ports:
    - "5432:5432"
```

## When to Migrate?

### Stay with SQLite if:
- < 100 concurrent users
- Single server deployment
- Development/testing environment
- Simplicity is priority

### Move to PostgreSQL when:
- Multiple concurrent users (100+)
- Need horizontal scaling
- Want real-time features
- Need advanced queries (JSONB queries, full-text search)
- Production deployment

## Migration Time Estimate
- Data export: 5 minutes
- PostgreSQL setup: 10 minutes
- Data import: 5-10 minutes
- Testing: 30 minutes
- **Total downtime: < 5 minutes** (if done with blue-green deployment)