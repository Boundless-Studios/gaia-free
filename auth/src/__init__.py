"""
Auth0 Authentication Module for Gaia

This module provides Auth0 authentication with RS256 JWT token verification
and database-backed user storage.
"""

from .models import User, OAuthAccount, AccessControl, AuthProvider, PermissionLevel
from .auth0_jwt_verifier import get_auth0_verifier

__all__ = [
    'User',
    'OAuthAccount',
    'AccessControl',
    'AuthProvider',
    'PermissionLevel',
    'get_auth0_verifier'
]