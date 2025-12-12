import { useState, useCallback, useMemo, useRef } from 'react';

/**
 * Turn-based message management hook.
 *
 * Replaces timestamp-based sorting with authoritative turn counters from the backend.
 * This solves message ordering issues caused by clock skew and race conditions.
 *
 * Turn Structure:
 * - Each turn has a monotonically increasing turn_number
 * - Within a turn, response_index orders messages:
 *   - 0: TURN_INPUT (player + DM input)
 *   - 1-N: STREAMING chunks (ephemeral, not persisted)
 *   - N+1: FINAL response
 */

/**
 * @typedef {Object} TurnInput
 * @property {Object|null} active_player - Active player's input
 * @property {Array} observer_inputs - Observer players' inputs
 * @property {Object|null} dm_input - DM's additions
 * @property {string} combined_prompt - Combined text sent to LLM
 */

/**
 * @typedef {Object} TurnState
 * @property {number} turn_number - Global turn counter
 * @property {TurnInput|null} input - Structured input for this turn
 * @property {string} streamingText - Accumulated streaming text
 * @property {Object|null} finalMessage - Complete DM response
 * @property {boolean} isStreaming - Whether currently streaming
 * @property {string|null} error - Error message if turn failed
 */

/**
 * Hook for managing turn-based messages.
 *
 * @param {string} campaignId - Campaign/session ID
 * @returns {Object} Turn state and handlers
 */
