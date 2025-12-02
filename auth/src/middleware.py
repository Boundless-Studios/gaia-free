"""
Authentication middleware for protecting API routes

Provides dependency injection for FastAPI routes to require authentication.
Uses Auth0 JWT tokens exclusively.
"""

import logging
import os
from typing import Optional, Annotated, Dict, Any
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from db.src import get_async_db
from auth.src.models import User, OAuthAccount, RegistrationStatus
from auth.src.auth0_jwt_verifier import get_auth0_verifier

logger = logging.getLogger(__name__)

# Security scheme for Swagger UI and REST auth (do not auto-error to allow cookie fallback)
security = HTTPBearer(auto_error=False)

_ENVIRONMENT = (os.getenv("GAIA_ENV") or os.getenv("ENVIRONMENT") or "development").lower()
_AUTO_PROVISION_FLAG = os.getenv("AUTH_AUTO_PROVISION_USERS")


def _str_to_bool(value: Optional[str]) -> bool:
    """Convert common truthy values to bool."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _should_auto_provision_users() -> bool:
    """
    Determine if Auth0 users should be auto-provisioned in the database.

    Controlled via AUTH_AUTO_PROVISION_USERS or defaults to enabled for local/dev environments.
    """
    if _AUTO_PROVISION_FLAG is not None:
        return _str_to_bool(_AUTO_PROVISION_FLAG)
    return _ENVIRONMENT in {"local", "development", "dev"}


async def _ensure_auth0_account_link(
    db: AsyncSession,
    user: User,
    auth0_user_id: str,
) -> None:
    """Ensure an OAuthAccount entry exists linking the user to Auth0."""
    from sqlalchemy import select  # Local import avoids global dependency at module import time

    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "auth0",
            OAuthAccount.provider_account_id == auth0_user_id,
        )
    )
    oauth_account = result.scalar_one_or_none()
    if oauth_account:
        return

    oauth_account = OAuthAccount(
        user_id=user.user_id,
        provider="auth0",
        provider_account_id=auth0_user_id,
    )
    db.add(oauth_account)


async def _auto_provision_auth0_user(
    db: AsyncSession,
    auth0_user_id: str,
    email: str,
    user_info: Dict[str, Any],
) -> Optional[User]:
    """
    Auto-create a local user record for an Auth0 identity when permitted.

    Returns the persisted User on success or None on failure.
    """
    from sqlalchemy import select  # Delayed import keeps function self-contained

    display_name = (
        user_info.get("name")
        or user_info.get("nickname")
        or (email.split("@")[0] if email else None)
    )
    metadata = {
        "auto_provisioned": True,
        "auth_provider": "auth0",
        "auth0_user_id": auth0_user_id,
    }

    user = User(
        email=email,
        display_name=display_name,
        is_active=False,
        is_admin=False,
        user_metadata=metadata,
        registration_status=RegistrationStatus.PENDING.value,
        last_login=datetime.now(timezone.utc),
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Another request may have created the user concurrently; try to fetch it
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        if not existing_user:
            logger.error("Auto-provision rollback; user %s still missing after IntegrityError", email)
            return None
        await _ensure_auth0_account_link(db, existing_user, auth0_user_id)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
        logger.info("Linked existing user %s to Auth0 account %s", email, auth0_user_id)
        return existing_user

    await _ensure_auth0_account_link(db, user, auth0_user_id)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            logger.info("Recovered auto-provision race for %s; using existing record", email)
            return existing_user
        logger.error("Failed to commit auto-provisioned user %s: %s", email, exc)
        return None

    await db.refresh(user)
    logger.info("Auto-provisioned Auth0 user %s (%s)", auth0_user_id, email)
    return user


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    request: Request,
    db: AsyncSession = Depends(get_async_db)
) -> User:
    """
    Get current authenticated user from Auth0 JWT token
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        User object if authenticated
        
    Raises:
        HTTPException: If authentication fails
    """
    logger.debug(f"🔐 [MIDDLEWARE] Starting user authentication")
    logger.debug(f"🔐 [MIDDLEWARE] Request path: {request.url.path}")
    logger.debug(f"🔐 [MIDDLEWARE] Headers: Authorization={'present' if 'authorization' in request.headers else 'missing'}")
    
    token = None
    # Prefer Authorization header if provided
    if credentials and credentials.credentials:
        token = credentials.credentials
        logger.debug(f"🔐 [MIDDLEWARE] Token extracted from Authorization header")
        logger.debug(f"🔐 [MIDDLEWARE] Token preview: {token[:50]}..." if len(token) > 50 else f"Token: {token}")
    else:
        # Fallback to cookie token if needed
        try:
            from auth.src.cookies import ACCESS_TOKEN_COOKIE_NAME
            token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
            if token:
                logger.debug(f"🔐 [MIDDLEWARE] Token extracted from cookie")
        except Exception as e:
            logger.debug(f"🔐 [MIDDLEWARE] Failed to check cookie: {e}")
            token = None
    
    if not token:
        logger.warning(f"🔐 [MIDDLEWARE] No token found in request")
        logger.debug(f"🔐 [MIDDLEWARE] Credentials object: {credentials}")
        logger.debug(f"🔐 [MIDDLEWARE] Request cookies: {list(request.cookies.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify Auth0 token
    logger.debug(f"🔐 [MIDDLEWARE] Getting Auth0 verifier")
    auth0_verifier = get_auth0_verifier()
    if not auth0_verifier:
        logger.error(f"🔐 [MIDDLEWARE] Auth0 verifier not available")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 not configured"
        )
    
    logger.debug(f"🔐 [MIDDLEWARE] Calling Auth0 verifier to validate token")
    user_info = auth0_verifier.verify_token(token)
    if not user_info:
        logger.warning(f"🔐 [MIDDLEWARE] Token verification failed - invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Auth0 token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user information from Auth0 token
    auth0_user_id = user_info.get("user_id")  # e.g., "auth0|123456"
    email = user_info.get("email")
    
    if not auth0_user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Auth0 token payload - missing user_id or email",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user exists with this Auth0 ID
    from sqlalchemy import select
    
    # First try to find by OAuth account
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "auth0",
            OAuthAccount.provider_account_id == auth0_user_id
        )
    )
    oauth_account = result.scalar_one_or_none()
    
    if oauth_account:
        result = await db.execute(
            select(User).where(User.user_id == oauth_account.user_id)
        )
        user = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user:
            try:
                await _ensure_auth0_account_link(db, user, auth0_user_id)
                await db.commit()
                logger.info("Linked existing user %s to Auth0 account %s", user.user_id, auth0_user_id)
            except Exception as exc:  # noqa: BLE001
                try:
                    await db.rollback()
                except Exception:  # noqa: BLE001
                    pass
                logger.warning("🔐 [MIDDLEWARE] Could not link OAuth account for %s: %s", email, exc)
        elif _should_auto_provision_users():
            logger.info("Auto-provisioning Auth0 user %s (%s)", auth0_user_id, email)
            user = await _auto_provision_auth0_user(db, auth0_user_id, email, user_info)

    if not user:
        logger.warning(
            "🔐 [MIDDLEWARE] Login denied: email not registered (%s)",
            email,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized. Please contact an administrator to request access."
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check registration status - users must complete registration before accessing the system
    # Allow access only to registration-related endpoints
    if user.registration_status == RegistrationStatus.PENDING.value:
        allowed_paths = [
            "/api/auth/eula",
            "/api/auth/complete-registration",
            "/api/auth/request-access",
            "/api/auth/registration-status",
            "/api/auth/logout",
            "/api/auth0/logout",
            "/api/auth0/verify",  # Allow token verification for pending users
        ]
        if not any(request.url.path.startswith(path) for path in allowed_paths):
            logger.warning(
                f"Registration incomplete for user {user.email}, blocking access to {request.url.path}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration incomplete. Please accept the EULA to continue.",
                headers={"X-Registration-Required": "true"}
            )

    # Check if user has completed registration but is not yet active (awaiting admin approval)
    if user.registration_status == RegistrationStatus.COMPLETED.value and not user.is_active:
        allowed_paths = [
            "/api/auth/registration-status",
            "/api/auth/logout",
            "/api/auth0/logout",
            "/api/auth0/verify",
        ]
        if not any(request.url.path.startswith(path) for path in allowed_paths):
            logger.warning(
                f"User {user.email} is awaiting approval, blocking access to {request.url.path}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your access request is pending admin approval.",
                headers={"X-Awaiting-Approval": "true"}
            )

    # Check if user account is disabled (not part of registration flow)
    # This should only apply to users who have completed registration but were explicitly deactivated
    if not user.is_active and user.registration_status == RegistrationStatus.COMPLETED.value:
        # Already handled above - user is awaiting approval
        pass
    elif not user.is_active and user.registration_status != RegistrationStatus.PENDING.value:
        # User is inactive for some other reason (account disabled, banned, etc.)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get current user and verify they are active
    
    Args:
        current_user: User from get_current_user dependency
        
    Returns:
        User object if active
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    Get current user and verify they are an admin
    
    Args:
        current_user: Active user from get_current_active_user dependency
        
    Returns:
        User object if admin
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    request: Request = None,
    db: AsyncSession = Depends(get_async_db)
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None
    Uses Auth0 tokens exclusively
    
    Args:
        authorization: Optional Authorization header
        db: Database session
        
    Returns:
        User object if authenticated, None otherwise
    """
    token = None
    if authorization:
        auth0_verifier = get_auth0_verifier()
        if auth0_verifier:
            token = auth0_verifier.extract_token_from_header(authorization)
    if not token and request is not None:
        try:
            from auth.src.cookies import ACCESS_TOKEN_COOKIE_NAME
            token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        except Exception:
            token = None
    # Also check query parameters for token (used by audio streaming)
    # SECURITY: Only accept query-string tokens for audio endpoints to prevent
    # token leakage via logs, browser history, and Referer headers
    if not token and request is not None:
        try:
            path = str(request.url.path) if hasattr(request.url, 'path') else str(request.url)
            is_audio_endpoint = path.startswith('/api/audio/stream') or path.startswith('/api/media/audio')
            if is_audio_endpoint:
                token = request.query_params.get("token")
        except Exception:
            token = None

    if not token:
        return None
    
    # Verify Auth0 token
    auth0_verifier = get_auth0_verifier()
    if not auth0_verifier:
        return None
    
    user_info = auth0_verifier.verify_token(token)
    if not user_info:
        return None
    
    # Extract user information
    auth0_user_id = user_info.get("user_id")
    email = user_info.get("email")
    
    if not auth0_user_id or not email:
        return None
    
    # Look up user by Auth0 ID or email
    from sqlalchemy import select
    
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "auth0",
            OAuthAccount.provider_account_id == auth0_user_id
        )
    )
    oauth_account = result.scalar_one_or_none()
    
    if oauth_account:
        result = await db.execute(
            select(User).where(User.user_id == oauth_account.user_id)
        )
        user = result.scalar_one_or_none()
    else:
        # Try by email for migration
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Create OAuth account entry for migration
            oauth_account = OAuthAccount(
                user_id=user.user_id,
                provider="auth0",
                provider_account_id=auth0_user_id
            )
            db.add(oauth_account)
            await db.commit()
    
    if user and user.is_active:
        return user
    
    return None


