import React, { useState, useEffect } from 'react';
import { useAudioStream } from '../../context/audioStreamContext.jsx';
import { API_CONFIG } from '../../config/api.js';
import './AudioDebugPage.css';

/**
 * Debug page for testing audio playback system
 *
 * Features:
 * - Queue multiple audio items using existing mp3s
 * - Monitor WebSocket messages in real-time
 * - View audio playback status
 * - Test frontend playback logic without TTS generation
 *
 * This page is development-only and should not be accessible in production.
 */
export const AudioDebugPage = () => {
  const [sessionId, setSessionId] = useState('debug-session');
  const [numItems, setNumItems] = useState(3);
  const [isLoading, setIsLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [wsMessages, setWsMessages] = useState([]);
  const [error, setError] = useState(null);

  const audioStream = useAudioStream();

  // Monitor WebSocket messages
  useEffect(() => {
    const originalConsoleLog = console.log;

    // Intercept console.log to capture WebSocket messages
    console.log = (...args) => {
      const message = args.join(' ');

      // Capture audio-related WebSocket messages
      if (message.includes('[AUDIO_DEBUG]') ||
          message.includes('audio_stream_started') ||
          message.includes('audio_stream_stopped') ||
          message.includes('DM WebSocket received')) {
        setWsMessages(prev => {
          const newMessage = {
            timestamp: new Date().toISOString(),
            message: message,
          };
          return [newMessage, ...prev].slice(0, 50); // Keep last 50 messages
        });
      }

      // Call original console.log
      originalConsoleLog(...args);
    };

    // Cleanup
    return () => {
      console.log = originalConsoleLog;
    };
  }, []);

  const handleQueueAudio = async () => {
    setIsLoading(true);
    setError(null);
    setLastResult(null);

    try {
      const backendUrl = API_CONFIG.BACKEND_URL || '';
      const url = `${backendUrl}/api/debug/queue-audio-test`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          num_items: numItems,
          use_sample_mp3s: true,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();
      setLastResult(result);

      console.log('[DEBUG_PAGE] ✅ Audio queued successfully:', result);

      // Only start stream if nothing is currently playing AND no pending requests
      // Backend manages queue ordering, frontend auto-advances on completion
      if (result.stream_url && audioStream && !audioStream.isStreaming) {
        // Check if there are OTHER pending requests in the backend queue
        const backendUrl = API_CONFIG.BACKEND_URL || '';
        const checkResponse = await fetch(`${backendUrl}/api/campaigns/${sessionId}/audio/queue`);
        const checkResult = await checkResponse.json();

        // If there are pending requests OTHER than the one we just queued, don't start
        // Let auto-advancement handle it when the current one completes
        if (checkResult.total_pending_requests <= 1) {
          console.log('[DEBUG_PAGE] 🎬 Starting first request:', result.stream_url);
          await audioStream.startStream(
            sessionId,
            0, // position_sec
            false, // isLateJoin
            result.chunk_ids || [], // chunkIds
            result.stream_url // providedStreamUrl
          );
        } else {
          console.log('[DEBUG_PAGE] ⏭️  Queue has %d pending requests, will auto-play:', checkResult.total_pending_requests);
        }
      } else if (audioStream?.isStreaming) {
        console.log('[DEBUG_PAGE] ⏭️  Request queued (will auto-play when current completes):', result.request_id);
      }
    } catch (err) {
      console.error('[DEBUG_PAGE] ❌ Failed to queue audio:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearMessages = () => {
    setWsMessages([]);
  };

  // Test rapid TTS submissions (simulates user selecting and submitting 4 times)
  const handleRapidTTSTest = async () => {
    setIsLoading(true);
    setError(null);
    setLastResult(null);

    try {
      const backendUrl = API_CONFIG.BACKEND_URL || '';
      const url = `${backendUrl}/api/tts/synthesize`;

      const testWords = ['First', 'Second', 'Third', 'Fourth'];

      console.log('[DEBUG_PAGE] 🔥 Starting rapid TTS test: queuing 4 requests in parallel...');

      // Queue 4 TTS requests in parallel (rapid succession)
      const promises = testWords.map(async (word, index) => {
        console.log(`[DEBUG_PAGE] 📤 Submitting playback for "${word}"`);

        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            text: word,
            voice: 'nathaniel',
            speed: 1.0,
            session_id: sessionId,
          }),
        });

        if (!response.ok) {
          throw new Error(`Request ${index + 1} failed: ${response.status}`);
        }

        const result = await response.json();
        console.log(`[DEBUG_PAGE] ✅ Queued playback for "${word}"`);
        return result;
      });

      const results = await Promise.all(promises);

      setLastResult({
        message: `Queued ${results.length} separate TTS requests`,
        requests: results,
      });

      console.log('[DEBUG_PAGE] 🎯 All 4 requests queued successfully');

      // Start playback on the FIRST request (others will auto-play in sequence)
      if (results.length > 0 && results[0].stream_url && audioStream && !audioStream.isStreaming) {
        const firstRequest = results[0];
        console.log('[DEBUG_PAGE] 🎬 Starting first TTS request:', firstRequest.stream_url);

        await audioStream.startStream(
          sessionId,
          0, // position_sec
          false, // isLateJoin
          [], // chunkIds - not needed for TTS
          firstRequest.stream_url // providedStreamUrl
        );
      } else if (audioStream?.isStreaming) {
        console.log('[DEBUG_PAGE] ⏭️  Requests queued (will auto-play when current completes)');
      }

    } catch (err) {
      console.error('[DEBUG_PAGE] ❌ Rapid TTS test failed:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="audio-debug-page">
      <header className="debug-header">
        <h1>🎵 Audio Playback Debug</h1>
        <p className="debug-subtitle">Test audio queue and playback system</p>
      </header>

      <div className="debug-content">
        {/* Control Panel */}
        <section className="debug-section control-panel">
          <h2>Queue Audio Items</h2>

          <div className="control-form">
            <div className="form-group">
              <label htmlFor="session-id">
                Session ID:
                <input
                  id="session-id"
                  type="text"
                  value={sessionId}
                  onChange={(e) => setSessionId(e.target.value)}
                  placeholder="debug-session"
                  data-testid="session-id-input"
                />
              </label>
            </div>

            <div className="form-group">
              <label htmlFor="num-items">
                Number of Items (1-10):
                <input
                  id="num-items"
                  type="number"
                  min="1"
                  max="10"
                  value={numItems}
                  onChange={(e) => setNumItems(parseInt(e.target.value, 10))}
                  data-testid="num-items-input"
                />
              </label>
            </div>

            <button
              onClick={handleQueueAudio}
              disabled={isLoading}
              className="queue-button"
              data-testid="queue-audio-button"
            >
              {isLoading ? 'Queueing...' : `Queue ${numItems} Audio Item${numItems > 1 ? 's' : ''}`}
            </button>

            <button
              onClick={handleRapidTTSTest}
              disabled={isLoading}
              className="queue-button rapid-test-button"
              data-testid="rapid-tts-test-button"
              style={{ marginTop: '10px', backgroundColor: '#ff6b35' }}
            >
              {isLoading ? 'Testing...' : '🔥 Test Rapid TTS (4 Separate Requests)'}
            </button>
          </div>

          {error && (
            <div className="error-message" data-testid="error-message">
              ❌ Error: {error}
            </div>
          )}

          {lastResult && (
            <div className="success-message" data-testid="success-message">
              ✅ {lastResult.message}
              <details>
                <summary>View Details</summary>
                <pre>{JSON.stringify(lastResult, null, 2)}</pre>
              </details>
            </div>
          )}
        </section>

        {/* Playback Status */}
        <section className="debug-section playback-status">
          <h2>Playback Status</h2>

          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Session:</span>
              <span className="status-value" data-testid="current-session">
                {audioStream.currentSessionId || 'None'}
              </span>
            </div>

            <div className="status-item">
              <span className="status-label">Streaming:</span>
              <span className={`status-value ${audioStream.isStreaming ? 'active' : ''}`} data-testid="is-streaming">
                {audioStream.isStreaming ? '🔴 Playing' : '⚪ Idle'}
              </span>
            </div>

            <div className="status-item">
              <span className="status-label">Muted:</span>
              <span className="status-value" data-testid="is-muted">
                {audioStream.isMuted ? '🔇 Yes' : '🔊 No'}
              </span>
            </div>

            <div className="status-item">
              <span className="status-label">Pending Chunks:</span>
              <span className="status-value" data-testid="pending-chunks">
                {audioStream.pendingChunkCount || 0}
              </span>
            </div>

            {audioStream.needsUserGesture && (
              <div className="status-item full-width">
                <button
                  onClick={audioStream.resumePlayback}
                  className="resume-button"
                  data-testid="resume-playback-button"
                >
                  ▶️ Resume Playback (User Gesture Required)
                </button>
              </div>
            )}
          </div>
        </section>

        {/* WebSocket Messages */}
        <section className="debug-section ws-messages">
          <div className="section-header">
            <h2>WebSocket Messages</h2>
            <button
              onClick={handleClearMessages}
              className="clear-button"
              data-testid="clear-messages-button"
            >
              Clear
            </button>
          </div>

          <div className="messages-container" data-testid="ws-messages-container">
            {wsMessages.length === 0 ? (
              <p className="no-messages">No messages yet. Queue some audio to see WebSocket traffic.</p>
            ) : (
              wsMessages.map((msg, index) => (
                <div key={index} className="message-item">
                  <span className="message-timestamp">
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="message-content">{msg.message}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default AudioDebugPage;
