"""
Auth0 authentication endpoints for FastAPI

Provides endpoints for Auth0 authentication flow and user management.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from db.src import get_async_db
from auth.src.models import User, OAuthAccount
from auth.src.middleware import CurrentUser, OptionalUser
from auth.src.auth0_jwt_verifier import get_auth0_verifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth0", tags=["auth0"])


@router.get("/verify")
async def verify_token(
    current_user: CurrentUser
) -> Dict[str, Any]:
    """
    Verify the current Auth0 token and return user information
    
    This endpoint is called by the frontend after receiving an Auth0 token
    to verify it's valid and get user details.
    
    Returns:
        User information from the verified token
    """
    return {
        "user_id": str(current_user.user_id),
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.display_name,
        "picture_url": current_user.avatar_url,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "email_verified": (current_user.user_metadata or {}).get("email_verified"),
        "created_at": current_user.created_at.isoformat(),
        "updated_at": current_user.updated_at.isoformat()
    }


@router.get("/user")
async def get_current_user_info(
    current_user: CurrentUser
) -> Dict[str, Any]:
    """
    Get current authenticated user information
    
    Returns:
        Current user details
    """
    return {
        "user_id": str(current_user.user_id),
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.display_name,
        "picture_url": current_user.avatar_url,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "email_verified": (current_user.user_metadata or {}).get("email_verified")
    }


@router.post("/logout")
async def logout(
    response: Response,
    current_user: OptionalUser = None
) -> Dict[str, str]:
    """
    Logout endpoint - clears any server-side session data
    
    Note: Auth0 handles the actual logout on their end.
    This endpoint is for clearing any server-side state.
    
    Returns:
        Success message
    """
    # Clear any cookies if we're using them
    try:
        from auth.src.cookies import ACCESS_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_NAME
        response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME)
        response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME)
    except ImportError:
        pass
    
    return {"message": "Logged out successfully"}


@router.get("/check")
async def check_auth(
    user: OptionalUser = None
) -> Dict[str, Any]:
    """
    Check if user is authenticated without requiring auth
    
    Returns:
        Authentication status and user info if authenticated
    """
    if user:
        return {
            "authenticated": True,
            "user": {
                "user_id": str(user.user_id),
                "email": user.email,
                "username": user.username,
                "is_admin": user.is_admin
            }
        }
    else:
        return {
            "authenticated": False,
            "user": None
        }


@router.get("/config")
async def get_auth_config() -> Dict[str, Any]:
    """
    Get Auth0 configuration for frontend
    
    Returns public Auth0 configuration that the frontend needs.
    Does not include sensitive information like client secrets.
    
    Returns:
        Public Auth0 configuration
    """
    import os
    
    domain = os.getenv("AUTH0_DOMAIN")
    audience = os.getenv("AUTH0_AUDIENCE")
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 not configured"
        )
    
    return {
        "domain": domain,
        "audience": audience,
        "issuer": f"https://{domain}/"
    }
