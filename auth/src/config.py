"""
Authentication configuration module.

Handles all configuration for authentication across services.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class AuthConfig:
    """Authentication configuration singleton"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # JWT Configuration
        self.jwt_secret_key = self._get_secret_key()
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )
        self.refresh_token_expire_days = int(
            os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
        )
        
        # Authentication settings
        self.auth_enabled = True
        
        # Service information
        self.service_name = os.getenv("SERVICE_NAME", "gaia-service")
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        self._initialized = True
        
        # Log configuration
        logger.info(f"Authentication ENABLED for {self.service_name}")
    
    def _get_secret_key(self) -> str:
        """Get JWT secret key from environment or file"""
        # Try environment variable first
        secret = os.getenv("JWT_SECRET_KEY")
        if secret:
            return secret
        
        # Try Docker secrets file
        secret_file = os.getenv("JWT_SECRET_KEY_FILE")
        if secret_file and os.path.exists(secret_file):
            try:
                with open(secret_file, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                logger.warning(f"Could not read JWT secret from file {secret_file}: {e}")
        
        # Try common secret paths
        common_paths = [
            "/run/secrets/jwt_secret",
            "/etc/secrets/jwt_secret",
            Path.home() / ".gaia" / "jwt_secret"
        ]
        
        for path in common_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        secret = f.read().strip()
                        if secret:
                            logger.info(f"Loaded JWT secret from {path}")
                            return secret
                except Exception as e:
                    logger.warning(f"Could not read JWT secret from {path}: {e}")
        
        # Development fallback
        if self.environment == "development":
            logger.warning("Using development JWT secret - CHANGE IN PRODUCTION!")
            return "dev-secret-key-change-in-production-please"
        
        raise ValueError(
            "JWT_SECRET_KEY is required in production. "
            "Set JWT_SECRET_KEY environment variable or JWT_SECRET_KEY_FILE path."
        )
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == "production"


# Global configuration instance
auth_config = AuthConfig()