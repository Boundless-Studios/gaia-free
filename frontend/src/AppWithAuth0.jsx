import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { Auth0Provider } from './providers/Auth0Provider';
import { Auth0AuthProvider, DevAuthProvider, useAuth } from './contexts/Auth0Context';
import App from './App';
import PlayerPage from './components/player/PlayerPage.jsx';
import WelcomePage from './components/WelcomePage.jsx';
import AudioNotificationHost from './components/audio/AudioNotificationHost.jsx';
import { getButtonClass } from './lib/tailwindComponents';
import AuthError from './components/AuthError.jsx';
import RegistrationFlow from './components/RegistrationFlow.jsx';
import PromptManager from './components/admin/PromptManager.jsx';
import SceneInspector from './components/admin/SceneInspector.jsx';
import { AudioDebugPage } from './components/debug/AudioDebugPage.jsx';
import { AudioStreamProvider } from './context/audioStreamContext.jsx';
import CollaborativeEditorTest from './pages/CollaborativeEditorTest.jsx';

// Auth0 Callback Component
// Note: The actual redirect after login is handled by onRedirectCallback in Auth0Provider
// This component just shows a loading state while Auth0 processes the callback
const Auth0Callback = () => {
  const { isAuthenticated, isLoading, error, user } = useAuth0();

  React.useEffect(() => {
    if (!isLoading) {
      console.log('[AUTH0_DEBUG] Callback processed, isAuthenticated:', isAuthenticated);
      console.log('[AUTH0_DEBUG] User info:', user);
      // Note: Navigation is handled by onRedirectCallback in Auth0Provider
      // which receives appState.returnTo and navigates there
    }
  }, [isAuthenticated, isLoading, user]);
  
  if (error) {
    console.error('[AUTH0_DEBUG] Callback error:', error);
    return (
      <div className="min-h-screen bg-gaia-dark flex items-center justify-center">
        <div className="bg-gaia-light border border-gaia-error rounded-lg p-6 max-w-md">
          <h2 className="text-xl font-bold text-gaia-error mb-2">Authentication Error</h2>
          <p className="text-gaia-muted">{error.message}</p>
        </div>
      </div>
    );
  }
  
  console.log('[AUTH0_DEBUG] Callback loading, isLoading:', isLoading, 'isAuthenticated:', isAuthenticated);
  
  return (
    <div className="min-h-screen bg-gaia-dark flex items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gaia-accent"></div>
    </div>
  );
};

// Login Page Component
const LoginPage = () => {
  const { login } = useAuth();
  
  return (
    <div className="min-h-screen bg-gaia-dark flex items-center justify-center">
      <div className="bg-gaia-light border border-gaia-border rounded-lg p-8 max-w-md w-full">
        <h1 className="text-3xl font-bold text-white mb-2">Welcome to Gaia</h1>
        <p className="text-gaia-muted mb-6">Sign in to continue your adventure</p>
        <button
          onClick={login}
          className={getButtonClass('primary')}
        >
          Sign in with Auth0
        </button>
      </div>
    </div>
  );
};

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading, user, login, getAccessTokenSilently } = useAuth();
  const location = window.location;
  const [registrationStatus, setRegistrationStatus] = React.useState('checking'); // checking, pending, completed
  const [showRegistration, setShowRegistration] = React.useState(false);

  React.useEffect(() => {
    // If not authenticated and not loading, trigger login with returnTo
    if (!loading && !isAuthenticated) {
      const returnTo = location.pathname + location.search;
      login({ appState: { returnTo } });
    }
  }, [isAuthenticated, loading, login, location]);

  // Check registration status after authentication
  React.useEffect(() => {
    if (isAuthenticated && user) {
      checkRegistrationStatus();
    }
  }, [isAuthenticated, user]);

  const checkRegistrationStatus = async () => {
    try {
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/auth/registration-status', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const status = await response.json();
        // Show registration flow if user hasn't completed registration OR if they're awaiting approval
        if (status.registration_status === 'pending' || !status.is_authorized) {
          setRegistrationStatus('pending');
          setShowRegistration(true);
        } else {
          setRegistrationStatus('completed');
          setShowRegistration(false);
        }
      } else if (response.status === 403) {
        // User has pending registration or is awaiting approval
        setRegistrationStatus('pending');
        setShowRegistration(true);
      } else {
        // Assume completed if we can't check
        console.warn('Failed to check registration status, assuming completed');
        setRegistrationStatus('completed');
      }
    } catch (error) {
      console.error('Error checking registration status:', error);
      // Assume completed if we can't check
      setRegistrationStatus('completed');
    }
  };

  const handleRegistrationComplete = () => {
    setShowRegistration(false);
    setRegistrationStatus('completed');
  };

  if (loading || registrationStatus === 'checking') {
    return (
      <div className="min-h-screen bg-gaia-dark flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gaia-accent"></div>
      </div>
    );
  }

  // If still not authenticated after effect, show loading
  if (!isAuthenticated || !user) {
    return (
      <div className="min-h-screen bg-gaia-dark flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gaia-accent"></div>
      </div>
    );
  }

  // Show registration flow if needed
  if (showRegistration) {
    return <RegistrationFlow onComplete={handleRegistrationComplete} />;
  }

  return children;
};