export function useTurnBasedMessages(campaignId) {
  // State: { [turnNumber]: TurnState }
  const [turnsByNumber, setTurnsByNumber] = useState({});

  // Track the current turn being processed
  const [processingTurn, setProcessingTurn] = useState(null);

  // Ref to track latest turn for ordering
  const latestTurnRef = useRef(0);

  /**
   * Handle turn_started event - marks a new turn as processing.
   */
  const handleTurnStarted = useCallback((data) => {
    const { turn_number, session_id } = data;

    console.log('🔄 handleTurnStarted called:', { turn_number, session_id, campaignId, match: session_id === campaignId });

    // Verify it's for our campaign (only skip if we have BOTH IDs and they don't match)
    if (session_id && campaignId && session_id !== campaignId) {
      console.log('🔄 handleTurnStarted: session_id mismatch, skipping');
      return;
    }

    console.log('🔄 handleTurnStarted: setting processingTurn to', turn_number);
    setProcessingTurn(turn_number);
    latestTurnRef.current = Math.max(latestTurnRef.current, turn_number);

    // Initialize turn state - mark as streaming so processing indicator shows immediately
    setTurnsByNumber(prev => ({
      ...prev,
      [turn_number]: {
        turn_number,
        input: null,
        streamingText: '',
        finalMessage: null,
        isStreaming: true,  // Show processing indicator immediately
        error: null,
      }
    }));
  }, [campaignId]);

  /**
   * Handle input_received event - immediately populate turn with submitted input.
   * This provides faster feedback than turn_message for the input text.
   */
  const handleInputReceived = useCallback((data) => {
    const { turn_number, session_id, input_text, active_player_input, dm_input } = data;

    console.log('📝 handleInputReceived called:', { turn_number, session_id, input_text_length: input_text?.length });

    // Verify it's for our campaign (only skip if we have BOTH IDs and they don't match)
    if (session_id && campaignId && session_id !== campaignId) {
      console.log('📝 handleInputReceived: session_id mismatch, skipping');
      return;
    }

    // Update turn with the input content immediately
    setTurnsByNumber(prev => {
      const turn = prev[turn_number] || {
        turn_number,
        input: null,
        streamingText: '',
        finalMessage: null,
        isStreaming: false,
        error: null,
      };

      // Build the input structure from the received data
      const inputContent = {
        active_player: active_player_input || null,
        observer_inputs: [],
        dm_input: dm_input || null,
        combined_prompt: input_text || '',
      };

      console.log('📝 handleInputReceived: setting input for turn', turn_number);

      return {
        ...prev,
        [turn_number]: {
          ...turn,
          input: inputContent,
          isStreaming: true, // Mark as streaming so the UI shows it's processing
        }
      };
    });
  }, [campaignId]);

  /**
   * Handle turn_message event - process turn input, streaming, or final messages.
   */
  const handleTurnMessage = useCallback((data) => {
    const {
      message_id,
      turn_number,
      response_index,
      response_type,
      role,
      content,
      character_name,
      has_audio,
    } = data;

    setTurnsByNumber(prev => {
      const turn = prev[turn_number] || {
        turn_number,
        input: null,
        streamingText: '',
        finalMessage: null,
        isStreaming: false,
        error: null,
      };

      if (response_type === 'turn_input') {
        // Structured input - preserves attribution
        return {
          ...prev,
          [turn_number]: {
            ...turn,
            input: content,
          }
        };
      }

      if (response_type === 'streaming') {
        // Streaming chunk - append to accumulated text
        return {
          ...prev,
          [turn_number]: {
            ...turn,
            streamingText: turn.streamingText + (content || ''),
            isStreaming: true,
          }
        };
      }

      if (response_type === 'final') {
        // Final response - complete the turn
        return {
          ...prev,
          [turn_number]: {
            ...turn,
            finalMessage: {
              message_id,
              turn_number,
              response_index,
              role,
              content,
              character_name,
              has_audio,
              timestamp: new Date().toISOString(),
            },
            isStreaming: false,
          }
        };
      }

      // System or other types - just store as-is
      return prev;
    });
  }, []);

  /**
   * Handle turn_complete event - marks turn as fully processed.
   */
  const handleTurnComplete = useCallback((data) => {
    const { turn_number, session_id } = data;

    // Verify it's for our campaign (only skip if we have BOTH IDs and they don't match)
    if (session_id && campaignId && session_id !== campaignId) return;

    // Clear processing state if this was the processing turn
    setProcessingTurn(prev => prev === turn_number ? null : prev);

    // Ensure streaming state is cleared
    setTurnsByNumber(prev => {
      const turn = prev[turn_number];
      if (turn && turn.isStreaming) {
        return {
          ...prev,
          [turn_number]: {
            ...turn,
            isStreaming: false,
          }
        };
      }
      return prev;
    });
  }, [campaignId]);

  /**
   * Handle turn_error event - marks turn as failed.
   */
  const handleTurnError = useCallback((data) => {
    const { turn_number, session_id, error } = data;

    // Verify it's for our campaign (only skip if we have BOTH IDs and they don't match)
    if (session_id && campaignId && session_id !== campaignId) return;

    // Clear processing state
    setProcessingTurn(prev => prev === turn_number ? null : prev);

    // Update turn with error
    setTurnsByNumber(prev => ({
      ...prev,
      [turn_number]: {
        ...(prev[turn_number] || { turn_number }),
        error,
        isStreaming: false,
      }
    }));
  }, [campaignId]);

  /**
   * Load existing turns from backend history.
   * Messages must have turn_number and response_type fields.
   * @param {Array} messages - Array of messages from backend
   * @param {number} backendCurrentTurn - Current turn from backend (authoritative source)
   * @param {boolean} isBackendProcessing - Whether backend is currently processing a turn (from campaign_state)
   */
  const loadTurnsFromHistory = useCallback((messages, backendCurrentTurn = null, isBackendProcessing = false) => {
    console.log('📚 loadTurnsFromHistory called with', messages?.length, 'messages');
    if (!Array.isArray(messages) || messages.length === 0) {
      console.log('📚 loadTurnsFromHistory: no messages to process');
      return;
    }

    // Debug: Log first 3 messages to see their structure
    console.log('📚 Sample messages:', messages.slice(0, 3).map(m => ({
      turn_number: m.turn_number,
      response_type: m.response_type,
      role: m.role,
      has_content: !!m.content,
    })));

    const turns = {};
    let maxTurn = 0;
    let skippedCount = 0;

    // Process messages with turn_number and response_type
    messages.forEach(msg => {
      const turnNumber = msg.turn_number;
      if (turnNumber == null) {
        skippedCount++;
        return;
      }

      maxTurn = Math.max(maxTurn, turnNumber);

      if (!turns[turnNumber]) {
        turns[turnNumber] = {
          turn_number: turnNumber,
          input: null,
          streamingText: '',
          finalMessage: null,
          isStreaming: false,
          error: null,
        };
      }

      const responseType = msg.response_type;
      if (responseType === 'turn_input') {
        turns[turnNumber].input = msg.content;
      } else if (responseType === 'final') {
        turns[turnNumber].finalMessage = msg;
      }
    });

    // Use backend's current_turn as authoritative source
    const finalTurn = backendCurrentTurn != null ? Math.max(backendCurrentTurn, maxTurn) : maxTurn;
    console.log('📚 loadTurnsFromHistory: created', Object.keys(turns).length, 'turns, maxTurn=', maxTurn, 'backendCurrentTurn=', backendCurrentTurn, 'finalTurn=', finalTurn, 'skipped=', skippedCount, 'isBackendProcessing=', isBackendProcessing);

    // ONLY mark the current turn as streaming if backend says it's processing
    // Historical incomplete turns (e.g., turn 2 interrupted) should NOT show as streaming
    if (isBackendProcessing && backendCurrentTurn != null) {
      // Backend is actively processing - mark the current turn as streaming
      if (turns[backendCurrentTurn]) {
        turns[backendCurrentTurn].isStreaming = true;
        console.log('📚 Marking turn', backendCurrentTurn, 'as streaming (backend is processing)');
      } else {
        // Create placeholder for in-progress turn
        console.log('📚 Creating placeholder for in-progress turn:', backendCurrentTurn);
        turns[backendCurrentTurn] = {
          turn_number: backendCurrentTurn,
          input: null,
          streamingText: '',
          finalMessage: null,
          isStreaming: true,
          error: null,
        };
      }
    }
    // Note: We no longer infer streaming state from missing finalMessage
    // Historical incomplete turns are displayed as-is without streaming indicator

    latestTurnRef.current = finalTurn;
    setTurnsByNumber(turns);
  }, []);

  /**
   * Clear all turns (e.g., when switching campaigns).
   */
  const clearTurns = useCallback(() => {
    setTurnsByNumber({});
    setProcessingTurn(null);
    latestTurnRef.current = 0;
  }, []);

  /**
   * Set the current turn number directly (from backend authoritative source).
   * This should be called when loading a campaign to initialize the turn counter.
   * @param {number} turnNumber - The turn number from backend
   */
  const setCurrentTurn = useCallback((turnNumber) => {
    if (turnNumber != null && turnNumber >= 0) {
      console.log('🔢 setCurrentTurn: setting latestTurnRef to', turnNumber);
      latestTurnRef.current = turnNumber;
    }
  }, []);

  /**
   * Append streaming text to the current processing turn.
   * Used to integrate narrative_chunk events into the turn-based view.
   * @param {string} text - Text chunk to append
   * @param {boolean} isFinal - Whether this is the final chunk
   */
  const appendStreamingText = useCallback((text, isFinal = false) => {
    // Find the current turn to update (processing turn or latest turn)
    const turnNum = processingTurn || latestTurnRef.current;
    if (!turnNum) {
      console.log('📺 appendStreamingText: no turn to update');
      return;
    }

    setTurnsByNumber(prev => {
      const turn = prev[turnNum];
      if (!turn) {
        console.log('📺 appendStreamingText: turn not found:', turnNum);
        return prev;
      }

      return {
        ...prev,
        [turnNum]: {
          ...turn,
          streamingText: (turn.streamingText || '') + (text || ''),
          isStreaming: !isFinal,
        }
      };
    });
  }, [processingTurn]);

  /**
   * Get ordered list of turns for rendering.
   */
  const orderedTurns = useMemo(() => {
    return Object.keys(turnsByNumber)
      .map(Number)
      .sort((a, b) => a - b)
      .map(turnNum => turnsByNumber[turnNum])
      .filter(turn => turn != null); // Filter out any undefined entries
  }, [turnsByNumber]);

  /**
   * Get the current turn number (for display).
   */
  const currentTurnNumber = latestTurnRef.current;

  /**
   * Check if currently processing a turn.
   */
  const isProcessing = processingTurn !== null;

  return {
    // State
    turns: orderedTurns,
    turnsByNumber,
    processingTurn,
    currentTurnNumber,
    isProcessing,

    // Event handlers
    handleTurnStarted,
    handleTurnMessage,
    handleTurnComplete,
    handleTurnError,
    handleInputReceived,

    // Actions
    loadTurnsFromHistory,
    clearTurns,
    appendStreamingText,
    setCurrentTurn,
  };
}

export default useTurnBasedMessages;
