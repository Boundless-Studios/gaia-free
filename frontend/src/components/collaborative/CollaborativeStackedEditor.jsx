import { useState, useEffect, useRef, useCallback, useMemo, useImperativeHandle, forwardRef } from 'react';
import PropTypes from 'prop-types';
import * as Y from 'yjs';
import './CollaborativeStackedEditor.css';

const REMOTE_ORIGIN = Symbol('collaboration-remote-update');

/**
 * CollaborativeStackedEditor - Stacked text boxes for each player
 *
 * Each player has their own isolated text entry. No shared editing.
 * Players can see each other's text (read-only) but only edit their own.
 *
 * Visual layout:
 * ┌─────────────────────┐
 * │ [Aragorn]:         │ ← Dark, non-editable label
 * ├─────────────────────┤
 * │ Player's text here │ ← Light, editable (if my section)
 * └─────────────────────┘
 * ───────────────────────
 * ┌─────────────────────┐
 * │ [Gandalf]:         │
 * ├─────────────────────┤
 * │ ...                │ ← Read-only for other players
 * └─────────────────────┘
 */
const CollaborativeStackedEditor = forwardRef(({
  sessionId,
  playerId,
  characterName,
  allPlayers = [],
  websocket,
  isMyTurn = false,
  onSubmit = null,
  showHeader = true,
  onConnectionChange = null,
  onMySectionChange = null,
  layout = 'stacked',
  // Voice transcription props
  isTranscribing = false,
  onToggleTranscription = null,
  showMicButton = false,
  voiceLevel = 0,
  // Show inline submit button in player's own section
  showInlineSubmit = false,
}, ref) => {
  const [isConnected, setIsConnected] = useState(false);
  // playerContents: { [playerId]: string } - each player's text content
  const [playerContents, setPlayerContents] = useState({});
  const [partialOverlays, setPartialOverlays] = useState({}); // {playerId: partialText}
  const ydocRef = useRef(null);
  const yMapRef = useRef(null);
  const textareasRef = useRef({});
  const registeredWebSocketRef = useRef(null);
  const lastLocalEditTimeRef = useRef(0);
  const isPushToTalkActiveRef = useRef(false);

  // Push-to-talk hotkey: Hold backtick (`) to enable voice transcription
  useEffect(() => {
    if (!showMicButton || !onToggleTranscription) return;

    const handleKeyDown = (e) => {
      if (e.key !== '`') return;
      if (isPushToTalkActiveRef.current) return;

      const activeElement = document.activeElement;
      const isInputFocused = activeElement && (
        activeElement.tagName === 'INPUT' ||
        activeElement.tagName === 'TEXTAREA' ||
        activeElement.isContentEditable
      );

      if (isInputFocused) return;

      e.preventDefault();
      isPushToTalkActiveRef.current = true;
      if (!isTranscribing) {
        console.log('🎤 Push-to-talk: Starting transcription (backtick held)');
        onToggleTranscription();
      }
    };

    const handleKeyUp = (e) => {
      if (e.key !== '`') return;
      if (!isPushToTalkActiveRef.current) return;

      isPushToTalkActiveRef.current = false;
      if (isTranscribing) {
        console.log('🎤 Push-to-talk: Stopping transcription (backtick released)');
        onToggleTranscription();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [showMicButton, onToggleTranscription, isTranscribing]);

  // Notify parent of connection state changes
  useEffect(() => {
    if (onConnectionChange) {
      onConnectionChange(isConnected);
    }
  }, [isConnected, onConnectionChange]);

  const logPrefix = useMemo(() => `[StackedCollab:${sessionId}:${playerId}]`, [sessionId, playerId]);
  const logDebug = useMemo(() => (...args) => console.debug(logPrefix, ...args), [logPrefix]);
  const logWarn = useMemo(() => (...args) => console.warn(logPrefix, ...args), [logPrefix]);
  const logError = useMemo(() => (...args) => console.error(logPrefix, ...args), [logPrefix]);

  // Initialize Yjs document with a Map structure (each player has their own key)
  useEffect(() => {
    if (!websocket) {
      logDebug('Initialization skipped – websocket not available');
      return;
    }

    logDebug('Starting collaborative session initialization');

    const ydoc = new Y.Doc();
    // Use a Map where each player's ID maps to their text content
    const yMap = ydoc.getMap('playerContents');
    ydocRef.current = ydoc;
    yMapRef.current = yMap;

    // Update local state whenever the Yjs map changes
    const updateContents = () => {
      const contents = {};
      yMap.forEach((value, key) => {
        contents[key] = value;
      });
      setPlayerContents(contents);
      logDebug('Updated player contents from Yjs', { playerCount: Object.keys(contents).length });

      // Notify parent of my section changes
      if (onMySectionChange) {
        onMySectionChange(contents[playerId] || '');
      }
    };

    yMap.observe(updateContents);
    updateContents(); // Initial render

    // Socket.IO message handlers
    const handleYjsUpdateMessage = (data) => {
      try {
        logDebug('Received yjs_update', { from: data.playerId });

        if (data.sessionId !== sessionId || !Array.isArray(data.update)) {
          return;
        }

        const isVoiceUpdate = data.source === 'voice';
        const isFromOtherPlayer = data.playerId !== playerId;

        // Apply updates from other players OR voice updates (even from self)
        if (isFromOtherPlayer || isVoiceUpdate) {
          if (isVoiceUpdate && !isFromOtherPlayer) {
            const timeSinceEdit = Date.now() - lastLocalEditTimeRef.current;
            if (timeSinceEdit < 2000) {
              logDebug('Ignoring voice update within 2s of local edit', { timeSinceEdit });
              return;
            }
          }
          const update = new Uint8Array(data.update);
          Y.applyUpdate(ydoc, update, REMOTE_ORIGIN);
          logDebug('Applied Yjs update', { from: data.playerId, source: data.source || 'peer' });
        }
      } catch (error) {
        logError('Error handling yjs_update', error);
      }
    };

    const handlePartialOverlayMessage = (data) => {
      try {
        if (data.sessionId !== sessionId) return;

        const overlayPlayerId = data.playerId;
        const overlayText = data.text || '';

        setPartialOverlays(prev => {
          if (overlayText) {
            return { ...prev, [overlayPlayerId]: overlayText };
          } else {
            const { [overlayPlayerId]: _, ...rest } = prev;
            return rest;
          }
        });
        logDebug('Updated partial overlay', { playerId: overlayPlayerId, hasText: !!overlayText });
      } catch (error) {
        logError('Error handling partial_overlay', error);
      }
    };

    const handleInitialState = (data) => {
      try {
        if (Array.isArray(data.update)) {
          const update = new Uint8Array(data.update);
          Y.applyUpdate(ydoc, update, REMOTE_ORIGIN);
          logDebug('Applied initial_state from backend', { size: data.update.length });
        }
      } catch (error) {
        logError('Error handling initial_state', error);
      }
    };

    const handleVoiceCommitted = (data) => {
      try {
        if (data.sessionId !== sessionId) return;
        if (data.playerId !== playerId) {
          logDebug('Ignoring voice_committed for other player', { from: data.playerId });
          return;
        }

        const text = data.text || '';
        if (!text) return;

        logDebug('Received voice_committed, appending text', { length: text.length });

        // Append voice text to my section
        ydoc.transact(() => {
          const currentContent = yMap.get(playerId) || '';
          const spacer = currentContent && !currentContent.endsWith(' ') && !currentContent.endsWith('\n') ? ' ' : '';
          yMap.set(playerId, currentContent + spacer + text);
        });

        logDebug('Inserted voice text into player section', { textLength: text.length });
      } catch (error) {
        logError('Error handling voice_committed', error);
      }
    };

    // Broadcast local Yjs changes via Socket.IO
    const handleYjsUpdate = (update, origin) => {
      if (origin === REMOTE_ORIGIN) {
        logDebug('Skipping broadcast – applied remote Yjs update');
        return;
      }

      lastLocalEditTimeRef.current = Date.now();

      if (!websocket || !websocket.connected) {
        logWarn('Cannot broadcast Yjs update – socket not connected');
        return;
      }

      websocket.emit('yjs_update', {
        sessionId,
        playerId,
        update: Array.from(update),
        timestamp: new Date().toISOString()
      });

      logDebug('Broadcasting Yjs update', { size: update.length });
    };

    const sendRegistration = () => {
      if (registeredWebSocketRef.current === websocket) {
        logDebug('Skipping registration - already registered with this websocket');
        return;
      }

      if (!websocket.connected) {
        logDebug('Skipping registration - socket not connected');
        return;
      }

      websocket.emit('register', {
        playerId,
        playerName: characterName,
        timestamp: new Date().toISOString()
      });

      registeredWebSocketRef.current = websocket;
      logDebug('Sent registration message', { playerId, playerName: characterName });
    };

    const handleConnect = () => {
      logDebug('Socket connected');
      setIsConnected(true);
      sendRegistration();
    };

    const handleDisconnect = () => {
      logDebug('Socket disconnected');
      setIsConnected(false);
      registeredWebSocketRef.current = null;
    };

    setIsConnected(websocket.connected === true);

    websocket.on('yjs_update', handleYjsUpdateMessage);
    websocket.on('partial_overlay', handlePartialOverlayMessage);
    websocket.on('initial_state', handleInitialState);
    websocket.on('voice_committed', handleVoiceCommitted);
    websocket.on('connect', handleConnect);
    websocket.on('disconnect', handleDisconnect);

    ydoc.on('update', handleYjsUpdate);

    if (websocket.connected) {
      sendRegistration();
    }

    return () => {
      logDebug('Destroying collaboration resources');

      websocket.off('yjs_update', handleYjsUpdateMessage);
      websocket.off('partial_overlay', handlePartialOverlayMessage);
      websocket.off('initial_state', handleInitialState);
      websocket.off('voice_committed', handleVoiceCommitted);
      websocket.off('connect', handleConnect);
      websocket.off('disconnect', handleDisconnect);

      ydoc.off('update', handleYjsUpdate);
      yMap.unobserve(updateContents);
      ydoc.destroy();
      setIsConnected(false);
    };
  }, [websocket, sessionId, playerId, characterName, logDebug, logWarn, logError, onMySectionChange]);

  // Handle text change for a player's textarea
  const handleTextChange = useCallback((targetPlayerId, newContent) => {
    const yMap = yMapRef.current;
    const ydoc = ydocRef.current;
    if (!yMap || !ydoc) return;

    // Only allow editing own section
    if (targetPlayerId !== playerId) {
      logWarn('Attempted to edit another player\'s section', { targetPlayerId, myId: playerId });
      return;
    }

    ydoc.transact(() => {
      yMap.set(playerId, newContent);
    });

    logDebug('Updated my section', { length: newContent.length });
  }, [playerId, logDebug, logWarn]);

  // Clear all player text in the Yjs document
  const clearAllText = useCallback(() => {
    const yMap = yMapRef.current;
    const ydoc = ydocRef.current;
    if (!yMap || !ydoc) return;

    ydoc.transact(() => {
      yMap.forEach((_, key) => {
        yMap.set(key, '');
      });
    });

    logDebug('Cleared all player text');
  }, [logDebug]);

  // Submit current player's input
  const handleSubmitMyInput = useCallback(() => {
    if (!onSubmit) return;

    const myContent = playerContents[playerId] || '';

    // If DM is submitting, combine all player inputs
    if (characterName === 'DM') {
      const combinedInput = allPlayers
        .map(player => {
          const content = (playerContents[player.id] || '').trim();
          return content ? `[${player.name}]: ${content}` : null;
        })
        .filter(Boolean)
        .join('\n\n');

      // DM can submit even with empty content (means "continue")
      onSubmit(combinedInput || '');
      clearAllText();
    } else {
      // Regular player submission (just their part)
      if (myContent.trim()) {
        onSubmit(myContent.trim());
      }
    }
  }, [onSubmit, playerContents, playerId, characterName, allPlayers, clearAllText]);

  // Insert text into current player's section
  const insertTextIntoMySection = useCallback((textToInsert) => {
    const yMap = yMapRef.current;
    const ydoc = ydocRef.current;
    if (!yMap || !ydoc || !textToInsert) return;

    ydoc.transact(() => {
      const currentContent = yMap.get(playerId) || '';
      const spacer = currentContent && !currentContent.endsWith(' ') && !currentContent.endsWith('\n') ? ' ' : '';
      yMap.set(playerId, currentContent + spacer + textToInsert);
    });

    logDebug('Inserted text into my section', { textLength: textToInsert.length });
  }, [playerId, logDebug]);

  // Replace text in current player's section
  const replaceMySection = useCallback((newText) => {
    const yMap = yMapRef.current;
    const ydoc = ydocRef.current;
    if (!yMap || !ydoc) return;

    ydoc.transact(() => {
      yMap.set(playerId, newText || '');
    });

    logDebug('Replaced my section', { textLength: newText?.length || 0 });
  }, [playerId, logDebug]);

  // Get current player's text content
  const getMyContent = useCallback(() => {
    return playerContents[playerId] || '';
  }, [playerContents, playerId]);

  // Clear current player's section
  const clearMySection = useCallback(() => {
    const yMap = yMapRef.current;
    const ydoc = ydocRef.current;
    if (!yMap || !ydoc) return;

    ydoc.transact(() => {
      yMap.set(playerId, '');
    });

    logDebug('Cleared my section');
  }, [playerId, logDebug]);

  useImperativeHandle(ref, () => ({
    submitMyInput: handleSubmitMyInput,
    insertText: insertTextIntoMySection,
    replaceText: replaceMySection,
    getMyContent,
    clearMySection,
  }), [handleSubmitMyInput, insertTextIntoMySection, replaceMySection, getMyContent, clearMySection]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmitMyInput();
    }
  }, [handleSubmitMyInput]);

  // Build sections for display from allPlayers and playerContents
  const visibleSections = useMemo(() => {
    // Extract current user's role from playerId (format: email:role or email:role:characterId)
    const playerIdParts = playerId?.split(':') || [];
    const myRole = playerIdParts[1];

    if (!myRole && playerId) {
      console.error('[CollabEditor] Invalid playerId format - missing role segment:', playerId);
    }

    // Deduplicate players by ID
    const uniquePlayersMap = new Map();
    for (const player of allPlayers) {
      if (!uniquePlayersMap.has(player.id)) {
        uniquePlayersMap.set(player.id, player);
      }
    }
    const uniquePlayers = Array.from(uniquePlayersMap.values());

    // Build sections from players
    const sections = uniquePlayers.map(player => ({
      playerId: player.id,
      playerName: player.name,
      content: playerContents[player.id] || ''
    }));

    // Sort: DM first
    const dmFirst = [...sections].sort((a, b) => {
      if (a.playerName === 'DM') return -1;
      if (b.playerName === 'DM') return 1;
      return 0;
    });

    // Filter based on role visibility
    const withoutHidden = dmFirst.filter((section) => {
      const sectionParts = section.playerId?.split(':') || [];
      const sectionRole = sectionParts[1];

      if (!sectionRole && section.playerId) {
        console.error('[CollabEditor] Section has invalid playerId format:', section.playerId);
        return true;
      }

      // DM sees everything
      if (myRole === 'dm') return true;

      // Players don't see DM's section
      if (myRole === 'player' && sectionRole === 'dm') return false;

      return true;
    });

    // Final sort: my section first, then alphabetical
    return withoutHidden.sort((a, b) => {
      // Always put own section first
      if (a.playerId === playerId) return -1;
      if (b.playerId === playerId) return 1;
      // Then alphabetical for the rest
      return a.playerName.localeCompare(b.playerName);
    });
  }, [allPlayers, playerContents, playerId]);

  const gridPlayerCountClass = layout === 'grid'
    ? `player-count-${Math.min(Math.max(visibleSections.length, 1), 4)}`
    : '';

  const rootClassName = useMemo(() => {
    const classes = ['stacked-collaborative-editor'];
    if (layout === 'grid') {
      classes.push('grid-layout');
    }
    return classes.join(' ');
  }, [layout]);

  return (
    <div
      className={`${rootClassName} ${gridPlayerCountClass}`.trim()}
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      {/* Header with connection status */}
      {showHeader && (
        <div className="stacked-editor-header">
          <div className="connection-status">
            <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`} />
            <span className="status-text">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <button
            className="submit-button"
            onClick={handleSubmitMyInput}
            disabled={!(playerContents[playerId] || '').trim()}
            title="Submit your input"
          >
            Submit
          </button>
        </div>
      )}

      {/* Stacked player sections */}
      <div className="player-sections-container">
        {visibleSections.map((section) => {
          const isMySection = section.playerId === playerId;
          const canEdit = isMySection;

          // Grace period after typing - don't apply voice-active state or show partials
          const timeSinceEdit = Date.now() - lastLocalEditTimeRef.current;
          const inTypingGracePeriod = isMySection && timeSinceEdit < 400;

          return (
            <div key={section.playerId} className={`player-section ${canEdit ? 'editable' : 'readonly'}`}>
              <div className="player-name-container">
                <span className="player-name">[{section.playerName}]:</span>
                {isMySection && <span className="you-indicator">(you)</span>}
                {isMySection && showInlineSubmit && onSubmit && (
                  <button
                    className="inline-submit-btn"
                    onClick={handleSubmitMyInput}
                    disabled={!(section.content || '').trim()}
                    title="Submit (Ctrl+Enter)"
                  >
                    Submit
                  </button>
                )}
                {isMySection && showMicButton && onToggleTranscription && (() => {
                  const isTooLow = voiceLevel < 0;
                  const absLevel = Math.abs(voiceLevel);
                  return (
                    <>
                      <button
                        className={`mic-control-inline ${isTranscribing ? 'active' : 'paused'} ${isTooLow ? 'too-low' : ''}`}
                        onClick={onToggleTranscription}
                        title={isTooLow ? 'Voice too low - speak louder!' : (isTranscribing ? 'Pause voice input (or release `)' : 'Start voice input (or hold `)')}
                        style={isTooLow ? { animation: 'pulse-yellow 0.5s ease-in-out infinite' } : {}}
                      >
                        {isTranscribing ? '🎤' : '🔇'}
                      </button>
                      {isTranscribing && (
                        <div
                          className="voice-level-indicator"
                          style={{
                            width: '40px',
                            height: '6px',
                            backgroundColor: '#333',
                            borderRadius: '3px',
                            overflow: 'hidden',
                            marginLeft: '6px',
                          }}
                        >
                          <div
                            style={{
                              width: `${absLevel}%`,
                              height: '100%',
                              backgroundColor: isTooLow ? '#facc15' : (absLevel > 30 ? '#4ade80' : '#6b7280'),
                              transition: 'width 0.05s ease-out',
                            }}
                          />
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
              <textarea
                ref={(el) => {
                  if (el) textareasRef.current[section.playerId] = el;
                }}
                className={`player-textarea ${isMySection && isTranscribing && Math.abs(voiceLevel) > 10 && !inTypingGracePeriod ? 'voice-active' : ''} ${partialOverlays[section.playerId] && !inTypingGracePeriod ? 'has-partial' : ''}`}
                value={
                  // Show partial while transcribing (not during typing grace period)
                  (partialOverlays[section.playerId] && !inTypingGracePeriod)
                    ? partialOverlays[section.playerId]
                    : section.content
                }
                onChange={(e) => {
                  if (canEdit && (!partialOverlays[section.playerId] || inTypingGracePeriod)) {
                    handleTextChange(section.playerId, e.target.value);
                  }
                }}
                readOnly={!canEdit || (isMySection && isTranscribing && Math.abs(voiceLevel) > 10 && !inTypingGracePeriod) || (!!partialOverlays[section.playerId] && !inTypingGracePeriod)}
                placeholder={isMySection && isTranscribing ? (Math.abs(voiceLevel) > 10 ? 'Listening...' : 'Speak or type...') : (canEdit ? 'Type your action here...' : '')}
                rows={3}
              />
            </div>
          );
        })}
      </div>

      {visibleSections.length === 0 && (
        <div className="empty-state">
          Waiting for players to join...
        </div>
      )}
    </div>
  );
});

CollaborativeStackedEditor.propTypes = {
  sessionId: PropTypes.string.isRequired,
  playerId: PropTypes.string.isRequired,
  characterName: PropTypes.string.isRequired,
  allPlayers: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired
  })),
  websocket: PropTypes.object.isRequired,
  isMyTurn: PropTypes.bool,
  onSubmit: PropTypes.func,
  showHeader: PropTypes.bool,
  onConnectionChange: PropTypes.func,
  onMySectionChange: PropTypes.func,
  layout: PropTypes.oneOf(['stacked', 'grid']),
  isTranscribing: PropTypes.bool,
  onToggleTranscription: PropTypes.func,
  showMicButton: PropTypes.bool,
  voiceLevel: PropTypes.number,
  showInlineSubmit: PropTypes.bool,
};

CollaborativeStackedEditor.defaultProps = {
  allPlayers: [],
  isMyTurn: false,
  onSubmit: null,
  showHeader: true,
  onConnectionChange: null,
  onMySectionChange: null,
  layout: 'stacked',
  isTranscribing: false,
  onToggleTranscription: null,
  showMicButton: false,
  voiceLevel: 0,
  showInlineSubmit: false,
};

export default CollaborativeStackedEditor;
