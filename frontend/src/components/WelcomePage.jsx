import React, {useState, useEffect} from 'react';
import {useNavigate, useSearchParams} from 'react-router-dom';
import {useAuth} from '../contexts/Auth0Context.jsx';
import apiService from '../services/apiService';
import CampaignManager from './CampaignManager.jsx';
import CampaignSetup from './CampaignSetup.jsx';
import PlayerSessionModal from './PlayerSessionModal.jsx';
import RegistrationFlow from './RegistrationFlow.jsx';
import background from '../assets/background.jpg';
import scrollImage from '../assets/scroll.png';
import logo from '../assets/logo.png';
import SharedHeaderLayout from './layout/SharedHeaderLayout.jsx';
import {API_CONFIG} from '../config/api.js';

const WelcomePage = () => {
    const DEV_BYPASS_AUTH = import.meta.env.DEV && import.meta.env.VITE_DEV_BYPASS_AUTH === "true"

    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();

    // Auth context
    const {isAuthenticated, loading, user, login, getAccessTokenSilently} = useAuth();

    // Backend readiness state
    const [backendReady, setBackendReady] = useState(false);
    const [backendError, setBackendError] = useState(null);
    const [checkingBackend, setCheckingBackend] = useState(true);

    // Modal state management
    const [showCampaignManager, setShowCampaignManager] = useState(false);
    const [showCampaignSetup, setShowCampaignSetup] = useState(false);
    const [showPlayerSessionModal, setShowPlayerSessionModal] = useState(false);

    // Invite token processing state
    const [processingInvite, setProcessingInvite] = useState(false);
    const [inviteError, setInviteError] = useState(null);

    // Registration status tracking
    const [checkingAuthorization, setCheckingAuthorization] = useState(false);
    const [showRegistration, setShowRegistration] = useState(false);

    // Check backend health on mount with retry logic
    useEffect(() => {
        let isMounted = true;
        let retryCount = 0;
        const maxRetries = 10;
        const retryDelay = 2000; // 2 seconds between retries

        const checkBackendHealth = async () => {
            try {
                const response = await fetch(API_CONFIG.HEALTH_ENDPOINT, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                    },
                });

                if (response.ok) {
                    const data = await response.json();
                    if (isMounted && data.status === 'healthy') {
                        console.log('Backend is ready');
                        setBackendReady(true);
                        setBackendError(null);
                        setCheckingBackend(false);
                        return true;
                    }
                }
                return false;
            } catch (error) {
                console.log(`Backend health check failed (attempt ${retryCount + 1}/${maxRetries}):`, error.message);
                return false;
            }
        };

        const attemptHealthCheck = async () => {
            const isHealthy = await checkBackendHealth();

            if (!isHealthy && isMounted) {
                retryCount++;
                if (retryCount < maxRetries) {
                    // Retry after delay
                    setTimeout(attemptHealthCheck, retryDelay);
                } else {
                    // Max retries exceeded
                    setBackendError('Unable to connect to server. Please refresh the page to try again.');
                    setCheckingBackend(false);
                }
            }
        };

        attemptHealthCheck();

        return () => {
            isMounted = false;
        };
    }, []);

    // Handle invite token on mount
    useEffect(() => {
        const inviteToken = searchParams.get('invite');
        if (!inviteToken) return;

        // Wait for auth state to be determined
        if (loading) return;

        // If not authenticated, redirect to login with invite token preserved
        if (!isAuthenticated && !DEV_BYPASS_AUTH) {
            console.log('🔐 User not authenticated, redirecting to login with invite token');
            login({
                appState: {
                    returnTo: `/?invite=${encodeURIComponent(inviteToken)}`
                }
            });
            return;
        }

        // User is authenticated, process the invite
        handleInviteToken(inviteToken);
    }, [searchParams, loading, isAuthenticated, login, DEV_BYPASS_AUTH]);

    // Handle intent after login (check URL params)
    useEffect(() => {
        const handleIntent = async () => {
            const intent = searchParams.get('intent');

            if (intent && isAuthenticated && !loading) {
                // Clear intent from URL
                searchParams.delete('intent');
                setSearchParams(searchParams, {replace: true});

                // Check authorization before opening modal
                const authorized = await checkUserAuthorization();
                if (!authorized) {
                    return;
                }

                // Open the intended modal
                if (intent === 'dm') {
                    setShowCampaignManager(true);
                } else if (intent === 'player') {
                    setShowPlayerSessionModal(true);
                }
            }
        };

        handleIntent();
    }, [searchParams, isAuthenticated, loading]);

    // Process invite token and auto-join session
    const handleInviteToken = async (token) => {
        try {
            setProcessingInvite(true);
            setInviteError(null);

            console.log('🎟️ Processing invite token:', token);

            const response = await apiService.joinSessionByInvite(token);
            const sessionId = response?.session_id;

            if (!sessionId) {
                throw new Error('Invite did not return a session ID');
            }

            console.log('✅ Joined session via invite:', sessionId);

            // Remove invite token from URL
            searchParams.delete('invite');
            setSearchParams(searchParams, {replace: true});

            // Navigate to player view for this session
            navigate(`/${sessionId}/player`, {replace: true});
        } catch (error) {
            console.error('❌ Failed to process invite:', error);
            setInviteError(error.message || 'Invalid or expired invite link');
            setProcessingInvite(false);

            // Remove invite token from URL even on error
            searchParams.delete('invite');
            setSearchParams(searchParams, {replace: true});
        }
    };

    // Check if user is authorized (whitelist check)
    const checkUserAuthorization = async () => {
        if (DEV_BYPASS_AUTH) {
            console.log("bypass authorization")
            return true
        }

        if (!user) return false;

        setCheckingAuthorization(true);

        try {
            const response = await fetch('/api/auth/registration-status', {
                headers: {
                    Authorization: `Bearer ${await getAccessTokenSilently()}`,
                },
            });

            if (response.ok) {
                const status = await response.json();

                // If pending or not authorized, show registration flow
                if (status.registration_status === 'pending' || !status.is_authorized) {
                    setShowRegistration(true);
                    return false;
                }

                return true; // Authorized
            } else if (response.status === 403) {
                setShowRegistration(true);
                return false;
            }

            // If we can't check, assume authorized (fallback)
            return true;
        } catch (error) {
            console.error('Error checking authorization:', error);
            return true; // Assume authorized on error
        } finally {
            setCheckingAuthorization(false);
        }
    };

    // Handler for "Dungeon Master" button
    const handleDungeonMasterClick = async () => {
        // If not authenticated, trigger login with intent
        if (DEV_BYPASS_AUTH) {
            console.log("bypass authorization")
        } else if (!isAuthenticated) {
            login({
                appState: {
                    returnTo: '/?intent=dm'
                }
            });
            return;
        }

        // If authenticated, check authorization before opening modal
        const authorized = await checkUserAuthorization();
        if (!authorized) {
            return; // checkUserAuthorization will handle showing registration flow
        }

        // User is authenticated and authorized, open modal
        setShowCampaignManager(true);
    };

    // Handler for "Adventurer" button
    const handleAdventurerClick = async () => {
        // If not authenticated, trigger login with intent
        if (DEV_BYPASS_AUTH) {
            console.log("bypass authorization")
            return true
        } else if (!isAuthenticated) {
            login({
                appState: {
                    returnTo: '/?intent=player'
                }
            });
            return;
        }

        // If authenticated, check authorization before opening modal
        const authorized = await checkUserAuthorization();
        if (!authorized) {
            return;
        }

        // User is authenticated and authorized, open modal
        setShowPlayerSessionModal(true);
    };

    // Handler for when DM wants to create new campaign (opens wizard)
    const handleRequestNewCampaign = () => {
        setShowCampaignManager(false);
        setShowCampaignSetup(true);
    };

    // Handler for when campaign setup wizard completes
    const handleCampaignSetupComplete = (campaignId) => {
        setShowCampaignSetup(false);
        if (campaignId) {
            // Navigate to DM view for the new campaign
            navigate(`/${campaignId}/dm`);
        }
    };

    return (
        <div className="min-h-screen bg-gaia-dark flex flex-col">
            <SharedHeaderLayout/>
            <div
                className="flex-grow flex flex-col items-center justify-center relative overflow-hidden"
                style={{
                    backgroundImage: `url(${background})`,
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                    backgroundRepeat: 'no-repeat'
                }}
            >
                {/* Dark overlay for better text readability */}
                <div className="absolute inset-0 bg-black/20"></div>

                {/* Loading overlay while checking backend */}
                {checkingBackend && (
                    <div className="absolute inset-0 bg-black/60 z-20 flex flex-col items-center justify-center">
                        <div className="text-center">
                            <div className="flex justify-center mb-6">
                                <img
                                    src={logo}
                                    alt="Fable Table"
                                    className="w-32 h-32 md:w-40 md:h-40 object-contain drop-shadow-2xl animate-pulse"
                                />
                            </div>
                            <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-amber-400 mx-auto mb-4"></div>
                            <p
                                className="text-xl text-gray-200 drop-shadow-lg"
                                style={{
                                    fontFamily: '"Cinzel", "Times New Roman", serif',
                                    textShadow: '0 0 10px rgba(0,0,0,0.9)'
                                }}
                            >
                                Preparing your adventure...
                            </p>
                        </div>
                    </div>
                )}

                {/* Backend error overlay */}
                {backendError && !checkingBackend && (
                    <div className="absolute inset-0 bg-black/70 z-20 flex flex-col items-center justify-center">
                        <div className="text-center max-w-md px-4">
                            <div className="flex justify-center mb-6">
                                <img
                                    src={logo}
                                    alt="Fable Table"
                                    className="w-32 h-32 md:w-40 md:h-40 object-contain drop-shadow-2xl opacity-50"
                                />
                            </div>
                            <p
                                className="text-xl text-red-300 mb-4 drop-shadow-lg"
                                style={{
                                    fontFamily: '"Cinzel", "Times New Roman", serif',
                                    textShadow: '0 0 10px rgba(0,0,0,0.9)'
                                }}
                            >
                                Connection Failed
                            </p>
                            <p className="text-gray-300 mb-6">{backendError}</p>
                            <button
                                onClick={() => window.location.reload()}
                                className="px-6 py-3 bg-amber-700 hover:bg-amber-600 text-white rounded-lg transition-colors duration-200 font-semibold"
                            >
                                Retry Connection
                            </button>
                        </div>
                    </div>
                )}

                {/* Main Content */}
                <main className="relative z-10 flex flex-col items-center justify-center px-4 py-8 max-w-2xl w-full">
                    {/* Logo and Title Section */}
                    <div className="text-center mb-12 space-y-6" style={{marginTop: '-100px'}}>
                        {/* Logo */}
                        <div className="flex justify-center mb-4">
                            <img
                                src={logo}
                                alt="Fable Table"
                                className="w-44 h-44 md:w-56 md:h-56 object-contain drop-shadow-2xl"
                            />
                        </div>
                        {/* Subtitle */}
                        <p
                            className="text-xl md:text-2xl text-gray-200 drop-shadow-lg tracking-wide"
                            style={{
                                fontFamily: '"Cinzel", "Times New Roman", serif',
                                textShadow: '0 0 10px rgba(0,0,0,0.9), 2px 2px 4px rgba(0,0,0,0.8)'
                            }}
                        >
                            Choose Your Journey
                        </p>

                        {/* Discord Link */}
                        <a
                            href="https://discord.gg/wmVQvjMGK"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 text-gray-300 hover:text-amber-400 transition-colors duration-200 mt-2"
                            title="Join our Discord"
                        >
                            <svg
                                viewBox="0 0 24 24"
                                fill="currentColor"
                                className="w-6 h-6"
                            >
                                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.947 2.418-2.157 2.418z"/>
                            </svg>
                            <span
                                className="text-sm"
                                style={{
                                    fontFamily: '"Cinzel", "Times New Roman", serif'
                                }}
                            >
                                Join our Discord
                            </span>
                        </a>
                    </div>

                    {/* Invite Processing Status */}
                    {processingInvite && (
                        <div
                            className="bg-blue-900/90 backdrop-blur-sm border border-blue-700 text-blue-100 px-6 py-4 rounded-lg mb-6 shadow-2xl">
                            <div className="flex items-center justify-center gap-3">
                                <div
                                    className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-300"></div>
                                <span className="text-lg">Processing invite link...</span>
                            </div>
                        </div>
                    )}

                    {/* Invite Error */}
                    {inviteError && (
                        <div
                            className="bg-red-900/90 backdrop-blur-sm border border-red-700 text-red-100 px-6 py-4 rounded-lg mb-6 shadow-2xl">
                            <p className="font-semibold mb-2 text-lg">❌ Invite Error</p>
                            <p className="text-sm">{inviteError}</p>
                            <button
                                onClick={() => setInviteError(null)}
                                className="mt-3 text-sm underline hover:text-red-200 transition-colors"
                            >
                                Dismiss
                            </button>
                        </div>
                    )}

                    {/* Scroll Buttons Container */}
                    <div className="flex flex-col md:flex-row gap-8 w-full max-w-4xl justify-center items-center">
                        {/* Dungeon Master Scroll Button */}
                        <button
                            onClick={handleDungeonMasterClick}
                            disabled={!backendReady}
                            className={`relative group transition-all duration-300 flex-1 md:max-w-md w-3/4 md:w-full md:-translate-x-6 ${
                                backendReady
                                    ? 'hover:scale-105 active:scale-95 cursor-pointer'
                                    : 'opacity-50 cursor-not-allowed'
                            }`}
                            style={{minHeight: '120px'}}
                        >
                            {/* Scroll Background */}
                            <img
                                src={scrollImage}
                                alt="Scroll"
                                className={`w-full h-full object-contain drop-shadow-2xl transition-all duration-300 ${
                                    backendReady ? 'group-hover:drop-shadow-[0_0_25px_rgba(218,165,32,0.7)]' : ''
                                }`}
                            />
                            {/* Text Overlay */}
                            <div className="absolute inset-0 flex items-center justify-center">
              <span
                  className={`text-2xl md:text-3xl font-bold transition-colors duration-300 px-8 ${
                      backendReady ? 'text-amber-900 group-hover:text-amber-800' : 'text-amber-900/70'
                  }`}
                  style={{
                      fontFamily: '"Pirata One", "Times New Roman", serif',
                      textShadow: '0 1px 2px rgba(0,0,0,0.2)'
                  }}
              >
                Storyteller
              </span>
                            </div>
                        </button>

                        {/* Adventurer Scroll Button */}
                        <button
                            onClick={handleAdventurerClick}
                            disabled={!backendReady}
                            className={`relative group transition-all duration-300 flex-1 md:max-w-md w-3/4 md:w-full md:translate-x-6 ${
                                backendReady
                                    ? 'hover:scale-105 active:scale-95 cursor-pointer'
                                    : 'opacity-50 cursor-not-allowed'
                            }`}
                            style={{minHeight: '120px'}}
                        >
                            {/* Scroll Background */}
                            <img
                                src={scrollImage}
                                alt="Scroll"
                                className={`w-full h-full object-contain drop-shadow-2xl transition-all duration-300 ${
                                    backendReady ? 'group-hover:drop-shadow-[0_0_25px_rgba(218,165,32,0.7)]' : ''
                                }`}
                            />
                            {/* Text Overlay */}
                            <div className="absolute inset-0 flex items-center justify-center">
              <span
                  className={`text-2xl md:text-3xl font-bold transition-colors duration-300 px-8 ${
                      backendReady ? 'text-amber-900 group-hover:text-amber-800' : 'text-amber-900/70'
                  }`}
                  style={{
                      fontFamily: '"Pirata One", "Times New Roman", serif',
                      textShadow: '0 1px 2px rgba(0,0,0,0.2)'
                  }}
              >
                Adventurer
              </span>
                            </div>
                        </button>
                    </div>
                </main>

                {/* ElevenLabs Grant Logo */}
                <div className="absolute bottom-4 right-4 z-10">
                    <a
                        href="https://elevenlabs.io/startup-grants"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="opacity-80 hover:opacity-100 transition-opacity duration-200"
                    >
                        <img
                            src="https://eleven-public-cdn.elevenlabs.io/payloadcms/cy7rxce8uki-IIElevenLabsGrants%201.webp"
                            alt="ElevenLabs"
                            style={{ width: '250px' }}
                        />
                    </a>
                </div>
            </div>

            {/* Campaign Manager Modal (for DM) */}
            <CampaignManager
                isOpen={showCampaignManager}
                mode="navigate"
                onClose={() => setShowCampaignManager(false)}
                onRequestNewCampaign={handleRequestNewCampaign}
            />

            {/* Campaign Setup Wizard Modal */}
            <CampaignSetup
                isOpen={showCampaignSetup}
                onCancel={() => setShowCampaignSetup(false)}
                onComplete={handleCampaignSetupComplete}
            />

            {/* Player Session Modal */}
            {showPlayerSessionModal && (
                <PlayerSessionModal
                    isOpen={showPlayerSessionModal}
                    onClose={() => setShowPlayerSessionModal(false)}
                />
            )}

            {/* Loading state while checking authorization */}
            {checkingAuthorization && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-gaia-light rounded-lg p-6">
                        <div
                            className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gaia-accent mx-auto"></div>
                        <p className="text-white mt-4">Checking access...</p>
                    </div>
                </div>
            )}

            {/* Show registration flow if needed */}
            {showRegistration && (
                <RegistrationFlow
                    onComplete={() => {
                        setShowRegistration(false);
                        // After registration, they can try the action again
                    }}
                />
            )}
        </div>
    );
};

export default WelcomePage;
