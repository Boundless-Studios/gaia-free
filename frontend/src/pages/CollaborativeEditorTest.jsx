import { useState, useRef, useEffect } from 'react';
import CollaborativeStackedEditor from '../components/collaborative/CollaborativeStackedEditor';
import './CollaborativeEditorTest.css';

/**
 * CollaborativeEditorTest - Admin test page for multi-user collaborative editing
 *
 * Features:
 * - Simulates multiple players in the same browser window
 * - Each player gets their own editor instance with unique ID
 * - Real WebSocket connections to backend for authentic testing
 * - Demonstrates real-time text sync and cursor tracking
 * - Turn rotation for testing submission permissions
 */
const CollaborativeEditorTest = () => {
  const [sessionId] = useState('collab-test-' + Date.now());
  const [currentTurnPlayerIndex, setCurrentTurnPlayerIndex] = useState(0);
  const [submittedTexts, setSubmittedTexts] = useState([]);
  const [editorGeneration, setEditorGeneration] = useState(0);

  // Players for testing
  const players = [
    { id: 'player-1', name: 'Aragorn' },
    { id: 'player-2', name: 'Gandalf' },
    { id: 'player-3', name: 'Legolas' },
    { id: 'player-4', name: 'Gimli' }
  ];

  // Player color assignment (same logic as in editor component)
  const getPlayerColor = (id) => {
    const colors = [
      '#ef4444', // red
      '#3b82f6', // blue
      '#10b981', // green
      '#f59e0b', // amber
      '#8b5cf6', // violet
      '#ec4899', // pink
      '#06b6d4', // cyan
      '#f97316', // orange
    ];

    let hash = 0;
    for (let i = 0; i < id.length; i++) {
      hash = id.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };

  const playerSocketsRef = useRef(new Map());

  // Create real WebSocket connection to backend collaborative endpoint
  const createRealWebSocket = (playerId) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname;
    const wsPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');

    // For development, connect to backend on port 8000
    const backendPort = process.env.NODE_ENV === 'development' ? '8000' : wsPort;
    const wsUrl = `${wsProtocol}//${wsHost}:${backendPort}/ws/collab/session/${sessionId}`;

    console.log(`[CollabTest] Creating WebSocket for player ${playerId}: ${wsUrl}`);

    try {
      const socket = new WebSocket(wsUrl);

      socket.addEventListener('open', () => {
        console.log(`[CollabTest] WebSocket connected for player ${playerId}`);
      });

      socket.addEventListener('error', (error) => {
        console.error(`[CollabTest] WebSocket error for player ${playerId}:`, error);
      });

      socket.addEventListener('close', () => {
        console.log(`[CollabTest] WebSocket closed for player ${playerId}`);
      });

      return socket;
    } catch (error) {
      console.error(`[CollabTest] Failed to create WebSocket for player ${playerId}:`, error);
      throw error;
    }
  };

  const teardownSockets = () => {
    playerSocketsRef.current.forEach((socket, playerId) => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        console.log(`[CollabTest] Closing socket for player ${playerId}`);
        socket.close();
      }
      playerSocketsRef.current.delete(playerId);
    });
  };

  const resetCollaborationSession = () => {
    teardownSockets();
    setEditorGeneration(prev => prev + 1);
  };

  const getSocketForPlayer = (playerId) => {
    if (!playerSocketsRef.current.has(playerId)) {
      playerSocketsRef.current.set(playerId, createRealWebSocket(playerId));
    }
    return playerSocketsRef.current.get(playerId);
  };

  useEffect(() => {
    return () => {
      teardownSockets();
    };
  }, []);

  // Handle turn submission
  const handleSubmit = (playerId, playerName, text) => {
    const submission = {
      playerId,
      playerName,
      text,
      timestamp: new Date().toISOString()
    };

    setSubmittedTexts(prev => [...prev, submission]);

    // Advance to next player's turn
    setCurrentTurnPlayerIndex(prev => (prev + 1) % players.length);

    // Reset editors for the next turn
    resetCollaborationSession();

    console.log(`${playerName} submitted turn:`, text);
  };

  // Manually advance turn
  const nextTurn = () => {
    setCurrentTurnPlayerIndex(prev => (prev + 1) % players.length);
  };

  // Clear all text
  const clearText = () => {
    resetCollaborationSession();
  };

  return (
    <div className="collaborative-test-page">
      <header className="test-header">
        <h1>Collaborative Editor Test Page</h1>
        <p className="test-description">
          Simulates {players.length} players editing the same text simultaneously.
          Each editor below represents a different player's view.
        </p>
      </header>

      {/* Connected Players Panel */}
      <div className="connected-players-panel">
        <h3>Connected Players</h3>
        <div className="players-list">
          {players.map((player) => (
            <div key={player.id} className="player-badge">
              <span
                className="player-badge-dot"
                style={{ backgroundColor: getPlayerColor(player.id) }}
              />
              <span
                className="player-badge-name"
                style={{ color: getPlayerColor(player.id) }}
              >
                {player.name}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="test-controls">
        <div className="current-turn-info">
          <strong>Current Turn:</strong> {players[currentTurnPlayerIndex].name}
        </div>
        <button onClick={nextTurn} className="control-button">
          Next Turn
        </button>
        <button onClick={clearText} className="control-button secondary">
          Clear Text
        </button>
      </div>

      <div className="editors-grid">
        {players.map((player, index) => (
          <div key={player.id} className="editor-panel">
            <div className="editor-panel-header">
              <h3>{player.name}</h3>
              {index === currentTurnPlayerIndex && (
                <span className="active-turn-badge">Active Turn</span>
              )}
            </div>
            <CollaborativeStackedEditor
              key={`${player.id}-${editorGeneration}`}
              sessionId={sessionId}
              playerId={player.id}
              characterName={player.name}
              allPlayers={players}
              isMyTurn={index === currentTurnPlayerIndex}
              websocket={getSocketForPlayer(player.id)}
            />
          </div>
        ))}
      </div>

      {submittedTexts.length > 0 && (
        <div className="submission-history">
          <h2>Submission History</h2>
          <div className="submissions-list">
            {submittedTexts.map((submission, index) => (
              <div key={index} className="submission-card">
                <div className="submission-header">
                  <strong>{submission.playerName}</strong>
                  <span className="submission-time">
                    {new Date(submission.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="submission-text">{submission.text}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="test-instructions">
        <h3>Testing Instructions</h3>
        <ul>
          <li><strong>Multi-user editing:</strong> Type in any editor - text appears in all editors instantly with proper CRDT sync via backend</li>
          <li><strong>Cursor tracking:</strong> Move cursor in one editor - colored cursor with player name appears in others (CodeMirror native support)</li>
          <li><strong>Selection tracking:</strong> Select text in one editor - highlighted selection visible to all players</li>
          <li><strong>Turn-based submission:</strong> Only the active turn player can submit (Ctrl+Enter or click Submit)</li>
          <li><strong>Conflict resolution:</strong> Type simultaneously in multiple editors - Yjs CRDT ensures no data loss</li>
          <li><strong>Real backend:</strong> Each editor uses a real WebSocket connection to <code>/ws/collab/session</code> endpoint</li>
        </ul>
      </div>
    </div>
  );
};

export default CollaborativeEditorTest;
