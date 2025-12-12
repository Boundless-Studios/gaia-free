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

    // Verify it's for our campaign
    if (session_id && session_id !== campaignId) return;

    setProcessingTurn(turn_number);
    latestTurnRef.current = Math.max(latestTurnRef.current, turn_number);

    // Initialize turn state
    setTurnsByNumber(prev => ({
      ...prev,
      [turn_number]: {
        turn_number,
        input: null,
        streamingText: '',
        finalMessage: null,
        isStreaming: false,
        error: null,
      }
    }));
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

    // Verify it's for our campaign
    if (session_id && session_id !== campaignId) return;

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

    // Verify it's for our campaign
    if (session_id && session_id !== campaignId) return;

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
   * Called when loading a campaign to restore turn state.
   * Supports both new format (with turn_number) and legacy format (user/dm pairs).
   */
  const loadTurnsFromHistory = useCallback((messages) => {
    if (!Array.isArray(messages) || messages.length === 0) return;

    const turns = {};
    let maxTurn = 0;

    // Check if messages have turn_number (new format)
    const hasNewFormat = messages.some(msg => msg.turn_number != null);

    if (hasNewFormat) {
      // New format: messages have turn_number and response_type
      messages.forEach(msg => {
        const turnNumber = msg.turn_number;
        if (turnNumber == null) return;

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
    } else {
      // Legacy format: convert user/dm message pairs to turns
      let turnNum = 0;
      let currentUserMsg = null;
      let currentDmMsgs = [];

      const processTurnGroup = () => {
        if (turnNum === 0) return;

        const turn = {
          turn_number: turnNum,
          input: null,
          streamingText: '',
          finalMessage: null,
          isStreaming: false,
          error: null,
        };

        // Convert user message to input
        if (currentUserMsg) {
          turn.input = {
            active_player: {
              character_id: currentUserMsg.character_id || 'player',
              character_name: currentUserMsg.character_name || currentUserMsg.characterName || 'Player',
              text: currentUserMsg.text || currentUserMsg.content || '',
            },
            observer_inputs: [],
            dm_input: null,
            combined_prompt: currentUserMsg.text || currentUserMsg.content || '',
          };
        }

        // Convert DM message to final response
        const dmMsg = currentDmMsgs[currentDmMsgs.length - 1];
        if (dmMsg) {
          // Extract content from various possible formats
          let dmContent = '';
          if (typeof dmMsg.text === 'string' && dmMsg.text) {
            dmContent = dmMsg.text;
          } else if (typeof dmMsg.content === 'string' && dmMsg.content) {
            dmContent = dmMsg.content;
          } else if (typeof dmMsg.content === 'object' && dmMsg.content) {
            // Handle structured content (answer or narrative)
            dmContent = dmMsg.content.answer || dmMsg.content.narrative || '';
          }
          // Also check structuredContent field
          if (!dmContent && dmMsg.structuredContent) {
            dmContent = dmMsg.structuredContent.answer || dmMsg.structuredContent.narrative || '';
          }

          turn.finalMessage = {
            message_id: dmMsg.message_id || dmMsg.id || `hist-${turnNum}-dm`,
            turn_number: turnNum,
            response_index: 2,
            role: 'assistant',
            content: dmContent,
            character_name: 'DM',
            has_audio: dmMsg.hasAudio || dmMsg.has_audio || false,
            timestamp: dmMsg.timestamp,
          };
        }

        turns[turnNum] = turn;
        maxTurn = Math.max(maxTurn, turnNum);
      };

      messages.forEach((msg) => {
        const isUser = msg.sender === 'user' || msg.role === 'user';
        const isDM = msg.sender === 'dm' || msg.role === 'assistant';

        if (isUser) {
          // New user message starts a new turn
          if (currentUserMsg || currentDmMsgs.length > 0) {
            processTurnGroup();
          }
          turnNum++;
          currentUserMsg = msg;
          currentDmMsgs = [];
        } else if (isDM) {
          // DM message belongs to current turn
          currentDmMsgs.push(msg);
        }
      });

      // Process final turn group
      if (currentUserMsg || currentDmMsgs.length > 0) {
        processTurnGroup();
      }
    }

    latestTurnRef.current = maxTurn;
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

    // Actions
    loadTurnsFromHistory,
    clearTurns,
  };
}

export default useTurnBasedMessages;
