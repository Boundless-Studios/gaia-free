import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/Auth0Context.jsx';
import apiService from '../services/apiService.js';
import './RegistrationFlow.css';

/**
 * RegistrationFlow component handles the user registration process.
 *
 * Flow:
 * 1. Check if user has completed registration
 * 2. If not, show EULA acceptance screen
 * 3. Allow user to opt-in to emails
 * 4. Complete registration on backend
 * 5. Show success message and redirect
 */
const RegistrationFlow = ({ onComplete }) => {
  const { isAuthenticated, user, getAccessTokenSilently } = useAuth();
  const [step, setStep] = useState('loading'); // loading, eula, completing, completed, error
  const [eulaData, setEulaData] = useState(null);
  const [registrationStatus, setRegistrationStatus] = useState(null);
  const [eulaAccepted, setEulaAccepted] = useState(false);
  const [emailOptIn, setEmailOptIn] = useState(false);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Check registration status on mount
  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    checkRegistrationStatus();
  }, [isAuthenticated]);

  const checkRegistrationStatus = async () => {
    try {
      const token = await getAccessTokenSilently();

      // Check registration status
      const statusResponse = await fetch('/api/auth/registration-status', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!statusResponse.ok) {
        throw new Error('Failed to check registration status');
      }

      const status = await statusResponse.json();
      setRegistrationStatus(status);

      // If completed but not authorized, show pending approval page
      if (status.registration_status === 'completed' && !status.is_authorized) {
        setStep('pending-approval');
        return;
      }

      // If completed and authorized, redirect to app
      if (status.registration_status === 'completed' && status.is_authorized) {
        setStep('completed');
        if (onComplete) {
          onComplete();
        }
        return;
      }

      // Load EULA
      const eulaResponse = await fetch('/api/auth/eula', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!eulaResponse.ok) {
        throw new Error('Failed to load EULA');
      }

      const eula = await eulaResponse.json();
      setEulaData(eula);
      setStep('eula');
    } catch (err) {
      console.error('Error checking registration status:', err);
      setError(err.message || 'Failed to load registration information');
      setStep('error');
    }
  };

  const handleRequestAccess = async () => {
    if (!eulaAccepted) {
      setError('You must accept the EULA to continue');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const token = await getAccessTokenSilently();

      const response = await fetch('/api/auth/request-access', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          eula_accepted: eulaAccepted,
          eula_version: eulaData.version,
          email_opt_in: emailOptIn,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to request access');
      }

      setStep('pending-approval');
    } catch (err) {
      console.error('Error requesting access:', err);
      setError(err.message || 'Failed to request access');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Loading state
  if (step === 'loading') {
    return (
      <div className="registration-flow">
        <div className="registration-container">
          <div className="loading-spinner">
            <div className="spinner"></div>
            <p>Loading registration information...</p>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (step === 'error') {
    return (
      <div className="registration-flow">
        <div className="registration-container">
          <div className="error-state">
            <div className="error-icon">⚠️</div>
            <h2>Registration Error</h2>
            <p>{error}</p>
            <button onClick={checkRegistrationStatus} className="retry-button">
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Pending approval state
  if (step === 'pending-approval') {
    return (
      <div className="registration-flow pending-approval-flow">
        <div className="pending-approval-background">
          <div className="pending-approval-overlay">
            <div className="pending-approval-content">
              <h2>Welcome to Fable Table</h2>
              <p className="pending-message">Your adventure begins soon</p>
              <div className="pending-details">
                <p>Your access request has been submitted and is awaiting admin approval.</p>
                <p>You'll receive an email at <strong>{user?.email}</strong> once you've been granted access.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Completed state
  if (step === 'completed') {
    return (
      <div className="registration-flow">
        <div className="registration-container">
          <div className="success-state">
            <div className="success-icon">✅</div>
            <h2>Registration Complete!</h2>
            <p>Welcome to Gaia! You now have full access to all features.</p>
            <div className="redirect-message">Redirecting you to the app...</div>
          </div>
        </div>
      </div>
    );
  }

  // EULA acceptance step
  return (
    <div className="registration-flow">
      <div className="registration-container">
        <div className="registration-header">
          <div className="alpha-badge">🔒 PRIVATE ALPHA</div>
          <h1>Welcome to Gaia!</h1>
          <p className="alpha-warning">
            You are accessing a <strong>private alpha build</strong> of GAIA.
            All content is confidential and protected by a Non-Disclosure Agreement (NDA).
          </p>
          <div className="nda-highlights">
            <div className="nda-item">
              <span className="icon">🚫</span>
              <span>No Streaming or Recording</span>
            </div>
            <div className="nda-item">
              <span className="icon">🤐</span>
              <span>Confidential Information</span>
            </div>
            <div className="nda-item">
              <span className="icon">🎮</span>
              <span>Playtesting Only</span>
            </div>
          </div>
        </div>

        <div className="eula-container">
          <div className="eula-header">
            <h2>GAIA Playtester Agreement (NDA + EULA)</h2>
            <span className="eula-version">Version {eulaData?.version}</span>
          </div>
          <div className="eula-content">
            <pre>{eulaData?.content}</pre>
          </div>
        </div>

        <div className="registration-form">
          <div className="nda-warning-box">
            <div className="warning-icon">⚠️</div>
            <div className="warning-content">
              <strong>Important NDA Requirements:</strong>
              <ul>
                <li>All game content and information is <strong>confidential</strong></li>
                <li><strong>DO NOT</strong> stream, record, or share screenshots without written permission</li>
                <li><strong>DO NOT</strong> discuss game details publicly or with non-playtesters</li>
                <li>Violation may result in immediate termination and legal action</li>
              </ul>
            </div>
          </div>

          <div className="form-section">
            <label className="checkbox-label eula-acceptance">
              <input
                type="checkbox"
                checked={eulaAccepted}
                onChange={(e) => setEulaAccepted(e.target.checked)}
              />
              <span>
                I have read and agree to the GAIA Playtester Agreement (NDA + EULA) and understand
                that all game content is confidential
              </span>
            </label>
          </div>

          <div className="form-section">
            <label className="checkbox-label email-optin">
              <input
                type="checkbox"
                checked={emailOptIn}
                onChange={(e) => setEmailOptIn(e.target.checked)}
              />
              <span>
                I would like to receive alpha testing updates and important announcements
              </span>
            </label>
            <p className="help-text">
              We'll send you important playtesting information, bug reports, and update notifications.
              Your email will never be shared with third parties.
            </p>
          </div>

          {error && (
            <div className="error-message">
              <span className="error-icon">⚠️</span>
              {error}
            </div>
          )}

          <div className="form-actions">
            <button
              onClick={handleRequestAccess}
              disabled={!eulaAccepted || isSubmitting}
              className="submit-button"
            >
              {isSubmitting ? 'Submitting Request...' : 'I Agree - Request Access'}
            </button>
            <p className="legal-notice">
              By clicking this button, you acknowledge that you understand and accept the NDA
              and confidentiality obligations outlined in the agreement above.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegistrationFlow;
