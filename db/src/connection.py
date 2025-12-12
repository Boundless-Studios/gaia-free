"""
Database connection management for Gaia

Handles both synchronous and asynchronous database connections
using SQLAlchemy 2.0 with PostgreSQL.
"""

import os
import logging
from typing import AsyncGenerator, Generator, Optional
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# Cache for secrets loaded from file (for uvicorn worker processes)
_secrets_cache: Optional[dict] = None



def _load_secrets_from_file() -> dict:
    """Load secrets from decrypted file if available.

    This handles the case where uvicorn --reload spawns workers that
    don't inherit environment variables from the parent process.
    """
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache

    _secrets_cache = {}
    secrets_file = os.getenv('DECRYPTED_SECRETS_FILE', '/tmp/.decrypted_secrets.env')
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        _secrets_cache[key.strip()] = value.strip()
            logger.debug(f"Loaded {len(_secrets_cache)} secrets from {secrets_file}")
        except Exception as e:
            logger.warning(f"Could not read secrets from {secrets_file}: {e}")
    return _secrets_cache


def _get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret from environment or decrypted secrets file."""
    value = os.getenv(key)
    if value:
        return value
    secrets = _load_secrets_from_file()
    return secrets.get(key, default)


class DatabaseManager:
    """Manages database connections and sessions"""
    
    def __init__(self):
        self.sync_engine = None
        self.async_engine = None
        self.sync_session_factory = None
        self.async_session_factory = None
        self._initialized = False
    
    def _get_database_url(self) -> Optional[str]:
        """Get database URL from environment or Docker secrets file"""
        # Try environment variable first
        url = os.getenv('DATABASE_URL','')
        logger.info(f"Retrieved db url: {url}")
        if url:
            return url

        # Try Docker secrets file (if DATABASE_URL_FILE is set)
        url_file = os.getenv('DATABASE_URL_FILE')
        if url_file and os.path.exists(url_file):
            try:
                with open(url_file, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                logger.warning(f"Could not read DATABASE_URL from file {url_file}: {e}")

        # Build from explicit POSTGRES_* variables if available (e.g., docker-compose)
        pg_host = os.getenv('POSTGRES_HOST')
        pg_port = os.getenv('POSTGRES_PORT') or '5432'
        pg_db = os.getenv('POSTGRES_DB')
        pg_user = os.getenv('POSTGRES_USER')
        pg_password = _get_secret('DB_PASSWORD') or _get_secret('POSTGRES_PASSWORD')
        if pg_host and pg_db and pg_user and pg_password:
            built_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
            logger.info(f"Built DATABASE_URL from POSTGRES_* variables for host {pg_host}")
            return built_url

        # Try building from Cloud SQL components (for Cloud Run)
        db_instance = os.getenv('DB_INSTANCE_CONNECTION_NAME')
        logger.info(f"[DB_DEBUG] DB_INSTANCE_CONNECTION_NAME={db_instance}")
        if db_instance:
            # For Cloud Run with Cloud SQL, build connection string for Unix socket
            db_user = os.getenv('POSTGRES_USER', 'gaia')
            db_password = _get_secret('DB_PASSWORD') or _get_secret('POSTGRES_PASSWORD')
            db_name = os.getenv('POSTGRES_DB', 'gaia')
            use_iam_auth = os.getenv('DB_USE_IAM_AUTH', 'false').lower() == 'true'

            logger.info(f"[DB_DEBUG] POSTGRES_USER={db_user}")
            logger.info(f"[DB_DEBUG] POSTGRES_DB={db_name}")
            logger.info(f"[DB_DEBUG] DB_USE_IAM_AUTH={os.getenv('DB_USE_IAM_AUTH')} -> {use_iam_auth}")
            logger.info(f"[DB_DEBUG] DB_PASSWORD present: {bool(db_password)}")

            # Cloud SQL Proxy uses Unix sockets at /cloudsql/<instance_connection_name>
            socket_path = f"/cloudsql/{db_instance}"

            if use_iam_auth:
                # IAM authentication mode - use service account email as user, no password
                # The Cloud SQL Proxy handles token generation automatically
                service_account = os.getenv('DB_IAM_USER') or os.getenv('RUNTIME_SERVICE_ACCOUNT')
                logger.info(f"[DB_DEBUG] DB_IAM_USER={os.getenv('DB_IAM_USER')}")
                logger.info(f"[DB_DEBUG] RUNTIME_SERVICE_ACCOUNT={os.getenv('RUNTIME_SERVICE_ACCOUNT')}")
                logger.info(f"[DB_DEBUG] Selected service_account={service_account}")
                if service_account:
                    url = f"postgresql://{service_account}@/{db_name}?host={socket_path}"
                    logger.info(f"Built DATABASE_URL with IAM auth for instance: {db_instance}, user: {service_account}")
                    return url
                else:
                    logger.error("DB_USE_IAM_AUTH=true but no DB_IAM_USER or RUNTIME_SERVICE_ACCOUNT set")
            elif db_password:
                # Password authentication mode (traditional)
                url = f"postgresql://{db_user}:{db_password}@/{db_name}?host={socket_path}"
                logger.info(f"Built DATABASE_URL from Cloud SQL components for instance: {db_instance}")
                return url
            else:
                logger.warning("DB_INSTANCE_CONNECTION_NAME found but no DB_PASSWORD and IAM auth not enabled")

        return None
    
    def initialize(self):
        """Initialize database connections"""
        if self._initialized:
            return
        
        logger.info("Retrieving db url")
        # Get database URL from environment or file
        database_url = self._get_database_url()
        
        if not database_url:
            # Only provide default in development mode
            if os.getenv('ENVIRONMENT', 'development') == 'development':
                # Build default URL from POSTGRES_* environment variables
                db_user = os.getenv('POSTGRES_USER', 'gaia')
                db_host = os.getenv('POSTGRES_HOST', 'localhost')
                db_port = os.getenv('POSTGRES_PORT', '5432')
                db_name = os.getenv('POSTGRES_DB', 'gaia')
                db_password = _get_secret('POSTGRES_PASSWORD', '')  # Get from env/secrets or empty
                logger.warning(f"No DATABASE_URL found, using development default with host={db_host}")
                # If password is empty, don't include it in URL (trust authentication)
                if db_password:
                    database_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
                else:
                    database_url = f'postgresql://{db_user}@{db_host}:{db_port}/{db_name}'
            else:
                raise ValueError("DATABASE_URL environment variable or file is required")
        
        # Create async URL (asyncpg driver - fastest for async)
        if database_url.startswith('postgresql://'):
            async_database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        else:
            async_database_url = database_url
        
        # Create sync URL (psycopg3 driver - recommended)
        # Note: psycopg3 uses 'postgresql+psycopg' not 'postgresql+psycopg3'
        if database_url.startswith('postgresql://'):
            sync_database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')
        else:
            sync_database_url = database_url
        
        # Create synchronous engine (for migrations and admin tasks)
        sync_connect_args = {}
        if sync_database_url.startswith('postgresql+psycopg'):
            # psycopg/libpq does not support asyncpg-style server_settings; set via options instead.
            sync_connect_args["options"] = "-c timezone=utc -c jit=off"

        self.sync_engine = create_engine(
            sync_database_url,
            echo=os.getenv('DATABASE_ECHO', 'false').lower() == 'true',
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_timeout=30,  # Timeout waiting for connection
            connect_args=sync_connect_args
        )
        
        # Create asynchronous engine (for API endpoints)
        self.async_engine = create_async_engine(
            async_database_url,
            echo=os.getenv('DATABASE_ECHO', 'false').lower() == 'true',
            pool_pre_ping=True,  # Verify connections before using
            pool_size=20,
            max_overflow=20,
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_timeout=30,  # Timeout waiting for connection
            connect_args={
                "server_settings": {
                    "jit": "off",  # Disable JIT for better latency
                    "search_path": "public,auth,game"  # Ensure correct schema search order
                },
                "command_timeout": 60,
                "ssl": "prefer"  # Use SSL when available
            } if async_database_url.startswith('postgresql+asyncpg') else {}
        )
        
        # Create session factories
        self.sync_session_factory = sessionmaker(
            bind=self.sync_engine,
            expire_on_commit=False
        )
        
        self.async_session_factory = async_sessionmaker(
            bind=self.async_engine,
            expire_on_commit=False
        )
        
        self._initialized = True
        logger.info("Database manager initialized successfully")
    
    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            async with self.async_session_factory() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def test_sync_connection(self) -> bool:
        """Test synchronous database connection"""
        try:
            with self.sync_session_factory() as session:
                result = session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Sync database connection test failed: {e}")
            return False
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session"""
        if not self._initialized:
            self.initialize()
        
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @contextmanager
    def get_sync_session(self) -> Generator[Session, None, None]:
        """Get sync database session"""
        if not self._initialized:
            self.initialize()
        
        with self.sync_session_factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
    
    async def create_tables(self):
        """Create all tables (for development/testing)"""
        from .base import Base
        
        if not self._initialized:
            self.initialize()
        
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
    
    async def drop_tables(self):
        """Drop all tables (for development/testing)"""
        from .base import Base
        
        if not self._initialized:
            self.initialize()
        
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped")
    
    async def cleanup(self):
        """Cleanup database connections"""
        if self.async_engine:
            await self.async_engine.dispose()
        
        if self.sync_engine:
            self.sync_engine.dispose()
        
        self._initialized = False
        logger.info("Database connections closed")


# Create global database manager instance
db_manager = DatabaseManager()


# Dependency injection functions for FastAPI
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async database session"""
    async with db_manager.get_async_session() as session:
        yield session


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for sync database session"""
    with db_manager.get_sync_session() as session:
        yield session