// User Menu Component
export const UserMenu = () => {
  const { user, logout } = useAuth();
  const [showMenu, setShowMenu] = React.useState(false);

  if (!user) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="flex items-center gap-1 bg-gaia-light border border-gaia-border rounded px-2 py-1 hover:bg-gaia-border transition-colors"
      >
        {user.picture_url ? (
          <img
            src={user.picture_url}
            alt={user.username}
            className="w-5 h-5 rounded-full"
          />
        ) : (
          <div className="w-5 h-5 rounded-full bg-gaia-accent flex items-center justify-center text-white text-xs">
            {(user.username || user.email)[0].toUpperCase()}
          </div>
        )}
        <span className="text-xs text-white">
          {user.username || user.email}
        </span>
        <svg className="w-3 h-3 text-gaia-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {showMenu && (
        <div className="absolute right-0 mt-2 w-48 bg-gaia-light border border-gaia-border rounded-lg shadow-lg overflow-hidden z-50">
          <div className="px-4 py-3 border-b border-gaia-border">
            <p className="text-xs text-gaia-muted">Signed in as</p>
            <p className="text-sm text-white font-medium truncate">{user.email}</p>
            {user.is_admin && (
              <span className="inline-block mt-1 px-2 py-0.5 bg-gaia-accent text-xs text-white rounded">
                Admin
              </span>
            )}
          </div>
          <button
            onClick={() => {
              setShowMenu(false);
              logout();
            }}
            className="w-full text-left px-4 py-2 text-sm text-white hover:bg-gaia-border transition-colors"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
};

// Main App with Auth0
const AppWithAuth0 = () => {
  // Check if we're in production mode
  const isProduction = window.location.hostname !== 'localhost' &&
                       window.location.hostname !== '127.0.0.1' &&
                       !window.location.hostname.startsWith('192.168.');

  // Check if Auth0 is configured
  const auth0Configured = import.meta.env.VITE_AUTH0_DOMAIN && import.meta.env.VITE_AUTH0_CLIENT_ID;

  // Use Auth0 if configured OR if explicitly required
  // NEW: Auto-enable Auth0 in dev if credentials are configured
  const requireAuth = isProduction || import.meta.env.VITE_REQUIRE_AUTH === 'true' || auth0Configured;

  // Log the authentication mode
  console.log(`🔐 Authentication mode: ${requireAuth && auth0Configured ? 'ENABLED' : 'DISABLED (Dev/Local)'}`);
  console.log(`   Auth0 Configured: ${auth0Configured ? 'YES' : 'NO'}`);
  console.log(`   Hostname: ${window.location.hostname}`);
  console.log(`   Is Production: ${isProduction}`);
  console.log(`   VITE_REQUIRE_AUTH: ${import.meta.env.VITE_REQUIRE_AUTH || 'not set'}`);

  // If Auth0 is not configured, render with a dev auth provider
  if (!auth0Configured) {
    if (requireAuth) {
      console.warn('⚠️ Authentication required but Auth0 not configured. Running in bypass mode.');
    }
    return (
      <Router>
        <DevAuthProvider>
          <AudioNotificationHost />
          <Routes>
            {/* Landing page and session-based routes */}
            <Route path="/" element={<WelcomePage />} />
            <Route path="/:sessionId/dm" element={<App />} />
            <Route path="/:sessionId/player" element={<PlayerPage />} />

            {/* Admin routes */}
            <Route path="/admin/prompts" element={<PromptManager />} />
            <Route path="/admin/scenes" element={<SceneInspector />} />

            {/* Debug routes */}
            <Route path="/admin/debug-audio" element={
              <AudioStreamProvider>
                <AudioDebugPage />
              </AudioStreamProvider>
            } />
            <Route path="/test/collaborative-editor" element={<CollaborativeEditorTest />} />

            {/* Legacy route redirects */}
            <Route path="/player" element={<Navigate to="/" replace />} />
            <Route path="/auth-error" element={<AuthError />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </DevAuthProvider>
      </Router>
    );
  }
  
  // Production mode with Auth0 - wrap everything in Auth0Provider
  return (
    <Router>
      <Auth0Provider>
        <Auth0AuthProvider>
          <AudioNotificationHost />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/callback" element={<Auth0Callback />} />
            <Route path="/auth-error" element={<AuthError />} />

            {/* Debug routes - NO AUTH REQUIRED for local testing */}
            <Route
              path="/admin/debug-audio"
              element={
                <AudioStreamProvider>
                  <AudioDebugPage />
                </AudioStreamProvider>
              }
            />
            <Route
              path="/test/collaborative-editor"
              element={<CollaborativeEditorTest />}
            />

            {/* Landing page and session-based routes */}
            <Route
              path="/"
              element={<WelcomePage />}
            />
            <Route
              path="/:sessionId/dm"
              element={
                <ProtectedRoute>
                  <App />
                </ProtectedRoute>
              }
            />
            <Route
              path="/:sessionId/player"
              element={
                <ProtectedRoute>
                  <PlayerPage />
                </ProtectedRoute>
              }
            />

            {/* Admin routes */}
            <Route
              path="/admin/prompts"
              element={
                <ProtectedRoute>
                  <PromptManager />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/scenes"
              element={
                <ProtectedRoute>
                  <SceneInspector />
                </ProtectedRoute>
              }
            />

            {/* Legacy route redirects */}
            <Route path="/player" element={<Navigate to="/" replace />} />
          </Routes>
        </Auth0AuthProvider>
      </Auth0Provider>
    </Router>
  );
};

export default AppWithAuth0;
