import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCardClass } from '../lib/tailwindComponents';

const AuthCallback = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // The AuthContext will handle the tokens from the URL
    // We just need to wait a moment and redirect
    const timer = setTimeout(() => {
      navigate('/');
    }, 1500);

    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="min-h-screen bg-gaia-dark flex items-center justify-center">
      <div className={`${getCardClass()} text-center`}>
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gaia-accent mx-auto mb-4"></div>
        <h2 className="text-xl font-semibold text-white mb-2">
          Authenticating...
        </h2>
        <p className="text-gaia-muted">
          Setting up your adventure, please wait...
        </p>
      </div>
    </div>
  );
};

export default AuthCallback;