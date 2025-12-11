import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import TurnMessage from '../components/player/TurnMessage.jsx';
import { useTurnBasedMessages } from '../hooks/useTurnBasedMessages.js';
import { useGameSocket } from '../hooks/useGameSocket.js';
import { LoadingProvider } from '../contexts/LoadingContext';
import '../components/player/TurnMessage.css';

/**
 * Test page for Turn-Based Message system
 * Tests the new turn-based ordering architecture
 *
 * Access at: /test/turn-messages
 */
const TurnBasedMessagesTestInner = () => {
  // Session/campaign ID for testing
  const [sessionId, setSessionId] = useState('test-session-' + Date.now());
  const [inputSessionId, setInputSessionId] = useState('');

  // Auth for socket connection
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();

  // Test form state
  const [messageText, setMessageText] = useState('I approach the mysterious door carefully.');
  const [playerName, setPlayerName] = useState('Test Player');
  const [dmText, setDmText] = useState('');

  // Test log
  const [testLog, setTestLog] = useState([]);
  const logRef = useRef(null);

  const log = useCallback((message, type = 'info') => {
    const timestamp = new Date().toISOString().split('T')[1].slice(0, 12);
    console.log(`[TurnTest] ${timestamp}: ${message}`);
    setTestLog(prev => [...prev.slice(-50), { timestamp, message, type }]);
  }, []);

  // Scroll log to bottom
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [testLog]);

  // Turn-based messages hook
  const {
    turns,
    turnsByNumber,
    processingTurn,
    currentTurnNumber,
    isProcessing,
    handleTurnStarted,
    handleTurnMessage,
    handleTurnComplete,
    handleTurnError,
    clearTurns,
  } = useTurnBasedMessages(sessionId);

  // WebSocket connection with turn handlers
  const {
    socket,
    isConnected,
    emit,
  } = useGameSocket({
    campaignId: sessionId,
    getAccessToken: isAuthenticated ? getAccessTokenSilently : null,
    role: 'dm',
    handlers: {
      // Turn-based events
      turn_started: (data) => {
        log(`turn_started: turn=${data.turn_number}`, 'event');
        handleTurnStarted(data);
      },
      turn_message: (data) => {
        log(`turn_message: turn=${data.turn_number} idx=${data.response_index} type=${data.response_type}`, 'event');
        handleTurnMessage(data);
      },
      turn_complete: (data) => {
        log(`turn_complete: turn=${data.turn_number}`, 'event');
        handleTurnComplete(data);
      },
      turn_error: (data) => {
        log(`turn_error: turn=${data.turn_number} error=${data.error}`, 'error');
        handleTurnError(data);
      },
      // Other events we want to see
      player_list: (data) => {
        log(`player_list: ${data.players?.length || 0} players`, 'event');
      },
      registered: (data) => {
        log(`registered: ${data.playerId}`, 'event');
      },
      narrative_chunk: (data) => {
        log(`narrative_chunk: ${data.content?.slice(0, 30)}...`, 'event');
      },
      campaign_updated: (data) => {
        log(`campaign_updated received`, 'event');
      },
    },
  });

  // Submit turn via WebSocket
  const handleSubmitTurn = useCallback(() => {
    if (!isConnected) {
      log('Cannot submit: not connected to WebSocket', 'error');
      return;
    }

    const turnData = {
      session_id: sessionId,
      message: messageText,
      active_player_input: {
        character_id: 'test-char-1',
        character_name: playerName,
        text: messageText,
        input_type: 'action',
      },
      observer_inputs: [],
      dm_input: dmText ? {
        text: dmText,
      } : null,
      metadata: {},
    };

    log(`Emitting submit_turn: "${messageText.slice(0, 40)}..."`, 'send');
    emit('submit_turn', turnData);
  }, [isConnected, sessionId, messageText, playerName, dmText, emit, log]);

  // Simulate turn events locally (for testing without backend)
  const handleSimulateTurn = useCallback(() => {
    const turnNum = currentTurnNumber + 1;
    log(`Simulating turn ${turnNum} locally`, 'simulate');

    // Simulate turn_started
    handleTurnStarted({ turn_number: turnNum, session_id: sessionId });

    // Simulate turn_input after short delay
    setTimeout(() => {
      handleTurnMessage({
        message_id: `sim-${turnNum}-0`,
        turn_number: turnNum,
        response_index: 0,
        response_type: 'turn_input',
        role: 'user',
        content: {
          active_player: {
            character_id: 'test-char-1',
            character_name: playerName,
            text: messageText,
          },
          observer_inputs: [],
          dm_input: dmText ? { text: dmText } : null,
          combined_prompt: messageText,
        },
      });
    }, 100);

    // Simulate streaming chunks
    const responseText = 'The ancient door creaks ominously as you approach. You notice strange runes glowing faintly along its frame, pulsing with an otherworldly light. A chill runs down your spine as you realize these symbols are warning glyphs - protective magic left by whoever sealed this chamber long ago.';
    let charIndex = 0;
    const streamInterval = setInterval(() => {
      if (charIndex >= responseText.length) {
        clearInterval(streamInterval);
        // Send final
        setTimeout(() => {
          handleTurnMessage({
            message_id: `sim-${turnNum}-final`,
            turn_number: turnNum,
            response_index: 2,
            response_type: 'final',
            role: 'assistant',
            content: responseText,
            has_audio: false,
          });
          handleTurnComplete({ turn_number: turnNum, session_id: sessionId });
        }, 200);
        return;
      }

      const chunk = responseText.slice(charIndex, charIndex + 5);
      charIndex += 5;
      handleTurnMessage({
        turn_number: turnNum,
        response_index: 1,
        response_type: 'streaming',
        content: chunk,
      });
    }, 30);
  }, [currentTurnNumber, sessionId, playerName, messageText, dmText, handleTurnStarted, handleTurnMessage, handleTurnComplete, log]);

  // Change session ID
  const handleChangeSession = useCallback(() => {
    if (inputSessionId.trim()) {
      setSessionId(inputSessionId.trim());
      clearTurns();
      log(`Changed session to: ${inputSessionId.trim()}`, 'info');
    }
  }, [inputSessionId, clearTurns, log]);

  // Handle image generated (for TurnMessage)
  const handleImageGenerated = useCallback((imageData) => {
    log(`Image generated: ${imageData.generated_image_type}`, 'info');
  }, [log]);

  return (
    <div className="turn-test-page" style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '20px', color: '#e0e0e0' }}>Turn-Based Messages Test</h1>

      {/* Connection Status */}
      <div style={{
        padding: '10px 15px',
        marginBottom: '20px',
        background: isConnected ? 'rgba(74, 158, 255, 0.1)' : 'rgba(255, 74, 74, 0.1)',
        border: `1px solid ${isConnected ? '#4a9eff' : '#ff4a4a'}`,
        borderRadius: '8px',
        display: 'flex',
        gap: '20px',
        alignItems: 'center',
      }}>
        <span style={{ fontWeight: 'bold', color: isConnected ? '#4a9eff' : '#ff4a4a' }}>
          {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
        </span>
        <span style={{ color: '#888' }}>Session: {sessionId}</span>
        <span style={{ color: '#888' }}>Current Turn: {currentTurnNumber}</span>
        <span style={{ color: '#888' }}>Processing: {isProcessing ? `Turn ${processingTurn}` : 'No'}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Left Column - Controls & Log */}
        <div>
          {/* Session Controls */}
          <div style={{
            padding: '15px',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '8px',
            marginBottom: '20px',
          }}>
            <h3 style={{ marginTop: 0, color: '#e0e0e0' }}>Session</h3>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
              <input
                type="text"
                placeholder="Session ID"
                value={inputSessionId}
                onChange={(e) => setInputSessionId(e.target.value)}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  background: '#1a1a1a',
                  border: '1px solid #3a3a3a',
                  borderRadius: '4px',
                  color: '#e0e0e0',
                }}
              />
              <button
                onClick={handleChangeSession}
                style={{
                  padding: '8px 16px',
                  background: '#4a9eff',
                  border: 'none',
                  borderRadius: '4px',
                  color: 'white',
                  cursor: 'pointer',
                }}
              >
                Change Session
              </button>
            </div>
            <button
              onClick={clearTurns}
              style={{
                padding: '8px 16px',
                background: '#ff4a4a',
                border: 'none',
                borderRadius: '4px',
                color: 'white',
                cursor: 'pointer',
              }}
            >
              Clear Turns
            </button>
          </div>

          {/* Turn Submission */}
          <div style={{
            padding: '15px',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '8px',
            marginBottom: '20px',
          }}>
            <h3 style={{ marginTop: 0, color: '#e0e0e0' }}>Submit Turn</h3>

            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#888' }}>Player Name:</label>
              <input
                type="text"
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: '#1a1a1a',
                  border: '1px solid #3a3a3a',
                  borderRadius: '4px',
                  color: '#e0e0e0',
                }}
              />
            </div>

            <div style={{ marginBottom: '10px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#888' }}>Player Action:</label>
              <textarea
                value={messageText}
                onChange={(e) => setMessageText(e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: '#1a1a1a',
                  border: '1px solid #3a3a3a',
                  borderRadius: '4px',
                  color: '#e0e0e0',
                  resize: 'vertical',
                }}
              />
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#888' }}>DM Addition (optional):</label>
              <input
                type="text"
                value={dmText}
                onChange={(e) => setDmText(e.target.value)}
                placeholder="DM context or modification..."
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: '#1a1a1a',
                  border: '1px solid #3a3a3a',
                  borderRadius: '4px',
                  color: '#e0e0e0',
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={handleSubmitTurn}
                disabled={!isConnected || isProcessing}
                style={{
                  flex: 1,
                  padding: '10px 20px',
                  background: isConnected && !isProcessing ? '#4a9eff' : '#555',
                  border: 'none',
                  borderRadius: '4px',
                  color: 'white',
                  cursor: isConnected && !isProcessing ? 'pointer' : 'not-allowed',
                  fontWeight: 'bold',
                }}
              >
                {isProcessing ? 'Processing...' : 'Submit Turn (WebSocket)'}
              </button>
              <button
                onClick={handleSimulateTurn}
                disabled={isProcessing}
                style={{
                  flex: 1,
                  padding: '10px 20px',
                  background: !isProcessing ? '#ffa500' : '#555',
                  border: 'none',
                  borderRadius: '4px',
                  color: 'white',
                  cursor: !isProcessing ? 'pointer' : 'not-allowed',
                  fontWeight: 'bold',
                }}
              >
                Simulate Turn (Local)
              </button>
            </div>
          </div>

          {/* Event Log */}
          <div style={{
            padding: '15px',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '8px',
          }}>
            <h3 style={{ marginTop: 0, color: '#e0e0e0' }}>Event Log</h3>
            <div
              ref={logRef}
              style={{
                height: '300px',
                overflowY: 'auto',
                background: '#0a0a0a',
                padding: '10px',
                borderRadius: '4px',
                fontFamily: 'monospace',
                fontSize: '12px',
              }}
            >
              {testLog.map((entry, i) => (
                <div
                  key={i}
                  style={{
                    color: entry.type === 'error' ? '#ff4a4a' :
                           entry.type === 'event' ? '#4a9eff' :
                           entry.type === 'send' ? '#4aff4a' :
                           entry.type === 'simulate' ? '#ffa500' :
                           '#888',
                    marginBottom: '2px',
                  }}
                >
                  <span style={{ color: '#555' }}>{entry.timestamp}</span> {entry.message}
                </div>
              ))}
              {testLog.length === 0 && (
                <div style={{ color: '#555' }}>No events yet...</div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column - Turn Messages Display */}
        <div>
          <div style={{
            padding: '15px',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '8px',
            minHeight: '500px',
          }}>
            <h3 style={{ marginTop: 0, color: '#e0e0e0' }}>Turn Messages ({turns.length} turns)</h3>

            <div style={{
              maxHeight: '600px',
              overflowY: 'auto',
            }}>
              {turns.length === 0 ? (
                <div style={{
                  padding: '40px',
                  textAlign: 'center',
                  color: '#555',
                }}>
                  No turns yet. Submit a turn or simulate one to see messages here.
                </div>
              ) : (
                turns.map((turn) => (
                  <TurnMessage
                    key={turn.turn_number}
                    turn={turn}
                    campaignId={sessionId}
                    onImageGenerated={handleImageGenerated}
                  />
                ))
              )}
            </div>
          </div>

          {/* Debug State */}
          <div style={{
            padding: '15px',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '8px',
            marginTop: '20px',
          }}>
            <h3 style={{ marginTop: 0, color: '#e0e0e0' }}>Debug State</h3>
            <pre style={{
              background: '#0a0a0a',
              padding: '10px',
              borderRadius: '4px',
              fontSize: '11px',
              color: '#888',
              overflow: 'auto',
              maxHeight: '200px',
            }}>
              {JSON.stringify({
                sessionId,
                isConnected,
                currentTurnNumber,
                processingTurn,
                isProcessing,
                turnsCount: turns.length,
                turnsByNumber: Object.keys(turnsByNumber).map(Number),
              }, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

// Wrap with LoadingProvider
const TurnBasedMessagesTest = () => (
  <LoadingProvider>
    <TurnBasedMessagesTestInner />
  </LoadingProvider>
);

export default TurnBasedMessagesTest;
