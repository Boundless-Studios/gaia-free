"""
Secure cookie management utilities for OAuth2/JWT tokens
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Response
from fastapi.responses import RedirectResponse

# Cookie configuration from environment
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)  # None = same-origin
COOKIE_PATH = os.getenv("COOKIE_PATH", "/")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"  # HTTPS only
COOKIE_HTTPONLY = True  # Always HttpOnly for security
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "none").lower()  # lax, strict, or none
ACCESS_TOKEN_COOKIE_NAME = "access_token"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_expires_minutes: int = 15,
    refresh_expires_days: int = 7
) -> None:
    """
    Set secure authentication cookies
    
    Args:
        response: FastAPI response object
        access_token: JWT access token
        refresh_token: JWT refresh token
        access_expires_minutes: Access token expiration in minutes
        refresh_expires_days: Refresh token expiration in days
    """
    # Set access token cookie
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        max_age=access_expires_minutes * 60,  # Convert to seconds
        expires=datetime.utcnow() + timedelta(minutes=access_expires_minutes),
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN,
        secure=COOKIE_SECURE,
        httponly=COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE
    )
    
    # Set refresh token cookie
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=refresh_expires_days * 24 * 60 * 60,  # Convert to seconds
        expires=datetime.utcnow() + timedelta(days=refresh_expires_days),
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN,
        secure=COOKIE_SECURE,
        httponly=COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Clear authentication cookies (used for logout)
    
    Args:
        response: FastAPI response object
    """
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN
    )
    
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN
    )


def create_redirect_with_cookies(
    redirect_url: str,
    access_token: str,
    refresh_token: str,
    access_expires_minutes: int = 15,
    refresh_expires_days: int = 7
) -> RedirectResponse:
    """
    Create a redirect response with authentication cookies set
    
    Args:
        redirect_url: URL to redirect to (without tokens)
        access_token: JWT access token
        refresh_token: JWT refresh token
        access_expires_minutes: Access token expiration in minutes
        refresh_expires_days: Refresh token expiration in days
    
    Returns:
        RedirectResponse with secure cookies set
    """
    response = RedirectResponse(url=redirect_url)
    
    set_auth_cookies(
        response=response,
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_minutes=access_expires_minutes,
        refresh_expires_days=refresh_expires_days
    )
    
    # Security headers to prevent referrer/token leakage and caching
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    
    return response


def get_cookie_config() -> dict:
    """
    Get current cookie configuration for debugging/logging
    
    Returns:
        Dictionary with cookie configuration
    """
    return {
        "domain": COOKIE_DOMAIN,
        "path": COOKIE_PATH,
        "secure": COOKIE_SECURE,
        "httponly": COOKIE_HTTPONLY,
        "samesite": COOKIE_SAMESITE,
        "access_token_name": ACCESS_TOKEN_COOKIE_NAME,
        "refresh_token_name": REFRESH_TOKEN_COOKIE_NAME
    }
