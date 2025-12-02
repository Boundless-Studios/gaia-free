import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { getButtonClass, getCardClass } from '../lib/tailwindComponents';

const AuthError = () => {
  const [searchParams] = useSearchParams();
  const [errorDetails, setErrorDetails] = useState({
    reason: '',
    message: '',
    title: 'Authentication Error',
    description: 'There was a problem with your authentication.',
    icon: '🚫'
  });

  useEffect(() => {
    const reason = searchParams.get('reason') || 'unknown';
    const message = searchParams.get('message') || 'An unknown error occurred';

    let details = {
      reason,
      message,
      title: 'Authentication Error',
      description: message,
      icon: '🚫'
    };

    // Customize error messages based on reason
    switch (reason) {
      case 'not_authorized':
        details = {
          ...details,
          title: 'Access Not Authorized',
          description: 'Your email address is not authorized to access this system. Please contact an administrator to request access.',
          icon: '🔒'
        };
        break;
      case 'invalid_token':
        details = {
          ...details,
          title: 'Invalid Authentication',
          description: 'Your authentication token is invalid or has expired. Please try logging in again.',
          icon: '⏰'
        };
        break;
      case 'oauth_error':
        details = {
          ...details,
          title: 'OAuth Authentication Failed',
          description: 'There was a problem authenticating with your OAuth provider. Please try again.',
          icon: '⚠️'
        };
        break;
      case 'network_error':
        details = {
          ...details,
          title: 'Network Error',
          description: 'Unable to connect to the authentication service. Please check your connection and try again.',
          icon: '🌐'
        };
        break;
      default:
        details = {
          ...details,
          title: 'Authentication Error',
          description: message || 'An unexpected error occurred during authentication.',
          icon: '❌'
        };
    }

    setErrorDetails(details);
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-gaia-dark flex items-center justify-center p-4">
      <div className={`${getCardClass()} max-w-lg w-full p-8`}>
        {/* Icon */}
        <div className="text-6xl text-center mb-6">
          {errorDetails.icon}
        </div>

        {/* Title */}
        <h1 className="text-3xl font-bold text-white text-center mb-4">
          {errorDetails.title}
        </h1>

        {/* Description */}
        <p className="text-gaia-muted text-center mb-8 leading-relaxed">
          {errorDetails.description}
        </p>

        {/* Error Details (if different from description) */}
        {errorDetails.message && errorDetails.message !== errorDetails.description && (
          <div className="bg-gaia-dark/50 border border-gaia-border rounded-lg p-4 mb-6">
            <p className="text-xs text-gaia-muted mb-1">Error Message:</p>
            <p className="text-sm text-white">{errorDetails.message}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-3">
          <Link
            to="/login"
            className={`${getButtonClass('primary')} w-full text-center`}
          >
            Return to Login
          </Link>

          {errorDetails.reason === 'not_authorized' && (
            <div className="text-center">
              <p className="text-sm text-gaia-muted mb-2">
                Need access? Contact your administrator
              </p>
              <a
                href="mailto:admin@example.com?subject=Gaia Access Request"
                className={`${getButtonClass('secondary')} inline-block`}
              >
                Request Access
              </a>
            </div>
          )}
        </div>

        {/* Debug Info (only in development) */}
        {process.env.NODE_ENV === 'development' && (
          <details className="mt-8 text-xs text-gaia-muted">
            <summary className="cursor-pointer hover:text-white">Debug Information</summary>
            <pre className="mt-2 p-2 bg-gaia-dark rounded overflow-x-auto">
              {JSON.stringify({ 
                reason: errorDetails.reason, 
                message: errorDetails.message,
                params: Object.fromEntries(searchParams.entries())
              }, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
};

export default AuthError;