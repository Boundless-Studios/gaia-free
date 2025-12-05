import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { API_CONFIG } from '../config/api';
import apiService from '../services/apiService';

const AUTH0_DEFAULT_SCOPES = ['openid', 'profile', 'email', 'offline_access'];
const AUTH0_AUDIENCE = import.meta.env.VITE_AUTH0_AUDIENCE || '';

const AuthContext = createContext(null);

const ensureAuthOptions = (options = {}) => {
  const merged = { ...options };
  const authParams = { ...(options.authorizationParams || {}) };

  if (AUTH0_AUDIENCE && !authParams.audience) {
    authParams.audience = AUTH0_AUDIENCE;
  }

  const currentScopes = new Set(
    (authParams.scope || '')
      .split(' ')
      .map((scope) => scope.trim())
      .filter(Boolean)
  );
  AUTH0_DEFAULT_SCOPES.forEach((scope) => currentScopes.add(scope));
  authParams.scope = Array.from(currentScopes).join(' ');

  merged.authorizationParams = authParams;
  return merged;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export function Auth0AuthProvider({ children }) {
  const {
    isAuthenticated,
    isLoading,
    user: auth0User,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently: auth0GetAccessTokenSilently,
    getIdTokenClaims
  } = useAuth0();

  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // Sync user data when Auth0 authentication changes
  useEffect(() => {
    const syncUserData = async () => {
      if (isAuthenticated && auth0User) {
        try {
          // Get the access token for API calls
          const token = await auth0GetAccessTokenSilently(ensureAuthOptions());
          setAccessToken(token);

          // Verify token with backend; enforce authorization
          try {
            const userData = await apiService.verifyAuth0Token(token);
            // Merge GAIA user data with Auth0 sub for audio queue matching
            // The backend uses auth0User.sub for WebSocket user identification
            setUser({
              ...userData,
              auth0_sub: auth0User.sub  // Auth0 subject ID (e.g., "google-oauth2|...")
            });
          } catch (error) {
            console.error('Failed to verify user with backend:', error);
            // If not authorized, route to auth error and log out
            const status = error?.status;
            if (status === 403) {
              navigate('/auth-error?reason=not_authorized');
            } else if (status === 401) {
              navigate('/auth-error?reason=invalid_token');
            } else {
              navigate('/auth-error?reason=oauth_error');
            }
            // Mark as unauthorized locally
            setUser(null);
            return;
          }
        } catch (error) {
          console.error('Error syncing user data:', error);
          navigate('/auth-error?reason=network_error');
          setUser(null);
          return;
        }
      } else {
        setUser(null);
        setAccessToken(null);
      }
      setLoading(false);
    };

    if (!isLoading) {
      syncUserData();
    }
  }, [isAuthenticated, isLoading, auth0User, auth0GetAccessTokenSilently]);

  const login = useCallback((options = {}) => {
    loginWithRedirect(ensureAuthOptions(options));
  }, [loginWithRedirect]);

  const logout = useCallback(() => {
    // Clear any local state
    setUser(null);
    setAccessToken(null);
    
    // Logout from Auth0
    auth0Logout({
      logoutParams: {
        returnTo: import.meta.env.VITE_AUTH0_LOGOUT_URL || window.location.origin
      }
    });
  }, [auth0Logout]);

  const refreshAccessToken = useCallback(async () => {
    try {
      const token = await auth0GetAccessTokenSilently(
        ensureAuthOptions({
          cacheMode: 'off' // Force token refresh
        })
      );
      setAccessToken(token);
      return token;
    } catch (error) {
      const errorMessage = `${error?.error || ''} ${error?.error_description || error?.message || ''}`.trim();
      const missingRefreshToken =
        error?.error === 'missing_refresh_token' ||
        /missing refresh token/i.test(errorMessage);

      if (missingRefreshToken) {
        console.warn('No refresh token available; prompting user to reauthenticate');
        await loginWithRedirect(
          ensureAuthOptions({
            authorizationParams: {
              prompt: 'login'
            }
          })
        );
        return null;
      }

      console.error('Failed to refresh token:', error);
      throw error;
    }
  }, [auth0GetAccessTokenSilently, loginWithRedirect]);

  const getAccessTokenSilently = useCallback(
    async (options = {}) => auth0GetAccessTokenSilently(ensureAuthOptions(options)),
    [auth0GetAccessTokenSilently]
  );

  // Handle authentication errors (expired tokens, etc.)
  const handleAuthError = useCallback((error) => {
    console.error('🔐 Authentication error detected, logging out:', error);
    logout();
  }, [logout]);

  const value = {
    user,
    accessToken,
    loading: loading || isLoading,
    isAuthenticated,
    login,
    logout,
    refreshAccessToken,
    getAccessTokenSilently,
    handleAuthError
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// Dev/bypass provider used when Auth0 is not required or not configured
export function DevAuthProvider({ children }) {
  const value = {
    user: null,
    accessToken: null,
    loading: false,
    isAuthenticated: false,
    login: () => {},
    logout: () => {},
    refreshAccessToken: async () => null,
    getAccessTokenSilently: async () => null,
    handleAuthError: () => {}
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
