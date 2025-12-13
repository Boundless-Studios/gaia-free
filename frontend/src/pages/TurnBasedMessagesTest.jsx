import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import TurnMessage from '../components/player/TurnMessage.jsx';
import PlayerView from '../components/player/PlayerView.jsx';
import { useTurnBasedMessages } from '../hooks/useTurnBasedMessages.js';
import { useGameSocket } from '../hooks/useGameSocket.js';
import { LoadingProvider } from '../contexts/LoadingContext';
import apiService from '../services/apiService.js';
import '../components/player/TurnMessage.css';
import '../components/player/PlayerView.css';

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

  // Messages container ref for autoscroll
  const messagesContainerRef = useRef(null);

  // Streaming state (like PlayerPage)
  const [streamingNarrative, setStreamingNarrative] = useState('');
  const [isNarrativeStreaming, setIsNarrativeStreaming] = useState(false);
  const streamingTurnRef = useRef(null); // Track which turn the streaming belongs to

  // Message history from API
  const [apiMessages, setApiMessages] = useState([]);

  // Tab switching test (simulates PlayerView behavior)
  const [simulatedTab, setSimulatedTab] = useState('voice');
  const [highlightInteract, setHighlightInteract] = useState(false);
  const wasProcessingRef = useRef(false);
  const [tabSwitchLog, setTabSwitchLog] = useState([]);

  // Toggle to show/hide embedded PlayerView
  const [showPlayerView, setShowPlayerView] = useState(true);

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

  // Turn-based messages hook - MUST be before any code that uses its values
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

  // Tab switching simulation (mirrors PlayerView logic)
  // This tests if isProcessing correctly triggers tab switches
  const isAnyTurnStreaming = turns.some(turn => turn.isStreaming);
  const isCurrentlyProcessing = isProcessing || isNarrativeStreaming || isAnyTurnStreaming;

  useEffect(() => {
    const timestamp = new Date().toISOString().split('T')[1].slice(0, 12);
    const logEntry = {
      timestamp,
      isProcessing,
      isNarrativeStreaming,
      isAnyTurnStreaming,
      isCurrentlyProcessing,
      wasProcessing: wasProcessingRef.current,
    };

    if (isCurrentlyProcessing && !wasProcessingRef.current) {
      // Processing just started - switch to history tab
      setSimulatedTab('history');
      setHighlightInteract(false);
      setTabSwitchLog(prev => [...prev.slice(-20), {
        ...logEntry,
        action: 'SWITCH_TO_HISTORY',
        reason: isProcessing ? 'isProcessing=true' : isNarrativeStreaming ? 'isNarrativeStreaming=true' : 'turn.isStreaming=true',
      }]);
    } else if (!isCurrentlyProcessing && wasProcessingRef.current) {
      // Processing just ended - highlight interact tab
      setHighlightInteract(true);
      setTabSwitchLog(prev => [...prev.slice(-20), {
        ...logEntry,
        action: 'HIGHLIGHT_INTERACT',
        reason: 'Processing completed',
      }]);
    }
    wasProcessingRef.current = isCurrentlyProcessing;
  }, [isCurrentlyProcessing, isProcessing, isNarrativeStreaming, isAnyTurnStreaming]);

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
      // Handle narrative_chunk like the real app does
      narrative_chunk: (data) => {
        log(`narrative_chunk: "${data.content?.slice(0, 30)}..." final=${data.is_final}`, 'event');

        if (data.content) {
          // Use existing turn if already started (from handleSubmitTurn), otherwise create new
          if (!streamingTurnRef.current) {
            const turnNum = currentTurnNumber + 1;
            streamingTurnRef.current = turnNum;
            handleTurnStarted({ turn_number: turnNum, session_id: sessionId });
          }

          // Accumulate streaming content
          setStreamingNarrative(prev => prev + data.content);
          setIsNarrativeStreaming(!data.is_final);

          // Send as streaming turn message
          handleTurnMessage({
            turn_number: streamingTurnRef.current,
            response_index: 1,
            response_type: 'streaming',
            content: data.content,
          });
        }

        if (data.is_final && streamingTurnRef.current) {
          const turnNum = streamingTurnRef.current;
          // Get the full accumulated text and send final
          setStreamingNarrative(prev => {
            const fullText = prev + (data.content || '');
            // Send final message
            handleTurnMessage({
              message_id: `narrative-${Date.now()}`,
              turn_number: turnNum,
              response_index: 2,
              response_type: 'final',
              role: 'assistant',
              content: fullText,
              has_audio: false,
            });
            handleTurnComplete({ turn_number: turnNum, session_id: sessionId });
            return ''; // Reset streaming
          });
          streamingTurnRef.current = null;
          setIsNarrativeStreaming(false);
        }
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

    // Start a new turn immediately with the player input
    const turnNum = currentTurnNumber + 1;
    streamingTurnRef.current = turnNum;

    handleTurnStarted({ turn_number: turnNum, session_id: sessionId });

    // Send turn_input immediately so player input shows
    handleTurnMessage({
      message_id: `submit-${turnNum}-input`,
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
  }, [isConnected, sessionId, messageText, playerName, dmText, emit, log, currentTurnNumber, handleTurnStarted, handleTurnMessage]);

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

  // Load campaign messages from API and convert to turns
  const handleLoadCampaign = useCallback(async () => {
    if (!sessionId) {
      log('No session ID provided', 'error');
      return;
    }

    log(`Loading campaign: ${sessionId}...`, 'info');

    try {
      const data = await apiService.readSimpleCampaign(sessionId);
      log(`Loaded campaign: ${data?.name || sessionId}`, 'info');

      if (data?.messages && Array.isArray(data.messages)) {
        setApiMessages(data.messages);
        log(`Found ${data.messages.length} messages`, 'info');

        // Convert messages to turns
        // Group messages by their turn_number if available, otherwise create pseudo-turns
        clearTurns();

        let turnNum = 0;
        let currentTurnMessages = [];

        data.messages.forEach((msg, idx) => {
          // Start a new turn on each user message
          if (msg.sender === 'user' || msg.role === 'user') {
            if (currentTurnMessages.length > 0) {
              // Process previous turn
              processTurn(turnNum, currentTurnMessages);
            }
            turnNum++;
            currentTurnMessages = [msg];
          } else {
            currentTurnMessages.push(msg);
          }
        });

        // Process final turn
        if (currentTurnMessages.length > 0) {
          processTurn(turnNum, currentTurnMessages);
        }

        log(`Created ${turnNum} turns from history`, 'info');
      }
    } catch (error) {
      log(`Failed to load campaign: ${error.message}`, 'error');
    }
  }, [sessionId, clearTurns, log, handleTurnStarted, handleTurnMessage, handleTurnComplete]);

  // Helper to convert message groups to turns
  const processTurn = useCallback((turnNum, messages) => {
    if (turnNum === 0 || messages.length === 0) return;

    handleTurnStarted({ turn_number: turnNum, session_id: sessionId });

    // Find user and DM messages
    const userMsg = messages.find(m => m.sender === 'user' || m.role === 'user');
    const dmMsg = messages.find(m => m.sender === 'dm' || m.role === 'assistant');

    // Send turn_input
    if (userMsg) {
      handleTurnMessage({
        message_id: userMsg.message_id || `hist-${turnNum}-input`,
        turn_number: turnNum,
        response_index: 0,
        response_type: 'turn_input',
        role: 'user',
        content: {
          active_player: {
            character_id: userMsg.character_id || 'player',
            character_name: userMsg.character_name || userMsg.characterName || 'Player',
            text: userMsg.text || userMsg.content || '',
          },
          observer_inputs: [],
          dm_input: null,
          combined_prompt: userMsg.text || userMsg.content || '',
        },
      });
    }

    // Send final DM response
    if (dmMsg) {
      handleTurnMessage({
        message_id: dmMsg.message_id || `hist-${turnNum}-dm`,
        turn_number: turnNum,
        response_index: 2,
        response_type: 'final',
        role: 'assistant',
        content: dmMsg.text || dmMsg.content || '',
        character_name: 'DM',
        has_audio: dmMsg.hasAudio || false,
      });
    }

    handleTurnComplete({ turn_number: turnNum, session_id: sessionId });
  }, [sessionId, handleTurnStarted, handleTurnMessage, handleTurnComplete]);

  // Autoscroll messages container when turns change or streaming updates
  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [turns.length, streamingNarrative]);

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
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={handleLoadCampaign}
                style={{
                  padding: '8px 16px',
                  background: '#4aff4a',
                  border: 'none',
                  borderRadius: '4px',
                  color: 'black',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                }}
              >
                Load Campaign
              </button>
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

            <div
              ref={messagesContainerRef}
              style={{
                maxHeight: '600px',
                overflowY: 'auto',
              }}
            >
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
            }}
            data-testid="debug-state"
            >
              {JSON.stringify({
                sessionId,
                isConnected,
                currentTurnNumber,
                processingTurn,
                isProcessing,
                turnsCount: turns.length,
                turnsByNumber: Object.keys(turnsByNumber).map(Number),
                apiMessagesCount: apiMessages.length,
                isNarrativeStreaming,
                isAnyTurnStreaming,
                isCurrentlyProcessing,
                simulatedTab,
                highlightInteract,
              }, null, 2)}
            </pre>
          </div>

          {/* Tab Switch Log */}
          <div style={{
            padding: '15px',
            background: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '8px',
            marginTop: '20px',
          }}>
            <h3 style={{ marginTop: 0, color: '#e0e0e0' }}>Tab Switch Log</h3>
            <div
              data-testid="tab-switch-log"
              style={{
                maxHeight: '150px',
                overflowY: 'auto',
                background: '#0a0a0a',
                padding: '10px',
                borderRadius: '4px',
                fontFamily: 'monospace',
                fontSize: '11px',
              }}
            >
              {tabSwitchLog.length === 0 ? (
                <div style={{ color: '#555' }}>No tab switches yet...</div>
              ) : (
                tabSwitchLog.map((entry, i) => (
                  <div
                    key={i}
                    style={{
                      color: entry.action === 'SWITCH_TO_HISTORY' ? '#4aff4a' : '#ffa500',
                      marginBottom: '4px',
                    }}
                  >
                    <span style={{ color: '#555' }}>{entry.timestamp}</span>{' '}
                    <strong>{entry.action}</strong> - {entry.reason}
                    <br />
                    <span style={{ color: '#666', fontSize: '10px' }}>
                      isProcessing={String(entry.isProcessing)}, isNarrativeStreaming={String(entry.isNarrativeStreaming)}, isAnyTurnStreaming={String(entry.isAnyTurnStreaming)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Embedded PlayerView Section */}
      <div style={{ marginTop: '30px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '15px',
          marginBottom: '15px',
        }}>
          <h2 style={{ margin: 0, color: '#e0e0e0' }}>Embedded PlayerView</h2>
          <button
            onClick={() => setShowPlayerView(!showPlayerView)}
            style={{
              padding: '6px 12px',
              background: showPlayerView ? '#4a9eff' : '#555',
              border: 'none',
              borderRadius: '4px',
              color: 'white',
              cursor: 'pointer',
            }}
          >
            {showPlayerView ? 'Hide' : 'Show'}
          </button>
          <span
            data-testid="player-view-state"
            style={{
              padding: '4px 8px',
              background: isProcessing ? 'rgba(74, 255, 74, 0.2)' : 'rgba(255, 255, 255, 0.1)',
              borderRadius: '4px',
              fontSize: '12px',
              color: isProcessing ? '#4aff4a' : '#888',
            }}
          >
            isProcessing: {String(isProcessing)}
          </span>
        </div>

        {showPlayerView && (
          <div
            style={{
              border: '2px solid #3a3a3a',
              borderRadius: '8px',
              overflow: 'hidden',
              height: '600px',
              background: '#1a1a1a',
            }}
            data-testid="embedded-player-view"
          >
            <PlayerView
              campaignId={sessionId}
              playerId="test-player"
              characterData={{ name: playerName, id: 'test-char-1' }}
              latestStructuredData={null}
              campaignMessages={apiMessages}
              turns={turns}
              isProcessing={isProcessing}
              streamingNarrative={streamingNarrative}
              streamingResponse=""
              isNarrativeStreaming={isNarrativeStreaming}
              isResponseStreaming={false}
              onPlayerAction={(action) => log(`PlayerView action: ${JSON.stringify(action)}`, 'event')}
              onLoadCampaignData={handleLoadCampaign}
            />
          </div>
        )}
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
