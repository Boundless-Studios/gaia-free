import React from 'react';
import { Auth0Provider as Auth0ProviderBase } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';

export function Auth0Provider({ children }) {
  const navigate = useNavigate();
  
  // Auth0 configuration from environment variables
  const domain = import.meta.env.VITE_AUTH0_DOMAIN;
  const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID;
  const audience = import.meta.env.VITE_AUTH0_AUDIENCE;
  const redirectUri = import.meta.env.VITE_AUTH0_REDIRECT_URI || window.location.origin;
  
  const onRedirectCallback = (appState) => {
    // Use the router to navigate to the returnTo page (or home if not set)
    navigate(appState?.returnTo || window.location.pathname);
  };

  if (!domain || !clientId) {
    console.error('Auth0 configuration missing. Please set VITE_AUTH0_DOMAIN and VITE_AUTH0_CLIENT_ID');
    return <div>Auth0 configuration error - check environment variables</div>;
  }

  return (
    <Auth0ProviderBase
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: redirectUri,
        audience: audience,
        scope: "openid profile email offline_access"
      }}
      onRedirectCallback={onRedirectCallback}
      cacheLocation="localstorage"
      useRefreshTokens={true}
    >
      {children}
    </Auth0ProviderBase>
  );
}