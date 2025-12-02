"""
Auth0 JWT token verifier for Speech-to-Text service

Verifies JWT tokens issued by Auth0 using RS256 algorithm and JWKS.
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from functools import lru_cache
import time

from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
import requests

logger = logging.getLogger(__name__)


class Auth0JWTVerifier:
    """Handles Auth0 JWT token verification for STT service"""
    
    def __init__(self):
        # Auth0 configuration
        self.auth0_domain = os.getenv("AUTH0_DOMAIN")
        self.auth0_audience = os.getenv("AUTH0_AUDIENCE", "https://api.your-domain.com")
        self.auth0_issuer = os.getenv("AUTH0_ISSUER")
        
        # Derive issuer from domain if not explicitly set
        if not self.auth0_issuer and self.auth0_domain:
            self.auth0_issuer = f"https://{self.auth0_domain}/"
        
        # JWKS URI for fetching public keys
        self.jwks_uri = os.getenv("AUTH0_JWKS_URI")
        if not self.jwks_uri and self.auth0_domain:
            self.jwks_uri = f"https://{self.auth0_domain}/.well-known/jwks.json"
        
        # Algorithm is always RS256 for Auth0
        self.algorithm = "RS256"
        
        # Cache for JWKS with 1 hour TTL
        self._jwks_cache = None
        self._jwks_cache_time = 0
        self._jwks_cache_ttl = 3600  # 1 hour
        
        # Validate configuration
        if not self.auth0_domain:
            logger.warning("AUTH0_DOMAIN not configured - Auth0 authentication disabled")
            raise ValueError("AUTH0_DOMAIN is required")
        if not self.auth0_audience:
            logger.warning("AUTH0_AUDIENCE not configured - using default")
        if not self.jwks_uri:
            raise ValueError("AUTH0_JWKS_URI could not be determined")
        
        logger.info(f"Auth0 JWT verifier initialized with domain: {self.auth0_domain}")
    
    @lru_cache(maxsize=1)
    def _fetch_jwks(self) -> Dict[str, Any]:
        """Fetch JSON Web Key Set from Auth0 with caching"""
        current_time = time.time()
        
        # Return cached JWKS if still valid
        if self._jwks_cache and (current_time - self._jwks_cache_time) < self._jwks_cache_ttl:
            return self._jwks_cache
        
        try:
            logger.debug(f"Fetching JWKS from: {self.jwks_uri}")
            response = requests.get(self.jwks_uri, timeout=10)
            response.raise_for_status()
            
            jwks = response.json()
            
            # Update cache
            self._jwks_cache = jwks
            self._jwks_cache_time = current_time
            
            logger.debug(f"Successfully fetched JWKS with {len(jwks.get('keys', []))} keys")
            return jwks
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch JWKS from {self.jwks_uri}: {e}")
            # Return cached JWKS if available, even if expired
            if self._jwks_cache:
                logger.warning("Using expired JWKS cache due to fetch failure")
                return self._jwks_cache
            raise ValueError(f"Could not fetch JWKS: {e}")
    
    def _get_rsa_key(self, token: str) -> Optional[Dict[str, Any]]:
        """Get the RSA key from JWKS that matches the token's kid"""
        try:
            # Get the key ID from the token header
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                logger.warning("Token missing 'kid' in header")
                return None
            
            # Fetch JWKS
            jwks = self._fetch_jwks()
            
            # Find the key with matching kid
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    return key
            
            logger.warning(f"No matching key found for kid: {kid}")
            # Clear cache to force refresh on next attempt
            self._jwks_cache = None
            return None
            
        except Exception as e:
            logger.error(f"Error getting RSA key: {e}")
            return None
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify an Auth0 JWT token and return payload"""
        try:
            # Validate token format first
            if not token or not isinstance(token, str):
                logger.warning("Invalid token format: empty or not a string")
                return None
            
            # Remove Bearer prefix if present
            if token.startswith("Bearer "):
                token = token[7:]
            
            # Check if token has proper JWT structure (header.payload.signature)
            parts = token.split('.')
            if len(parts) != 3:
                logger.warning(f"Invalid JWT structure: expected 3 segments, got {len(parts)}")
                return None
            
            # Get the RSA key for verification
            rsa_key = self._get_rsa_key(token)
            if not rsa_key:
                logger.warning("Could not get RSA key for token verification")
                return None
            
            # Decode and verify the token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=[self.algorithm],
                audience=self.auth0_audience,
                issuer=self.auth0_issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require_exp": True,
                    "require_iat": True,
                    "require_sub": True
                }
            )
            
            # Extract user information from Auth0 claims
            user_info = {
                "user_id": payload.get("sub"),  # Auth0 user ID
                "email": payload.get("email"),
                "email_verified": payload.get("email_verified", False),
                "name": payload.get("name"),
                "nickname": payload.get("nickname"),
                "picture": payload.get("picture"),
                "updated_at": payload.get("updated_at"),
                # Custom claims
                "permissions": payload.get("permissions", []),
                "roles": payload.get("https://api.your-domain.com/roles", []),  # Custom namespace for roles
                "is_admin": "admin" in payload.get("https://api.your-domain.com/roles", []),
                # Token metadata
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
                "scope": payload.get("scope", "").split() if payload.get("scope") else [],
                # Raw payload for any additional processing
                "raw_payload": payload
            }
            
            logger.debug(f"Successfully verified token for user: {user_info['user_id']}")
            return user_info
            
        except ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except JWTClaimsError as e:
            logger.warning(f"Invalid JWT claims: {e}")
            return None
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying Auth0 JWT: {e}")
            return None
    
    def extract_token_from_header(self, authorization: Optional[str]) -> Optional[str]:
        """Extract token from Authorization header"""
        if not authorization:
            return None
        
        parts = authorization.split()
        
        # Check for Bearer token
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        
        return None


# Global Auth0 JWT verifier instance (only initialize if Auth0 is configured)
auth0_jwt_verifier = None

def initialize_auth0_verifier():
    """Initialize the Auth0 JWT verifier if configuration is present"""
    global auth0_jwt_verifier
    
    if os.getenv("AUTH0_DOMAIN"):
        try:
            auth0_jwt_verifier = Auth0JWTVerifier()
            logger.info("Auth0 JWT verifier initialized successfully for STT service")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Auth0 JWT verifier: {e}")
            return False
    else:
        logger.info("Auth0 not configured for STT service, using legacy authentication")
        return False


def get_auth0_verifier() -> Optional[Auth0JWTVerifier]:
    """Get the Auth0 JWT verifier instance"""
    global auth0_jwt_verifier
    
    if not auth0_jwt_verifier:
        initialize_auth0_verifier()
    
    return auth0_jwt_verifier