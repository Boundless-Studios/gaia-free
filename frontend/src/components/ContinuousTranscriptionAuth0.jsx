import React, { useState, useRef, useEffect, useCallback } from 'react';
import { API_CONFIG } from '../config/api';
import { useAuth0 } from '@auth0/auth0-react';
import { getButtonClass, cn } from '../lib/tailwindComponents';
import apiService from '../services/apiService';

const ContinuousTranscription = ({ onTranscriptionUpdate, onSendMessage, sessionId }) => {
  const [isListening, setIsListening] = useState(false);
  const [transcribedText, setTranscribedText] = useState('');
  const [voiceActive, setVoiceActive] = useState(false);
  const [error, setError] = useState(null);
  const [showControls, setShowControls] = useState(false);
  const [sendImmediately, setSendImmediately] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  
  // Auth0 hook for getting access token
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();
  
  const websocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorRef = useRef(null);
  const audioStreamRef = useRef(null);
  const currentTranscriptionRef = useRef('');
  const reconnectTimeoutRef = useRef(null);
  const pausedRef = useRef(false);
  
  // Keep track of the accumulated text that hasn't been sent
  const [unsentText, setUnsentText] = useState('');
  
  // Update unsent text whenever transcribed text changes
  useEffect(() => {
    currentTranscriptionRef.current = transcribedText;
    setUnsentText(transcribedText);
  }, [transcribedText]);
  
  // Voice activity polling
  useEffect(() => {
    if (!isListening || !sessionId) return;
    
    const pollVoiceActivity = async () => {
      try {
        const data = await apiService.getVoiceActivity(sessionId);
        if (data) {
          setVoiceActive(data.is_active);
        }
      } catch (error) {
        console.error('Error polling voice activity:', error);
      }
    };
    
    const interval = setInterval(pollVoiceActivity, 500);
    return () => clearInterval(interval);
  }, [isListening, sessionId]);
  
  const handleSendUnsentText = useCallback(() => {
    if (unsentText.trim()) {
      console.log('[ContinuousTranscription] Sending unsent text:', unsentText);
      // Use onSendMessage if available, otherwise fall back to onTranscriptionUpdate
      if (onSendMessage) {
        onSendMessage(unsentText);
      } else if (onTranscriptionUpdate) {
        onTranscriptionUpdate(unsentText);
      }
      // Clear both the transcribed text and unsent text
      setTranscribedText('');
      setUnsentText('');
    }
  }, [unsentText, onSendMessage, onTranscriptionUpdate]);
  
  const handleTogglePause = useCallback(() => {
    console.log('[ContinuousTranscription] Toggle pause from', isPaused, 'to', !isPaused);
    const newPausedState = !isPaused;
    setIsPaused(newPausedState);
    pausedRef.current = newPausedState;
    
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      const message = {
        event: newPausedState ? 'pause_transcription' : 'resume_transcription',
        data: {}
      };
      console.log('[ContinuousTranscription] Sending WebSocket message:', message);
      websocketRef.current.send(JSON.stringify(message));
    }
  }, [isPaused]);
  
  const cleanupAudioResources = useCallback(() => {
    console.log('[ContinuousTranscription] Cleaning up audio resources');
    
    // Stop audio processing
    if (processorRef.current) {
      try {
        processorRef.current.disconnect();
      } catch (e) {
        console.error('Error disconnecting processor:', e);
      }
      processorRef.current = null;
    }
    
    // Stop media stream
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => {
        track.stop();
      });
      mediaStreamRef.current = null;
    }
    
    // Close audio context
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      try {
        audioContextRef.current.close();
      } catch (e) {
        console.error('Error closing audio context:', e);
      }
      audioContextRef.current = null;
    }
    
    audioStreamRef.current = null;
  }, []);
  
  const closeWebSocket = useCallback(() => {
    console.log('[ContinuousTranscription] Closing WebSocket connection');
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (websocketRef.current) {
      // Remove event listeners before closing
      websocketRef.current.onmessage = null;
      websocketRef.current.onerror = null;
      websocketRef.current.onclose = null;
      
      if (websocketRef.current.readyState === WebSocket.OPEN) {
        try {
          // Send stop message before closing
          const stopMessage = {
            event: 'stop_continuous',
            data: {}
          };
          websocketRef.current.send(JSON.stringify(stopMessage));
        } catch (e) {
          console.error('Error sending stop message:', e);
        }
      }
      
      if (websocketRef.current.readyState !== WebSocket.CLOSED) {
        websocketRef.current.close();
      }
      websocketRef.current = null;
    }
  }, []);
  
  const sendAudioChunk = useCallback((audioData) => {
    if (!websocketRef.current || websocketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    
    if (pausedRef.current) {
      return;
    }
    
    try {
      websocketRef.current.send(audioData);
    } catch (error) {
      console.error('Error sending audio chunk:', error);
    }
  }, []);
  
  const startListening = async () => {
    try {
      console.log('[ContinuousTranscription] Starting continuous transcription');
      setError(null);
      
      // Get Auth0 access token if authenticated
      let accessToken = null;
      if (isAuthenticated) {
        try {
          accessToken = await getAccessTokenSilently();
        } catch (error) {
          console.error('Error getting Auth0 token:', error);
        }
      }
      
      // Request microphone access
      console.log('[ContinuousTranscription] Requesting microphone permission...');
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ 
          audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
        console.log('[ContinuousTranscription] Microphone access granted');
      } catch (micError) {
        console.error('[ContinuousTranscription] Microphone access denied:', micError);
        if (micError.name === 'NotAllowedError') {
          setError('Microphone access denied. Please enable microphone permissions in your browser settings.');
        } else if (micError.name === 'NotFoundError') {
          setError('No microphone found. Please connect a microphone and try again.');
        } else {
          setError(`Microphone error: ${micError.message}`);
        }
        setIsListening(false);
        return; // Exit early if mic access fails
      }
      mediaStreamRef.current = stream;
      
      // Create audio context
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000
      });
      
      const source = audioContextRef.current.createMediaStreamSource(stream);
      const processor = audioContextRef.current.createScriptProcessor(2048, 1, 1);
      processorRef.current = processor;
      
      // Create audio stream buffer
      audioStreamRef.current = new Int16Array(0);
      
      processor.onaudioprocess = (e) => {
        if (pausedRef.current) return;
        
        const inputData = e.inputBuffer.getChannelData(0);
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          pcm16[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
        }
        
        sendAudioChunk(pcm16.buffer);
        
        // Accumulate audio for voice activity detection
        const newStream = new Int16Array(audioStreamRef.current.length + pcm16.length);
        newStream.set(audioStreamRef.current);
        newStream.set(pcm16, audioStreamRef.current.length);
        audioStreamRef.current = newStream;
        
        // Keep only last 5 minutes of audio (at 16kHz)
        const maxSamples = 16000 * 300; // 5 minutes
        if (audioStreamRef.current.length > maxSamples) {
          audioStreamRef.current = audioStreamRef.current.slice(-maxSamples);
        }
      };
      
      source.connect(processor);
      processor.connect(audioContextRef.current.destination);
      
      console.log('[ContinuousTranscription] Audio context created:', {
        sampleRate: audioContextRef.current.sampleRate,
        state: audioContextRef.current.state,
        stream: !!audioStreamRef.current
      });
      
      // Create WebSocket connection with authentication token
      const wsUrl = accessToken 
        ? `${API_CONFIG.WS_TRANSCRIBE}?token=${accessToken}`
        : API_CONFIG.WS_TRANSCRIBE;
      const ws = new WebSocket(wsUrl);
      websocketRef.current = ws;
      
      ws.onopen = () => {
        console.log('WebSocket connected for continuous transcription');
        
        // Send start recording message
        const startMessage = {
          event: 'start_continuous',
          data: {
            user_id: 'frontend_user',
            audio_config: {
              sample_rate: 16000,
              channels: 1,
              format: 'pcm16'
            }
          }
        };
        ws.send(JSON.stringify(startMessage));
        setIsListening(true);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.event === 'transcription') {
            const text = data.data.text;
            if (text) {
              console.log('[ContinuousTranscription] Received transcription:', text);
              setTranscribedText(prev => {
                const newText = prev + (prev ? ' ' : '') + text;
                currentTranscriptionRef.current = newText;
                
                // If sendImmediately is enabled, send it right away
                if (sendImmediately && onTranscriptionUpdate) {
                  console.log('[ContinuousTranscription] Auto-sending:', text);
                  onTranscriptionUpdate(text);
                  return ''; // Clear after sending
                }
                
                return newText;
              });
            }
          } else if (data.event === 'voice_activity') {
            setVoiceActive(data.data.is_active);
          } else if (data.event === 'error') {
            console.error('WebSocket error:', data.data.message);
            setError(data.data.message);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error. Please try again.');
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        if (isListening) {
          // Only attempt reconnect if we're supposed to be listening
          console.log('Attempting to reconnect in 2 seconds...');
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isListening) {
              startListening();
            }
          }, 2000);
        }
      };
      
    } catch (error) {
      console.error('Error starting continuous transcription:', error);
      setError(error.message || 'Failed to start transcription');
      setIsListening(false);
      cleanupAudioResources();
    }
  };
  
  const stopListening = useCallback(() => {
    console.log('[ContinuousTranscription] Stopping continuous transcription');
    setIsListening(false);
    setVoiceActive(false);
    setIsPaused(false);
    pausedRef.current = false;
    
    closeWebSocket();
    cleanupAudioResources();
  }, [closeWebSocket, cleanupAudioResources]);
  
  useEffect(() => {
    return () => {
      console.log('[ContinuousTranscription] Component unmounting, cleaning up');
      stopListening();
    };
  }, [stopListening]);
  
  // Toggle controls visibility
  const _toggleControls = () => {
    setShowControls(!showControls);
  };
  
  return (
    <div className="flex flex-col gap-2">
      {/* Voice activity indicator - always visible when listening */}
      {isListening && (
        <div className="mb-2">
          <VoiceActivityIndicator isActive={voiceActive} />
        </div>
      )}
      
      {/* Control panel - always visible */}
      <div className="bg-gaia-light border border-gaia-border rounded-lg p-4 space-y-3">
          {/* Transcription controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={isListening ? stopListening : startListening}
              disabled={!!error}
              className={cn(
                getButtonClass(isListening ? 'danger' : 'primary'),
                error && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isListening ? '🔴 Stop Listening' : '🎤 Start Listening'}
            </button>
            
            {isListening && (
              <button
                onClick={handleTogglePause}
                className={getButtonClass('secondary')}
                title={isPaused ? 'Resume transcription' : 'Pause transcription'}
              >
                {isPaused ? '▶️ Resume' : '⏸️ Pause'}
              </button>
            )}
            
            <label className="flex items-center gap-2 ml-4">
              <input
                type="checkbox"
                checked={sendImmediately}
                onChange={(e) => setSendImmediately(e.target.checked)}
                className="w-4 h-4 text-gaia-accent bg-gaia-dark border-gaia-border rounded focus:ring-gaia-accent focus:ring-2"
              />
              <span className="text-sm text-gaia-muted">Auto-send</span>
            </label>
          </div>
          
          {/* Status messages */}
          {error && (
            <div className="bg-red-500/10 border border-red-500 text-red-400 px-3 py-2 rounded-md text-sm">
              {error}
            </div>
          )}
          
          {isPaused && (
            <div className="bg-yellow-500/10 border border-yellow-500 text-yellow-400 px-3 py-2 rounded-md text-sm">
              Transcription paused - click Resume to continue
            </div>
          )}
          
          {/* Transcribed text display */}
          <div className="space-y-2">
            <textarea
              value={transcribedText}
              onChange={(e) => setTranscribedText(e.target.value)}
              className="w-full bg-gaia-dark border border-gaia-border rounded-md p-3 text-white text-sm resize-y min-h-[160px] focus:outline-none focus:ring-2 focus:ring-purple-500/50"
              placeholder="Transcribed text will appear here..."
            />
            <button
              onClick={handleSendUnsentText}
              disabled={!unsentText.trim()}
              className={cn(
                getButtonClass('primary'),
                !unsentText.trim() && 'opacity-50 cursor-not-allowed'
              )}
            >
              📤 Send Unsent Text
            </button>
          </div>
        </div>
    </div>
  );
};

// Voice Activity Indicator Component
const VoiceActivityIndicator = ({ isActive }) => {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-gaia-light border border-gaia-border rounded-md">
      <div className={cn(
        'w-3 h-3 rounded-full transition-colors duration-200',
        isActive ? 'bg-green-500 animate-pulse' : 'bg-gray-500'
      )} />
      <span className="text-sm text-gaia-muted">
        {isActive ? 'Speaking' : 'Silent'}
      </span>
    </div>
  );
};

export default ContinuousTranscription;