import { useState, useRef, useEffect, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { Button } from './base-ui/Button';
import { Textarea } from './base-ui/Textarea';
import { API_CONFIG } from '../config/api';
import './ContinuousTranscription.css';

/**
 * Voice Input Component using ElevenLabs Scribe V2 Realtime API (via backend proxy)
 *
 * This component connects to the backend STT service which proxies requests to
 * ElevenLabs Scribe V2 for real-time speech-to-text transcription with built-in
 * VAD (Voice Activity Detection) for automatic pause detection and natural
 * conversation flow. The API key is kept secure on the backend.
 */
const VoiceInputScribeV2 = ({
  onSendMessage,
  isTTSPlaying = false,
  conversationalMode = true,
  userEmail = null,
  characterId = null,
  autoStart = false,
  onVoiceLevel = null,
  onRecordingStop = null
}) => {
  const { user, getAccessTokenSilently } = useAuth0();
  const [isRecording, setIsRecording] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [transcriptionText, setTranscriptionText] = useState('');
  const [partialText, setPartialText] = useState('');
  const [error, setError] = useState(null);
  const [voiceLevel, setVoiceLevel] = useState(0);
  const [voiceDetected, setVoiceDetected] = useState(false);
  const [voiceTooLow, setVoiceTooLow] = useState(false);
  const [queuePosition, setQueuePosition] = useState(null); // null = not queued

  const processorRef = useRef(null);
  const voiceLevelRef = useRef(0); // Ref for audio processor to check level
  const websocketRef = useRef(null);
  const audioStreamRef = useRef(null);
  const transcriptionTextAreaRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const sourceRef = useRef(null);
  const voiceLevelMonitorRef = useRef(null);
  const isTTSPlayingRef = useRef(isTTSPlaying);
  const isRecordingRef = useRef(false);
  const lastVoiceActivityRef = useRef(Date.now());
  const partialTextRef = useRef('');  // Track partial for stopRecording commit
  const firstChunkSentRef = useRef(false); // Track when first PCM chunk is emitted
  const streamingStartTimeRef = useRef(null); // Track when we started streaming for timing diagnostics
  const hasAutoStartedRef = useRef(false); // Guard against React StrictMode double-mount

  // Silence timeout configuration
  const SILENCE_TIMEOUT_MS = 15000;  // 15 seconds of silence triggers auto-stop
  const VOICE_THRESHOLD = 5;         // 5% volume threshold

  // Update refs when state/props change
  useEffect(() => {
    isTTSPlayingRef.current = isTTSPlaying;
  }, [isTTSPlaying]);

  useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);

  useEffect(() => {
    partialTextRef.current = partialText;
  }, [partialText]);

  // Auto-start recording when component mounts if autoStart is true
  // Uses ref guard to prevent duplicate connections in React StrictMode
  useEffect(() => {
    if (autoStart && !hasAutoStartedRef.current && !isRecording && !isConnecting) {
      hasAutoStartedRef.current = true;
      console.log('🎤 Auto-starting recording on mount');
      startRecording();
    }
  }, [autoStart]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  // Auto-resize textarea as content changes
  useEffect(() => {
    if (transcriptionTextAreaRef.current) {
      transcriptionTextAreaRef.current.style.height = 'auto';
      transcriptionTextAreaRef.current.style.height = transcriptionTextAreaRef.current.scrollHeight + 'px';
    }
  }, [transcriptionText, partialText]);

  /**
   * Start recording and connect to ElevenLabs Scribe V2 Realtime API
   */
  const startRecording = useCallback(async () => {
    try {
      console.log('🎤 Starting Scribe V2 recording...');
      setIsConnecting(true);
      setError(null);

      // Get microphone permission
      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000  // ElevenLabs recommends 16kHz
        }
      });
      console.log('✅ Microphone permission granted');

      audioStreamRef.current = micStream;

      // Set up audio analysis for voice level visualization
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      audioContextRef.current = new AudioContextClass({ sampleRate: 16000 });

      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      analyserRef.current = audioContextRef.current.createAnalyser();
      sourceRef.current = audioContextRef.current.createMediaStreamSource(micStream);
      sourceRef.current.connect(analyserRef.current);
      analyserRef.current.fftSize = 2048;

      // Connect to backend STT service (which proxies to ElevenLabs Scribe V2)
      const sttBaseUrl = API_CONFIG.STT_BASE_URL || 'http://localhost:8001';
      const wsUrl = sttBaseUrl.replace(/^http/, 'ws') + '/stt/transcribe/realtime';

      // Get auth token and pass via WebSocket subprotocol (more secure than URL query param)
      let wsProtocols = [];
      try {
        const token = await getAccessTokenSilently();
        if (token) {
          // Pass token as subprotocol - backend expects "token.{jwt}" format
          wsProtocols = [`token.${token}`];
          console.log('🔐 Auth token will be sent via WebSocket subprotocol');
        }
      } catch (authError) {
        console.warn('⚠️ Could not get auth token for STT:', authError.message);
      }

      console.log('🔌 Connecting to STT service:', wsUrl);

      // Create WebSocket with subprotocol for auth (avoids token in URL)
      const ws = wsProtocols.length > 0
        ? new WebSocket(wsUrl, wsProtocols)
        : new WebSocket(wsUrl);
      websocketRef.current = ws;

      ws.onopen = () => {
        console.log('✅ Connected to backend STT service, waiting for ready signal...');
        // DON'T start streaming yet - wait for 'ready' event from backend
        // This prevents audio loss when queued for a connection slot
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleScribeMessage(data);
        } catch (err) {
          console.error('❌ Error parsing WebSocket message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setError('Connection error with speech recognition service');
      };

      ws.onclose = (event) => {
        console.log('🔌 WebSocket closed:', event.code, event.reason);
        setIsRecording(false);
        isRecordingRef.current = false;
        // Notify parent that recording has stopped
        if (onRecordingStop) {
          onRecordingStop();
        }
        if (event.code !== 1000) {
          setError(`Connection closed: ${event.reason || 'Unknown reason'}`);
        }
      };

    } catch (err) {
      console.error('❌ Failed to start recording:', err);
      setError(err.message);
      setIsConnecting(false);
      // Notify parent that recording failed to start
      if (onRecordingStop) {
        onRecordingStop();
      }
    }
  }, [conversationalMode, userEmail, characterId, user?.email, getAccessTokenSilently, onRecordingStop]);

  /**
   * Handle messages from backend STT service
   */
  const handleScribeMessage = (message) => {
    const event = message.event;
    const data = message.data || {};

    switch (event) {
      case 'partial_transcript':
        // Show partial transcription as user speaks
        // Backend strips cumulative prefix, we receive only the new portion
        console.log('📄 Partial:', data.text);
        setPartialText(data.text || '');
        setVoiceDetected(true);
        // In conversational mode, also send partials to editor for live preview
        if (conversationalMode && onSendMessage && data.text?.trim()) {
          onSendMessage(data.text, {
            user_email: userEmail || user?.email,
            character_id: characterId,
            is_partial: true,
            auto_submitted: false
          });
        }
        break;

      case 'transcription_segment':
        // Final transcription (pause detected by VAD)
        // Backend strips cumulative prefix, we receive only the new refined portion
        const committedText = data.text || '';
        console.log('✅ Committed:', committedText);

        // If recording has stopped, ignore this event - we already committed locally in stopRecording()
        // This prevents duplicate commits when the backend's timer fires after user stops recording
        if (!isRecordingRef.current) {
          console.log('⏭️ Ignoring transcription_segment because recording already stopped');
          break;
        }

        if (committedText.trim()) {
          // In conversational mode, auto-submit when committed
          if (conversationalMode && onSendMessage) {
            console.log('🗣️ Auto-submitting committed transcript');
            onSendMessage(committedText, {
              user_email: userEmail || user?.email,
              character_id: characterId,
              is_partial: false,
              auto_submitted: true,
              confidence: data.confidence
            });
            // Clear text after auto-submit
            setTranscriptionText('');
            setPartialText('');
          } else {
            // Manual mode: accumulate text
            setTranscriptionText(prev => {
              const separator = prev.trim() ? ' ' : '';
              return prev + separator + committedText;
            });
            setPartialText('');
          }
        }
        setVoiceDetected(false);
        break;

      case 'error':
        console.error('❌ STT error:', data.message);
        setError(data.message || 'Transcription error');
        break;

      case 'pong':
        // Heartbeat response - ignore
        break;

      case 'queued':
        // Connection queued due to capacity limits
        console.log('⏳ Queued at position:', data.position);
        setQueuePosition(data.position);
        break;

      case 'queue_position':
        // Queue position updated
        console.log('📍 Queue position:', data.position);
        setQueuePosition(data.position);
        break;

      case 'ready':
      case 'slot_available':
        // Connection slot acquired, ready to stream audio
        console.log('🟢 Ready to stream audio');
        setQueuePosition(null);
        setIsConnecting(false);
        setIsRecording(true);
        isRecordingRef.current = true;  // Set ref immediately for callbacks
        streamingStartTimeRef.current = Date.now(); // mark when streaming is about to start
        firstChunkSentRef.current = false;
        // Now start streaming audio to backend
        if (websocketRef.current) {
          startPCMAudioStreaming(websocketRef.current);
          startVoiceLevelMonitoring();
        }
        break;

      default:
        console.log('📨 Unknown event type:', event);
    }
  };

  /**
   * Start streaming raw PCM audio to backend STT service
   * Uses ScriptProcessorNode to capture raw 16-bit PCM samples
   */
  const startPCMAudioStreaming = (ws) => {
    // Create ScriptProcessorNode for raw PCM capture
    // Buffer size of 4096 samples at 16kHz = ~256ms chunks
    const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    // Connect source -> processor -> destination (required for processor to work)
    sourceRef.current.connect(processor);
    processor.connect(audioContextRef.current.destination);

    processor.onaudioprocess = (e) => {
      // Check recording flag first (set immediately on stop)
      if (!isRecordingRef.current || ws.readyState !== WebSocket.OPEN) return;

      // Only send audio if voice level is above 5% threshold
      try {
        // Get Float32 audio samples from input buffer
        const float32Data = e.inputBuffer.getChannelData(0);

        // Convert Float32 (-1 to 1) to Int16 (-32768 to 32767)
        const int16Data = new Int16Array(float32Data.length);
        for (let i = 0; i < float32Data.length; i++) {
          const s = Math.max(-1, Math.min(1, float32Data[i]));
          int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Send raw PCM bytes to backend
        ws.send(int16Data.buffer);

        if (!firstChunkSentRef.current) {
          firstChunkSentRef.current = true;
          const delta = streamingStartTimeRef.current ? (Date.now() - streamingStartTimeRef.current) : 0;
          console.log(`⏱️ First PCM chunk sent (${int16Data.byteLength} bytes) after ${delta}ms from ready`);
        }
      } catch (err) {
        console.error('❌ Error sending PCM audio:', err);
      }
    };

    console.log('🎙️ Started raw PCM audio streaming (16kHz, 16-bit)');
  };

  /**
   * Monitor voice levels for visual feedback and silence timeout
   * Uses isRecordingRef to avoid stale closure issues with async state updates
   */
  const startVoiceLevelMonitoring = () => {
    // Reset silence timer on start
    lastVoiceActivityRef.current = Date.now();

    const updateVoiceLevel = () => {
      if (!analyserRef.current || !isRecordingRef.current) {
        return;
      }

      const bufferLength = analyserRef.current.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      analyserRef.current.getByteFrequencyData(dataArray);

      // Calculate average volume
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }

      const average = sum / bufferLength;
      const volumeLevel = Math.min(100, (average / 255) * 100);

      setVoiceLevel(volumeLevel);
      voiceLevelRef.current = volumeLevel; // Update ref for audio processor

      // Track voice activity for silence timeout
      if (volumeLevel > VOICE_THRESHOLD) {
        lastVoiceActivityRef.current = Date.now();
      }

      // Check for extended silence - auto-stop recording
      const silenceDuration = Date.now() - lastVoiceActivityRef.current;
      if (silenceDuration >= SILENCE_TIMEOUT_MS && isRecordingRef.current) {
        console.log(`🔇 Auto-stopping after ${(silenceDuration / 1000).toFixed(1)}s of silence`);
        stopRecording();
        return;  // Don't schedule next frame
      }

      // Track if voice is too low (below 5% threshold) - includes silence
      const isTooLow = volumeLevel < VOICE_THRESHOLD;
      setVoiceTooLow(isTooLow);
      // Notify parent of voice level for external indicators (negative value = too low warning)
      if (onVoiceLevel) {
        onVoiceLevel(isTooLow ? -volumeLevel : volumeLevel);
      }

      if (isRecordingRef.current) {
        voiceLevelMonitorRef.current = requestAnimationFrame(updateVoiceLevel);
      }
    };

    updateVoiceLevel();
  };

  /**
   * Stop recording and close connection
   */
  const stopRecording = useCallback(() => {
    console.log('🛑 Stopping recording...');

    // Set flag FIRST to stop audio callbacks immediately
    isRecordingRef.current = false;

    if (voiceLevelMonitorRef.current) {
      cancelAnimationFrame(voiceLevelMonitorRef.current);
    }

    // Disconnect and clean up audio processor
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }

    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach(track => track.stop());
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
    }

    // Commit partial text locally BEFORE closing websocket
    // This ensures text isn't lost if backend cleanup message doesn't arrive
    const currentPartial = partialTextRef.current;
    if (currentPartial?.trim() && conversationalMode && onSendMessage) {
      console.log('📤 Committing partial text locally on stop:', currentPartial);
      onSendMessage(currentPartial.trim() + '. ', {
        user_email: userEmail || user?.email,
        character_id: characterId,
        is_partial: false,
        auto_submitted: true
      });
    }

    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      websocketRef.current.close(1000, 'Normal closure');
    }

    setIsRecording(false);
    setVoiceDetected(false);
    setVoiceLevel(0);
    setQueuePosition(null);
    setPartialText('');  // Clear overlay immediately
  }, [conversationalMode, onSendMessage, userEmail, characterId, user?.email]);

  /**
   * Toggle recording on/off
   */
  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  /**
   * Manual send for non-conversational mode
   */
  const handleManualSend = () => {
    const text = transcriptionText.trim();
    if (text && onSendMessage) {
      onSendMessage(text, {
        user_email: userEmail || user?.email,
        character_id: characterId,
        auto_submitted: false
      });
      setTranscriptionText('');
    }
  };

  // Get display text (committed + partial)
  const displayText = transcriptionText + (partialText ? (transcriptionText ? '\n\n' : '') + partialText : '');

  return (
    <div className="continuous-transcription">
      {/* Error Display */}
      {error && (
        <div className="error-banner">
          ⚠️ {error}
          <button onClick={() => setError(null)} className="error-close">✕</button>
        </div>
      )}

      {/* Voice Level Indicator */}
      <div className="voice-indicator">
        <div className="voice-level-bar">
          <div
            className="voice-level-fill"
            style={{ width: `${voiceLevel}%` }}
          />
        </div>
        <div className={`voice-status ${voiceDetected ? 'active' : ''}`}>
          {voiceDetected ? '🎤 Speaking...' : '🔇 Silent'}
        </div>
      </div>

      {/* Transcription Display */}
      <Textarea
        ref={transcriptionTextAreaRef}
        value={displayText}
        onChange={(e) => setTranscriptionText(e.target.value)}
        placeholder={
          conversationalMode
            ? "Start speaking... (auto-sends on pause)"
            : "Your transcription will appear here..."
        }
        className="transcription-textarea"
        rows={4}
        disabled={conversationalMode && isRecording}
      />

      {/* Controls */}
      <div className="transcription-controls">
        <Button
          onClick={toggleRecording}
          disabled={isConnecting && !queuePosition}
          variant={isRecording ? 'destructive' : 'default'}
        >
          {queuePosition ? (
            <>⏳ Queued (#{queuePosition})...</>
          ) : isConnecting ? (
            <>⏳ Connecting...</>
          ) : isRecording ? (
            <>🛑 Stop Listening</>
          ) : (
            <>🎤 Start Listening</>
          )}
        </Button>

        {/* Audio level indicator - minimalist horizontal bar */}
        {isRecording && (
          <div
            style={{
              width: '60px',
              height: '6px',
              backgroundColor: '#e0e0e0',
              borderRadius: '3px',
              overflow: 'hidden',
              marginLeft: '8px',
            }}
          >
            <div
              style={{
                width: `${voiceLevel}%`,
                height: '100%',
                backgroundColor: voiceLevel > 30 ? '#4ade80' : '#9ca3af',
                transition: 'width 0.05s ease-out',
              }}
            />
          </div>
        )}

        {!conversationalMode && (
          <Button
            onClick={handleManualSend}
            disabled={!transcriptionText.trim() || isRecording}
            variant="primary"
          >
            📤 Send
          </Button>
        )}

        {conversationalMode && (
          <div className="conversational-mode-badge">
            🗣️ Conversational Mode
          </div>
        )}
      </div>

      {/* Info Text */}
      <div className="info-text">
        {conversationalMode ? (
          <p>💡 Speak naturally. The system will automatically detect pauses and send your message.</p>
        ) : (
          <p>💡 Click "Start Listening" to begin transcription, then "Send" when ready.</p>
        )}
      </div>
    </div>
  );
};

export default VoiceInputScribeV2;