class PermissionChecker:
    """
    Dependency for checking specific permissions
    
    Usage:
        @app.get("/campaigns/{campaign_id}")
        async def get_campaign(
            campaign_id: str,
            user: User = Depends(
                PermissionChecker("campaign", "read")
            )
        ):
            ...
    """
    
    def __init__(self, resource_type: str, permission_level: str):
        self.resource_type = resource_type
        self.permission_level = permission_level
    
    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_async_db)
    ) -> User:
        """
        Check if user has permission for the resource
        
        Args:
            request: FastAPI request to get resource_id from path
            current_user: Authenticated user
            db: Database session
            
        Returns:
            User if permission granted
            
        Raises:
            HTTPException: If permission denied
        """
        # Admin users have all permissions
        if current_user.is_admin:
            return current_user
        
        # Extract resource_id from path parameters
        resource_id = request.path_params.get(f"{self.resource_type}_id")
        if not resource_id:
            # If no specific resource, check for global permission
            resource_id = "global"
        
        # Check permission
        from sqlalchemy import select, and_
        from auth.src.models import AccessControl
        
        result = await db.execute(
            select(AccessControl).where(
                and_(
                    AccessControl.user_id == current_user.user_id,
                    AccessControl.resource_type == self.resource_type,
                    AccessControl.resource_id == resource_id,
                    AccessControl.permission_level == self.permission_level
                )
            )
        )
        permission = result.scalar_one_or_none()
        
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No {self.permission_level} permission for {self.resource_type}"
            )
        
        # Check if permission has expired
        if permission.expires_at and permission.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission has expired"
            )
        
        return current_user


# Session management is now handled entirely by Auth0
# Local session tracking has been removed in favor of Auth0's session management


# Convenience type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
