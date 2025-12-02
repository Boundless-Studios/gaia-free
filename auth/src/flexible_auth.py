"""
Flexible authentication dependencies for development and production environments.

This module provides authentication dependencies that can be disabled for local
development while maintaining security in production.
"""

import os
import logging
from types import SimpleNamespace
from typing import Optional, Any, Dict
from fastapi import Depends, HTTPException, status, WebSocket, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


def _str_to_bool(value: Optional[str]) -> bool:
    """Interpret common truthy strings."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


DISABLE_AUTH_ENV = _str_to_bool(os.getenv("DISABLE_AUTH") or os.getenv("AUTH_DISABLED"))
AUTH_AVAILABLE = not DISABLE_AUTH_ENV
TEST_IDENTITY = SimpleNamespace(
    user_id="test-user",
    email="test-user@example.com",
)


def _build_disabled_dependencies() -> Dict[str, Any]:
    """Return no-op auth dependencies when auth is disabled or unavailable."""
    logger.info("Authentication DISABLED (DISABLE_AUTH=true)")
    return {
        "require_auth": Depends(lambda: TEST_IDENTITY),
        "require_admin": Depends(lambda: TEST_IDENTITY),
        "optional_auth": Depends(lambda: TEST_IDENTITY),
        "websocket_auth": _no_auth_websocket,
        "AUTH_AVAILABLE": False,
    }


def _build_enabled_dependencies() -> Dict[str, Any]:
    """Return real auth dependencies when auth is enabled."""
    from auth.src.middleware import (
        get_current_user,
        get_admin_user,
        get_optional_user,
    )
    from auth.src.auth0_jwt_verifier import get_auth0_verifier

    auth0_verifier = get_auth0_verifier()
    if not auth0_verifier:
        raise RuntimeError("Auth0 verifier is not configured")
    logger.info("Authentication ENABLED")
    return {
        "require_auth": Depends(get_current_user),
        "require_admin": Depends(get_admin_user),
        "optional_auth": Depends(get_optional_user),
        "websocket_auth": _create_websocket_auth(auth0_verifier),
        "AUTH_AVAILABLE": True,
    }


_auth_deps: Optional[Dict[str, Any]] = None


def get_auth_dependencies():
    """
    Returns authentication dependencies based on environment configuration.

    Returns:
        Dict containing authentication dependencies that can be used across services

    Raises:
        RuntimeError: If authentication is required but initialization fails
    """
    global _auth_deps, AUTH_AVAILABLE
    if _auth_deps is not None:
        return _auth_deps

    if DISABLE_AUTH_ENV:
        # Only allow disabling auth when explicitly configured for development
        logger.warning("Authentication EXPLICITLY DISABLED via environment variable")
        AUTH_AVAILABLE = False
        _auth_deps = _build_disabled_dependencies()
        return _auth_deps

    try:
        deps = _build_enabled_dependencies()
        if deps.get("AUTH_AVAILABLE"):
            AUTH_AVAILABLE = True
            _auth_deps = deps
        else:
            # Auth0 failed to initialize - this is an error, not a fallback scenario
            AUTH_AVAILABLE = False
            logger.error("Auth0 initialization returned unavailable status")
            raise RuntimeError("Authentication is required but Auth0 initialization failed")
    except Exception as exc:
        # SECURITY FIX: Do NOT fall back to disabled auth when Auth0 fails
        # This was allowing unregistered users to access the system via TEST_IDENTITY
        AUTH_AVAILABLE = False
        logger.error("Authentication initialization failed: %s", exc)
        logger.error("SECURITY: Refusing to fall back to disabled auth - authentication is REQUIRED")
        raise RuntimeError(f"Authentication is required but initialization failed: {exc}")
    return _auth_deps


async def _no_auth_dependency():
    """Dummy dependency that returns None when auth is disabled."""
    return TEST_IDENTITY


async def _no_auth_websocket(websocket: WebSocket, token: Optional[str] = Query(None)):
    """Dummy WebSocket auth that returns None when auth is disabled."""
    return {
        "user_id": TEST_IDENTITY.user_id,
        "email": TEST_IDENTITY.email,
    }


def _create_websocket_auth(auth0_verifier):
    """Create WebSocket authentication function with the provided Auth0 verifier."""
    
    async def verify_websocket_token(websocket: WebSocket, token: Optional[str] = Query(None)):
        """Verify JWT token for WebSocket connections."""
        # Prefer HttpOnly cookie token
        from auth.src.cookies import ACCESS_TOKEN_COOKIE_NAME

        cookie_token = websocket.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        header_protocol = websocket.headers.get("sec-websocket-protocol")

        candidate_token = token or cookie_token

        # If a subprotocol header is provided, try to extract a token
        if not candidate_token and header_protocol:
            # Accept raw token or formats like "Bearer <token>" or "jwt,<token>"
            parts = [p.strip() for p in header_protocol.split(",")]
            for p in parts:
                if p.lower().startswith("bearer "):
                    candidate_token = p.split(" ", 1)[1]
                    break
                # If it looks like a JWT (three segments), accept it
                if p.count(".") == 2:
                    candidate_token = p
                    break

        if not candidate_token:
            await websocket.accept()
            await websocket.close(code=1008, reason="Authentication required")
            raise HTTPException(status_code=401, detail="Authentication required")

        payload = auth0_verifier.verify_access_token(candidate_token)
        if not payload:
            await websocket.accept()
            await websocket.close(code=1008, reason="Invalid authentication")
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
        return payload
    
    return verify_websocket_token


def require_auth_if_available():
    """
    Returns a dependency that requires auth only if AUTH is enabled.
    
    This is useful for endpoints that should be protected in production
    but accessible in local development.
    """
    auth_deps = get_auth_dependencies()
    return auth_deps['require_auth']


def require_admin_if_available():
    """
    Returns a dependency that requires admin auth only if AUTH is enabled.
    
    This is useful for admin endpoints that should be protected in production
    but accessible in local development.
    """
    auth_deps = get_auth_dependencies()
    return auth_deps['require_admin']


def optional_auth():
    """
    Returns a dependency for optional authentication.
    
    Always attempts authentication if credentials are provided,
    but doesn't require them.
    """
    auth_deps = get_auth_dependencies()
    return auth_deps['optional_auth']


def websocket_auth():
    """
    Returns WebSocket authentication dependency.
    
    Handles authentication for WebSocket connections with proper
    fallback for local development.
    """
    auth_deps = get_auth_dependencies()
    return auth_deps['websocket_auth']


def is_auth_available() -> bool:
    """Check if authentication is available and enabled."""
    return AUTH_AVAILABLE


# Convenience exports for backwards compatibility (imported in multiple services)

def get_cached_auth_dependencies():
    """Get cached auth dependencies to avoid re-initialization."""
    return get_auth_dependencies()


# Ensure AUTH_AVAILABLE reflects configuration at import time
get_auth_dependencies()
