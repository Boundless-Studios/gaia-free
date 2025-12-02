import { useState, useEffect, useRef, useCallback } from 'react';
import * as Y from 'yjs';
import { encodeStateAsUpdate, applyUpdate } from 'yjs';

/**
 * useCollaborativeText - Hook for managing collaborative text editing with Yjs
 *
 * Features:
 * - CRDT-based text synchronization using Yjs
 * - Cursor position tracking for all players
 * - Integration with existing WebSocket infrastructure
 * - Automatic conflict resolution
 *
 * @param {string} sessionId - Campaign/session identifier
 * @param {string} playerId - Current player's unique ID
 * @param {string} characterName - Player's character name
 * @param {object} websocket - WebSocket connection
 * @param {boolean} isActivePlayer - Whether this player has the active turn
 * @returns {object} { text, cursors, updateText, updateCursor, isConnected }
 */
const useCollaborativeText = ({ sessionId, playerId, characterName, websocket, isActivePlayer = false }) => {
  const [text, setText] = useState('');
  const [cursors, setCursors] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  // Refs to persist across renders
  const ydocRef = useRef(null);
  const ytextRef = useRef(null);
  const lastKnownTextRef = useRef('');
  const playerColorRef = useRef(null);

  // Generate consistent color for player based on playerId
  const getPlayerColor = useCallback((id) => {
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

    // Hash playerId to get consistent color
    let hash = 0;
    for (let i = 0; i < id.length; i++) {
      hash = id.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  }, []);

  // Initialize Yjs document
  useEffect(() => {
    if (!ydocRef.current) {
      ydocRef.current = new Y.Doc();
      ytextRef.current = ydocRef.current.getText('content');
      playerColorRef.current = getPlayerColor(playerId);

      // Listen to Yjs text changes
      ytextRef.current.observe(() => {
        const newText = ytextRef.current.toString();
        if (newText !== lastKnownTextRef.current) {
          lastKnownTextRef.current = newText;
          setText(newText);
        }
      });
    }

    return () => {
      // Cleanup
      if (ydocRef.current) {
        ydocRef.current.destroy();
        ydocRef.current = null;
        ytextRef.current = null;
      }
    };
  }, [playerId, getPlayerColor]);

  // WebSocket message handler
  useEffect(() => {
    if (!websocket) return;

    const handleMessage = (event) => {
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;

        switch (data.type) {
          case 'text_sync': {
            // Initial sync or full text update from another player
            if (data.sessionId === sessionId && ytextRef.current) {
              const currentText = ytextRef.current.toString();
              if (data.text !== currentText) {
                // Replace entire text
                ytextRef.current.delete(0, currentText.length);
                ytextRef.current.insert(0, data.text);
              }
            }
            break;
          }

          case 'text_edit': {
            // Incremental edit from another player
            if (data.sessionId === sessionId && data.playerId !== playerId && ytextRef.current) {
              const { operation } = data;

              if (operation.type === 'insert') {
                ytextRef.current.insert(operation.pos, operation.text);
              } else if (operation.type === 'delete') {
                ytextRef.current.delete(operation.pos, operation.length);
              }
            }
            break;
          }

          case 'cursor_update': {
            // Cursor position update from another player
            if (data.sessionId === sessionId) {
              setCursors(prevCursors => {
                const filtered = prevCursors.filter(c => c.playerId !== data.playerId);

                // Add/update cursor
                return [
                  ...filtered,
                  {
                    playerId: data.playerId,
                    characterName: data.characterName,
                    position: data.position,
                    selection: data.selection,
                    color: data.color || getPlayerColor(data.playerId),
                    isActivePlayer: data.isActivePlayer || false,
                    lastUpdate: Date.now()
                  }
                ];
              });
            }
            break;
          }

          case 'player_disconnected': {
            // Remove cursor when player disconnects
            if (data.sessionId === sessionId) {
              setCursors(prevCursors =>
                prevCursors.filter(c => c.playerId !== data.playerId)
              );
            }
            break;
          }

          case 'collaborative_editor_sync': {
            // Full state sync (cursors + text)
            if (data.sessionId === sessionId) {
              if (data.text && ytextRef.current) {
                const currentText = ytextRef.current.toString();
                if (data.text !== currentText) {
                  ytextRef.current.delete(0, currentText.length);
                  ytextRef.current.insert(0, data.text);
                }
              }

              if (data.cursors) {
                setCursors(data.cursors.filter(c => c.playerId !== playerId));
              }
            }
            break;
          }
        }
      } catch (error) {
        console.error('Error handling collaborative text message:', error);
      }
    };

    // Check if websocket has addEventListener (browser WebSocket API or mock)
    if (websocket.addEventListener) {
      websocket.addEventListener('message', handleMessage);

      // Set initial connection status
      const currentStatus = websocket.readyState === 1; // 1 = OPEN
      setIsConnected(currentStatus);

      // Listen for connection state changes (real WebSocket only)
      const handleOpen = () => setIsConnected(true);
      const handleClose = () => setIsConnected(false);

      websocket.addEventListener('open', handleOpen);
      websocket.addEventListener('close', handleClose);

      return () => {
        websocket.removeEventListener('message', handleMessage);
        websocket.removeEventListener('open', handleOpen);
        websocket.removeEventListener('close', handleClose);
      };
    } else {
      // Custom WebSocket wrapper (like in useDMWebSocket)
      console.warn('WebSocket does not have addEventListener, skipping message handler setup');
      setIsConnected(false);
    }
  }, [websocket, sessionId, playerId, characterName, getPlayerColor]);

  // Clean up stale cursors (older than 30 seconds)
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      setCursors(prevCursors =>
        prevCursors.filter(c => now - c.lastUpdate < 30000)
      );
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Update text locally and broadcast to others
  const updateText = useCallback((newText) => {
    if (!ytextRef.current || !websocket) return;

    const currentText = ytextRef.current.toString();

    // Calculate diff and apply to Yjs
    if (newText !== currentText) {
      // Simple diff algorithm (can be optimized)
      const minLength = Math.min(newText.length, currentText.length);
      let commonPrefix = 0;

      while (commonPrefix < minLength && newText[commonPrefix] === currentText[commonPrefix]) {
        commonPrefix++;
      }

      let commonSuffix = 0;
      while (
        commonSuffix < minLength - commonPrefix &&
        newText[newText.length - 1 - commonSuffix] === currentText[currentText.length - 1 - commonSuffix]
      ) {
        commonSuffix++;
      }

      const deleteLength = currentText.length - commonPrefix - commonSuffix;
      const insertText = newText.substring(commonPrefix, newText.length - commonSuffix);

      // Apply to Yjs
      if (deleteLength > 0) {
        ytextRef.current.delete(commonPrefix, deleteLength);
      }
      if (insertText.length > 0) {
        ytextRef.current.insert(commonPrefix, insertText);
      }

      // Broadcast changes
      if (deleteLength > 0) {
        websocket.send(JSON.stringify({
          type: 'text_edit',
          sessionId,
          playerId,
          operation: {
            type: 'delete',
            pos: commonPrefix,
            length: deleteLength
          },
          timestamp: new Date().toISOString()
        }));
      }

      if (insertText.length > 0) {
        websocket.send(JSON.stringify({
          type: 'text_edit',
          sessionId,
          playerId,
          operation: {
            type: 'insert',
            pos: commonPrefix,
            text: insertText
          },
          timestamp: new Date().toISOString()
        }));
      }
    }
  }, [websocket, sessionId, playerId]);

  // Update cursor position and broadcast
  const updateCursor = useCallback((position, selectionEnd = null) => {
    if (!websocket) return;

    websocket.send(JSON.stringify({
      type: 'cursor_update',
      sessionId,
      playerId,
      characterName,
      position,
      selection: selectionEnd !== null ? { start: position, end: selectionEnd } : null,
      color: playerColorRef.current,
      isActivePlayer,
      timestamp: new Date().toISOString()
    }));
  }, [websocket, sessionId, playerId, characterName, isActivePlayer]);

  return {
    text,
    cursors,
    updateText,
    updateCursor,
    isConnected
  };
};

export default useCollaborativeText;
