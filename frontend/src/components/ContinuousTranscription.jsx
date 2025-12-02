import { useState, useRef, useEffect, useImperativeHandle, forwardRef, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { API_CONFIG } from '../config/api.js';
import { Button } from './base-ui/Button';
import { Textarea } from './base-ui/Textarea';
import './ContinuousTranscription.css';

const ContinuousTranscription = forwardRef(({
  onSendMessage,
  isTTSPlaying = false,
  onRecordingStateChange,
  conversationalMode = true,  // Enable conversational mode by default
  userEmail = null,
  characterId = null
}, ref) => {
  const { getAccessTokenSilently } = useAuth0();
  const [isRecording, setIsRecording] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [transcriptionText, setTranscriptionText] = useState('');
  const [error, setError] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [voiceLevel, setVoiceLevel] = useState(0);
  const [voiceDetected, setVoiceDetected] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [updateKey, setUpdateKey] = useState(0); // Force update mechanism
  const [sessionId, setSessionId] = useState(null); // Store session ID for polling
  
  const mediaRecorderRef = useRef(null);
  const websocketRef = useRef(null);
  const audioStreamRef = useRef(null);
  const transcriptionTextAreaRef = useRef(null);
  const recordingIntervalRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const voiceLevelMonitorRef = useRef(null);
  const isTTSPlayingRef = useRef(isTTSPlaying);
  const isPausedRef = useRef(false);
  const cursorPositionRef = useRef(null);
  const _silenceStartRef = useRef(null);
  const currentRecorderRef = useRef(null);
  const _voiceChunksRef = useRef([]);
  const transcriptionTextRef = useRef(''); // Ref to store current transcription text
  const voiceDetectedRef = useRef(false); // Ref to track voice detection state
  
  
  // Update ref when prop changes
  useEffect(() => {
    isTTSPlayingRef.current = isTTSPlaying;
  }, [isTTSPlaying]);
  
  // Update transcriptionText ref when state changes
  useEffect(() => {
    transcriptionTextRef.current = transcriptionText;
  }, [transcriptionText]);
  
  // Update pause ref when state changes
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);
  
  // Notify parent of recording state changes
  useEffect(() => {
    if (onRecordingStateChange) {
      onRecordingStateChange({ isRecording, sessionId });
    }
  }, [isRecording, sessionId, onRecordingStateChange]);
  
  // Expose toggleRecording method via ref (moved after function definitions)
  // This will be defined later to avoid initialization issues

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Clean up any open connections on unmount
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
      if (voiceLevelMonitorRef.current) {
        clearInterval(voiceLevelMonitorRef.current);
      }
      if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
        websocketRef.current.close(1000, 'Normal closure');
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach(track => track.stop());
        // Also stop the original streams if they exist
        if (audioStreamRef.current._micStream) {
          audioStreamRef.current._micStream.getTracks().forEach(track => track.stop());
        }
        if (audioStreamRef.current._displayStream) {
          audioStreamRef.current._displayStream.getTracks().forEach(track => track.stop());
        }
        // Close the mixing audio context if it exists
        if (audioStreamRef.current._audioContext && audioStreamRef.current._audioContext.state !== 'closed') {
          audioStreamRef.current._audioContext.close();
        }
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }
    };
  }, []);
  
  // Auto-resize textarea as content changes
  useEffect(() => {
    if (transcriptionTextAreaRef.current) {
      transcriptionTextAreaRef.current.style.height = 'auto';
      transcriptionTextAreaRef.current.style.height = transcriptionTextAreaRef.current.scrollHeight + 'px';
      
      // Restore cursor position if it was saved
      if (cursorPositionRef.current !== null) {
        transcriptionTextAreaRef.current.setSelectionRange(
          cursorPositionRef.current,
          cursorPositionRef.current
        );
        cursorPositionRef.current = null;
      }
    }
  }, [transcriptionText]);
  
  // Start continuous recording
  const startRecording = useCallback(async () => {
    try {
      console.log('Starting continuous recording...');
      setIsConnecting(true);
      setError(null);
      
      // Get microphone permission
      console.log('Requesting microphone permission...');
      const micStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 48000
        } 
      });
      console.log('Microphone permission granted, stream:', micStream);
      
      // Get system audio through screen sharing
      console.log('Requesting screen share for system audio...');
      try {
        const displayStream = await navigator.mediaDevices.getDisplayMedia({
          video: true,  // Required even if we only want audio
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            sampleRate: 48000
          }
        });
        console.log('Display stream obtained:', displayStream);
        
        // Stop the video track immediately since we only want audio
        const videoTrack = displayStream.getVideoTracks()[0];
        if (videoTrack) {
          videoTrack.stop();
          console.log('Stopped video track');
        }
        
        // Check if we got audio from the display
        const displayAudioTrack = displayStream.getAudioTracks()[0];
        if (displayAudioTrack) {
          console.log('System audio track obtained:', displayAudioTrack.label);
          
          // Create a combined stream with both mic and system audio
          const audioContext = new (window.AudioContext || window.webkitAudioContext)();
          const micSource = audioContext.createMediaStreamSource(micStream);
          const systemSource = audioContext.createMediaStreamSource(displayStream);
          const destination = audioContext.createMediaStreamDestination();
          
          // Mix both audio sources
          micSource.connect(destination);
          systemSource.connect(destination);
          
          // Use the combined stream
          audioStreamRef.current = destination.stream;
          console.log('Using combined audio stream');
          
          // Store references for cleanup
          audioStreamRef.current._micStream = micStream;
          audioStreamRef.current._displayStream = displayStream;
          audioStreamRef.current._audioContext = audioContext;
        } else {
          console.log('No system audio available, using microphone only');
          audioStreamRef.current = micStream;
        }
      } catch (err) {
        console.log('Screen share cancelled or failed:', err.message);
        console.log('Using microphone only');
        audioStreamRef.current = micStream;
      }
      
      // Set up audio analysis for voice detection
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      audioContextRef.current = new AudioContextClass();
      
      // Resume audio context if suspended (required in some browsers)
      if (audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume();
      }
      
      analyserRef.current = audioContextRef.current.createAnalyser();
      const source = audioContextRef.current.createMediaStreamSource(audioStreamRef.current);
      source.connect(analyserRef.current);
      analyserRef.current.fftSize = 2048; // Higher FFT size for better frequency resolution
      console.log('Audio analyser setup complete:', {
        analyser: !!analyserRef.current,
        audioContext: audioContextRef.current.state,
        stream: !!audioStreamRef.current
      });
      
      // Create WebSocket connection with authentication token
      let accessToken = null;
      try {
        accessToken = await getAccessTokenSilently();
      } catch (error) {
        console.warn('Could not get Auth0 token for WebSocket:', error);
      }
      const wsUrl = accessToken 
        ? `${API_CONFIG.WS_TRANSCRIBE}?token=${accessToken}`
        : API_CONFIG.WS_TRANSCRIBE;
      const ws = new WebSocket(wsUrl);
      websocketRef.current = ws;
      
      ws.onopen = () => {
        console.log('WebSocket connected for continuous transcription');
        console.log('Conversational mode:', conversationalMode, 'User:', userEmail, 'Character:', characterId);

        // Send start recording message with metadata
        const startMessage = {
          event: 'start_continuous',
          data: {
            user_id: 'frontend_user',
            audio_config: {
              sampleRate: 48000,
              channels: 1,
              format: 'webm'
            }
          },
          metadata: {
            conversational_mode: conversationalMode,
            user_email: userEmail,
            character_id: characterId
          }
        };
        ws.send(JSON.stringify(startMessage));
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        switch (data.event) {
          case 'session_started': {
            console.log('Session started, initializing recording segments');
            // Store session ID for polling
            const receivedSessionId = data.data?.session_id;
            if (receivedSessionId) {
              setSessionId(receivedSessionId);
            }
            setIsConnecting(false);
            setIsRecording(true);
            startRecordingSegments(audioStreamRef.current);
            // Start voice level monitoring for UI
            startVoiceLevelMonitoring();
            break;
          }
            
          case 'transcription_segment': {
            console.log('TRANSCRIPTION RECEIVED:', data.data.text);
            console.log('Current transcription text length:', transcriptionText.length);
            console.log('WebSocket state:', websocketRef.current?.readyState);
            console.log('isRecording:', isRecording);
            
            // Always append transcription, even if paused (since pause triggers transcription)
            console.log('TRANSCRIPTION_SEGMENT received with text:', data.data.text);
            console.log('Current transcription text from ref:', transcriptionTextRef.current);
            
            // Save cursor position
            if (transcriptionTextAreaRef.current) {
              cursorPositionRef.current = transcriptionTextAreaRef.current.selectionStart;
            }
            
            // Use the ref to get the most current text
            const currentText = transcriptionTextRef.current;
            // Add line breaks between segments for better readability
            const separator = currentText.trim() ? '\n\n' : '';
            const newText = currentText + separator + data.data.text;
            console.log('New text will be:', newText);
            console.log('Text length before:', currentText.length, 'after:', newText.length);
            
            transcriptionTextRef.current = newText;
            setTranscriptionText(newText);
            setIsProcessing(false);
            // Force a re-render
            setUpdateKey(k => k + 1);
            break;
          }
            
          case 'voice_status': {
            // Real-time voice status from backend
            const voiceStatus = data.data;
            console.log('Backend voice status:', voiceStatus.active ? '🎤 ACTIVE' : '🔇 INACTIVE', 
                        `(confidence: ${voiceStatus.confidence}%)`);
            // Update UI based on backend voice detection
            setVoiceDetected(voiceStatus.active);
            break;
          }
          
          case 'voice_activity': {
            // Voice activity update from backend
            const activity = data.data;
            console.log('Voice activity update:', activity.active ? '🎤 VOICE' : '🔇 SILENT');
            setVoiceDetected(activity.active);
            break;
          }
            
          case 'transcription_paused':
            console.log('Transcription paused confirmed by backend');
            break;
            
          case 'transcription_resumed':
            console.log('Transcription resumed confirmed by backend');
            break;

          case 'conversation_pause_detected': {
            console.log('🗣️ Conversational pause detected - auto-submitting transcription');
            const transcriptionData = data.data;
            console.log('Conversation data:', transcriptionData);

            // Auto-submit the transcription
            if (transcriptionData.text && onSendMessage) {
              console.log('Auto-sending message:', transcriptionData.text);
              onSendMessage(transcriptionData.text, {
                user_email: transcriptionData.user_email,
                character_id: transcriptionData.character_id,
                auto_submitted: true
              });

              // Clear the transcription text after auto-submit
              transcriptionTextRef.current = '';
              setTranscriptionText('');
              console.log('Cleared transcription after auto-submit');
            }
            break;
          }

          case 'error':
            console.error('WebSocket error:', data.data.message);
            setError(data.data.message);
            setIsProcessing(false);
            break;

          default:
            console.log('Unknown event:', data.event);
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error');
        setIsProcessing(false);
      };
      
      ws.onclose = (event) => {
        console.log('WebSocket closed:', event);
        console.log('Close code:', event.code, 'Reason:', event.reason);
        setIsRecording(false);
        setIsProcessing(false);
        if (event.code !== 1000) { // 1000 is normal closure
          setError(`WebSocket closed unexpectedly: ${event.reason || 'Unknown reason'}`);
        }
      };
      
    } catch (err) {
      console.error('Failed to start recording:', err);
      setError(err.message);
      setIsConnecting(false);
    }
  }, [conversationalMode, userEmail, characterId, onSendMessage, getAccessTokenSilently]);
  
  // Simple volume level detection for visual feedback
  const getVolumeLevel = () => {
    if (!analyserRef.current) {
      return 0;
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
    
    return volumeLevel;
  };
  
  // Monitor voice levels for UI feedback
  const startVoiceLevelMonitoring = () => {
    console.log('Starting voice level monitoring...');
    if (voiceLevelMonitorRef.current) {
      cancelAnimationFrame(voiceLevelMonitorRef.current);
    }
    
    // Use requestAnimationFrame for smoother updates
    const updateVoiceLevel = () => {
      if (!analyserRef.current || !isRecording) {
        console.log('Stopping voice monitoring - no analyser or not recording');
        return;
      }
      
      const volumeLevel = getVolumeLevel();
      
      // Update voice level for the visual meter
      setVoiceLevel(volumeLevel);
      
      // Simple threshold for local voice indicator (not used for backend)
      const hasVoice = volumeLevel > 5;
      setVoiceDetected(hasVoice);
      voiceDetectedRef.current = hasVoice;
      
      // Continue monitoring
      if (isRecording) {
        voiceLevelMonitorRef.current = requestAnimationFrame(updateVoiceLevel);
      }
    };
    
    // Start the animation frame loop
    voiceLevelMonitorRef.current = requestAnimationFrame(updateVoiceLevel);
  };
  
  // Start recording segments with voice-based chunking
  const startRecordingSegments = (stream) => {
    console.log('Starting voice-based recording');
    
    const CHUNK_INTERVAL_MS = 100; // How often to check for segments
    const MAX_SEGMENT_DURATION_MS = 30000; // Maximum 30 seconds per segment
    
    let chunks = [];
    let segmentStartTime = Date.now();
    let headerChunk = null;
    let wasPaused = false;
    let allChunksSinceLastSend = []; // Track ALL chunks since last transcription
    
    // Create continuous recorder
    const recorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'
    });
    
    currentRecorderRef.current = recorder;
    
    // Track pending chunks that haven't been added yet
    let pendingChunks = [];
    
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        // Store first chunk as header
        if (!headerChunk) {
          headerChunk = event.data;
        }
        pendingChunks.push(event.data);
        // Also immediately add to allChunksSinceLastSend
        allChunksSinceLastSend.push(event.data);
        
        // Send chunk to backend for real-time voice detection
        if (!isPausedRef.current && websocketRef.current?.readyState === WebSocket.OPEN) {
          const reader = new FileReader();
          reader.onloadend = () => {
            try {
              const base64data = reader.result.split(',')[1];
              websocketRef.current.send(JSON.stringify({
                event: 'audio_chunk_realtime',
                data: {
                  chunk: base64data,
                  timestamp: Date.now()
                }
              }));
              // Log first few chunks to verify sending
              if (allChunksSinceLastSend.length <= 3) {
                console.log(`Sent audio_chunk_realtime #${allChunksSinceLastSend.length}`);
              }
            } catch (error) {
              console.error('Error sending audio chunk:', error);
            }
          };
          reader.onerror = (error) => {
            console.error('FileReader error:', error);
          };
          reader.readAsDataURL(event.data);
        }
      }
    };
    
    // Start continuous recording
    recorder.start(CHUNK_INTERVAL_MS);
    
    // Voice detection loop
    const voiceCheckInterval = setInterval(() => {
      if (!websocketRef.current || websocketRef.current.readyState !== WebSocket.OPEN) {
        clearInterval(voiceCheckInterval);
        if (recorder.state === 'recording') {
          recorder.stop();
        }
        return;
      }
      
      // Add any pending chunks to the main chunks array
      if (pendingChunks.length > 0) {
        chunks.push(...pendingChunks);
        // Move pending chunks to main chunks array
        pendingChunks = [];
      }
      
      const now = Date.now();
      
      // Check if pause state just changed
      if (!wasPaused && isPausedRef.current) {
        // Just paused - force recorder to flush any buffered data
        if (recorder.state === 'recording') {
          console.log('Requesting data from recorder...');
          recorder.requestData(); // Force data to be available
        }
        
        // Wait a bit for the data to be flushed
        setTimeout(() => {
          console.log(`PAUSE: allChunksSinceLastSend has ${allChunksSinceLastSend.length} chunks`);
          console.log(`PAUSE: pendingChunks has ${pendingChunks.length} chunks`);
          console.log(`PAUSE: chunks has ${chunks.length} chunks`);
          
          // Add any remaining pending chunks that might not have been added yet
          if (pendingChunks.length > 0) {
            console.log(`PAUSE: Adding ${pendingChunks.length} pending chunks to allChunksSinceLastSend`);
            allChunksSinceLastSend.push(...pendingChunks);
            pendingChunks = [];
          }
          
          // Send ALL collected audio since last transcription
          if (allChunksSinceLastSend.length > 0) {
            console.log(`PAUSE: Sending ${allChunksSinceLastSend.length} total chunks for transcription`);
            const segmentChunks = [...allChunksSinceLastSend];
            
            // Reset ALL collections
            chunks = [];
            allChunksSinceLastSend = [];
            pendingChunks = [];
            segmentStartTime = now;
            
            // Send the segment with force flag
            console.log('PAUSE: Calling processAndSendSegment with forceSend=true');
            processAndSendSegment(segmentChunks, null, true); // true = force send
          } else {
            console.log('PAUSE: No chunks to send!');
          }
        }, 800); // Increase delay to ensure all data is captured
        
        wasPaused = true;
      } else if (wasPaused && !isPausedRef.current) {
        // Just resumed - reset everything
        console.log('Resumed recording');
        chunks = [];
        pendingChunks = [];
        allChunksSinceLastSend = [];
        segmentStartTime = now;
        wasPaused = false;
      }
      
      // Only process segments when not paused
      if (!isPausedRef.current && !isTTSPlayingRef.current) {
        // Check if we should end the current segment based on time
        const segmentDuration = now - segmentStartTime;
        
        // Send segments periodically (every 400ms) or when max duration reached
        // 400ms gives enough audio for voice detection while staying responsive
        const shouldEndSegment = (
          (segmentDuration >= 400 && chunks.length > 0) || // Send every 400ms if we have data
          (segmentDuration >= MAX_SEGMENT_DURATION_MS) // Max duration reached
        );
        
        if (shouldEndSegment && chunks.length > 0) {
          console.log(`ENDING SEGMENT: after ${segmentDuration}ms with ${chunks.length} chunks`);
          
          // Process and send the segment
          const segmentChunks = [...chunks];
          
          // Reset for next segment
          chunks = [];
          // DON'T reset allChunksSinceLastSend here - only reset it after the segment is actually sent
          segmentStartTime = now;
          
          // Pass a callback to reset allChunksSinceLastSend after successful send
          processAndSendSegment(segmentChunks, () => {
            console.log('Normal segment: Clearing allChunksSinceLastSend after successful send');
            allChunksSinceLastSend = [];
          });
        }
      }
    }, CHUNK_INTERVAL_MS);
    
    // Store interval reference for cleanup
    recordingIntervalRef.current = voiceCheckInterval;
    
    // Helper function to process and send segment
    const processAndSendSegment = async (segmentChunks, onSuccess, forceSend = false) => {
      if (segmentChunks.length === 0 || !websocketRef.current || websocketRef.current.readyState !== WebSocket.OPEN) {
        console.log(`Not sending: chunks=${segmentChunks.length}, ws ready=${websocketRef.current?.readyState === WebSocket.OPEN}`);
        return;
      }
      
      // Always send segments when we have chunks (backend will do voice detection)
      if (forceSend || segmentChunks.length > 0) {
        // Include header chunk if needed
        const allChunks = headerChunk ? [headerChunk, ...segmentChunks] : segmentChunks;
        const audioBlob = new Blob(allChunks, { type: 'audio/webm' });
        
        // Convert to base64 and send
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64data = reader.result.split(',')[1];
          
          if (websocketRef.current?.readyState === WebSocket.OPEN) {
            setIsProcessing(true);
            websocketRef.current.send(JSON.stringify({
              event: 'audio_segment',
              data: {
                audio: base64data,
                timestamp: Date.now()
              }
            }));
            
            // Call success callback if provided
            if (onSuccess) {
              onSuccess();
            }
          }
        };
        reader.readAsDataURL(audioBlob);
      }
    };
  };
  
  // Stop recording
  const stopRecording = useCallback(() => {
    // Stop intervals
    if (recordingIntervalRef.current) {
      clearInterval(recordingIntervalRef.current);
      recordingIntervalRef.current = null;
    }
    if (voiceLevelMonitorRef.current) {
      cancelAnimationFrame(voiceLevelMonitorRef.current);
      voiceLevelMonitorRef.current = null;
    }
    
    // Stop any active recorder
    if (currentRecorderRef.current && currentRecorderRef.current.state !== 'inactive') {
      currentRecorderRef.current.stop();
      currentRecorderRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    
    // Stop audio stream
    if (audioStreamRef.current) {
      // Stop all tracks in the combined stream
      audioStreamRef.current.getTracks().forEach(track => track.stop());
      
      // Also stop the original streams if they exist
      if (audioStreamRef.current._micStream) {
        audioStreamRef.current._micStream.getTracks().forEach(track => track.stop());
      }
      if (audioStreamRef.current._displayStream) {
        audioStreamRef.current._displayStream.getTracks().forEach(track => track.stop());
      }
      
      // Close the mixing audio context if it exists
      if (audioStreamRef.current._audioContext && audioStreamRef.current._audioContext.state !== 'closed') {
        audioStreamRef.current._audioContext.close();
      }
      
      audioStreamRef.current = null;
    }
    
    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    // Close WebSocket
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        event: 'stop_continuous',
        data: {}
      }));
      websocketRef.current.close(1000, 'Normal closure');
    }
    
    setIsRecording(false);
    setSessionId(null);
  }, []);
  
  // Send transcription
  const handleSendTranscription = () => {
    const textToSend = transcriptionText.trim();
    
    if (textToSend && onSendMessage) {
      onSendMessage(textToSend);
      // Clear the transcription after sending
      setTranscriptionText('');
    }
  };
  
  // Clear transcription
  const handleClear = () => {
    setTranscriptionText('');
    transcriptionTextRef.current = '';
    if (transcriptionTextAreaRef.current) {
      transcriptionTextAreaRef.current.focus();
    }
  };
  
  // Expose toggleRecording method via ref (moved here after function definitions)
  useImperativeHandle(ref, () => ({
    toggleRecording: () => {
      if (isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    }
  }), [isRecording, startRecording, stopRecording]);
  
  return (
    <div className="continuous-transcription">
      <div className="header">
        <h3>Voice</h3>
        <div className="controls">
          {!isRecording ? (
            <Button
              className="control-button start"
              onClick={startRecording}
              disabled={isConnecting}
              variant="primary"
            >
              {isConnecting ? '🔄 Connecting...' : '🎤 Start Listening'}
            </Button>
          ) : (
            <>
              <Button
                className="control-button stop"
                onClick={stopRecording}
                variant="danger"
              >
                ⏹️ Stop Listening
              </Button>
              <Button
                className={`control-button pause ${isPaused ? 'paused' : ''}`}
                onClick={() => {
                  const newPausedState = !isPaused;
                  setIsPaused(newPausedState);
                  
                  // Notify backend about pause/resume
                  if (websocketRef.current?.readyState === WebSocket.OPEN) {
                    websocketRef.current.send(JSON.stringify({
                      event: newPausedState ? 'pause_transcription' : 'resume_transcription',
                      data: {}
                    }));
                  }
                }}
                title={isPaused ? "Resume transcription" : "Pause transcription (mic stays on)"}
                variant="secondary"
              >
                {isPaused ? '▶️ Resume' : '⏸️ Pause'}
              </Button>
              <div className="voice-indicator" key={`voice-${voiceDetected}-${voiceLevel}`}>
                <div 
                  className="voice-level" 
                  style={{
                    width: `${voiceLevel}%`,
                    backgroundColor: isPaused ? '#ff9800' : (isTTSPlaying ? '#ff9800' : (voiceDetected ? '#4caf50' : '#666'))
                  }}
                />
                <div className="voice-status">
                  {isPaused ? '⏸️' : (isTTSPlaying ? '⏸️' : (voiceDetected ? '🎤' : '🔇'))}
                </div>
              </div>
              {(isTTSPlaying || isPaused) && (
                <div style={{
                  backgroundColor: '#ff9800',
                  color: 'white',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  textAlign: 'center',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  maxWidth: '150px'
                }}>
                  {isPaused ? 'Paused' : 'TTS playing'}
                </div>
              )}
            </>
          )}
          <Button
            className="control-button clear"
            onClick={handleClear}
            disabled={!transcriptionText.trim()}
            variant="secondary"
          >
            🗑️ Clear
          </Button>
        </div>
      </div>
      
      {error && (
        <div className="error-message">
          ⚠️ {error}
        </div>
      )}
      
      <div className="transcription-container" key={updateKey}>
        <Textarea
          ref={transcriptionTextAreaRef}
          className="transcription-textarea"
          value={transcriptionText}
          onChange={(e) => setTranscriptionText(e.target.value)}
          placeholder="Click 'Start Listening' to begin continuous transcription. You can edit this text at any time."
          onKeyDown={(e) => {
            // Cmd/Ctrl + Enter to send
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              handleSendTranscription();
            }
          }}
        />
        {isProcessing && (
          <div className="processing-indicator">
            <div className="pulse"></div>
            <span>Processing...</span>
          </div>
        )}
      </div>
      
      <div className="send-section">
        <Button
          className="send-button"
          onClick={handleSendTranscription}
          disabled={!transcriptionText.trim()}
          variant="primary"
        >
          📤 Send Text (Ctrl+Enter)
        </Button>
      </div>
    </div>
  );
});

ContinuousTranscription.displayName = 'ContinuousTranscription';

export default ContinuousTranscription;