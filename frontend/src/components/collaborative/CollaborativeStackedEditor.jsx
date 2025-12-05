import { useState, useEffect, useRef, useCallback, useMemo, useImperativeHandle, forwardRef } from 'react';
import PropTypes from 'prop-types';
import * as Y from 'yjs';
import './CollaborativeStackedEditor.css';

const REMOTE_ORIGIN = Symbol('collaboration-remote-update');

/**
 * CollaborativeStackedEditor - Stacked text boxes for each player
 *
 * Visual layout:
 * ┌─────────────────────┐
 * │ [Aragorn]:         │ ← Dark, non-editable label
 * ├─────────────────────┤
 * │ Player's text here │ ← Light, editable (if my turn)
 * └─────────────────────┘
 * ─────────────────────── ← Separator
 * ┌─────────────────────┐
 * │ [Gandalf]:         │
 * ├─────────────────────┤
 * │ ...                │
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
  voiceLevel = 0
}, ref) => {
  const [isConnected, setIsConnected] = useState(false);
  const [sections, setSections] = useState([]);
  const [partialOverlays, setPartialOverlays] = useState({}); // {playerId: partialText}
  const ydocRef = useRef(null);
  const ytextRef = useRef(null);
  const textareasRef = useRef({});
  const registeredWebSocketRef = useRef(null); // Track which websocket we've registered with
  const lastLocalEditTimeRef = useRef(0); // Track when user last made a local edit (ms since epoch)
  const isPushToTalkActiveRef = useRef(false); // Track if push-to-talk is currently active

  // Push-to-talk hotkey: Hold backtick (`) to enable voice transcription
  useEffect(() => {
    if (!showMicButton || !onToggleTranscription) return;

    const handleKeyDown = (e) => {
      // Only trigger on backtick key
      if (e.key !== '`') return;

      // Don't trigger if already in push-to-talk mode (key repeat)
      if (isPushToTalkActiveRef.current) return;

      // Don't trigger if focus is in a text input, textarea, or contenteditable
      const activeElement = document.activeElement;
      const isInputFocused = activeElement && (
        activeElement.tagName === 'INPUT' ||
        activeElement.tagName === 'TEXTAREA' ||
        activeElement.isContentEditable
      );

      if (isInputFocused) return;

      // Prevent the backtick from being typed
      e.preventDefault();

      // Start push-to-talk
      isPushToTalkActiveRef.current = true;
      if (!isTranscribing) {
        console.log('🎤 Push-to-talk: Starting transcription (backtick held)');
        onToggleTranscription();
      }
    };

    const handleKeyUp = (e) => {
      // Only trigger on backtick key
      if (e.key !== '`') return;

      // Only stop if we started via push-to-talk
      if (!isPushToTalkActiveRef.current) return;

      // End push-to-talk
      isPushToTalkActiveRef.current = false;
      if (isTranscribing) {
        console.log('🎤 Push-to-talk: Stopping transcription (backtick released)');
        onToggleTranscription();
      }
    };

    // Add listeners to window for global hotkey
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
  const allPlayersRef = useRef(allPlayers); // Stable ref to avoid useEffect re-runs

  const logPrefix = useMemo(() => `[StackedCollab:${sessionId}:${playerId}]`, [sessionId, playerId]);
  const logDebug = useMemo(() => (...args) => console.debug(logPrefix, ...args), [logPrefix]);
  const logWarn = useMemo(() => (...args) => console.warn(logPrefix, ...args), [logPrefix]);
  const logError = useMemo(() => (...args) => console.error(logPrefix, ...args), [logPrefix]);

  // Parse Yjs document into player sections
  // Uses allPlayersRef to avoid causing useEffect re-runs when allPlayers changes
  const parseDocumentIntoSections = useCallback((text) => {
    const playerSections = [];
    const currentAllPlayers = allPlayersRef.current;

    console.log('[DEBUG parseDoc] characterName:', characterName);
    console.log('[DEBUG parseDoc] allPlayers:', currentAllPlayers.map(p => ({ id: p.id, name: p.name })));
    console.log('[DEBUG parseDoc] Document text:', text);

    // Deduplicate players by ID to prevent multiple sections for same player
    const uniquePlayersMap = new Map();
    for (const player of currentAllPlayers) {
      if (!uniquePlayersMap.has(player.id)) {
        uniquePlayersMap.set(player.id, player);
      }
    }
    const uniquePlayers = Array.from(uniquePlayersMap.values());

    console.log('[DEBUG parseDoc] Unique players after deduplication:', uniquePlayers.map(p => ({ id: p.id, name: p.name })));

    for (const player of uniquePlayers) {
      const playerLabel = `[${player.name}]:`;
      const labelIndex = text.indexOf(playerLabel);

      if (labelIndex === -1) {
        // Special handling for DM - they don't have a label, extract from beginning
        if (player.name === 'DM') {
          const firstLabelMatch = text.match(/\[/);
          const contentEnd = firstLabelMatch ? firstLabelMatch.index : text.length;
          const content = text.slice(0, contentEnd);

          playerSections.push({
            playerId: player.id,
            playerName: player.name,
            content: content,
            startPos: 0,
            endPos: contentEnd
          });
          continue;
        }

        // Player not in document yet
        playerSections.push({
          playerId: player.id,
          playerName: player.name,
          content: '',
          startPos: -1,
          endPos: -1
        });
        continue;
      }

      const contentStart = labelIndex + playerLabel.length;

      // Find next player label or end of document
      let contentEnd = text.length;
      const afterLabel = text.slice(contentStart);
      const nextLabelMatch = afterLabel.match(/\n\[/);
      if (nextLabelMatch) {
        contentEnd = contentStart + nextLabelMatch.index;
      }

      let content = text.slice(contentStart, contentEnd);

      playerSections.push({
        playerId: player.id,
        playerName: player.name,
        content: content,
        startPos: contentStart,
        endPos: contentEnd
      });
    }

    return playerSections;
  }, []); // Uses allPlayersRef to avoid re-creating this callback when allPlayers changes

  // Keep allPlayersRef in sync with allPlayers prop and re-parse sections when players change
  useEffect(() => {
    allPlayersRef.current = allPlayers;
    // Re-parse sections with updated player list (without reinitializing Yjs document)
    if (ytextRef.current) {
      const text = ytextRef.current.toString();
      const parsed = parseDocumentIntoSections(text);
      setSections(parsed);
    }
  }, [allPlayers, parseDocumentIntoSections]);

  // Notify parent of connection state changes
  useEffect(() => {
    if (onConnectionChange) {
      onConnectionChange(isConnected);
    }
  }, [isConnected, onConnectionChange]);

  // Initialize Yjs document
  useEffect(() => {
    if (!websocket) {
      logDebug('Initialization skipped – websocket not available');
      return;
    }

    logDebug('Starting collaborative session initialization');

    const ydoc = new Y.Doc();
    const ytext = ydoc.getText('codemirror');
    ydocRef.current = ydoc;
    ytextRef.current = ytext;

    // Parse and render sections whenever Yjs document changes
    const updateSections = () => {
      const text = ytext.toString();
      const parsed = parseDocumentIntoSections(text);
      setSections(parsed);
      logDebug('Updated sections', { count: parsed.length });

      if (onMySectionChange) {
        const mySection = parsed.find((section) => section.playerId === playerId);
        onMySectionChange(mySection?.content || '');
      }
    };

    ytext.observe(updateSections);
    updateSections(); // Initial render

    // WebSocket message handling
    const handleMessage = (event) => {
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        logDebug('Received WebSocket message', data.type);

        if (data.type === 'initial_state') {
          if (Array.isArray(data.update)) {
            const update = new Uint8Array(data.update);
            Y.applyUpdate(ydoc, update, REMOTE_ORIGIN);
            logDebug('Applied initial_state from backend', { size: data.update.length });
          }
        } else if (
          data.type === 'yjs_update' &&
          data.sessionId === sessionId &&
          Array.isArray(data.update)
        ) {
          // Check if this is a voice update (from backend STT) or from another player
          const isVoiceUpdate = data.source === 'voice';
          const isFromOtherPlayer = data.playerId !== playerId;

          // Apply updates from other players OR voice updates (even from self)
          if (isFromOtherPlayer || isVoiceUpdate) {
            // For voice updates from self, use a grace period after local edits
            // This prevents voice updates from overwriting user's manual edits/deletions
            // Uses client-side time only to avoid clock skew issues
            if (isVoiceUpdate && !isFromOtherPlayer) {
              const timeSinceEdit = Date.now() - lastLocalEditTimeRef.current;
              if (timeSinceEdit < 2000) { // 2 second grace period after local edit
                logDebug('Ignoring voice update within 2s of local edit', { timeSinceEdit });
                return; // Skip - user edited recently
              }
            }
            const update = new Uint8Array(data.update);
            Y.applyUpdate(ydoc, update, REMOTE_ORIGIN);
            logDebug('Applied Yjs update', { from: data.playerId, source: data.source || 'peer' });
          }
        } else if (data.type === 'partial_overlay' && data.sessionId === sessionId) {
          // Handle partial overlay for voice transcription preview
          const overlayPlayerId = data.playerId;
          const overlayText = data.text || '';

          setPartialOverlays(prev => {
            if (overlayText) {
              return { ...prev, [overlayPlayerId]: overlayText };
            } else {
              // Empty text clears the overlay
              const { [overlayPlayerId]: _, ...rest } = prev;
              return rest;
            }
          });
          logDebug('Updated partial overlay', { playerId: overlayPlayerId, hasText: !!overlayText });
        }
      } catch (error) {
        logError('Error handling collaboration message', error);
      }
    };

    // Broadcast local Yjs changes
    const handleYjsUpdate = (update, origin) => {
      if (origin === REMOTE_ORIGIN) {
        logDebug('Skipping broadcast – applied remote Yjs update');
        return;
      }

      // User made a local edit - track the time to filter stale voice updates
      lastLocalEditTimeRef.current = Date.now();

      if (!websocket || typeof websocket.send !== 'function') {
        logWarn('Cannot broadcast Yjs update – WebSocket missing send()');
        return;
      }

      websocket.send(JSON.stringify({
        type: 'yjs_update',
        sessionId,
        playerId,
        update: Array.from(update),
        timestamp: new Date().toISOString()
      }));
      logDebug('Broadcasting Yjs update', { size: update.length });
    };

    const sendRegistration = () => {
      // Only register if this is a different websocket instance than before
      if (registeredWebSocketRef.current === websocket) {
        logDebug('Skipping registration - already registered with this websocket');
        return;
      }

      if (websocket && typeof websocket.send === 'function' && websocket.readyState === 1) {
        websocket.send(JSON.stringify({
          type: 'register',
          playerId,
          playerName: characterName,
          timestamp: new Date().toISOString()
        }));
        registeredWebSocketRef.current = websocket;
        logDebug('Sent registration message', { playerId, playerName: characterName });
      }
    };

    const handleOpen = () => {
      logDebug('WebSocket open event');
      setIsConnected(true);
      sendRegistration();
    };

    const handleClose = () => {
      logDebug('WebSocket close event');
      setIsConnected(false);
      registeredWebSocketRef.current = null; // Allow re-registration on reconnect
    };

    setIsConnected(websocket.readyState === 1);

    websocket.addEventListener?.('message', handleMessage);
    websocket.addEventListener?.('open', handleOpen);
    websocket.addEventListener?.('close', handleClose);
    ydoc.on('update', handleYjsUpdate);

    // If WebSocket already open, send registration
    if (websocket.readyState === 1) {
      sendRegistration();
    }

    return () => {
      logDebug('Destroying collaboration resources');
      websocket.removeEventListener?.('message', handleMessage);
      websocket.removeEventListener?.('open', handleOpen);
      websocket.removeEventListener?.('close', handleClose);
      ydoc.off('update', handleYjsUpdate);
      ytext.unobserve(updateSections);
      ydoc.destroy();
      setIsConnected(false);
      // Don't reset registeredWebSocketRef here - let it persist across effect re-runs
      // It will only be reset when websocket actually closes or component unmounts
    };
  }, [websocket, sessionId, playerId, characterName, parseDocumentIntoSections, logDebug, logWarn, logError, onMySectionChange]);

  // Handle text change in a player's textarea
  const handleTextChange = useCallback((playerName, newContent) => {
    const ytext = ytextRef.current;
    const ydoc = ydocRef.current;
    if (!ytext || !ydoc) return;

    const fullText = ytext.toString();
    const playerLabel = `[${playerName}]:`;
    let labelIndex = fullText.indexOf(playerLabel);

    // If label doesn't exist, create it
    if (labelIndex === -1) {
      logDebug('Player label not found, creating it', { playerName });

      ydoc.transact(() => {
        if (fullText.length === 0) {
          // First player - just add the label
          ytext.insert(0, playerLabel);
        } else {
          // Subsequent player - add with newlines
          ytext.insert(fullText.length, `\n\n${playerLabel}`);
        }
      });

      // Update labelIndex after insertion
      const updatedText = ytext.toString();
      labelIndex = updatedText.indexOf(playerLabel);

      if (labelIndex === -1) {
        logError('Failed to create player label', { playerName });
        return;
      }
    }

    const contentStart = labelIndex + playerLabel.length;

    // Find content end
    let contentEnd = fullText.length;
    const afterLabel = fullText.slice(contentStart);
    const nextLabelMatch = afterLabel.match(/\n\[/);
    if (nextLabelMatch) {
      contentEnd = contentStart + nextLabelMatch.index;
    }

    const currentContent = fullText.slice(contentStart, contentEnd);

    // Only update if content actually changed
    if (currentContent === newContent) {
      return;
    }

    ydoc.transact(() => {
      // Delete old content
      const deleteLength = contentEnd - contentStart;
      if (deleteLength > 0) {
        ytext.delete(contentStart, deleteLength);
      }

      // Insert new content
      if (newContent.length > 0) {
        ytext.insert(contentStart, newContent);
      }
    });

    logDebug('Updated player section', { playerName, oldLength: currentContent.length, newLength: newContent.length });
  }, [logDebug, logWarn]);

  // Clear all player text in the Yjs document
  const clearAllText = useCallback(() => {
    const ytext = ytextRef.current;
    const ydoc = ydocRef.current;
    if (!ytext || !ydoc) return;

    ydoc.transact(() => {
      const fullText = ytext.toString();
      if (fullText.length > 0) {
        ytext.delete(0, fullText.length);
      }
    });

    logDebug('Cleared all player text');
  }, [logDebug]);

  // Submit current player's input
  const handleSubmitMyInput = useCallback(() => {
    if (!onSubmit) return;

    // If DM is submitting, combine all player inputs
    if (characterName === 'DM') {
      const combinedInput = sections
        .filter(section => section.content && section.content.trim())
        .map(section => `[${section.playerName}]: ${section.content.trim()}`)
        .join('\n\n');

      if (combinedInput) {
        onSubmit(combinedInput);
        clearAllText();
      }
    } else {
      // Regular player submission (just their part)
      const mySection = sections.find(s => s.playerId === playerId);
      if (mySection && mySection.content.trim()) {
        onSubmit(mySection.content.trim());
      }
    }
  }, [onSubmit, sections, playerId, characterName, clearAllText]);

  // Insert text into current player's section
  const insertTextIntoMySection = useCallback((textToInsert) => {
    const ytext = ytextRef.current;
    const ydoc = ydocRef.current;
    if (!ytext || !ydoc || !textToInsert) return;

    let fullText = ytext.toString();
    const playerLabel = `[${characterName}]:`;
    let labelIndex = fullText.indexOf(playerLabel);

    // Special handling for DM - they don't have a label in the document
    if (labelIndex === -1 && characterName === 'DM') {
      // Insert at beginning of document for DM (before first player label)
      const firstLabelMatch = fullText.match(/\[/);
      const insertPosition = firstLabelMatch ? firstLabelMatch.index : fullText.length;

      // Add spacing if inserting before content
      const separator = insertPosition > 0 && fullText[insertPosition - 1] !== '\n' ? ' ' : '';

      ydoc.transact(() => {
        ytext.insert(insertPosition, separator + textToInsert);
      });

      logDebug('Inserted text into DM section (beginning)', { textLength: textToInsert.length });
      return;
    }

    // If label doesn't exist for regular player, create it
    if (labelIndex === -1) {
      logDebug('Player label not found during insertion, creating it', { characterName });

      ydoc.transact(() => {
        if (fullText.length === 0) {
          // First player - just add the label
          ytext.insert(0, playerLabel);
        } else {
          // Subsequent player - add with newlines
          ytext.insert(fullText.length, `\n\n${playerLabel}`);
        }
      });

      // Update text and labelIndex after insertion
      fullText = ytext.toString();
      labelIndex = fullText.indexOf(playerLabel);

      if (labelIndex === -1) {
        logError('Failed to create player label during insertion', { characterName });
        return;
      }
    }

    const contentStart = labelIndex + playerLabel.length;

    // Find content end
    let contentEnd = fullText.length;
    const afterLabel = fullText.slice(contentStart);
    const nextLabelMatch = afterLabel.match(/\n\[/);
    if (nextLabelMatch) {
      contentEnd = contentStart + nextLabelMatch.index;
    }

    const currentContent = fullText.slice(contentStart, contentEnd).trim();

    // Insert text at the end of current content with appropriate spacing
    const separator = currentContent ? ' ' : '';
    // Calculate insert position relative to the start of the document
    // We need to find where currentContent ends within the slice to account for trailing spaces if any,
    // but we trimmed currentContent for the check.
    // Actually, we want to append to the *actual* content, likely preserving trailing newlines of the section?
    // The logic in handleTextChange replaces the whole section.
    // Here we want to append.
    
    // Re-calculate content end without trim for positioning
    // But we want to append visually nicely.
    
    // Let's just append to the end of the section (before next label)
    const insertPosition = contentEnd;
    const spacer = (insertPosition > contentStart && fullText[insertPosition - 1] !== ' ' && fullText[insertPosition - 1] !== '\n') ? ' ' : '';

    ydoc.transact(() => {
      ytext.insert(insertPosition, spacer + textToInsert);
    });

    logDebug('Inserted text into my section', { textLength: textToInsert.length });
  }, [characterName, logDebug, logWarn, logError]);

  // Replace text in current player's section (for voice partials that replace previous content)
  const replaceMySection = useCallback((newText) => {
    const ytext = ytextRef.current;
    const ydoc = ydocRef.current;
    if (!ytext || !ydoc) return;

    const fullText = ytext.toString();
    const playerLabel = `[${characterName}]:`;
    const labelIndex = fullText.indexOf(playerLabel);

    if (labelIndex === -1) {
      if (characterName === 'DM') {
        // For DM, find content before first player label
        const firstLabelMatch = fullText.match(/\[/);
        const contentEnd = firstLabelMatch ? firstLabelMatch.index : fullText.length;

        ydoc.transact(() => {
          // Delete existing DM content and insert new
          if (contentEnd > 0) {
            ytext.delete(0, contentEnd);
          }
          ytext.insert(0, newText || '');
        });

        logDebug('Replaced DM section', { textLength: newText?.length || 0 });
        return;
      }
      logWarn('Cannot replace text - player label not found', { characterName });
      return;
    }

    const contentStart = labelIndex + playerLabel.length;

    // Find content end
    let contentEnd = fullText.length;
    const afterLabel = fullText.slice(contentStart);
    const nextLabelMatch = afterLabel.match(/\n\[/);
    if (nextLabelMatch) {
      contentEnd = contentStart + nextLabelMatch.index;
    }

    // Calculate the actual content range (skip leading whitespace after label)
    const contentWithWhitespace = fullText.slice(contentStart, contentEnd);
    const leadingWhitespace = contentWithWhitespace.match(/^\s*/)[0];
    const actualContentStart = contentStart + leadingWhitespace.length;

    ydoc.transact(() => {
      // Delete existing content (preserving the label and its whitespace)
      const deleteLength = contentEnd - actualContentStart;
      if (deleteLength > 0) {
        ytext.delete(actualContentStart, deleteLength);
      }
      // Insert new text (with a space after the label if needed)
      const prefix = leadingWhitespace.length === 0 ? ' ' : '';
      ytext.insert(actualContentStart, prefix + (newText || ''));
    });

    logDebug('Replaced my section', { textLength: newText?.length || 0 });
  }, [characterName, logDebug, logWarn]);

  useImperativeHandle(ref, () => ({
    submitMyInput: handleSubmitMyInput,
    insertText: insertTextIntoMySection,
    replaceText: replaceMySection,
  }), [handleSubmitMyInput, insertTextIntoMySection, replaceMySection]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    // Ctrl+Enter or Cmd+Enter to submit
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmitMyInput();
    }
  }, [handleSubmitMyInput]);

  const visibleSections = useMemo(() => {
    // Extract current user's role from playerId (format: email:role or email:role:characterId)
    const playerIdParts = playerId?.split(':') || [];
    const myRole = playerIdParts[1];

    if (!myRole && playerId) {
      console.error('[CollabEditor] Invalid playerId format - missing role segment:', playerId);
    }

    const dmFirst = [...sections].sort((a, b) => {
      if (a.playerName === 'DM') return -1;
      if (b.playerName === 'DM') return 1;
      return 0;
    });

    const withoutHidden = dmFirst.filter((section) => {
      // Extract section's role from their playerId
      const sectionParts = section.playerId?.split(':') || [];
      const sectionRole = sectionParts[1];

      if (!sectionRole && section.playerId) {
        console.error('[CollabEditor] Section has invalid playerId format:', section.playerId);
        return true; // Show sections with invalid IDs rather than hiding
      }

      // DM sees everything
      if (myRole === 'dm') return true;

      // Players don't see DM's section
      if (myRole === 'player' && sectionRole === 'dm') return false;

      return true;
    });

    return withoutHidden.sort((a, b) => {
      if (myRole === 'dm') {
        return a.playerName.localeCompare(b.playerName);
      }
      if (a.playerId === playerId) return -1;
      if (b.playerId === playerId) return 1;
      return a.playerName.localeCompare(b.playerName);
    });
  }, [sections, playerId]);

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

  useEffect(() => {
    // Keep hook for future side effects; no resizing here to honor user-controlled sizing
  }, [visibleSections, partialOverlays]);

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
            disabled={!sections.find(s => s.playerId === playerId)?.content.trim()}
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

          // 400ms grace period after typing - don't apply voice-active state or show partials
          const timeSinceEdit = Date.now() - lastLocalEditTimeRef.current;
          const inTypingGracePeriod = isMySection && timeSinceEdit < 400;

          return (
            <div key={section.playerId} className={`player-section ${canEdit ? 'editable' : 'readonly'}`}>
              <div className="player-name-container">
                <span className="player-name">[{section.playerName}]:</span>
                {isMySection && <span className="you-indicator">(you)</span>}
                {isMySection && showMicButton && onToggleTranscription && (() => {
                  // Negative voiceLevel indicates "too low" warning from VoiceInputScribeV2
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
                  // Show ONLY the partial while transcribing (not concatenated with committed)
                  // This gives cleaner UX - user sees just what they're currently saying
                  // But not during typing grace period - let user type freely
                  (partialOverlays[section.playerId] && !inTypingGracePeriod)
                    ? partialOverlays[section.playerId]
                    : section.content
                }
                onChange={(e) => {
                  // Don't allow edits while partial is showing (wait for final)
                  // Unless in typing grace period - let user continue editing
                  if (canEdit && (!partialOverlays[section.playerId] || inTypingGracePeriod)) {
                    handleTextChange(section.playerName, e.target.value);
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
};

export default CollaborativeStackedEditor;
