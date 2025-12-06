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
                    <div className="flex flex-col md:flex-row gap-8 w-full max-w-4xl justify-center">
                        {/* Dungeon Master Scroll Button */}
                        <button
                            onClick={handleDungeonMasterClick}
                            disabled={!backendReady}
                            className={`relative group transition-all duration-300 flex-1 md:max-w-md ${
                                backendReady
                                    ? 'hover:scale-105 active:scale-95 cursor-pointer'
                                    : 'opacity-50 cursor-not-allowed'
                            }`}
                            style={{minHeight: '120px', transform: 'translateX(-25px)'}}
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
                Dungeon Master
              </span>
                            </div>
                        </button>

                        {/* Adventurer Scroll Button */}
                        <button
                            onClick={handleAdventurerClick}
                            disabled={!backendReady}
                            className={`relative group transition-all duration-300 flex-1 md:max-w-md ${
                                backendReady
                                    ? 'hover:scale-105 active:scale-95 cursor-pointer'
                                    : 'opacity-50 cursor-not-allowed'
                            }`}
                            style={{minHeight: '120px', transform: 'translateX(25px)'}}
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
